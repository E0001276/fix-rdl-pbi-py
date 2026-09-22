from paginated import _resolve_semantic_models_for_rdl
from workspace import (
    get_paginated_report_definition,
    update_paginated_info_definition,
)


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
    return str(datasource.get("name") or datasource.get("datasourceName") or "").strip()


def _target_database(semantic_model_id: str) -> str:
    return f"sobe_wowvirtualserver-{semantic_model_id}"


def get_paginated_report_datasources(powerbi, workspace_id: str, report_id: str) -> list[dict]:
    response = powerbi.get(f"groups/{workspace_id}/reports/{report_id}/datasources")
    return _datasources(response.json())


def _get_persisted_rdl_datasource_names(
    fabric, workspace_id: str, info
) -> list[str]:
    """Return persisted RDL datasource names with targeted cache refresh.

    Definitions loaded during initial discovery are reused for the entire run.
    A fresh Fabric call is made only when a previous write could not be verified
    and therefore marked this one snapshot stale.
    """
    if not info.definition_current or not info.datasource_names:
        definition = get_paginated_report_definition(
            fabric, workspace_id, info.item.id
        )
        update_paginated_info_definition(info, definition, current=True)
        print("  RDL definition     : FABRIC REST (TARGETED CACHE REFRESH)")
    else:
        print("  RDL definition     : EXECUTION CACHE")

    return list(info.datasource_names)


def _find_runtime_for_rdl(runtime_datasources: list[dict], rdl_name: str):
    exact = [ds for ds in runtime_datasources if _norm(_runtime_name(ds)) == _norm(rdl_name)]
    if len(exact) == 1:
        return exact[0]
    # Safe legacy fallback only when Power BI exposes a single datasource.
    if len(runtime_datasources) == 1:
        return runtime_datasources[0]
    return None


def _build_update_details(runtime_datasources: list[dict], datasource_models: dict):
    details = []
    unresolved_runtime = []
    for rdl_name, model in datasource_models.items():
        runtime = _find_runtime_for_rdl(runtime_datasources, rdl_name)
        if runtime is None and len(runtime_datasources) > 1:
            unresolved_runtime.append(rdl_name)
            continue
        current_server = _connection_details(runtime or {}).get("server") or ""
        target_server = current_server or DEFAULT_POWER_BI_SERVER
        details.append(
            {
                "datasourceName": rdl_name,
                "connectionDetails": {
                    "server": target_server,
                    "database": _target_database(model.id),
                },
            }
        )
    return details, unresolved_runtime


def _runtime_matches_target(runtime_datasources: list[dict], datasource_models: dict) -> bool:
    if not runtime_datasources or not datasource_models:
        return False
    for rdl_name, model in datasource_models.items():
        runtime = _find_runtime_for_rdl(runtime_datasources, rdl_name)
        if runtime is None:
            return False
        database = _connection_details(runtime).get("database")
        if _norm(database) != _norm(_target_database(model.id)):
            return False
    return True


def bind_paginated_reports_to_semantic_models(
    powerbi,
    fabric,
    workspace_items,
    paginated_infos,
    config,
):
    """Bind each paginated-report datasource to its own semantic model.

    A paginated report can contain multiple Power BI datasources.  Each datasource
    is resolved independently from its persisted RDL name, so reports such as
    Desmarca FOVISSSTE Global/Detalle can bind `..._DesmarcaFOVISSSTE` to the
    Desmarca FOVISSSTE model and `..._FOVISSSTE` to the FOVISSSTE model.
    """
    if not config.bind_paginated_reports_to_semantic_models:
        print("Paginated report runtime datasource binding is disabled by configuration.")
        return []

    failures = []
    results = []

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Paginated reports to bind: {len(paginated_infos)}")
    print("API: Power BI REST API v1.0")
    print("Strategy: per-datasource semantic model resolution")

    for index, info in enumerate(paginated_infos, start=1):
        item = info.item
        print("-" * 80)
        print(f"[{index}/{len(paginated_infos)}] Paginated Report Runtime Datasource")
        print(f"  Name              : {item.name}")
        print(f"  Report Id         : {item.id}")

        try:
            runtime_datasources = get_paginated_report_datasources(
                powerbi, config.workspace_id, item.id
            )
            rdl_names = _get_persisted_rdl_datasource_names(
                fabric, config.workspace_id, info
            )
        except Exception as exc:
            message = f"Datasource discovery failed: {exc}"
            print(f"  Status             : GET_FAILED\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "GET_FAILED"))
            continue

        datasource_resolution, resolution_failures = _resolve_semantic_models_for_rdl(
            workspace_items, item, rdl_names
        )
        if resolution_failures:
            message = "Unable to resolve semantic model(s) safely: " + " | ".join(resolution_failures)
            print("  Status             : UNRESOLVED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "UNRESOLVED"))
            continue

        datasource_models = {
            name: model for name, (model, _reason) in datasource_resolution.items()
        }

        print(f"  Runtime datasources: {len(runtime_datasources)}")
        for ds in runtime_datasources:
            details = _connection_details(ds)
            print(f"    - Name           : {_runtime_name(ds) or '(none)'}")
            print(f"      Type           : {ds.get('datasourceType') or '(none)'}")
            print(f"      Server         : {details.get('server') or '(none)'}")
            print(f"      Database       : {details.get('database') or '(none)'}")

        print(f"  Persisted RDL datasource names: {len(rdl_names)}")
        for name in rdl_names:
            model, reason = datasource_resolution[name]
            print(f"    - {name}")
            print(f"      Semantic model : {model.name} [{model.id}]")
            print(f"      Resolution      : {reason}")

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

        if _runtime_matches_target(runtime_datasources, datasource_models):
            print("  Status             : ALREADY CORRECT")
            results.append((item.name, "UNCHANGED"))
            continue

        update_details, unresolved_runtime = _build_update_details(
            runtime_datasources, datasource_models
        )
        if unresolved_runtime:
            message = (
                "Power BI returned multiple runtime datasources but none matched these RDL datasource names exactly: "
                + ", ".join(unresolved_runtime)
            )
            print(f"  Status             : UNRESOLVED\n  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "UNRESOLVED"))
            continue

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

        persisted_ok = _runtime_matches_target(persisted, datasource_models)
        print("  Runtime verification: " + ("VERIFIED PER DATASOURCE" if persisted_ok else "FAILED"))
        if not persisted_ok:
            observed = " | ".join(
                f"name={_runtime_name(ds) or '(none)'}; "
                f"server={_connection_details(ds).get('server')}; "
                f"database={_connection_details(ds).get('database')}"
                for ds in persisted
            )
            expected = " | ".join(
                f"{name}={_target_database(model.id)}"
                for name, model in datasource_models.items()
            )
            message = (
                "Power BI accepted UpdateDatasources but one or more datasource-specific target databases were not persisted. "
                f"Expected: {expected}. Found: {observed or '(none)'}"
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
