import base64
import json
import re
import unicodedata

from workspace import get_report_definition, update_report_definition

_GENERIC_PAGE_WORDS = {"reporte", "report", "paginado", "paginada", "paginated"}

_CANONICAL_WORDS = {
    "aceptado": "aceptado",
    "aceptada": "aceptado",
    "aceptados": "aceptado",
    "aceptadas": "aceptado",
    "rechazado": "rechazado",
    "rechazada": "rechazado",
    "rechazados": "rechazado",
    "rechazadas": "rechazado",
    "recibido": "recibido",
    "recibida": "recibido",
    "recibidos": "recibido",
    "recibidas": "recibido",
}


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _tokens(value: str, drop_generic: bool = False):
    tokens = _plain(value).split()
    if drop_generic:
        tokens = [token for token in tokens if token not in _GENERIC_PAGE_WORDS]
    return [_CANONICAL_WORDS.get(token, token) for token in tokens]


def _strip_report_prefix(candidate_name: str, report_name: str) -> str:
    candidate_tokens = _tokens(candidate_name)
    report_tokens = _tokens(report_name)
    if candidate_tokens[: len(report_tokens)] == report_tokens:
        candidate_tokens = candidate_tokens[len(report_tokens) :]
    return " ".join(candidate_tokens)


def _folder_candidates(paginated_infos, visual):
    if not visual.report_folder_id:
        return list(paginated_infos)
    same_folder = [
        info
        for info in paginated_infos
        if info.item.folder_id == visual.report_folder_id
    ]
    return same_folder or list(paginated_infos)


def _resolve_by_page_label(candidates, visual):
    page_tokens = _tokens(visual.page_name, drop_generic=True)
    page_key = " ".join(page_tokens)
    if not page_key:
        return None

    exact = []
    for info in candidates:
        suffix = _strip_report_prefix(info.item.name, visual.report_name)
        if suffix == page_key:
            exact.append(info)
    if len(exact) == 1:
        return exact[0], "page label matches paginated report suffix"

    scored = []
    page_set = set(page_tokens)
    for info in candidates:
        suffix_tokens = _tokens(
            _strip_report_prefix(info.item.name, visual.report_name)
        )
        score = len(page_set & set(suffix_tokens))
        if score:
            scored.append((score, info))

    if scored:
        max_score = max(score for score, _ in scored)
        best = [info for score, info in scored if score == max_score]
        if len(best) == 1:
            return best[0], "page label uniquely matches paginated report"
    return None


def _resolve_by_parameters(candidates, visual):
    if not visual.parameter_names:
        return None

    exact = [
        info
        for info in candidates
        if info.parameter_names and info.parameter_names == visual.parameter_names
    ]
    if len(exact) == 1:
        return exact[0], "RDL Visual parameter mapping matches RDL parameters"

    scored = []
    for info in candidates:
        if not info.parameter_names:
            continue
        overlap = len(visual.parameter_names & info.parameter_names)
        missing = len(visual.parameter_names - info.parameter_names)
        if overlap:
            scored.append((overlap, -missing, info))

    if scored:
        best_key = max((overlap, missing_score) for overlap, missing_score, _ in scored)
        best = [
            info
            for overlap, missing_score, info in scored
            if (overlap, missing_score) == best_key
        ]
        if len(best) == 1 and best_key[0] == len(visual.parameter_names):
            return best[0], "RDL Visual parameters are contained in one RDL definition"
    return None


def _resolve_paginated(paginated_infos, visual):
    candidates = _folder_candidates(paginated_infos, visual)
    used_folder = bool(visual.report_folder_id) and len(candidates) < len(
        paginated_infos
    )

    if len(candidates) == 1:
        return candidates[0], (
            "single paginated report in the same workspace folder"
            if used_folder
            else "single paginated report in workspace"
        )

    by_page = _resolve_by_page_label(candidates, visual)
    if by_page:
        return by_page

    by_parameters = _resolve_by_parameters(candidates, visual)
    if by_parameters:
        return by_parameters

    if candidates is not paginated_infos and len(candidates) != len(paginated_infos):
        by_page = _resolve_by_page_label(paginated_infos, visual)
        if by_page:
            return by_page
        by_parameters = _resolve_by_parameters(paginated_infos, visual)
        if by_parameters:
            return by_parameters

    return None, f"{len(candidates)} candidate paginated reports"


def summarize_discovery(workspace_items, rdl_visuals, config):
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
    print(f"Total workspace items: {len(workspace_items)}")


def _print_resolution_header(index, total, visual):
    print("-" * 80)
    print(f"[{index}/{total}] Resolving RDL Visual")
    print(f"  Main report        : {visual.report_name}")
    print(f"  Main report Id     : {visual.report_id}")
    print(f"  Report folder Id   : {visual.report_folder_id or '(root)'}")
    print(f"  Page               : {visual.page_name or '(unnamed page)'}")
    print(f"  Definition part    : {visual.definition_part_path}")
    print(f"  Current itemId     : {visual.old_item_id or '(empty)'}")
    print(f"  Current workspaceId: {visual.old_workspace_id or '(empty)'}")
    print(
        "  Visual parameters  : "
        + (", ".join(sorted(visual.parameter_names)) or "(none)")
    )


def _encode_json_part(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


# def _set_literal_value(node: dict, value: str) -> None:
#     node.setdefault("expr", {}).setdefault("Literal", {})["Value"] = f"'{value}'"


def _patch_rdl_visual_part(part: dict, target_item_id: str, target_workspace_id: str):
    if part.get("payloadType") != "InlineBase64":
        raise RuntimeError(
            f"Unsupported payload type for {part.get('path')}: {part.get('payloadType')}"
        )

    raw = base64.b64decode(part.get("payload", "")).decode("utf-8-sig")
    data = json.loads(raw)
    visual = data.get("visual", {})
    if visual.get("visualType") != "rdlVisual":
        raise RuntimeError(f"Definition part is not an RDL visual: {part.get('path')}")

    try:
        objects = visual.setdefault("objects", {})
        report_info = objects.setdefault("reportInfo", [])
        if not report_info:
            report_info.append({})
        properties = report_info[0].setdefault("properties", {})

        # Replace the complete reference, not only the two literal values.
        # This mirrors the canonical ItemLocation structure produced by Power BI
        # when the user manually selects a paginated report in the visual UI.
        properties["reference"] = {
            "kind": "ItemLocation",
            "byReference": {
                "itemId": {"expr": {"Literal": {"Value": f"'{target_item_id}'"}}},
                "workspaceId": {
                    "expr": {"Literal": {"Value": f"'{target_workspace_id}'"}}
                },
            },
        }
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"Unable to create RDL visual report reference in {part.get('path')}"
        ) from exc

    part["payload"] = _encode_json_part(data)


def _read_reference_from_definition(definition_response: dict, part_path: str):
    for part in definition_response.get("definition", {}).get("parts", []):
        if part.get("path") != part_path:
            continue
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


def apply_remediation(fabric, rdl_visuals, paginated_infos, workspace_items, config):
    unresolved = []
    plan = []

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"RDL Visuals to resolve: {len(rdl_visuals)}")
    print()

    for index, visual in enumerate(rdl_visuals, start=1):
        _print_resolution_header(index, len(rdl_visuals), visual)

        candidates = _folder_candidates(paginated_infos, visual)
        print(f"  Candidate reports  : {len(candidates)}")
        for candidate in candidates:
            print(f"    - {candidate.item.name} [{candidate.item.id}]")

        paginated, reason = _resolve_paginated(paginated_infos, visual)
        if paginated is None:
            unresolved.append(visual)
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

    if unresolved and config.fail_on_unresolved_rdl_visual:
        raise RuntimeError(
            f"Unable to resolve {len(unresolved)} RDL Visual relationship(s) safely. No report definitions were updated."
        )

    print("=" * 80)
    print("RDL VISUAL APPLY")
    print("=" * 80)

    if not config.apply_rdl_visual_fix:
        print("Apply is disabled by configuration (applyRdlVisualFix=false).")
    else:
        by_report = {}
        for visual, target, reason, needs_update in plan:
            if needs_update:
                by_report.setdefault(visual.report_id, []).append((visual, target))

        for report_id, changes in by_report.items():
            report_name = changes[0][0].report_name
            print(f"[REPORT] {report_name} [{report_id}]")
            definition_response = get_report_definition(
                fabric, config.workspace_id, report_id
            )
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
                _patch_rdl_visual_part(part, target.id, config.workspace_id)

            print("  Calling Update Report Definition...")
            status_code = update_report_definition(
                fabric, config.workspace_id, report_id, definition
            )
            print(f"  UpdateDefinition   : HTTP {status_code}")

            print("  Verifying updated references...")
            verify_definition = get_report_definition(
                fabric, config.workspace_id, report_id
            )
            for visual, target in changes:
                actual_item_id, actual_workspace_id = _read_reference_from_definition(
                    verify_definition, visual.definition_part_path
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
                        f"RDL visual update verification failed for {report_name} / {visual.page_name}."
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
