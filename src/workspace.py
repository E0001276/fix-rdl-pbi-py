import base64
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import PurePosixPath


@dataclass
class WorkspaceItem:
    id: str
    name: str
    kind: str
    folder_id: str = ""


@dataclass
class WorkspaceRdlVisual:
    report_id: str
    report_name: str
    report_folder_id: str
    page_name: str
    definition_part_path: str
    old_item_id: str
    old_workspace_id: str
    parameter_names: set[str] = field(default_factory=set)
    definition_format: str = "PBIR"
    legacy_section_name: str = ""
    legacy_visual_name: str = ""


@dataclass
class PaginatedReportInfo:
    item: WorkspaceItem
    parameter_names: set[str] = field(default_factory=set)


class WorkspaceItems(list):
    @property
    def reports(self):
        return [item for item in self if item.kind == "Report"]

    @property
    def semantic_models(self):
        return [item for item in self if item.kind == "SemanticModel"]

    @property
    def paginated_reports(self):
        return [item for item in self if item.kind == "PaginatedReport"]


def _list_all(client, path: str):
    items = []
    next_url = path
    page_number = 1

    while next_url:
        response = client.get(next_url)
        data = response.json()
        page_items = data.get("value", [])
        items.extend(page_items)

        if page_number > 1:
            print(
                f"    [PAGE {page_number}] {len(page_items)} additional item(s) loaded."
            )

        next_url = data.get("continuationUri")
        if not next_url:
            token = data.get("continuationToken")
            next_url = f"{path}?continuationToken={token}" if token else None
        page_number += 1

    return items


def _print_item(item: WorkspaceItem) -> None:
    print(f"    - {item.name}")
    print(f"      Id      : {item.id}")
    print(f"      FolderId: {item.folder_id or '(root)'}")


def list_fabric_workspace_items(client, workspace_id: str):
    items = WorkspaceItems()
    endpoints = (
        ("reports", "Report", "REPORTS"),
        ("semanticModels", "SemanticModel", "SEMANTIC MODELS"),
        ("paginatedReports", "PaginatedReport", "PAGINATED REPORTS"),
    )

    for endpoint, kind, label in endpoints:
        print(f"[DISCOVERY] Loading {label}...")
        values = _list_all(client, f"workspaces/{workspace_id}/{endpoint}")
        print(f"  Found: {len(values)}")

        for value in values:
            item = WorkspaceItem(
                id=value["id"],
                name=value.get("displayName") or value.get("name") or value["id"],
                kind=kind,
                folder_id=value.get("folderId") or "",
            )
            items.append(item)
            _print_item(item)

        print()

    return items


def _decode_part(part):
    payload = part.get("payload", "")
    if part.get("payloadType") == "InlineBase64":
        return base64.b64decode(payload).decode("utf-8-sig")
    return payload


def _get_definition(client, workspace_id: str, item: WorkspaceItem):
    if item.kind == "Report":
        path = f"workspaces/{workspace_id}/reports/{item.id}/getDefinition"
    elif item.kind == "PaginatedReport":
        # Microsoft documents `format` as optional. When omitted,
        # PaginatedReportDefinition is the default. Some tenants currently
        # reject the explicit query string with InvalidDefinitionFormat, so
        # use the documented default form of the endpoint.
        path = f"workspaces/{workspace_id}/paginatedReports/{item.id}/getDefinition"
    else:
        raise ValueError(f"Definitions are not loaded for item type {item.kind}.")

    response = client.post(path)
    return client.get_json_lro_result(response)


def _literal_value(node):
    try:
        return node["expr"]["Literal"]["Value"].strip("'")
    except (KeyError, TypeError, AttributeError):
        return ""


def _rdl_visual_parameter_names(visual):
    result = set()
    try:
        mappings_value = visual["objects"]["parameterMapping"][0]["properties"][
            "mappings"
        ]
        raw = _literal_value(mappings_value)
        if raw:
            for mapping in json.loads(raw):
                name = mapping.get("paramName")
                if name:
                    result.add(name)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        pass
    return result


def _legacy_rdl_visual_reference(visual):
    old_item_id = ""
    old_workspace_id = ""

    try:
        properties = visual["objects"]["reportInfo"][0]["properties"]

        old_item_id = _literal_value(properties.get("reportId", {}))
        old_workspace_id = _literal_value(properties.get("workspaceId", {}))

        if not old_item_id or not old_workspace_id:
            ref = properties.get("reference", {}).get("byReference", {})
            old_item_id = old_item_id or _literal_value(ref.get("itemId", {}))
            old_workspace_id = old_workspace_id or _literal_value(
                ref.get("workspaceId", {})
            )
    except (KeyError, IndexError, TypeError):
        pass

    return old_item_id, old_workspace_id


def _discover_legacy_report_visuals(report, path, text):
    visuals = []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"  [WARN] Invalid legacy report JSON: {path}")
        return visuals

    for section in data.get("sections", []):
        page_name = section.get("displayName") or section.get("name") or ""
        section_name = section.get("name") or ""

        for container in section.get("visualContainers", []):
            raw_config = container.get("config", "")
            if not raw_config:
                continue

            try:
                config = json.loads(raw_config)
            except (TypeError, json.JSONDecodeError):
                continue

            visual = config.get("singleVisual", {})
            if visual.get("visualType") != "rdlVisual":
                continue

            old_item_id, old_workspace_id = _legacy_rdl_visual_reference(visual)

            visuals.append(
                WorkspaceRdlVisual(
                    report_id=report.id,
                    report_name=report.name,
                    report_folder_id=report.folder_id,
                    page_name=page_name,
                    definition_part_path=path,
                    old_item_id=old_item_id,
                    old_workspace_id=old_workspace_id,
                    parameter_names=_rdl_visual_parameter_names(visual),
                    definition_format="LegacyReportJson",
                    legacy_section_name=section_name,
                    legacy_visual_name=config.get("name") or "",
                )
            )

    return visuals


def discover_report_definitions(client, workspace_id: str, workspace_items):
    visuals = []
    reports = workspace_items.reports

    print(f"[REPORT DEFINITIONS] Reports to inspect: {len(reports)}")
    print()

    for index, report in enumerate(reports, start=1):
        print(f"[{index}/{len(reports)}] Report: {report.name}")
        print(f"  Report Id : {report.id}")
        print(f"  Folder Id : {report.folder_id or '(root)'}")
        print("  Loading definition...")

        definition_response = _get_definition(client, workspace_id, report)
        parts = definition_response.get("definition", {}).get("parts", [])
        print(f"  Definition parts: {len(parts)}")

        decoded = {}
        for part in parts:
            path = str(part.get("path", ""))
            if not path.lower().endswith(".json"):
                continue
            try:
                decoded[path] = _decode_part(part)
            except (UnicodeDecodeError, ValueError):
                print(f"  [WARN] Could not decode JSON part: {path}")

        page_names = {}
        for path, text in decoded.items():
            pure = PurePosixPath(path)
            if pure.name != "page.json":
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                print(f"  [WARN] Invalid page JSON: {path}")
                continue
            page_names[str(pure.parent)] = data.get("displayName") or data.get(
                "name", ""
            )

        print(f"  Pages found: {len(page_names)}")

        report_visuals = []
        for path, text in decoded.items():
            pure = PurePosixPath(path)
            if pure.name != "visual.json":
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                print(f"  [WARN] Invalid visual JSON: {path}")
                continue

            visual = data.get("visual", {})
            if visual.get("visualType") != "rdlVisual":
                continue

            old_item_id = ""
            old_workspace_id = ""
            try:
                ref = visual["objects"]["reportInfo"][0]["properties"]["reference"][
                    "byReference"
                ]
                old_item_id = _literal_value(ref.get("itemId", {}))
                old_workspace_id = _literal_value(ref.get("workspaceId", {}))
            except (KeyError, IndexError, TypeError):
                pass

            page_dir = str(pure.parents[2]) if len(pure.parents) >= 3 else ""
            workspace_visual = WorkspaceRdlVisual(
                report_id=report.id,
                report_name=report.name,
                report_folder_id=report.folder_id,
                page_name=page_names.get(page_dir, ""),
                definition_part_path=path,
                old_item_id=old_item_id,
                old_workspace_id=old_workspace_id,
                parameter_names=_rdl_visual_parameter_names(visual),
            )
            report_visuals.append(workspace_visual)
            visuals.append(workspace_visual)

        for path, text in decoded.items():
            if PurePosixPath(path).name != "report.json":
                continue
            legacy_visuals = _discover_legacy_report_visuals(report, path, text)
            report_visuals.extend(legacy_visuals)
            visuals.extend(legacy_visuals)

        print(f"  RDL Visuals found: {len(report_visuals)}")
        for visual in report_visuals:
            print(f"    - Page             : {visual.page_name or '(unnamed page)'}")
            print(f"      Definition part  : {visual.definition_part_path}")
            print(f"      Current itemId   : {visual.old_item_id or '(empty)'}")
            print(
                f"      Current workspace: "
                f"{visual.old_workspace_id or '(empty)'}"
            )
            print(
                "      Parameters       : "
                + (", ".join(sorted(visual.parameter_names)) or "(none)")
            )

        print()

    return visuals


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _rdl_parameter_names(xml_text: str):
    result = set()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return result

    for element in root.iter():
        if _xml_local_name(element.tag) == "ReportParameter":
            name = element.attrib.get("Name")
            if name:
                result.add(name)
    return result


def discover_paginated_report_definitions(client, workspace_id: str, workspace_items):
    result = []
    reports = workspace_items.paginated_reports

    print(f"[PAGINATED DEFINITIONS] Reports to inspect: {len(reports)}")
    print()

    for index, report in enumerate(reports, start=1):
        print(f"[{index}/{len(reports)}] Paginated report: {report.name}")
        print(f"  Report Id : {report.id}")
        print(f"  Folder Id : {report.folder_id or '(root)'}")
        print("  Loading RDL definition...")

        definition_response = _get_definition(client, workspace_id, report)
        parts = definition_response.get("definition", {}).get("parts", [])
        print(f"  Definition parts: {len(parts)}")

        parameter_names = set()
        rdl_count = 0
        for part in parts:
            if str(part.get("path", "")).lower().endswith(".rdl"):
                rdl_count += 1
                parameter_names |= _rdl_parameter_names(_decode_part(part))

        print(f"  RDL parts       : {rdl_count}")
        print(
            "  RDL parameters  : "
            + (", ".join(sorted(parameter_names)) or "(none)")
        )
        print("  Status          : LOADED")
        print()

        result.append(PaginatedReportInfo(report, parameter_names))

    return result


def get_report_definition(client, workspace_id: str, report_id: str):
    response = client.post(
        f"workspaces/{workspace_id}/reports/{report_id}/getDefinition"
    )
    return client.get_json_lro_result(response)


def get_paginated_report_definition(client, workspace_id: str, report_id: str):
    # `format` is optional per Microsoft Learn. If omitted,
    # PaginatedReportDefinition is used by default.
    response = client.post(
        f"workspaces/{workspace_id}/paginatedReports/{report_id}/getDefinition"
    )
    return client.get_json_lro_result(response)


def update_report_definition(client, workspace_id: str, report_id: str, definition: dict):
    response = client.post(
        f"workspaces/{workspace_id}/reports/{report_id}/updateDefinition",
        json={"definition": definition},
    )
    status_code = response.status_code
    client.wait_for_lro_completion(response)
    return status_code


def update_paginated_report_definition(
    client, workspace_id: str, report_id: str, definition: dict
):
    response = client.post(
        f"workspaces/{workspace_id}/paginatedReports/{report_id}/updateDefinition",
        json={"definition": definition},
    )
    status_code = response.status_code
    client.wait_for_lro_completion(response)
    return status_code
