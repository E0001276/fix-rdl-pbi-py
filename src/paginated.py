import base64
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from workspace import get_paginated_report_definition, update_paginated_report_definition


@dataclass
class PaginatedBindingResult:
    paginated_report_id: str
    paginated_report_name: str
    semantic_model_id: str
    semantic_model_name: str
    status: str
    message: str = ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_workspace_datasource_prefix(workspace_name: str) -> str:
    return re.sub(r"[\s-]+", "", workspace_name or "")


def _target_datasource_name(current_name: str, workspace_name: str) -> str:
    """Target-only equivalent of the .NET workspace-prefix replacement.

    We do not need the source workspace name: the current RDL itself supplies the
    suffix. Replace only the prefix before the first underscore with the normalized
    target workspace name, preserving the datasource-specific suffix exactly.
    """
    if not current_name:
        return current_name
    target_prefix = _normalize_workspace_datasource_prefix(workspace_name)
    if "_" in current_name:
        _, suffix = current_name.split("_", 1)
        return f"{target_prefix}_{suffix}"
    return current_name


def _decode_part(part: dict) -> str:
    payload = part.get("payload", "")
    if part.get("payloadType") == "InlineBase64":
        return base64.b64decode(payload).decode("utf-8-sig")
    return payload


def _encode_rdl(xml_text: str) -> str:
    return base64.b64encode(xml_text.encode("utf-8")).decode("ascii")


def _validate_rdl_namespace(xml_text: str) -> None:
    """Fail fast if the RDL root no longer declares the report namespace as default.

    The RDL service expects the Report element to identify the 2016/01 report
    definition namespace. We intentionally preserve the original XML text rather
    than parsing and serializing it because ElementTree can move a nested default
    namespace (for AnalysisServices/QueryDefinition) to the document root and
    rewrite Report/DataSource elements with an ns0 prefix.
    """
    report_open = re.search(r"<Report\b[^>]*>", xml_text, flags=re.DOTALL)
    if not report_open:
        raise RuntimeError("RDL root <Report> element was not found.")

    expected = 'xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"'
    if expected not in report_open.group(0):
        raise RuntimeError(
            "RDL root Report element does not preserve the expected 2016/01 "
            "reportdefinition default namespace."
        )

    if re.search(r"<ns\d+:Report\b", xml_text):
        raise RuntimeError(
            "RDL root was namespace-rewritten (for example ns0:Report). "
            "The post-deploy refuses to upload a rewritten RDL."
        )


def _replace_tag_text(xml_text: str, tag_name: str, transform) -> tuple[str, bool]:
    pattern = re.compile(
        rf"(<{re.escape(tag_name)}\b[^>]*>)(.*?)(</{re.escape(tag_name)}>)",
        flags=re.DOTALL,
    )
    changed = False

    def repl(match):
        nonlocal changed
        old = match.group(2)
        new = transform(old)
        if new != old:
            changed = True
        return match.group(1) + new + match.group(3)

    return pattern.sub(repl, xml_text), changed


def _replace_datasource_names(xml_text: str, workspace_name: str):
    pattern = re.compile(r'(<DataSource\b[^>]*\bName=")([^"]+)(")')
    mapping = {}
    changed = False

    def repl(match):
        nonlocal changed
        old = match.group(2)
        new = _target_datasource_name(old, workspace_name)
        mapping[old] = new
        if new != old:
            changed = True
        return match.group(1) + new + match.group(3)

    return pattern.sub(repl, xml_text), mapping, changed


def _find_rdl_part(definition_response: dict) -> dict:
    parts = definition_response.get("definition", {}).get("parts", [])
    rdl_parts = [
        p for p in parts if str(p.get("path", "")).lower().endswith(".rdl")
    ]
    if len(rdl_parts) != 1:
        raise RuntimeError(
            f"Expected exactly one RDL definition part, found {len(rdl_parts)}."
        )
    return rdl_parts[0]


def _extract_rdl_binding(xml_text: str) -> dict:
    result = {
        "datasource_names": [],
        "dataset_datasource_names": [],
        "workspace_names": [],
        "dataset_names": [],
        "connect_strings": [],
    }

    root = ET.fromstring(xml_text)
    for element in root.iter():
        local = _local_name(element.tag)
        if local == "DataSource":
            name = element.attrib.get("Name")
            if name:
                result["datasource_names"].append(name)
        elif local == "DataSourceName" and element.text:
            result["dataset_datasource_names"].append(element.text.strip())
        elif local == "PowerBIWorkspaceName" and element.text:
            result["workspace_names"].append(element.text.strip())
        elif local == "PowerBIDatasetName" and element.text:
            result["dataset_names"].append(element.text.strip())
        elif local == "ConnectString" and element.text:
            result["connect_strings"].append(element.text.strip())
    return result


def _resolve_semantic_model(workspace_items, paginated_item):
    same_folder = [
        model
        for model in workspace_items.semantic_models
        if model.folder_id == paginated_item.folder_id
    ]
    if len(same_folder) == 1:
        return same_folder[0], "single semantic model in the same workspace folder"
    return None, f"{len(same_folder)} semantic models in the same workspace folder"


def _update_connect_string(value: str, target_model_id: str) -> str:
    result = value or ""
    target_database = f"sobe_wowvirtualserver-{target_model_id}"
    result = re.sub(
        r"(?i)(Initial\s+Catalog\s*=\s*)sobe_wowvirtualserver-[0-9a-f-]{36}",
        lambda m: m.group(1) + target_database,
        result,
    )
    result = re.sub(
        r"(?i)(semanticmodelid\s*=\s*)[0-9a-f-]{36}",
        lambda m: m.group(1) + target_model_id,
        result,
    )
    return result


def _patch_rdl(
    xml_text: str,
    workspace_name: str,
    semantic_model_id: str,
    semantic_model_name: str,
):
    """Patch only the binding values while preserving the original RDL XML.

    IMPORTANT: do not round-trip the RDL through ElementTree serialization.
    The document contains a nested AnalysisServices QueryDefinition default
    namespace. Registering all namespaces and serializing the tree can promote
    that nested namespace to the document root and rewrite the report namespace
    with an ns0 prefix. Fabric accepts the payload, but the paginated report can
    then be left with invalid underlying data-source state.
    """
    _validate_rdl_namespace(xml_text)

    result, datasource_name_map, ds_changed = _replace_datasource_names(
        xml_text, workspace_name
    )
    changed = ds_changed

    result, c = _replace_tag_text(
        result,
        "ConnectString",
        lambda value: _update_connect_string(value, semantic_model_id),
    )
    changed = changed or c

    result, c = _replace_tag_text(
        result, "rd:PowerBIWorkspaceName", lambda _value: workspace_name
    )
    changed = changed or c

    result, c = _replace_tag_text(
        result, "rd:PowerBIDatasetName", lambda _value: semantic_model_name
    )
    changed = changed or c

    def map_datasource(value: str) -> str:
        stripped = value.strip()
        replacement = datasource_name_map.get(stripped) or _target_datasource_name(
            stripped, workspace_name
        )
        # Preserve any whitespace around the original text node.
        left = value[: len(value) - len(value.lstrip())]
        right = value[len(value.rstrip()) :]
        return left + replacement + right

    result, c = _replace_tag_text(result, "DataSourceName", map_datasource)
    changed = changed or c

    _validate_rdl_namespace(result)

    # Guard against the exact namespace corruption observed in v15 diagnostics.
    if 'xmlns="http://schemas.microsoft.com/AnalysisServices/QueryDefinition"' in re.search(
        r"<Report\b[^>]*>", result, flags=re.DOTALL
    ).group(0):
        raise RuntimeError(
            "RDL root default namespace was changed to AnalysisServices/QueryDefinition."
        )

    return changed, result


def _is_binding_logically_correct(
    binding: dict,
    workspace_name: str,
    semantic_model_name: str,
) -> bool:
    """Match the .NET logical rule without consulting a source workspace.

    The expected datasource name is derived from the current target RDL: preserve
    everything after the first underscore and replace only the workspace prefix.
    The virtual database GUID is intentionally excluded; runtime binding handles it.
    """
    if not binding["datasource_names"]:
        return False

    expected_names = [
        _target_datasource_name(name, workspace_name)
        for name in binding["datasource_names"]
    ]
    datasource_names_ok = all(
        current.casefold() == expected.casefold()
        for current, expected in zip(binding["datasource_names"], expected_names)
    )

    expected_set = {name.casefold() for name in expected_names if name}
    dataset_refs_ok = bool(binding["dataset_datasource_names"]) and all(
        name.casefold() in expected_set
        for name in binding["dataset_datasource_names"]
    )
    workspace_ok = bool(binding["workspace_names"]) and all(
        name.casefold() == workspace_name.casefold()
        for name in binding["workspace_names"]
    )
    dataset_ok = bool(binding["dataset_names"]) and all(
        name.casefold() == semantic_model_name.casefold()
        for name in binding["dataset_names"]
    )
    return datasource_names_ok and dataset_refs_ok and workspace_ok and dataset_ok


def _build_fabric_definition(original_response: dict, item_name: str, xml_after: str) -> dict:
    """Build the smallest supported PaginatedReportDefinition payload.

    Microsoft documents the RDL part as required and the .platform part as optional.
    Do not echo the service-generated .platform part back during a content-only
    remediation. This avoids coupling the RDL replacement to Git/platform metadata.

    The caller intentionally omits the optional `format` property because this tenant
    rejects an explicit PaginatedReportDefinition value even though it is documented.
    The type-specific endpoint uses PaginatedReportDefinition as its default format.
    """
    original = original_response.get("definition", {})
    original_parts = original.get("parts", [])
    if not any(str(p.get("path", "")).lower().endswith(".rdl") for p in original_parts):
        raise RuntimeError("The Fabric paginated definition did not contain an RDL part.")

    return {
        "parts": [
            {
                "path": f"{item_name}.rdl",
                "payload": _encode_rdl(xml_after),
                "payloadType": "InlineBase64",
            }
        ]
    }



def _expected_datasource_name(workspace_name: str, semantic_model_name: str) -> str:
    workspace_prefix = re.sub(r"[\s-]+", "", workspace_name or "")
    model_suffix = re.sub(r"[\s-]+", "", semantic_model_name or "")
    return f"{workspace_prefix}_{model_suffix}"


def _binding_matches_target(binding: dict, workspace_name: str, model_name: str) -> bool:
    expected_ds = _expected_datasource_name(workspace_name, model_name).lower()
    ds_names = [str(x).strip().lower() for x in binding.get("datasource_names", [])]
    ws_names = [str(x).strip().lower() for x in binding.get("workspace_names", [])]
    model_names = [str(x).strip().lower() for x in binding.get("dataset_names", [])]
    return (
        bool(ds_names)
        and all(x == expected_ds for x in ds_names)
        and bool(ws_names)
        and all(x == (workspace_name or "").strip().lower() for x in ws_names)
        and bool(model_names)
        and all(x == (model_name or "").strip().lower() for x in model_names)
    )


def _extract_created_item_id(client, response):
    if response.status_code == 201:
        body = response.json()
        return body.get("id") or body.get("itemId")
    if response.status_code == 202:
        result = client.get_json_lro_result(response)
        if isinstance(result, dict):
            return result.get("id") or result.get("itemId")
    return None


def remediate_paginated_reports(fabric, workspace_items, paginated_infos, config):
    if not config.apply_paginated_report_fix:
        print("Paginated report remediation is disabled by configuration.")
        return []

    results = []
    failures = []

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Paginated reports to remediate: {len(paginated_infos)}")
    print("API: Microsoft Fabric REST API v1 only")
    print()

    for index, info in enumerate(paginated_infos, start=1):
        item = info.item
        print("-" * 80)
        print(f"[{index}/{len(paginated_infos)}] Paginated Report")
        print(f"  Name              : {item.name}")
        print(f"  Report Id         : {item.id}")
        print(f"  Folder Id         : {item.folder_id or '(root)'}")

        model, reason = _resolve_semantic_model(workspace_items, item)
        if model is None:
            message = f"Unable to resolve semantic model safely: {reason}."
            print("  Semantic model    : NOT RESOLVED")
            print(f"  Reason            : {message}")
            failures.append(message)
            results.append(
                PaginatedBindingResult(item.id, item.name, "", "", "UNRESOLVED", message)
            )
            continue

        print(f"  Semantic model    : {model.name} [{model.id}]")
        print(f"  Resolution reason : {reason}")

        before = get_paginated_report_definition(fabric, config.workspace_id, item.id)
        part = _find_rdl_part(before)
        xml_before = _decode_part(part)
        binding_before = _extract_rdl_binding(xml_before)

        print("  Current RDL binding:")
        print("    DataSource Name  : " + (", ".join(binding_before["datasource_names"]) or "(none)"))
        print("    Workspace         : " + (", ".join(binding_before["workspace_names"]) or "(none)"))
        print("    Semantic Model    : " + (", ".join(binding_before["dataset_names"]) or "(none)"))
        print("    Connect String    : " + (" | ".join(binding_before["connect_strings"]) or "(none)"))

        if _is_binding_logically_correct(
            binding_before, config.workspace_name, model.name
        ):
            print("  Logical RDL binding: ALREADY CORRECT")
            print("  Note               : virtual database GUID is handled by Power BI runtime binding")
            print("  Status             : ALREADY CORRECT")
            results.append(
                PaginatedBindingResult(item.id, item.name, model.id, model.name, "UNCHANGED")
            )
            continue

        changed, xml_after = _patch_rdl(
            xml_before,
            config.workspace_name,
            model.id,
            model.name,
        )
        if not changed:
            message = "The RDL was not already correct but no patchable binding fields changed."
            print("  Status             : PATCH_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append(
                PaginatedBindingResult(item.id, item.name, model.id, model.name, "PATCH_FAILED", message)
            )
            continue

        patched_binding = _extract_rdl_binding(xml_after)
        if not _is_binding_logically_correct(
            patched_binding, config.workspace_name, model.name
        ):
            message = "Local RDL validation failed before calling Fabric updateDefinition."
            print("  Status             : LOCAL_VERIFY_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append(
                PaginatedBindingResult(item.id, item.name, model.id, model.name, "LOCAL_VERIFY_FAILED", message)
            )
            continue

        print("  XML patch strategy  : TEXT-PRESERVING (no XML re-serialization)")
        print("  Namespace integrity : VALID")
        print("  Patched RDL binding (local validation):")
        print("    DataSource Name  : " + (", ".join(patched_binding["datasource_names"]) or "(none)"))
        print("    Workspace         : " + (", ".join(patched_binding["workspace_names"]) or "(none)"))
        print("    Semantic Model    : " + (", ".join(patched_binding["dataset_names"]) or "(none)"))
        print("    Connect String    : " + (" | ".join(patched_binding["connect_strings"]) or "(none)"))

        definition = _build_fabric_definition(before, item.name, xml_after)
        print("  Updating RDL definition with Fabric REST...")
        print("  Definition format : default (PaginatedReportDefinition)")
        print(f"  RDL part path      : {item.name}.rdl")
        print(f"  Definition parts  : {len(definition['parts'])} (RDL only; .platform omitted)")

        try:
            status = update_paginated_report_definition(
                fabric, config.workspace_id, item.id, definition
            )
            print(f"  UpdateDefinition   : HTTP {status}")
        except Exception as exc:
            message = str(exc)
            print("  Status             : UPDATE_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append(
                PaginatedBindingResult(item.id, item.name, model.id, model.name, "UPDATE_FAILED", message)
            )
            continue

        # IMPORTANT: never recreate, delete, or rename a Paginated Report item.
        # Recreating an item changes its Fabric itemId and Git integration sees the
        # operation as DELETE + ADD, producing duplicated entries in Source Control.
        # The working .NET implementation keeps the original item identity and fixes
        # the runtime datasource separately. We do the same here.
        #
        # We still perform one diagnostic read after updateDefinition. If Fabric has
        # not reflected the logical RDL binding yet, that condition is NON-BLOCKING:
        # the next phase (Power BI Default.UpdateDatasources) fixes the effective
        # runtime connection without replacing the item.
        try:
            persisted = get_paginated_report_definition(
                fabric, config.workspace_id, item.id
            )
            persisted_part = _find_rdl_part(persisted)
            persisted_xml = _decode_part(persisted_part)
            persisted_binding = _extract_rdl_binding(persisted_xml)
            persisted_ok = _binding_matches_target(
                persisted_binding, config.workspace_name, model.name
            )

            if persisted_ok:
                print("  RDL verification   : VERIFIED")
                print("  Status             : UPDATED AND VERIFIED")
                results.append(
                    PaginatedBindingResult(
                        item.id, item.name, model.id, model.name, "UPDATED"
                    )
                )
            else:
                print("  RDL verification   : NOT REFLECTED (NON-BLOCKING)")
                print("  Persisted DataSource: " + (
                    ", ".join(persisted_binding["datasource_names"]) or "(none)"
                ))
                print("  Persisted Workspace : " + (
                    ", ".join(persisted_binding["workspace_names"]) or "(none)"
                ))
                print("  Item identity      : PRESERVED")
                print("  Recreation         : DISABLED")
                print("  Status             : UPDATED (HTTP ACCEPTED; RUNTIME BINDING NEXT)")
                results.append(
                    PaginatedBindingResult(
                        item.id, item.name, model.id, model.name,
                        "UPDATED_RUNTIME_BINDING_PENDING"
                    )
                )
        except Exception as exc:
            print("  RDL verification   : SKIPPED (NON-BLOCKING)")
            print(f"  Verification reason: {exc}")
            print("  Item identity      : PRESERVED")
            print("  Recreation         : DISABLED")
            print("  Status             : UPDATED (HTTP ACCEPTED; RUNTIME BINDING NEXT)")
            results.append(
                PaginatedBindingResult(
                    item.id, item.name, model.id, model.name,
                    "UPDATED_RUNTIME_BINDING_PENDING"
                )
            )

    print()
    print("=" * 80)
    print("PAGINATED REPORT SUMMARY")
    print("=" * 80)
    for result in results:
        print(
            f"- {result.paginated_report_name}: {result.status} -> "
            f"{result.semantic_model_name or '(not resolved)'} "
            f"[{result.semantic_model_id or '-'}]"
        )

    if failures and config.fail_on_unresolved_paginated_report:
        raise RuntimeError(
            f"Unable to safely remediate {len(failures)} paginated report relationship(s)."
        )

    return results
