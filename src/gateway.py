import json
import time
from dataclasses import dataclass

import requests


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


def _normalize(value) -> str:
    return str(value or "").strip().casefold()


def _connection_details(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _oracle_matches_expected(datasource, expected_database: str) -> bool:
    if _normalize(datasource.get("datasourceType")) != "oracle":
        return False

    expected = _normalize(expected_database)
    if not expected:
        return True

    details = _connection_details(datasource.get("connectionDetails"))
    candidates = {
        _normalize(details.get("server")),
        _normalize(details.get("database")),
    }
    candidates.discard("")
    return expected in candidates


def _describe_details(datasource) -> str:
    details = _connection_details(datasource.get("connectionDetails"))
    if not details:
        return "(no connection details)"
    return ", ".join(f"{key}={value}" for key, value in sorted(details.items()))


def _get_dataset_datasources(powerbi, workspace_id: str, dataset_id: str):
    response = powerbi.get(
        f"groups/{workspace_id}/datasets/{dataset_id}/datasources"
    )
    return response.json().get("value", [])


def _discover_gateways(powerbi, workspace_id: str, dataset_id: str):
    response = powerbi.get(
        f"groups/{workspace_id}/datasets/{dataset_id}/Default.DiscoverGateways"
    )
    return response.json().get("value", [])


def _get_gateway_datasources(powerbi, gateway_id: str):
    response = powerbi.get(f"gateways/{gateway_id}/datasources")
    return response.json().get("value", [])


def _bind_to_gateway(
    powerbi,
    workspace_id: str,
    dataset_id: str,
    gateway_id: str,
    datasource_id: str,
):
    body = {
        "gatewayObjectId": gateway_id,
        "datasourceObjectIds": [datasource_id],
    }
    return powerbi.post(
        f"groups/{workspace_id}/datasets/{dataset_id}/Default.BindToGateway",
        json=body,
    )


def _verify_gateway_binding(
    powerbi,
    workspace_id: str,
    dataset_id: str,
    expected_gateway_id: str,
    expected_datasource_id: str,
    expected_database: str,
    max_attempts: int = 10,
    delay_seconds: int = 3,
):
    """Poll dataset datasources until the expected gateway binding is visible.

    BindToGateway may return before GET .../datasources reflects gatewayId and
    datasourceId. This method therefore retries the documented dataset
    datasources endpoint instead of treating the first read as final.
    """
    last_datasources = []

    for attempt in range(1, max_attempts + 1):
        print(f"  Verification attempt: {attempt}/{max_attempts}")

        last_datasources = _get_dataset_datasources(
            powerbi, workspace_id, dataset_id
        )

        if not last_datasources:
            print("    No datasources returned.")
        else:
            for datasource in last_datasources:
                details = _connection_details(datasource.get("connectionDetails"))
                gateway_id = datasource.get("gatewayId") or ""
                datasource_id = datasource.get("datasourceId") or ""

                print(f"    datasourceType : {datasource.get('datasourceType') or '(empty)'}")
                print(f"    server         : {details.get('server') or '(empty)'}")
                print(f"    database       : {details.get('database') or '(empty)'}")
                print(f"    gatewayId      : {gateway_id or '(not bound)'}")
                print(f"    datasourceId   : {datasource_id or '(not bound)'}")

                if (
                    _oracle_matches_expected(datasource, expected_database)
                    and _normalize(gateway_id) == _normalize(expected_gateway_id)
                    and _normalize(datasource_id) == _normalize(expected_datasource_id)
                ):
                    return True, last_datasources

        if attempt < max_attempts:
            print(
                f"    Binding not visible yet. Waiting {delay_seconds} seconds..."
            )
            time.sleep(delay_seconds)

    return False, last_datasources


def _find_matching_gateway_datasources(
    powerbi,
    gateways,
    expected_database: str,
):
    matches = []
    inspection_errors = []

    for gateway in gateways:
        gateway_id = gateway.get("id", "")
        gateway_name = gateway.get("name", gateway_id)
        print(f"    Inspecting gateway: {gateway_name} [{gateway_id}]")

        try:
            datasources = _get_gateway_datasources(powerbi, gateway_id)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "?"
            message = (
                f"Unable to list datasources for gateway {gateway_name} "
                f"[{gateway_id}] (HTTP {status_code})."
            )
            inspection_errors.append(message)
            print(f"      WARNING: {message}")
            continue

        print(f"      Gateway datasources: {len(datasources)}")
        for datasource in datasources:
            datasource_id = datasource.get("id", "")
            datasource_name = datasource.get("datasourceName", datasource_id)
            datasource_type = datasource.get("datasourceType", "")
            details = _describe_details(datasource)
            is_match = _oracle_matches_expected(datasource, expected_database)

            print(
                f"        - {datasource_name} [{datasource_id}] "
                f"type={datasource_type}; {details}; "
                f"match={'YES' if is_match else 'NO'}"
            )

            if is_match:
                matches.append((gateway, datasource))

    return matches, inspection_errors


def bind_semantic_models_to_gateway(
    powerbi,
    workspace_items,
    config,
):
    semantic_models = workspace_items.semantic_models
    results = []

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Semantic Models to inspect: {len(semantic_models)}")
    print(f"Expected Oracle source     : {config.expected_oracle_database or '(not configured)'}")
    print()

    if not config.bind_semantic_models_to_gateway:
        print("[GATEWAY] Binding is disabled by configuration.")
        return results

    if not config.expected_oracle_database:
        raise RuntimeError(
            "expectedOracleDatabase is required for safe automatic gateway binding."
        )

    failures = []

    for index, model in enumerate(semantic_models, start=1):
        print("-" * 80)
        print(f"[{index}/{len(semantic_models)}] Semantic Model")
        print(f"  Name              : {model.name}")
        print(f"  Model Id          : {model.id}")
        print(f"  Folder Id         : {model.folder_id or '(root)'}")

        dataset_datasources = _get_dataset_datasources(
            powerbi, config.workspace_id, model.id
        )
        print(f"  Dataset datasources: {len(dataset_datasources)}")

        oracle_sources = [
            datasource
            for datasource in dataset_datasources
            if _normalize(datasource.get("datasourceType")) == "oracle"
        ]

        if not oracle_sources:
            message = "No Oracle datasource was found in the semantic model."
            print(f"  Status            : SKIPPED")
            print(f"  Reason            : {message}")
            results.append(
                GatewayBindingResult(model.id, model.name, "SKIPPED", message=message)
            )
            print()
            continue

        expected_sources = [
            datasource
            for datasource in oracle_sources
            if _oracle_matches_expected(datasource, config.expected_oracle_database)
        ]

        for datasource in oracle_sources:
            print(f"  Oracle datasource : {_describe_details(datasource)}")
            print(f"    gatewayId        : {datasource.get('gatewayId') or '(not bound)'}")
            print(f"    datasourceId     : {datasource.get('datasourceId') or '(not bound)'}")
            print(
                "    expected source  : "
                + (
                    "YES"
                    if _oracle_matches_expected(
                        datasource, config.expected_oracle_database
                    )
                    else "NO"
                )
            )

        if not expected_sources:
            message = (
                f"The semantic model does not expose an Oracle datasource matching "
                f"'{config.expected_oracle_database}'."
            )
            print("  Status            : ERROR")
            print(f"  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "ERROR", message=message)
            )
            print()
            continue

        if len(expected_sources) > 1:
            message = (
                f"More than one Oracle datasource in the semantic model matches "
                f"'{config.expected_oracle_database}'."
            )
            print("  Status            : AMBIGUOUS")
            print(f"  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "AMBIGUOUS", message=message)
            )
            print()
            continue

        current = expected_sources[0]
        current_gateway_id = current.get("gatewayId") or ""
        current_datasource_id = current.get("datasourceId") or ""

        if current_gateway_id and current_datasource_id:
            message = "The semantic model is already bound to a gateway datasource."
            print("  Binding status    : ALREADY BOUND")
            print(f"  Gateway Id        : {current_gateway_id}")
            print(f"  Datasource Id     : {current_datasource_id}")
            print("  Apply status      : NOT REQUIRED")
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ALREADY_BOUND",
                    gateway_id=current_gateway_id,
                    datasource_id=current_datasource_id,
                    message=message,
                )
            )
            print()
            continue

        print("  Binding status    : NOT BOUND")
        print("  Discovering compatible gateways...")
        gateways = _discover_gateways(powerbi, config.workspace_id, model.id)
        print(f"  Compatible gateways: {len(gateways)}")
        for gateway in gateways:
            print(
                f"    - {gateway.get('name', gateway.get('id', ''))} "
                f"[{gateway.get('id', '')}]"
            )

        if not gateways:
            message = "Power BI did not return any compatible on-premises gateway."
            print("  Status            : ERROR")
            print(f"  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "ERROR", message=message)
            )
            print()
            continue

        matches, inspection_errors = _find_matching_gateway_datasources(
            powerbi,
            gateways,
            config.expected_oracle_database,
        )

        print(f"  Matching gateway datasources: {len(matches)}")

        if len(matches) != 1:
            if len(matches) == 0:
                message = (
                    f"No unique Oracle gateway datasource matching "
                    f"'{config.expected_oracle_database}' was found."
                )
                if inspection_errors:
                    message += " Some gateway datasources could not be inspected."
            else:
                message = (
                    f"{len(matches)} Oracle gateway datasources match "
                    f"'{config.expected_oracle_database}'; automatic selection is unsafe."
                )

            print("  Status            : " + ("AMBIGUOUS" if matches else "ERROR"))
            print(f"  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "AMBIGUOUS" if matches else "ERROR",
                    message=message,
                )
            )
            print()
            continue

        gateway, gateway_datasource = matches[0]
        gateway_id = gateway.get("id", "")
        gateway_name = gateway.get("name", gateway_id)
        datasource_id = gateway_datasource.get("id", "")
        datasource_name = gateway_datasource.get("datasourceName", datasource_id)

        print(f"  Target gateway    : {gateway_name} [{gateway_id}]")
        print(f"  Target datasource : {datasource_name} [{datasource_id}]")
        print(f"  Target details    : {_describe_details(gateway_datasource)}")
        print("  Applying BindToGateway...")

        bind_response = _bind_to_gateway(
            powerbi,
            config.workspace_id,
            model.id,
            gateway_id,
            datasource_id,
        )
        print(f"  BindToGateway     : HTTP {bind_response.status_code}")
        print("  Verifying gateway binding...")

        verified, verified_sources = _verify_gateway_binding(
            powerbi=powerbi,
            workspace_id=config.workspace_id,
            dataset_id=model.id,
            expected_gateway_id=gateway_id,
            expected_datasource_id=datasource_id,
            expected_database=config.expected_oracle_database,
            max_attempts=config.gateway_verify_max_attempts,
            delay_seconds=config.gateway_verify_delay_seconds,
        )

        if not verified:
            message = (
                "BindToGateway was accepted, but the expected gateway binding was not "
                "visible after all verification attempts."
            )
            print("  Verification      : FAILED")
            print(f"  Reason            : {message}")
            print("  Last datasource state:")

            if not verified_sources:
                print("    (no datasources returned)")
            else:
                for datasource in verified_sources:
                    details = _connection_details(datasource.get("connectionDetails"))
                    print(f"    - Type         : {datasource.get('datasourceType') or '(empty)'}")
                    print(f"      Server       : {details.get('server') or '(empty)'}")
                    print(f"      Database     : {details.get('database') or '(empty)'}")
                    print(f"      Gateway Id   : {datasource.get('gatewayId') or '(not bound)'}")
                    print(f"      Datasource Id: {datasource.get('datasourceId') or '(not bound)'}")

            failures.append(message)
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "VERIFY_FAILED",
                    gateway_id=gateway_id,
                    gateway_name=gateway_name,
                    datasource_id=datasource_id,
                    datasource_name=datasource_name,
                    message=message,
                )
            )
            print()
            continue

        print("  Verification      : OK")
        print("  Apply status      : UPDATED")
        results.append(
            GatewayBindingResult(
                model.id,
                model.name,
                "UPDATED",
                gateway_id=gateway_id,
                gateway_name=gateway_name,
                datasource_id=datasource_id,
                datasource_name=datasource_name,
                message="Gateway binding updated and verified.",
            )
        )
        print()

    print("=" * 80)
    print("SEMANTIC MODEL GATEWAY SUMMARY")
    print("=" * 80)
    for result in results:
        print(f"- {result.semantic_model_name}: {result.status}")
        if result.gateway_id:
            print(
                f"  Gateway   : {result.gateway_name or '(name unavailable)'} "
                f"[{result.gateway_id}]"
            )
        if result.datasource_id:
            print(
                f"  Datasource: {result.datasource_name or '(name unavailable)'} "
                f"[{result.datasource_id}]"
            )
        if result.message:
            print(f"  Detail    : {result.message}")

    if failures and config.fail_on_unresolved_gateway_binding:
        raise RuntimeError(
            f"Unable to safely bind {len(failures)} semantic model gateway relationship(s)."
        )

    return results
