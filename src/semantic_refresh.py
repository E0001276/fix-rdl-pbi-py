import time


def get_dataset_info(powerbi, workspace_id: str, dataset_id: str) -> dict:
    return powerbi.get(f"groups/{workspace_id}/datasets/{dataset_id}").json()


def get_latest_refresh(powerbi, workspace_id: str, dataset_id: str) -> dict | None:
    response = powerbi.get(
        f"groups/{workspace_id}/datasets/{dataset_id}/refreshes",
        params={"$top": 1},
    )
    values = response.json().get("value", [])
    return values[0] if values else None


def refresh_semantic_models(powerbi, workspace_items, config):
    if not config.refresh_semantic_models:
        print("Semantic model refresh is disabled by configuration.")
        return []

    results = []
    failures = []
    models = workspace_items.semantic_models

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Semantic Models to refresh: {len(models)}")
    print(f"Wait for completion       : {config.wait_for_refresh}")

    for index, model in enumerate(models, start=1):
        print("-" * 80)
        print(f"[{index}/{len(models)}] Semantic Model Refresh")
        print(f"  Name              : {model.name}")
        print(f"  Model Id          : {model.id}")
        try:
            info = get_dataset_info(powerbi, config.workspace_id, model.id)
            is_refreshable = bool(info.get("isRefreshable"))
            print(f"  IsRefreshable     : {is_refreshable}")
            if not is_refreshable:
                raise RuntimeError("Power BI reports isRefreshable=false for this semantic model.")

            response = powerbi.post(
                f"groups/{config.workspace_id}/datasets/{model.id}/refreshes",
                json={"notifyOption": "NoNotification"},
            )
            print(f"  Refresh request   : HTTP {response.status_code}")

            if not config.wait_for_refresh:
                print("  Status            : STARTED")
                results.append((model, "STARTED"))
                continue

            deadline = time.monotonic() + config.refresh_timeout_seconds
            while time.monotonic() < deadline:
                time.sleep(config.refresh_poll_seconds)
                latest = get_latest_refresh(powerbi, config.workspace_id, model.id)
                status = str((latest or {}).get("status") or "").strip()
                request_id = str((latest or {}).get("requestId") or "").strip()
                print(
                    f"  Refresh status    : {status or '(unknown)'}"
                    + (f" [{request_id}]" if request_id else "")
                )
                if status.casefold() == "completed":
                    print("  Status            : COMPLETED")
                    results.append((model, "COMPLETED"))
                    break
                if status.casefold() in {"failed", "cancelled", "canceled", "disabled"}:
                    error = (latest or {}).get("serviceExceptionJson") or ""
                    raise RuntimeError(f"Refresh finished with status {status}. {error}")
            else:
                raise TimeoutError(
                    f"Refresh did not complete within {config.refresh_timeout_seconds} seconds."
                )

        except Exception as exc:
            message = str(exc)
            print("  Status            : ERROR")
            print(f"  Reason            : {message}")
            failures.append((model, message))
            results.append((model, "ERROR"))

    print()
    print("=" * 80)
    print("SEMANTIC MODEL REFRESH SUMMARY")
    print("=" * 80)
    for model, status in results:
        print(f"- {model.name}: {status}")

    if failures and config.fail_on_refresh_error:
        raise RuntimeError(
            f"Unable to refresh {len(failures)} semantic model(s)."
        )
    return results
