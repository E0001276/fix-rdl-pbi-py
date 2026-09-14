import time


POWER_BI_SERVER = "pbiazure://api.powerbi.com/;"


def _norm(value) -> str:
    return str(value or "").strip().casefold()


def _datasources(payload: dict) -> list[dict]:
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return [item for item in values if isinstance(item, dict)]


def _connection_details(datasource: dict) -> dict:
    details = datasource.get("connectionDetails")
    return details if isinstance(details, dict) else {}


def _target_database(semantic_model_id: str) -> str:
    return f"sobe_wowvirtualserver-{semantic_model_id}"


def _is_target(datasource: dict, semantic_model_id: str) -> bool:
    details = _connection_details(datasource)
    return (
        _norm(details.get("server")) == _norm(POWER_BI_SERVER)
        and _norm(details.get("database")) == _norm(_target_database(semantic_model_id))
    )


def get_paginated_report_datasources(powerbi, workspace_id: str, report_id: str) -> list[dict]:
    response = powerbi.get(
        f"groups/{workspace_id}/reports/{report_id}/datasources"
    )
    return _datasources(response.json())


def update_paginated_report_datasource(
    powerbi,
    workspace_id: str,
    report_id: str,
    datasource_name: str,
    semantic_model_id: str,
) -> int:
    payload = {
        "updateDetails": [
            {
                "datasourceName": datasource_name,
                "connectionDetails": {
                    "server": POWER_BI_SERVER,
                    "database": _target_database(semantic_model_id),
                },
            }
        ]
    }
    response = powerbi.post(
        f"groups/{workspace_id}/reports/{report_id}/Default.UpdateDatasources",
        json=payload,
    )
    return response.status_code


def bind_paginated_reports_to_semantic_models(
    powerbi,
    workspace_items,
    paginated_infos,
    config,
):
    """Update the runtime datasource of each paginated report via Power BI REST.

    Fabric updateDefinition changes the RDL definition. Power BI's
    Default.UpdateDatasources changes the paginated report datasource used by the
    service at runtime. Both are needed in this deployment model.
    """
    if not config.bind_paginated_reports_to_semantic_models:
        print("Paginated report runtime datasource binding is disabled by configuration.")
        return []

    from paginated import _resolve_semantic_model

    failures = []
    results = []

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Paginated reports to bind: {len(paginated_infos)}")
    print("API: Power BI REST API v1.0")

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

        try:
            current = get_paginated_report_datasources(
                powerbi, config.workspace_id, item.id
            )
        except Exception as exc:
            message = f"GET datasources failed: {exc}"
            print(f"  Status             : GET_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "GET_FAILED"))
            continue

        print(f"  Runtime datasources: {len(current)}")
        for ds in current:
            details = _connection_details(ds)
            print(f"    - Name           : {ds.get('datasourceName') or '(none)'}")
            print(f"      Type           : {ds.get('datasourceType') or '(none)'}")
            print(f"      Server         : {details.get('server') or '(none)'}")
            print(f"      Database       : {details.get('database') or '(none)'}")

        candidates = [ds for ds in current if ds.get("datasourceName")]
        if len(candidates) != 1:
            message = (
                f"Expected exactly one named runtime datasource, found {len(candidates)}."
            )
            print("  Status             : AMBIGUOUS_DATASOURCE")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "AMBIGUOUS_DATASOURCE"))
            continue

        datasource = candidates[0]
        datasource_name = datasource.get("datasourceName")
        target_database = _target_database(model.id)

        if _is_target(datasource, model.id):
            print("  Target server      : " + POWER_BI_SERVER)
            print("  Target database    : " + target_database)
            print("  Status             : ALREADY CORRECT")
            results.append((item.name, "UNCHANGED"))
            continue

        print(f"  DatasourceName used: {datasource_name}")
        print("  Target server      : " + POWER_BI_SERVER)
        print("  Target database    : " + target_database)
        print("  Calling Default.UpdateDatasources...")

        try:
            status = update_paginated_report_datasource(
                powerbi,
                config.workspace_id,
                item.id,
                datasource_name,
                model.id,
            )
            print(f"  UpdateDatasources  : HTTP {status}")
        except Exception as exc:
            message = f"Default.UpdateDatasources failed: {exc}"
            print("  Status             : UPDATE_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append((item.name, "UPDATE_FAILED"))
            continue

        verified = False
        last = []
        for attempt in range(1, 6):
            if attempt > 1:
                time.sleep(2)
            try:
                last = get_paginated_report_datasources(
                    powerbi, config.workspace_id, item.id
                )
            except Exception as exc:
                print(f"  Runtime verification: attempt {attempt}/5 -> GET ERROR: {exc}")
                continue

            verified = any(_is_target(ds, model.id) for ds in last)
            print(
                f"  Runtime verification: attempt {attempt}/5 -> "
                + ("VERIFIED" if verified else "PENDING")
            )
            if verified:
                break

        if not verified:
            observed = []
            for ds in last:
                details = _connection_details(ds)
                observed.append(
                    f"{ds.get('datasourceName')}: server={details.get('server')}, database={details.get('database')}"
                )
            message = (
                "Power BI accepted Default.UpdateDatasources but the target semantic model "
                "was not observed by GET /datasources. Observed: " + " | ".join(observed)
            )
            print("  Status             : VERIFY_FAILED")
            print(f"  Reason             : {message}")
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
