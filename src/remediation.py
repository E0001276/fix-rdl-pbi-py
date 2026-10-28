import base64
import json
from collections import Counter

from paginated_mapping import PaginatedReportMapping
from workspace import get_report_definition, update_report_definition


def summarize_discovery(workspace_items, rdl_visuals, config, mapping):
    counts = {"Report": 0, "SemanticModel": 0, "PaginatedReport": 0}
    for item in workspace_items:
        if item.kind in counts:
            counts[item.kind] += 1

    print(f"Workspace            : {config.workspace_name}")
    print(f"Workspace Id         : {config.workspace_id}")
    print(f"Reports              : {counts['Report']}")
    print(f"Semantic Models      : {counts['SemanticModel']}")
    print(f"Paginated Reports    : {counts['PaginatedReport']}")
    print(f"RDL Visuals          : {len(rdl_visuals)}")
    print(f"Mapping reports      : {mapping.report_count}")
    print(f"Mapping pages        : {mapping.page_count}")
    print(f"Total workspace items: {len(workspace_items)}")


def print_resolution_header(index, total, visual):
    print("-" * 80)
    print(f"[{index}/{total}] Resolving RDL Visual")
    print(f"  Main report        : {visual.report_name}")
    print(f"  Main report Id     : {visual.report_id}")
    print(f"  Page               : {visual.page_name or '(unnamed page)'}")
    print(f"  Definition part    : {visual.definition_part_path}")
    print(f"  Current itemId     : {visual.old_item_id or '(empty)'}")
    print(f"  Current workspaceId: {visual.old_workspace_id or '(empty)'}")


def validate_mapping_cardinality(rdl_visuals) -> None:
    """Fail when mapping v1 cannot distinguish multiple RDL visuals on one page."""
    counts = Counter((visual.report_name, visual.page_name) for visual in rdl_visuals)
    ambiguous = [key for key, count in counts.items() if count > 1]
    if not ambiguous:
        return

    details = "; ".join(
        f"{report} / {page or '(unnamed page)'} ({counts[(report, page)]} visuals)"
        for report, page in ambiguous
    )
    raise RuntimeError(
        "reports.yaml version 1 supports one RDL visual per "
        f"report page. Multiple RDL visuals were found: {details}."
    )


def index_paginated_reports(paginated_infos):
    by_name = {}
    for info in paginated_infos:
        by_name.setdefault(info.item.name, []).append(info)
    return by_name


def resolve_from_mapping(
    mapping: PaginatedReportMapping,
    paginated_by_name: dict,
    visual,
):
    relation = mapping.find(visual.report_name, visual.page_name)
    if relation is None:
        return None, (
            "mapping entry not found for "
            f"report='{visual.report_name}', page='{visual.page_name}'"
        )

    matches = paginated_by_name.get(relation.paginated_report, [])
    if not matches:
        return None, (
            "mapped paginated report was not found in target workspace: "
            f"'{relation.paginated_report}'"
        )

    if len(matches) > 1:
        ids = ", ".join(info.item.id for info in matches)
        return None, (
            "mapped paginated report name is ambiguous in target workspace: "
            f"'{relation.paginated_report}' matched {len(matches)} items [{ids}]"
        )

    return matches[0], (
        "explicit mapping: "
        f"{visual.report_name} / {visual.page_name} -> {relation.paginated_report}"
    )


def encode_json_part(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def patch_rdl_visual_part(part: dict, target_item_id: str, target_workspace_id: str):
    if part.get("payloadType") != "InlineBase64":
        raise RuntimeError(
            f"Unsupported payload type for {part.get('path')}: {part.get('payloadType')}"
        )

    raw = base64.b64decode(part.get("payload", "")).decode("utf-8-sig")
    data = json.loads(raw)
    visual = data.get("visual", {})
    if visual.get("visualType") != "rdlVisual":
        raise RuntimeError(f"Definition part is not an RDL visual: {part.get('path')}")

    objects = visual.setdefault("objects", {})
    report_info = objects.setdefault("reportInfo", [])
    if not report_info:
        report_info.append({})
    properties = report_info[0].setdefault("properties", {})

    # PBIR stores the linked paginated report as an ItemLocation reference.
    # Replace only this relationship; parameterMapping and the rest of the
    # visual definition are intentionally preserved.
    properties["reference"] = {
        "kind": "ItemLocation",
        "byReference": {
            "itemId": {"expr": {"Literal": {"Value": f"'{target_item_id}'"}}},
            "workspaceId": {
                "expr": {"Literal": {"Value": f"'{target_workspace_id}'"}}
            },
        },
    }

    part["payload"] = encode_json_part(data)


def patch_legacy_rdl_visual_part(
    part: dict, visual_locator, target_item_id: str, target_workspace_id: str
):
    if part.get("payloadType") != "InlineBase64":
        raise RuntimeError(
            f"Unsupported payload type for {part.get('path')}: {part.get('payloadType')}"
        )

    raw = base64.b64decode(part.get("payload", "")).decode("utf-8-sig")
    data = json.loads(raw)

    for section in data.get("sections", []):
        if section.get("name") != visual_locator.legacy_section_name:
            continue

        for container in section.get("visualContainers", []):
            raw_config = container.get("config", "")
            if not raw_config:
                continue

            try:
                config = json.loads(raw_config)
            except (TypeError, json.JSONDecodeError):
                continue

            if config.get("name") != visual_locator.legacy_visual_name:
                continue

            visual = config.get("singleVisual", {})
            if visual.get("visualType") != "rdlVisual":
                raise RuntimeError(
                    f"Legacy visual is not an RDL visual: {visual_locator.page_name}"
                )

            objects = visual.setdefault("objects", {})
            report_info = objects.setdefault("reportInfo", [])
            if not report_info:
                report_info.append({})
            properties = report_info[0].setdefault("properties", {})

            # Legacy report.json uses direct reportId/workspaceId literals.
            # parameterMapping is intentionally left untouched.
            properties["reportId"] = {
                "expr": {"Literal": {"Value": f"'{target_item_id}'"}}
            }
            properties["workspaceId"] = {
                "expr": {"Literal": {"Value": f"'{target_workspace_id}'"}}
            }

            config["singleVisual"] = visual
            container["config"] = json.dumps(
                config, ensure_ascii=False, separators=(",", ":")
            )
            part["payload"] = encode_json_part(data)
            return

    raise RuntimeError(
        "Unable to locate legacy RDL visual in "
        f"{part.get('path')} / {visual_locator.page_name}."
    )


def read_legacy_reference(part: dict, visual_locator):
    if part.get("payloadType") != "InlineBase64":
        return "", ""

    raw = base64.b64decode(part.get("payload", "")).decode("utf-8-sig")
    data = json.loads(raw)

    for section in data.get("sections", []):
        if section.get("name") != visual_locator.legacy_section_name:
            continue

        for container in section.get("visualContainers", []):
            raw_config = container.get("config", "")
            if not raw_config:
                continue
            try:
                config = json.loads(raw_config)
            except (TypeError, json.JSONDecodeError):
                continue
            if config.get("name") != visual_locator.legacy_visual_name:
                continue

            visual = config.get("singleVisual", {})
            try:
                properties = visual["objects"]["reportInfo"][0]["properties"]
                item_id = properties["reportId"]["expr"]["Literal"]["Value"].strip("'")
                workspace_id = properties["workspaceId"]["expr"]["Literal"][
                    "Value"
                ].strip("'")
                return item_id, workspace_id
            except (KeyError, IndexError, TypeError, AttributeError):
                return "", ""

    return "", ""


def read_reference_from_definition(definition_response: dict, visual_locator):
    for part in definition_response.get("definition", {}).get("parts", []):
        if part.get("path") != visual_locator.definition_part_path:
            continue
        if visual_locator.definition_format == "LegacyReportJson":
            return read_legacy_reference(part, visual_locator)
        if part.get("payloadType") != "InlineBase64":
            return "", ""
        raw = base64.b64decode(part.get("payload", "")).decode("utf-8-sig")
        data = json.loads(raw)
        try:
            ref = data["visual"]["objects"]["reportInfo"][0]["properties"]["reference"][
                "byReference"
            ]
            item_id = ref["itemId"]["expr"]["Literal"]["Value"].strip("'")
            workspace_id = ref["workspaceId"]["expr"]["Literal"]["Value"].strip("'")
            return item_id, workspace_id
        except (KeyError, IndexError, TypeError, AttributeError):
            return "", ""
    return "", ""


def apply_remediation(
    fabric,
    rdl_visuals,
    paginated_infos,
    config,
    mapping: PaginatedReportMapping,
    report_definition_cache: dict | None = None,
):
    """Resolve and repair RDL Visual links using explicit mapping only.

    Resolution is deterministic:
      Report displayName + Page displayName -> PaginatedReport displayName.

    No folder, parameter, fuzzy-name, source-workspace, or historical lookup is
    used.  The target paginated report ID is obtained from the current target
    workspace by exact displayName.
    """
    validate_mapping_cardinality(rdl_visuals)
    paginated_by_name = index_paginated_reports(paginated_infos)

    unresolved = []
    plan = []
    used_mapping_keys = set()

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"Mapping  : {config.reports_mapping_path}")
    print(f"RDL Visuals to resolve: {len(rdl_visuals)}")
    print()

    for index, visual in enumerate(rdl_visuals, start=1):
        print_resolution_header(index, len(rdl_visuals), visual)

        paginated, reason = resolve_from_mapping(mapping, paginated_by_name, visual)
        relation = mapping.find(visual.report_name, visual.page_name)
        if relation is not None:
            used_mapping_keys.add((relation.report, relation.page))

        if paginated is None:
            unresolved.append((visual, reason))
            print("  Target report      : NOT RESOLVED")
            print(f"  Resolution reason  : {reason}")
            print("  Resolution status  : UNRESOLVED")
            print("  Apply status       : NOT APPLIED")
            print()
            continue

        already_points_to_target = visual.old_item_id == paginated.item.id
        workspace_is_current = visual.old_workspace_id == config.workspace_id
        needs_update = not (already_points_to_target and workspace_is_current)
        plan.append((visual, paginated.item, reason, needs_update))

        print(f"  Target report      : {paginated.item.name}")
        print(f"  Target report Id   : {paginated.item.id}")
        print(f"  Resolution reason  : {reason}")
        print(
            "  Current reference  : "
            + ("MATCHES TARGET" if already_points_to_target else "DIFFERS FROM TARGET")
        )
        print(
            "  Workspace reference: "
            + ("CURRENT" if workspace_is_current else "DIFFERS FROM TARGET")
        )
        print("  Resolution status  : TARGET IDENTIFIED")
        print(
            "  Apply status       : "
            + ("NOT REQUIRED" if not needs_update else "PENDING")
        )
        print()

    unused_mapping_keys = mapping.keys() - used_mapping_keys
    if unused_mapping_keys:
        print("[MAPPING] Entries not used by discovered RDL Visuals:")
        for report_name, page_name in sorted(unused_mapping_keys):
            print(f"  - {report_name} / {page_name}")
        print()

    if unresolved and config.fail_on_unresolved_rdl_visual:
        details = "; ".join(
            f"{visual.report_name} / {visual.page_name}: {reason}"
            for visual, reason in unresolved
        )
        raise RuntimeError(
            f"Unable to resolve {len(unresolved)} RDL Visual relationship(s) "
            f"from reports.yaml. No report definitions were updated. {details}"
        )

    print("=" * 80)
    print("RDL VISUAL APPLY")
    print("=" * 80)

    if not config.apply_rdl_visual_fix:
        print("Apply is disabled by configuration (applyRdlVisualFix=false).")
    else:
        by_report = {}
        for visual, target, _, needs_update in plan:
            if needs_update:
                by_report.setdefault(visual.report_id, []).append((visual, target))

        for report_id, changes in by_report.items():
            report_name = changes[0][0].report_name
            print(f"[REPORT] {report_name} [{report_id}]")
            if report_definition_cache is not None and report_id in report_definition_cache:
                definition_response = report_definition_cache[report_id]
                print("  Definition source  : EXECUTION CACHE")
            else:
                definition_response = get_report_definition(
                    fabric, config.workspace_id, report_id
                )
                if report_definition_cache is not None:
                    report_definition_cache[report_id] = definition_response
                print("  Definition source  : FABRIC REST")

            definition = definition_response.get("definition", {})
            parts = definition.get("parts", [])
            parts_by_path = {part.get("path"): part for part in parts}

            for visual, target in changes:
                part = parts_by_path.get(visual.definition_part_path)
                if part is None:
                    raise RuntimeError(
                        f"Definition part not found: {visual.definition_part_path}"
                    )

                print(f"  Patching page      : {visual.page_name}")
                print(f"    Old itemId       : {visual.old_item_id or '(empty)'}")
                print(f"    New itemId       : {target.id}")
                print(f"    Old workspaceId  : {visual.old_workspace_id or '(empty)'}")
                print(f"    New workspaceId  : {config.workspace_id}")

                if visual.definition_format == "LegacyReportJson":
                    patch_legacy_rdl_visual_part(
                        part, visual, target.id, config.workspace_id
                    )
                else:
                    patch_rdl_visual_part(part, target.id, config.workspace_id)

            print("  Calling Update Report Definition...")
            status_code = update_report_definition(
                fabric, config.workspace_id, report_id, definition
            )
            print(f"  UpdateDefinition   : HTTP {status_code}")

            print("  Verifying updated references...")
            verify_definition = get_report_definition(
                fabric, config.workspace_id, report_id
            )
            if report_definition_cache is not None:
                report_definition_cache[report_id] = verify_definition

            for visual, target in changes:
                actual_item_id, actual_workspace_id = read_reference_from_definition(
                    verify_definition, visual
                )
                ok = (
                    actual_item_id == target.id
                    and actual_workspace_id == config.workspace_id
                )
                print(f"    {visual.page_name}: {'OK' if ok else 'FAILED'}")
                print(f"      itemId      : {actual_item_id or '(empty)'}")
                print(f"      workspaceId : {actual_workspace_id or '(empty)'}")
                if not ok:
                    raise RuntimeError(
                        f"RDL visual update verification failed for "
                        f"{report_name} / {visual.page_name}."
                    )

            print("  Apply status       : UPDATED AND VERIFIED")
            print()

    resolved = [(visual, target) for visual, target, _, _ in plan]
    updated_count = sum(1 for _, _, _, needs_update in plan if needs_update)

    print("=" * 80)
    print("POST-DEPLOY SUMMARY")
    print("=" * 80)
    print(f"Workspace           : {config.workspace_name}")
    print(f"Workspace Id        : {config.workspace_id}")
    print(f"RDL Visuals         : {len(rdl_visuals)}")
    print(f"Resolved            : {len(resolved)}")
    print(f"Unresolved          : {len(unresolved)}")
    print(f"Updates required    : {updated_count}")

    if resolved:
        print()
        print("Resolved relationships:")
        for visual, target in resolved:
            print(f"  - {visual.report_name} / {visual.page_name or '(unnamed page)'}")
            print(f"    -> {target.name} [{target.id}]")

    print()
    print(f"RDL Visual relationships resolved: {len(resolved)}/{len(rdl_visuals)}")
    if config.apply_rdl_visual_fix:
        print("RDL Visual report definitions updated and verified where required.")
    else:
        print("RDL Visual apply phase was disabled.")
