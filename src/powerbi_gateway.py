import json
from dataclasses import dataclass


@dataclass
class GatewayBindingResult:
    semantic_model_id: str
    semantic_model_name: str
    status: str
    gateway_id: str = ""
    gateway_name: str = ""
    message: str = ""


def _norm(value) -> str:
    return str(value or "").strip().casefold()


def _details(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _matches_expected_oracle(datasource: dict, expected_database: str) -> bool:
    if _norm(datasource.get("datasourceType")) != "oracle":
        return False
    expected = _norm(expected_database)
    if not expected:
        return True
    details = _details(datasource.get("connectionDetails"))
    return expected in {
        _norm(details.get("server")),
        _norm(details.get("database")),
    }


def _get_dataset_datasources(powerbi, workspace_id: str, dataset_id: str) -> list[dict]:
    response = powerbi.get(f"groups/{workspace_id}/datasets/{dataset_id}/datasources")
    value = response.json().get("value", [])
    return [item for item in value if isinstance(item, dict)]


def _discover_gateways(powerbi, workspace_id: str, dataset_id: str) -> list[dict]:
    response = powerbi.get(
        f"groups/{workspace_id}/datasets/{dataset_id}/Default.DiscoverGateways"
    )
    value = response.json().get("value", [])
    unique = {}
    for item in value:
        if isinstance(item, dict) and item.get("id"):
            unique.setdefault(_norm(item["id"]), item)
    return list(unique.values())


def _take_over_dataset(powerbi, workspace_id: str, dataset_id: str):
    return powerbi.post(f"groups/{workspace_id}/datasets/{dataset_id}/Default.TakeOver")


def bind_semantic_models_to_gateway(powerbi, workspace_items, config):
    """Mirror the proven .NET BindToGateway flow using target workspace only.

    Resolution is target-only: inspect each target semantic model's Oracle datasource,
    ask Power BI which gateways can bind that model, require exactly one compatible
    gateway, and call Default.BindToGateway. No source workspace is consulted.
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
        f"Expected Oracle source    : {config.expected_oracle_database or '(not configured)'}"
    )
    print("API: Power BI REST API v1.0 (same operation used by the .NET application)")

    for index, model in enumerate(models, start=1):
        print("-" * 80)
        print(f"[{index}/{len(models)}] Semantic Model")
        print(f"  Name              : {model.name}")
        print(f"  Model Id          : {model.id}")
        print(f"  Folder Id         : {model.folder_id or '(root)'}")

        try:
            datasources = _get_dataset_datasources(
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
            if _matches_expected_oracle(ds, config.expected_oracle_database)
        ]
        print(f"  Matching Oracle sources: {len(oracle_sources)}")
        for ds in oracle_sources:
            d = _details(ds.get("connectionDetails"))
            print(f"    - server      : {d.get('server') or '(none)'}")
            print(f"      database    : {d.get('database') or '(none)'}")
            print(f"      gatewayId   : {ds.get('gatewayId') or '(not bound)'}")
            print(f"      datasourceId: {ds.get('datasourceId') or '(not bound)'}")

        if not oracle_sources:
            message = (
                "No Oracle datasource matching "
                f"'{config.expected_oracle_database}' was found in the semantic model."
            )
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "ERROR", message=message)
            )
            continue

        # Same pragmatic rule as the .NET app: a target datasource already exposing
        # gatewayId+datasourceId is considered bound.
        if all(ds.get("gatewayId") and ds.get("datasourceId") for ds in oracle_sources):
            gateway_ids = {str(ds.get("gatewayId")) for ds in oracle_sources}
            print("  Binding status    : ALREADY BOUND")
            print(f"  Gateway Id(s)     : {', '.join(sorted(gateway_ids))}")
            print("  Apply status      : NOT REQUIRED")
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ALREADY_BOUND",
                    gateway_id=next(iter(gateway_ids)) if len(gateway_ids) == 1 else "",
                )
            )
            continue

        try:
            gateways = _discover_gateways(powerbi, config.workspace_id, model.id)
        except Exception as exc:
            message = f"Default.DiscoverGateways failed: {exc}"
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "ERROR", message=message)
            )
            continue

        print(f"  Compatible gateways: {len(gateways)}")
        for gateway in gateways:
            print(
                f"    - {gateway.get('name') or '(unnamed)'} [{gateway.get('id') or ''}]"
            )

        if len(gateways) != 1:
            message = (
                "The semantic model could not be resolved to a single on-premises gateway. "
                f"DiscoverGateways returned {len(gateways)} unique gateway(s)."
            )
            print(f"  Status            : AMBIGUOUS\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(model.id, model.name, "AMBIGUOUS", message=message)
            )
            continue

        gateway = gateways[0]
        gateway_id = gateway.get("id") or ""
        gateway_name = gateway.get("name") or ""
        payload = {
            "gatewayObjectId": gateway_id,
            "datasourceObjectIds": None,
        }
        print(f"  Target gateway    : {gateway_name or '(unnamed)'} [{gateway_id}]")

        print("  Calling Default.TakeOver...")
        try:
            takeover_response = _take_over_dataset(
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
                    gateway_id=gateway_id,
                    gateway_name=gateway_name,
                    message=message,
                )
            )
            continue

        print("  Calling Default.BindToGateway...")
        try:
            response = powerbi.post(
                f"groups/{config.workspace_id}/datasets/{model.id}/Default.BindToGateway",
                json=payload,
            )
            print(f"  BindToGateway     : HTTP {response.status_code}")
            print("  Status            : UPDATED")
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "UPDATED",
                    gateway_id=gateway_id,
                    gateway_name=gateway_name,
                )
            )
        except Exception as exc:
            message = f"Default.BindToGateway failed: {exc}"
            print(f"  Status            : ERROR\n  Reason            : {message}")
            failures.append(message)
            results.append(
                GatewayBindingResult(
                    model.id,
                    model.name,
                    "ERROR",
                    gateway_id=gateway_id,
                    gateway_name=gateway_name,
                    message=message,
                )
            )

    print()
    print("=" * 80)
    print("SEMANTIC MODEL GATEWAY SUMMARY")
    print("=" * 80)
    for result in results:
        print(f"- {result.semantic_model_name}: {result.status}")

    if failures and config.fail_on_unresolved_connection_binding:
        raise RuntimeError(
            f"Unable to safely bind {len(failures)} semantic model gateway relationship(s)."
        )
    return results
