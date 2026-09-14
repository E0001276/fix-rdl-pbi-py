import base64
import io
import re
import time
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


def _register_namespaces(xml_text: str) -> None:
    try:
        for _, ns in ET.iterparse(io.StringIO(xml_text), events=("start-ns",)):
            prefix, uri = ns
            try:
                ET.register_namespace(prefix or "", uri)
            except ValueError:
                pass
    except ET.ParseError:
        pass


def _serialize_xml(root: ET.Element) -> str:
    buffer = io.BytesIO()
    ET.ElementTree(root).write(
        buffer,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )
    return buffer.getvalue().decode("utf-8")


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
    _register_namespaces(xml_text)
    root = ET.fromstring(xml_text)

    changed = False
    datasource_name_map = {}

    for element in root.iter():
        if _local_name(element.tag) != "DataSource":
            continue
        old_name = element.attrib.get("Name", "")
        if not old_name:
            continue
        new_name = _target_datasource_name(old_name, workspace_name)
        datasource_name_map[old_name] = new_name
        if new_name != old_name:
            element.set("Name", new_name)
            changed = True

    for element in root.iter():
        local = _local_name(element.tag)
        if local == "ConnectString":
            old = element.text or ""
            new = _update_connect_string(old, semantic_model_id)
            if new != old:
                element.text = new
                changed = True
        elif local == "PowerBIWorkspaceName":
            old = (element.text or "").strip()
            if old != workspace_name:
                element.text = workspace_name
                changed = True
        elif local == "PowerBIDatasetName":
            old = (element.text or "").strip()
            if old != semantic_model_name:
                element.text = semantic_model_name
                changed = True
        elif local == "DataSourceName":
            old = (element.text or "").strip()
            if not old:
                continue
            new = datasource_name_map.get(old) or _target_datasource_name(
                old, workspace_name
            )
            if new != old:
                element.text = new
                changed = True

    return changed, _serialize_xml(root)


def _is_binding_correct(
    binding: dict,
    workspace_name: str,
    semantic_model_id: str,
    semantic_model_name: str,
) -> bool:
    if not binding["datasource_names"]:
        return False

    target_prefix = _normalize_workspace_datasource_prefix(workspace_name) + "_"
    target_database = f"sobe_wowvirtualserver-{semantic_model_id}".casefold()

    datasource_names_ok = all(
        name.casefold().startswith(target_prefix.casefold())
        for name in binding["datasource_names"]
    )
    dataset_refs_ok = all(
        name.casefold().startswith(target_prefix.casefold())
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
    catalog_ok = bool(binding["connect_strings"]) and all(
        target_database in value.casefold() for value in binding["connect_strings"]
    )

    return (
        datasource_names_ok
        and dataset_refs_ok
        and workspace_ok
        and dataset_ok
        and catalog_ok
    )


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

        if _is_binding_correct(
            binding_before, config.workspace_name, model.id, model.name
        ):
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
        if not _is_binding_correct(
            patched_binding, config.workspace_name, model.id, model.name
        ):
            message = "Local RDL validation failed before calling Fabric updateDefinition."
            print("  Status             : LOCAL_VERIFY_FAILED")
            print(f"  Reason             : {message}")
            failures.append(message)
            results.append(
                PaginatedBindingResult(item.id, item.name, model.id, model.name, "LOCAL_VERIFY_FAILED", message)
            )
            continue

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

        verified = False
        last_binding = binding_before
        for attempt in range(1, config.paginated_verify_max_attempts + 1):
            persisted = get_paginated_report_definition(
                fabric, config.workspace_id, item.id
            )
            persisted_part = _find_rdl_part(persisted)
            persisted_xml = _decode_part(persisted_part)
            last_binding = _extract_rdl_binding(persisted_xml)
            verified = _is_binding_correct(
                last_binding, config.workspace_name, model.id, model.name
            )
            print(
                f"  RDL verification   : attempt {attempt}/"
                f"{config.paginated_verify_max_attempts} -> "
                f"{'OK' if verified else 'PENDING'}"
            )
            if verified:
                break
            if attempt < config.paginated_verify_max_attempts:
                time.sleep(config.paginated_verify_delay_seconds)

        if verified:
            print("  Status             : UPDATED AND VERIFIED")
            results.append(
                PaginatedBindingResult(item.id, item.name, model.id, model.name, "UPDATED")
            )
        else:
            message = (
                "Fabric updateDefinition completed, but getDefinition did not return "
                "the expected target binding."
            )
            print("  Status             : VERIFY_FAILED")
            print(f"  Reason             : {message}")
            print("  Persisted datasource: " + (", ".join(last_binding["datasource_names"]) or "(none)"))
            print("  Persisted workspace : " + (", ".join(last_binding["workspace_names"]) or "(none)"))
            print("  Persisted model     : " + (", ".join(last_binding["dataset_names"]) or "(none)"))
            print("  Persisted connect   : " + (" | ".join(last_binding["connect_strings"]) or "(none)"))
            failures.append(message)
            results.append(
                PaginatedBindingResult(item.id, item.name, model.id, model.name, "VERIFY_FAILED", message)
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
