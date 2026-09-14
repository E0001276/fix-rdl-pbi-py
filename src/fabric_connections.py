from dataclasses import dataclass


@dataclass
class ConnectionMatch:
    id: str
    display_name: str
    gateway_id: str
    connectivity_type: str
    connection_type: str
    path: str
    raw: dict


def _list_all_connections(fabric):
    items = []
    next_url = "connections"
    while next_url:
        response = fabric.get(next_url)
        data = response.json()
        items.extend(data.get("value", []))
        next_url = data.get("continuationUri")
        if not next_url:
            token = data.get("continuationToken")
            next_url = f"connections?continuationToken={token}" if token else None
    return items


def _normalize(value: str) -> str:
    return (value or "").strip().casefold()


def _is_oracle(connection: dict) -> bool:
    details = connection.get("connectionDetails") or {}
    kind = _normalize(str(details.get("type") or ""))
    return "oracle" in kind


def _matches_expected(connection: dict, expected: str) -> bool:
    expected_n = _normalize(expected)
    if not expected_n:
        return False

    details = connection.get("connectionDetails") or {}
    candidates = [
        connection.get("displayName"),
        details.get("path"),
    ]
    return any(expected_n in _normalize(str(value or "")) for value in candidates)


def _as_match(connection: dict) -> ConnectionMatch:
    details = connection.get("connectionDetails") or {}
    return ConnectionMatch(
        id=connection.get("id", ""),
        display_name=connection.get("displayName", ""),
        gateway_id=connection.get("gatewayId", ""),
        connectivity_type=connection.get("connectivityType", ""),
        connection_type=str(details.get("type") or ""),
        path=str(details.get("path") or ""),
        raw=connection,
    )


def _resolve_connection(fabric, expected_oracle_database: str) -> ConnectionMatch:
    print("[CONNECTION DISCOVERY] Listing Fabric connections available to the caller...")
    values = _list_all_connections(fabric)
    print(f"  Connections visible: {len(values)}")

    oracle = [item for item in values if _is_oracle(item)]
    print(f"  Oracle connections : {len(oracle)}")
    for item in oracle:
        details = item.get("connectionDetails") or {}
        print(
            f"    - {item.get('displayName', '(unnamed)')} [{item.get('id', '')}]\n"
            f"      connectivityType: {item.get('connectivityType', '')}\n"
            f"      gatewayId       : {item.get('gatewayId', '') or '(none)'}\n"
            f"      path            : {details.get('path', '')}"
        )

    matches = [
        item for item in oracle if _matches_expected(item, expected_oracle_database)
    ]
    print(f"  Matching expected source '{expected_oracle_database}': {len(matches)}")

    if len(matches) != 1:
        names = ", ".join(item.get("displayName", "") for item in matches) or "(none)"
        raise RuntimeError(
            "Unable to safely resolve exactly one Fabric Oracle connection for "
            f"'{expected_oracle_database}'. Matches: {names}."
        )

    return _as_match(matches[0])


def bind_semantic_models_to_connections(fabric, workspace_items, config):
    if not config.bind_semantic_models_to_connection:
        print("Semantic model connection binding is disabled by configuration.")
        return []

    if not config.expected_oracle_database:
        raise RuntimeError(
            "expectedOracleDatabase is required for Fabric connection binding."
        )

    target = _resolve_connection(fabric, config.expected_oracle_database)

    print()
    print("[TARGET CONNECTION]")
    print(f"  Name             : {target.display_name}")
    print(f"  Connection Id    : {target.id}")
    print(f"  Gateway Id       : {target.gateway_id or '(none)'}")
    print(f"  Connectivity Type: {target.connectivity_type}")
    print(f"  Connection Type  : {target.connection_type}")
    print(f"  Path             : {target.path}")
    print()

    if not target.id or not target.connectivity_type or not target.connection_type:
        raise RuntimeError("The resolved Fabric connection is missing required metadata.")

    results = []
    failures = []
    models = workspace_items.semantic_models
    print(f"Semantic Models to bind: {len(models)}")

    for index, model in enumerate(models, start=1):
        print("-" * 80)
        print(f"[{index}/{len(models)}] Semantic Model")
        print(f"  Name          : {model.name}")
        print(f"  Model Id      : {model.id}")
        print(f"  Folder Id     : {model.folder_id or '(root)'}")
        print(f"  Connection    : {target.display_name} [{target.id}]")
        print("  API           : Fabric semanticModels/{id}/bindConnection")

        payload = {
            "connectionBinding": {
                "id": target.id,
                "connectivityType": target.connectivity_type,
                "connectionDetails": {
                    "type": target.connection_type,
                    "path": target.path,
                },
            }
        }

        try:
            response = fabric.post(
                f"workspaces/{config.workspace_id}/semanticModels/{model.id}/bindConnection",
                json=payload,
            )
            print(f"  BindConnection: HTTP {response.status_code}")
            print("  Status        : ACCEPTED BY FABRIC")
            results.append((model, target, "BOUND"))
        except Exception as exc:
            message = str(exc)
            print("  Status        : FAILED")
            print(f"  Reason        : {message}")
            failures.append((model, message))
            results.append((model, target, "FAILED"))

    print()
    print("=" * 80)
    print("SEMANTIC MODEL CONNECTION SUMMARY")
    print("=" * 80)
    for model, _, status in results:
        print(f"- {model.name}: {status}")

    if failures and config.fail_on_unresolved_connection_binding:
        raise RuntimeError(
            f"Unable to bind {len(failures)} semantic model connection(s) with Fabric REST."
        )

    return results
