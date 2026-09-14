from paginated import (
    _extract_rdl_binding,
    _find_rdl_part,
    _decode_part,
    _resolve_semantic_model,
)
from workspace import get_paginated_report_definition


DEFAULT_POWER_BI_SERVER = "pbiazure://api.powerbi.com/"


def _norm(value) -> str:
    return str(value or "").strip().rstrip("/").casefold()


def _datasources(payload: dict) -> list[dict]:
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return [item for item in values if isinstance(item, dict)]


def _connection_details(datasource: dict) -> dict:
    details = datasource.get("connectionDetails")
    return details if isinstance(details, dict) else {}


def _runtime_name(datasource: dict) -> str:
    # GET /reports/{id}/datasources returns `name`. Older/custom responses can
    # expose datasourceName, so retain it only as a fallback.
    return str(datasource.get("name") or datasource.get("datasourceName") or "").strip()


def _target_database(semantic_model_id: str) -> str:
    return f"sobe_wowvirtualserver-{semantic_model_id}"


def get_paginated_report_datasources(powerbi, workspace_id: str, report_id: str) -> list[dict]:
    response = powerbi.get(f"groups/{workspace_id}/reports/{report_id}/datasources")
    return _datasources(response.json())


def _get_persisted_rdl_datasource_names(fabric, workspace_id: str, report_id: str) -> list[str]:
    definition = get_paginated_report_definition(fabric, workspace_id, report_id)
    part = _find_rdl_part(definition)
    binding = _extract_rdl_binding(_decode_part(part))
    # Preserve RDL order and remove duplicates case-insensitively.
    names = []
    seen = set()
    for name in binding.get("datasource_names", []):
        key = str(name).casefold()
        if name and key not in seen:
            names.append(name)
            seen.add(key)
    return names


def _find_runtime_for_rdl(runtime_datasources: list[dict], rdl_name: str):
    exact = [ds for ds in runtime_datasources if _norm(_runtime_name(ds)) == _norm(rdl_name)]
    if exact:
        return exact[0]
    # This fallback is intentionally identical to the .NET implementation: when
    # Power BI exposes only one runtime datasource, use it even if its runtime
    # name lags the physical RDL datasource name.
    return runtime_datasources[0] if runtime_datasources else None


def _build_update_details(runtime_datasources: list[dict], rdl_names: list[str], semantic_model_id: str):
    target_database = _target_database(semantic_model_id)
    details = []
    for rdl_name in rdl_names:
        runtime = _find_runtime_for_rdl(runtime_datasources, rdl_name)
        current_server = _connection_details(runtime or {}).get("server") or ""
        target_server = current_server or DEFAULT_POWER_BI_SERVER
        details.append(
            {
                "datasourceName": rdl_name,
                "connectionDetails": {
                    "server": target_server,
                    "database": target_database,
                },
            }
        )
    return details


def bind_paginated_reports_to_semantic_models(
    powerbi,
    fabric,
    workspace_items,
    paginated_infos,
    config,
):
    """Mirror the proven .NET paginated runtime remediation, target-only.

    The target semantic model is resolved from the target workspace folder.
    The persisted target RDL supplies datasourceName. Power BI GET /datasources
    supplies the current server. Only the virtual database semantic-model ID is
    replaced. TakeOver is executed before Default.UpdateDatasources, exactly as
    in the working .NET application.
    """
    if not config.bind_paginated_reports_to_semantic_models:
        print("Paginated report runtime datasource binding is disabled by configuration.")
        return []

    failures = []
    results = []

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Paginated reports to bind: {len(paginated_infos)}")
    print("API: Power BI REST API v1.0")
    print("Strategy: .NET parity, target-only resolution")

    for index, info in enumerate(paginated_infos, start=1):
        item = info.item
        print("-" * 80)
        print(f"[{index}/{len(paginated_infos)}] Paginated Report Runtime Datasource")
        print(f"  Name              : {item.name}")
        print(f"  Report Id         : {item.id}")

        model, reason = _resolve_semantic_model(workspace_items, item)
        if model is None:
            message = f"Unable to resolve semantic model safely: {reason}."
            print("  Semantic model    : NOT RESOLVED")
            print(f"  Reason            : {message}")
            failures.append(message)
            results.append((item.name, "UNRESOLVED"))
            continue

        print(f"  Semantic model    : {model.name} [{model.id}]")
        print(f"  Resolution reason : {reason}")
        target_database = _target_database(model.id)

        try:
            runtime_datasources = get_paginated_report_datasources(
                powerbi, config.workspace_id, item.id
            )
            rdl_names = _get_persisted_rdl_datasource_names(
                fabric, config.workspace_id, item.id
            )
        except Exception as exc:
            message = f"Datasource discovery failed: {exc}"
            print(f"  Status             : GET_FAILED\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "GET_FAILED"))
            continue

        print(f"  Runtime datasources: {len(runtime_datasources)}")
        for ds in runtime_datasources:
            details = _connection_details(ds)
            print(f"    - Name           : {_runtime_name(ds) or '(none)'}")
            print(f"      Type           : {ds.get('datasourceType') or '(none)'}")
            print(f"      Server         : {details.get('server') or '(none)'}")
            print(f"      Database       : {details.get('database') or '(none)'}")

        print(f"  Persisted RDL datasource names: {len(rdl_names)}")
        for name in rdl_names:
            print(f"    - {name}")

        if not runtime_datasources:
            message = "Power BI returned no runtime datasource for this paginated report."
            print(f"  Status             : ERROR\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "ERROR"))
            continue
        if not rdl_names:
            message = "The persisted RDL contains no embedded datasource name."
            print(f"  Status             : ERROR\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "ERROR"))
            continue

        runtime_already_correct = all(
            _norm(_connection_details(ds).get("database")) == _norm(target_database)
            for ds in runtime_datasources
        )
        if runtime_already_correct:
            print(f"  Target database    : {target_database}")
            print("  Status             : ALREADY CORRECT")
            results.append((item.name, "UNCHANGED"))
            continue

        update_details = _build_update_details(
            runtime_datasources, rdl_names, model.id
        )
        print(f"  Target database    : {target_database}")
        for detail in update_details:
            print(f"  Update datasource  : {detail['datasourceName']}")
            print(f"    Server           : {detail['connectionDetails']['server']}")
            print(f"    Database         : {detail['connectionDetails']['database']}")

        try:
            print("  Calling Default.TakeOver...")
            takeover = powerbi.post(
                f"groups/{config.workspace_id}/reports/{item.id}/Default.TakeOver"
            )
            print(f"  TakeOver           : HTTP {takeover.status_code}")

            print("  Calling Default.UpdateDatasources...")
            update = powerbi.post(
                f"groups/{config.workspace_id}/reports/{item.id}/Default.UpdateDatasources",
                json={"updateDetails": update_details},
            )
            print(f"  UpdateDatasources  : HTTP {update.status_code}")
        except Exception as exc:
            message = f"Paginated runtime update failed: {exc}"
            print(f"  Status             : UPDATE_FAILED\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "UPDATE_FAILED"))
            continue

        # The .NET application verifies once, immediately, through GET /datasources.
        try:
            persisted = get_paginated_report_datasources(
                powerbi, config.workspace_id, item.id
            )
        except Exception as exc:
            message = f"Runtime verification GET failed: {exc}"
            print(f"  Status             : VERIFY_FAILED\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "VERIFY_FAILED"))
            continue

        persisted_ok = bool(persisted) and all(
            _norm(_connection_details(ds).get("database")) == _norm(target_database)
            for ds in persisted
        )
        print("  Runtime verification: " + ("VERIFIED" if persisted_ok else "FAILED"))
        if not persisted_ok:
            observed = " | ".join(
                f"name={_runtime_name(ds) or '(none)'}; "
                f"server={_connection_details(ds).get('server')}; "
                f"database={_connection_details(ds).get('database')}"
                for ds in persisted
            )
            message = (
                "Power BI accepted UpdateDatasources but the target database was not persisted. "
                f"Expected {target_database}. Found: {observed or '(none)'}"
            )
            print(f"  Status             : VERIFY_FAILED\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "VERIFY_FAILED"))
            continue

        print("  Status             : UPDATED AND VERIFIED")
        results.append((item.name, "UPDATED"))

    print()
    print("=" * 80)
    print("PAGINATED RUNTIME DATASOURCE SUMMARY")
    print("=" * 80)
    for name, status in results:
        print(f"- {name}: {status}")

    if failures and config.fail_on_unresolved_paginated_datasource_binding:
        raise RuntimeError(
            f"Unable to safely bind {len(failures)} paginated report runtime datasource(s)."
        )
    return results
