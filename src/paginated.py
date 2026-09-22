import base64
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from workspace import (
    get_paginated_report_definition,
    update_paginated_report_definition,
)


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



def _find_rdl_part(definition_response: dict) -> dict:
    parts = definition_response.get("definition", {}).get("parts", [])
    rdl_parts = [p for p in parts if str(p.get("path", "")).lower().endswith(".rdl")]
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



def _compact_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _datasource_suffix(datasource_name: str) -> str:
    value = str(datasource_name or "").strip()
    if "_" in value:
        return value.split("_", 1)[1]
    return value


def _resolve_semantic_model_for_datasource(
    workspace_items, paginated_item, datasource_name: str
):
    """Resolve one embedded RDL datasource to one target semantic model.

    Multi-datasource paginated reports can legitimately use semantic models from
    different Fabric folders.  The datasource suffix is therefore the primary
    identity signal (for example `wsdevcicd_FOVISSSTE` -> `FOVISSSTE`).
    Folder-based resolution remains only as a safe fallback for the traditional
    single-datasource reports.
    """
    suffix = _datasource_suffix(datasource_name)
    suffix_key = _compact_name(suffix)
    if not suffix_key:
        return None, "datasource name does not contain a resolvable model suffix"

    same_folder = [
        model
        for model in workspace_items.semantic_models
        if model.folder_id == paginated_item.folder_id
    ]
    same_folder_matches = [
        model for model in same_folder if _compact_name(model.name) == suffix_key
    ]
    if len(same_folder_matches) == 1:
        return same_folder_matches[0], "datasource suffix exactly matches semantic model name in paginated-report folder"
    if len(same_folder_matches) > 1:
        return None, f"datasource suffix matched {len(same_folder_matches)} semantic models in the paginated-report folder"

    global_matches = [
        model
        for model in workspace_items.semantic_models
        if _compact_name(model.name) == suffix_key
    ]
    if len(global_matches) == 1:
        return global_matches[0], "datasource suffix exactly matches semantic model name in target workspace"
    if len(global_matches) > 1:
        return None, f"datasource suffix matched {len(global_matches)} semantic models in target workspace"

    if len(same_folder) == 1:
        return same_folder[0], "single semantic model in the same workspace folder (fallback)"

    return None, (
        f"no semantic model matches datasource suffix '{suffix}', and the paginated-report "
        f"folder contains {len(same_folder)} semantic models"
    )


def _resolve_semantic_models_for_rdl(
    workspace_items, paginated_item, datasource_names: list[str]
):
    resolved = {}
    failures = []
    for datasource_name in datasource_names:
        model, reason = _resolve_semantic_model_for_datasource(
            workspace_items, paginated_item, datasource_name
        )
        if model is None:
            failures.append(f"{datasource_name}: {reason}")
        else:
            resolved[datasource_name] = (model, reason)
    return resolved, failures


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
    datasource_models: dict,
):
    """Patch each embedded datasource independently while preserving RDL XML.

    `datasource_models` is keyed by the current RDL datasource name and each value
    is a WorkspaceItem semantic model.  This is required for reports such as
    Desmarca FOVISSSTE Global/Detalle, which contain two datasources backed by two
    different semantic models.
    """
    _validate_rdl_namespace(xml_text)

    datasource_pattern = re.compile(
        r'(<DataSource\b[^>]*\bName=")([^"]+)("[^>]*>)(.*?)(</DataSource>)',
        flags=re.DOTALL,
    )
    datasource_name_map = {}
    changed = False

    def patch_datasource(match):
        nonlocal changed
        prefix, old_name, open_tail, body, close = match.groups()
        model = datasource_models.get(old_name)
        if model is None:
            return match.group(0)

        new_name = _target_datasource_name(old_name, workspace_name)
        datasource_name_map[old_name] = new_name
        new_body = body

        new_body, c = _replace_tag_text(
            new_body,
            "ConnectString",
            lambda value: _update_connect_string(value, model.id),
        )
        changed = changed or c

        new_body, c = _replace_tag_text(
            new_body, "rd:PowerBIWorkspaceName", lambda _value: workspace_name
        )
        changed = changed or c

        new_body, c = _replace_tag_text(
            new_body, "rd:PowerBIDatasetName", lambda _value: model.name
        )
        changed = changed or c

        if new_name != old_name:
            changed = True

        return prefix + new_name + open_tail + new_body + close

    result = datasource_pattern.sub(patch_datasource, xml_text)

    def map_datasource(value: str) -> str:
        stripped = value.strip()
        replacement = datasource_name_map.get(stripped) or _target_datasource_name(
            stripped, workspace_name
        )
        left = value[: len(value) - len(value.lstrip())]
        right = value[len(value.rstrip()) :]
        return left + replacement + right

    result, c = _replace_tag_text(result, "DataSourceName", map_datasource)
    changed = changed or c

    _validate_rdl_namespace(result)
    if (
        'xmlns="http://schemas.microsoft.com/AnalysisServices/QueryDefinition"'
        in re.search(r"<Report\b[^>]*>", result, flags=re.DOTALL).group(0)
    ):
        raise RuntimeError(
            "RDL root default namespace was changed to AnalysisServices/QueryDefinition."
        )

    return changed, result


def _extract_datasource_bindings(xml_text: str) -> list[dict]:
    """Return datasource-level binding details, preserving datasource identity."""
    root = ET.fromstring(xml_text)
    result = []
    for element in root.iter():
        if _local_name(element.tag) != "DataSource":
            continue
        entry = {
            "name": element.attrib.get("Name") or "",
            "workspace_name": "",
            "dataset_name": "",
            "connect_string": "",
        }
        for child in element.iter():
            local = _local_name(child.tag)
            text = (child.text or "").strip()
            if local == "PowerBIWorkspaceName" and text:
                entry["workspace_name"] = text
            elif local == "PowerBIDatasetName" and text:
                entry["dataset_name"] = text
            elif local == "ConnectString" and text:
                entry["connect_string"] = text
        result.append(entry)
    return result


def _datasource_bindings_match_target(
    xml_text: str, workspace_name: str, datasource_models: dict
) -> bool:
    bindings = _extract_datasource_bindings(xml_text)
    if len(bindings) != len(datasource_models):
        return False

    expected_by_name = {}
    for old_name, model in datasource_models.items():
        expected_by_name[_target_datasource_name(old_name, workspace_name).casefold()] = model

    for binding in bindings:
        model = expected_by_name.get(str(binding["name"]).casefold())
        if model is None:
            return False
        if str(binding["workspace_name"]).casefold() != workspace_name.casefold():
            return False
        if str(binding["dataset_name"]).casefold() != model.name.casefold():
            return False
        target_database = f"sobe_wowvirtualserver-{model.id}".casefold()
        if target_database not in str(binding["connect_string"]).casefold():
            return False
    return True



def _build_fabric_definition(
    original_response: dict, item_name: str, xml_after: str
) -> dict:
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
        raise RuntimeError(
            "The Fabric paginated definition did not contain an RDL part."
        )

    return {
        "parts": [
            {
                "path": f"{item_name}.rdl",
                "payload": _encode_rdl(xml_after),
                "payloadType": "InlineBase64",
            }
        ]
    }




def remediate_paginated_reports(fabric, workspace_items, paginated_infos, config):
    if not config.apply_paginated_report_fix:
        print("Paginated report remediation is disabled by configuration.")
        return []

    results = []
    failures = []

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Paginated reports to remediate: {len(paginated_infos)}")
    print("API: Microsoft Fabric REST API v1 only")
    print("Binding strategy: datasource-level semantic model resolution")
    print()

    for index, info in enumerate(paginated_infos, start=1):
        item = info.item
        print("-" * 80)
        print(f"[{index}/{len(paginated_infos)}] Paginated Report")
        print(f"  Name              : {item.name}")
        print(f"  Report Id         : {item.id}")
        print(f"  Folder Id         : {item.folder_id or '(root)'}")

        before = get_paginated_report_definition(fabric, config.workspace_id, item.id)
        part = _find_rdl_part(before)
        xml_before = _decode_part(part)
        if getattr(fabric, "diagnostics", None) is not None:
            fabric.diagnostics.log_rdl(item.name, item.id, "before", xml_before)
        binding_before = _extract_rdl_binding(xml_before)
        datasource_names = list(dict.fromkeys(binding_before["datasource_names"]))

        datasource_models, resolution_failures = _resolve_semantic_models_for_rdl(
            workspace_items, item, datasource_names
        )
        if resolution_failures:
            message = "Unable to resolve semantic model(s) safely: " + " | ".join(resolution_failures)
            print("  Semantic models   : NOT RESOLVED")
            print(f"  Reason            : {message}")
            failures.append(message)
            results.append(PaginatedBindingResult(item.id, item.name, "", "", "UNRESOLVED", message))
            continue

        print("  Datasource mappings:")
        for ds_name, (model, reason) in datasource_models.items():
            print(f"    - {ds_name}")
            print(f"      Semantic model : {model.name} [{model.id}]")
            print(f"      Resolution      : {reason}")

        model_map = {name: model for name, (model, _reason) in datasource_models.items()}
        model_names = ", ".join(dict.fromkeys(model.name for model in model_map.values()))
        model_ids = ", ".join(dict.fromkeys(model.id for model in model_map.values()))

        print("  Current RDL binding:")
        print("    DataSource Name  : " + (", ".join(binding_before["datasource_names"]) or "(none)"))
        print("    Workspace         : " + (", ".join(binding_before["workspace_names"]) or "(none)"))
        print("    Semantic Model    : " + (", ".join(binding_before["dataset_names"]) or "(none)"))
        print("    Connect String    : " + (" | ".join(binding_before["connect_strings"]) or "(none)"))

        if _datasource_bindings_match_target(xml_before, config.workspace_name, model_map):
            if getattr(fabric, "diagnostics", None) is not None:
                fabric.diagnostics.log_rdl(item.name, item.id, "after", xml_before)
            print("  Logical RDL binding: ALREADY CORRECT")
            print("  Status             : ALREADY CORRECT")
            results.append(PaginatedBindingResult(item.id, item.name, model_ids, model_names, "UNCHANGED"))
            continue

        changed, xml_after = _patch_rdl(xml_before, config.workspace_name, model_map)
        if getattr(fabric, "diagnostics", None) is not None:
            fabric.diagnostics.log_rdl(item.name, item.id, "after", xml_after)
        if not changed:
            message = "The RDL was not already correct but no patchable binding fields changed."
            print("  Status             : PATCH_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append(PaginatedBindingResult(item.id, item.name, model_ids, model_names, "PATCH_FAILED", message))
            continue

        if not _datasource_bindings_match_target(xml_after, config.workspace_name, model_map):
            message = "Datasource-level local RDL validation failed before calling Fabric updateDefinition."
            print("  Status             : LOCAL_VERIFY_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append(PaginatedBindingResult(item.id, item.name, model_ids, model_names, "LOCAL_VERIFY_FAILED", message))
            continue

        patched_binding = _extract_rdl_binding(xml_after)
        print("  XML patch strategy  : TEXT-PRESERVING (no XML re-serialization)")
        print("  Namespace integrity : VALID")
        print("  Patched RDL binding (local validation):")
        print("    DataSource Name  : " + (", ".join(patched_binding["datasource_names"]) or "(none)"))
        print("    Workspace         : " + (", ".join(patched_binding["workspace_names"]) or "(none)"))
        print("    Semantic Model    : " + (", ".join(patched_binding["dataset_names"]) or "(none)"))
        print("    Connect String    : " + (" | ".join(patched_binding["connect_strings"]) or "(none)"))

        definition = _build_fabric_definition(before, item.name, xml_after)
        print("  Updating RDL definition with Fabric REST...")
        try:
            status = update_paginated_report_definition(fabric, config.workspace_id, item.id, definition)
            print(f"  UpdateDefinition   : HTTP {status}")
        except Exception as exc:
            message = str(exc)
            print("  Status             : UPDATE_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append(PaginatedBindingResult(item.id, item.name, model_ids, model_names, "UPDATE_FAILED", message))
            continue

        try:
            persisted = get_paginated_report_definition(fabric, config.workspace_id, item.id)
            persisted_part = _find_rdl_part(persisted)
            persisted_xml = _decode_part(persisted_part)
            persisted_ok = _datasource_bindings_match_target(persisted_xml, config.workspace_name, model_map)
            if persisted_ok:
                print("  RDL verification   : VERIFIED PER DATASOURCE")
                print("  Status             : UPDATED AND VERIFIED")
                results.append(PaginatedBindingResult(item.id, item.name, model_ids, model_names, "UPDATED"))
            else:
                print("  RDL verification   : NOT REFLECTED (NON-BLOCKING)")
                print("  Item identity      : PRESERVED")
                print("  Recreation         : DISABLED")
                print("  Status             : UPDATED (HTTP ACCEPTED; RUNTIME BINDING NEXT)")
                results.append(PaginatedBindingResult(item.id, item.name, model_ids, model_names, "UPDATED_RUNTIME_BINDING_PENDING"))
        except Exception as exc:
            print("  RDL verification   : SKIPPED (NON-BLOCKING)")
            print(f"  Verification reason: {exc}")
            print("  Item identity      : PRESERVED")
            print("  Recreation         : DISABLED")
            results.append(PaginatedBindingResult(item.id, item.name, model_ids, model_names, "UPDATED_RUNTIME_BINDING_PENDING"))

    print()
    print("=" * 80)
    print("PAGINATED REPORT SUMMARY")
    print("=" * 80)
    for result in results:
        print(f"- {result.paginated_report_name}: {result.status} -> {result.semantic_model_name or '(not resolved)'} [{result.semantic_model_id or '-'}]")

    if failures and config.fail_on_unresolved_paginated_report:
        raise RuntimeError(f"Unable to safely remediate {len(failures)} paginated report relationship(s).")

    return results

