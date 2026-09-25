import json
from dataclasses import dataclass


@dataclass(frozen=True)
class TargetOracleConnection:
    connection_id: str
    connection_name: str
    gateway_id: str
    connectivity_type: str
    oracle_server: str


@dataclass
class GatewayBindingResult:
    semantic_model_id: str
    semantic_model_name: str
    status: str
    gateway_id: str = ""
    gateway_name: str = ""
    datasource_id: str = ""
    datasource_name: str = ""
    message: str = ""


def normalize_text(value) -> str:
    return str(value or "").strip().casefold()


def parse_connection_details(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def matches_expected_oracle(datasource: dict, expected_database: str) -> bool:
    if normalize_text(datasource.get("datasourceType")) != "oracle":
        return False

    expected = normalize_text(expected_database)
    if not expected:
        return True

    details = parse_connection_details(datasource.get("connectionDetails"))
    return expected in {
        normalize_text(details.get("server")),
        normalize_text(details.get("database")),
    }


def list_fabric_connections(fabric) -> list[dict]:
    """Return every Fabric connection visible to the current identity."""
    connections = []
    continuation_token = None

    while True:
        params = {}
        if continuation_token:
            params["continuationToken"] = continuation_token

        response = fabric.get("connections", params=params)
        data = response.json()
        connections.extend(
            item for item in data.get("value", []) if isinstance(item, dict)
        )

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break

    return connections


def resolve_target_oracle_connection(fabric, config) -> TargetOracleConnection:
    """Resolve the configured logical Fabric connection to concrete runtime IDs.

    The environment YAML contains stable, human-readable values only:
      * expectedOracleDatabase: physical Oracle server expected by the model.
      * semanticModelConnectionName: logical Fabric connection to use.

    gatewayId and datasource/connection id are discovered at runtime from
    GET https://api.fabric.microsoft.com/v1/connections.
    """
    connection_name = config.semantic_model_connection_name.strip()
    expected_server = config.expected_oracle_database.strip()

    if not connection_name:
        raise RuntimeError(
            "'semanticModelConnectionName' is required when semantic model "
            "gateway binding is enabled."
        )

    if not expected_server:
        raise RuntimeError(
            "'expectedOracleDatabase' is required when semantic model gateway "
            "binding is enabled."
        )

    connections = list_fabric_connections(fabric)

    same_name = [
        connection
        for connection in connections
        if normalize_text(connection.get("displayName"))
        == normalize_text(connection_name)
    ]

    matches = []
    for connection in same_name:
        details = parse_connection_details(connection.get("connectionDetails"))
        is_oracle = normalize_text(details.get("type")) == "oracle"
        is_on_premises = (
            normalize_text(connection.get("connectivityType"))
            == normalize_text("OnPremisesGateway")
        )
        server_matches = normalize_text(details.get("path")) == normalize_text(
            expected_server
        )

        if is_oracle and is_on_premises and server_matches:
            matches.append(connection)

    print("Target Fabric connection discovery")
    print(f"  Connection name   : {connection_name}")
    print(f"  Oracle server     : {expected_server}")
    print(f"  Same-name matches : {len(same_name)}")
    print(f"  Valid matches     : {len(matches)}")

    for connection in same_name:
        details = parse_connection_details(connection.get("connectionDetails"))
        print(
            "    - "
            f"id={connection.get('id') or '(none)'}, "
            f"gatewayId={connection.get('gatewayId') or '(none)'}, "
            f"connectivityType={connection.get('connectivityType') or '(none)'}, "
            f"type={details.get('type') or '(none)'}, "
            f"path={details.get('path') or '(none)'}"
        )

    if len(matches) != 1:
        raise RuntimeError(
            "Unable to resolve exactly one on-premises Oracle Fabric connection "
            f"with displayName='{connection_name}' and path='{expected_server}'. "
            f"Same-name connections={len(same_name)}, valid matches={len(matches)}."
        )

    connection = matches[0]
    connection_id = str(connection.get("id") or "").strip()
    gateway_id = str(connection.get("gatewayId") or "").strip()
    details = parse_connection_details(connection.get("connectionDetails"))

    if not connection_id or not gateway_id:
        raise RuntimeError(
            f"Fabric connection '{connection_name}' does not expose both id and gatewayId."
        )

    target = TargetOracleConnection(
        connection_id=connection_id,
        connection_name=str(connection.get("displayName") or connection_name),
        gateway_id=gateway_id,
        connectivity_type=str(connection.get("connectivityType") or ""),
        oracle_server=str(details.get("path") or ""),
    )

    print("  Resolved target")
    print(f"    Connection Id   : {target.connection_id}")
    print(f"    Gateway Id      : {target.gateway_id}")
    print(f"    Connectivity    : {target.connectivity_type}")
    print(f"    Oracle server   : {target.oracle_server}")

    return target


def get_dataset_datasources(powerbi, workspace_id: str, dataset_id: str) -> list[dict]:
    response = powerbi.get(f"groups/{workspace_id}/datasets/{dataset_id}/datasources")
    value = response.json().get("value", [])
    return [item for item in value if isinstance(item, dict)]


def take_over_dataset(powerbi, workspace_id: str, dataset_id: str):
    return powerbi.post(f"groups/{workspace_id}/datasets/{dataset_id}/Default.TakeOver")


def is_bound_to_target(
    oracle_sources: list[dict],
    target: TargetOracleConnection,
) -> bool:
    if not oracle_sources:
        return False

    expected_gateway_id = normalize_text(target.gateway_id)
    expected_datasource_id = normalize_text(target.connection_id)

    return all(
        normalize_text(ds.get("gatewayId")) == expected_gateway_id
        and normalize_text(ds.get("datasourceId")) == expected_datasource_id
        for ds in oracle_sources
    )


def verify_target_binding(
    powerbi,
    workspace_id: str,
    dataset_id: str,
    expected_database: str,
    target: TargetOracleConnection,
) -> tuple[bool, list[dict]]:
    datasources = get_dataset_datasources(powerbi, workspace_id, dataset_id)
    oracle_sources = [
        ds
        for ds in datasources
        if matches_expected_oracle(ds, expected_database)
    ]
    return is_bound_to_target(oracle_sources, target), oracle_sources


def bind_semantic_models_to_gateway(fabric, powerbi, workspace_items, config):
    """Bind target semantic models to the configured logical Fabric connection.

    The target connection is discovered dynamically by display name and physical
    Oracle server. Existing bindings are accepted only when BOTH gatewayId and
    datasourceId match that resolved target connection.
    """
    if not config.bind_semantic_models_to_connection:
        print("Semantic model gateway binding is disabled by configuration.")
        return []

    failures = []
    results = []
    models = workspace_items.semantic_models

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Semantic Models to inspect: {len(models)}")
    print(
        f"Expected Oracle server    : "
        f"{config.expected_oracle_database or '(not configured)'}"
    )
    print(
        f"Target Fabric connection  : "
        f"{config.semantic_model_connection_name or '(not configured)'}"
    )
    print(
        "Connection resolution      : Fabric GET /connections; "
        "gatewayId and datasourceId are discovered at runtime"
    )

    try:
        target = resolve_target_oracle_connection(fabric, config)
    except Exception as exc:
        message = f"Target Fabric connection resolution failed: {exc}"
        print(f"Status: ERROR\nReason: {message}")
        if config.fail_on_unresolved_connection_binding:
            raise RuntimeError(message) from exc
        return [GatewayBindingResult("", "", "ERROR", message=message)]

    for index, model in enumerate(models, start=1):
        print("-" * 80)
        print(f"[{index}/{len(models)}] Semantic Model")
        print(f"  Name              : {model.name}")
        print(f"  Model Id          : {model.id}")
        print(f"  Folder Id         : {model.folder_id or '(root)'}")

        try:
            datasources = get_dataset_datasources(
                powerbi, config.workspace_id, model.id
            )
        except Exception as exc:
            message = f"GET dataset datasources failed: {exc}"
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "ERROR", message=message)
            )
            continue

        oracle_sources = [
            ds
            for ds in datasources
            if matches_expected_oracle(ds, config.expected_oracle_database)
        ]

        print(f"  Matching Oracle sources: {len(oracle_sources)}")
        for ds in oracle_sources:
            details = parse_connection_details(ds.get("connectionDetails"))
            print(f"    - server      : {details.get('server') or '(none)'}")
            print(f"      database    : {details.get('database') or '(none)'}")
            print(f"      gatewayId   : {ds.get('gatewayId') or '(not bound)'}")
            print(f"      datasourceId: {ds.get('datasourceId') or '(not bound)'}")

        if not oracle_sources:
            message = (
                "No Oracle datasource matching physical server "
                f"'{config.expected_oracle_database}' was found in the semantic model."
            )
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "ERROR", message=message)
            )
            continue

        print(f"  Target connection : {target.connection_name}")
        print(f"  Target gateway Id : {target.gateway_id}")
        print(f"  Target datasource : {target.connection_id}")

        if is_bound_to_target(oracle_sources, target):
            print("  Binding status    : ALREADY BOUND TO TARGET")
            print("  Apply status      : NOT REQUIRED")
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ALREADY_BOUND",
                    gateway_id=target.gateway_id,
                    datasource_id=target.connection_id,
                    datasource_name=target.connection_name,
                )
            )
            continue

        existing_bindings = {
            (
                str(ds.get("gatewayId") or ""),
                str(ds.get("datasourceId") or ""),
            )
            for ds in oracle_sources
        }
        print("  Binding status    : WRONG OR MISSING TARGET BINDING")
        for gateway_id, datasource_id in sorted(existing_bindings):
            print(
                f"    current gatewayId={gateway_id or '(none)'}, "
                f"datasourceId={datasource_id or '(none)'}"
            )

        payload = {
            "gatewayObjectId": target.gateway_id,
            "datasourceObjectIds": [target.connection_id],
        }

        print("  Calling Default.TakeOver...")
        try:
            takeover_response = take_over_dataset(
                powerbi,
                config.workspace_id,
                model.id,
            )
            print(f"  TakeOver          : HTTP {takeover_response.status_code}")
        except Exception as exc:
            message = f"Default.TakeOver failed: {exc}"
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ERROR",
                    gateway_id=target.gateway_id,
                    datasource_id=target.connection_id,
                    datasource_name=target.connection_name,
                    message=message,
                )
            )
            continue

        print("  Calling Default.BindToGateway...")
        print(f"  Payload gateway   : {target.gateway_id}")
        print(f"  Payload datasource: {target.connection_id}")

        try:
            response = powerbi.post(
                f"groups/{config.workspace_id}/datasets/{model.id}/Default.BindToGateway",
                json=payload,
            )
            print(f"  BindToGateway     : HTTP {response.status_code}")
        except Exception as exc:
            message = f"Default.BindToGateway failed: {exc}"
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ERROR",
                    gateway_id=target.gateway_id,
                    datasource_id=target.connection_id,
                    datasource_name=target.connection_name,
                    message=message,
                )
            )
            continue

        try:
            verified, verified_sources = verify_target_binding(
                powerbi,
                config.workspace_id,
                model.id,
                config.expected_oracle_database,
                target,
            )
        except Exception as exc:
            message = f"Post-bind verification failed: {exc}"
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ERROR",
                    gateway_id=target.gateway_id,
                    datasource_id=target.connection_id,
                    datasource_name=target.connection_name,
                    message=message,
                )
            )
            continue

        if not verified:
            current_pairs = [
                (
                    ds.get("gatewayId") or "(none)",
                    ds.get("datasourceId") or "(none)",
                )
                for ds in verified_sources
            ]
            message = (
                "BindToGateway returned successfully, but the semantic model is not "
                "bound to the configured target connection after verification. "
                f"Current bindings={current_pairs}."
            )
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ERROR",
                    gateway_id=target.gateway_id,
                    datasource_id=target.connection_id,
                    datasource_name=target.connection_name,
                    message=message,
                )
            )
            continue

        print("  Verification      : TARGET BINDING VERIFIED")
        print("  Status            : UPDATED AND VERIFIED")
        results.append(
            GatewayBindingResult(
                model.id,
                model.name,
                "UPDATED_AND_VERIFIED",
                gateway_id=target.gateway_id,
                datasource_id=target.connection_id,
                datasource_name=target.connection_name,
            )
        )

    print()
    print("=" * 80)
    print("SEMANTIC MODEL GATEWAY SUMMARY")
    print("=" * 80)
    print(f"Target Fabric connection: {target.connection_name}")
    print(f"Target gateway Id       : {target.gateway_id}")
    print(f"Target datasource Id    : {target.connection_id}")
    for result in results:
        print(f"- {result.semantic_model_name}: {result.status}")

    if failures and config.fail_on_unresolved_connection_binding:
        raise RuntimeError(
            f"Unable to safely bind {len(failures)} semantic model gateway relationship(s)."
        )

    return results
