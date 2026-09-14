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


def _normalize(value) -> str:
    return str(value or "").strip().casefold()


def _safe_display_name(connection: dict) -> str:
    value = connection.get("displayName")
    return str(value).strip() if value is not None and str(value).strip() else "(unnamed)"


def _is_oracle(connection: dict) -> bool:
    details = connection.get("connectionDetails") or {}
    return _normalize(details.get("type")) == "oracle"


def _is_on_premises_gateway(connection: dict) -> bool:
    return _normalize(connection.get("connectivityType")) == "onpremisesgateway"


def _matches_expected_exact(connection: dict, expected: str) -> bool:
    """Require the shared Oracle connection to match by BOTH name and path."""
    expected_n = _normalize(expected)
    if not expected_n:
        return False

    details = connection.get("connectionDetails") or {}
    return (
        _normalize(connection.get("displayName")) == expected_n
        and _normalize(details.get("path")) == expected_n
    )


def _as_match(connection: dict) -> ConnectionMatch:
    details = connection.get("connectionDetails") or {}
    return ConnectionMatch(
        id=str(connection.get("id") or ""),
        display_name=_safe_display_name(connection),
        gateway_id=str(connection.get("gatewayId") or ""),
        connectivity_type=str(connection.get("connectivityType") or ""),
        connection_type=str(details.get("type") or ""),
        path=str(details.get("path") or ""),
        raw=connection,
    )


def _format_candidate(connection: dict) -> str:
    details = connection.get("connectionDetails") or {}
    return (
        f"{_safe_display_name(connection)} "
        f"[{connection.get('id', '')}] "
        f"connectivityType={connection.get('connectivityType', '')}; "
        f"gatewayId={connection.get('gatewayId') or '(none)'}; "
        f"path={details.get('path', '')}"
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
            f"    - {_safe_display_name(item)} [{item.get('id', '')}]\n"
            f"      connectivityType: {item.get('connectivityType', '')}\n"
            f"      gatewayId       : {item.get('gatewayId', '') or '(none)'}\n"
            f"      path            : {details.get('path', '')}"
        )

    # The target used by this post-deploy is the shared on-premises gateway
    # connection, not a PersonalCloud connection that happens to have the same
    # Oracle path. Fabric can return both kinds from GET /v1/connections.
    on_prem_oracle = [item for item in oracle if _is_on_premises_gateway(item)]
    print(f"  On-premises Oracle connections: {len(on_prem_oracle)}")

    matches = [
        item
        for item in on_prem_oracle
        if _matches_expected_exact(item, expected_oracle_database)
    ]
    print(
        f"  Matching exact named on-premises source '{expected_oracle_database}': "
        f"{len(matches)}"
    )

    # Prefer the explicit display name if the same path is exposed by more than
    # one shared gateway connection.
    if len(matches) > 1:
        expected_n = _normalize(expected_oracle_database)
        named_matches = [
            item
            for item in matches
            if _normalize(item.get("displayName")) == expected_n
        ]
        if len(named_matches) == 1:
            matches = named_matches
            print("  Tie-breaker          : exact displayName match")

    if len(matches) != 1:
        if matches:
            candidates = " | ".join(_format_candidate(item) for item in matches)
        else:
            same_source_other_types = [
                item
                for item in oracle
                if _matches_expected_exact(item, expected_oracle_database)
            ]
            candidates = (
                " | ".join(_format_candidate(item) for item in same_source_other_types)
                if same_source_other_types
                else "(none)"
            )

        raise RuntimeError(
            "Unable to safely resolve exactly one OnPremisesGateway Oracle "
            f"connection for '{expected_oracle_database}'. Candidates: {candidates}."
        )

    selected = _as_match(matches[0])
    print("  Selected connection:")
    print(f"    Name             : {selected.display_name}")
    print(f"    Connection Id    : {selected.id}")
    print(f"    Connectivity Type: {selected.connectivity_type}")
    print(f"    Gateway Id       : {selected.gateway_id or '(none)'}")
    print(f"    Path             : {selected.path}")
    return selected


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

    if _normalize(target.connectivity_type) != "onpremisesgateway":
        raise RuntimeError(
            "The resolved Fabric connection is not an OnPremisesGateway connection."
        )

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
