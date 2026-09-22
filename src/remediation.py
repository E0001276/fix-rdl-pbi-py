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



def _folder_candidates(paginated_infos, visual):
    if not visual.report_folder_id:
        return list(paginated_infos)
    same_folder = [
        info
        for info in paginated_infos
        if info.item.folder_id == visual.report_folder_id
    ]
    return same_folder or list(paginated_infos)


def _list_paginated_reports_in_workspace(fabric, workspace_id: str):
    """Return paginated report metadata from any accessible workspace.

    The RDL Visual already stores the original workspaceId + itemId.  We use
    that real reference first instead of guessing the destination from the
    page name.
    """
    reports = []
    path = f"workspaces/{workspace_id}/paginatedReports"
    next_url = path

    while next_url:
        response = fabric.get(next_url)
        data = response.json()
        reports.extend(data.get("value", []))

        next_url = data.get("continuationUri")
        if not next_url:
            token = data.get("continuationToken")
            next_url = f"{path}?continuationToken={token}" if token else None

    return reports


def _source_workspace_catalog(fabric, workspace_id: str, cache: dict):
    """Load and cache paginated reports from an accessible workspace.

    Cache entries contain either the workspace catalog or the access/error text
    so multiple visuals never repeat the same API call.
    """
    key = f"workspace:{workspace_id}"
    if key in cache:
        return cache[key]

    try:
        reports = _list_paginated_reports_in_workspace(fabric, workspace_id)
        entry = {"reports": reports, "error": ""}
    except Exception as exc:
        entry = {"reports": [], "error": str(exc)}

    cache[key] = entry
    return entry


def _list_accessible_workspaces(fabric, cache: dict):
    """Return every Fabric workspace visible to the execution identity.

    This is used only when a report reference is hybrid: workspaceId already
    points to the target workspace but itemId still belongs to an older
    workspace.  Results are cached for the complete remediation run.
    """
    key = "accessible_workspaces"
    if key in cache:
        return cache[key]

    workspaces = []
    path = "workspaces"
    next_url = path

    try:
        while next_url:
            response = fabric.get(next_url)
            data = response.json()
            workspaces.extend(data.get("value", []))

            next_url = data.get("continuationUri")
            if not next_url:
                token = data.get("continuationToken")
                next_url = f"{path}?continuationToken={token}" if token else None

        entry = {"workspaces": workspaces, "error": ""}
    except Exception as exc:
        entry = {"workspaces": [], "error": str(exc)}

    cache[key] = entry
    return entry


def _workspace_display_name(workspace: dict) -> str:
    return str(
        workspace.get("displayName")
        or workspace.get("name")
        or workspace.get("id")
        or ""
    ).strip()


def _global_historical_item_lookup(
    fabric,
    historical_item_id: str,
    target_workspace_id: str,
    cache: dict,
):
    """Find a historical paginated-report itemId across accessible workspaces.

    Power BI/Fabric Git transformations can produce a hybrid reference where
    workspaceId has already been changed to the target workspace while itemId
    still belongs to the previous workspace.  In that state the original
    workspaceId has been lost, but the historical itemId remains authoritative.

    The function searches the paginated-report catalogs of all workspaces that
    the execution identity can read.  It never uses a page label or report-name
    heuristic to identify the source artifact.
    """
    lookup_key = f"historical_item:{historical_item_id}"
    if lookup_key in cache:
        return cache[lookup_key]

    workspace_entry = _list_accessible_workspaces(fabric, cache)
    if workspace_entry["error"]:
        result = {
            "matches": [],
            "errors": [],
            "error": "unable to list accessible workspaces: "
            + workspace_entry["error"],
        }
        cache[lookup_key] = result
        return result

    matches = []
    errors = []

    for workspace in workspace_entry["workspaces"]:
        workspace_id = str(workspace.get("id") or "").strip()
        if not workspace_id or workspace_id == target_workspace_id:
            continue

        catalog = _source_workspace_catalog(fabric, workspace_id, cache)
        if catalog["error"]:
            errors.append(
                {
                    "workspaceId": workspace_id,
                    "workspaceName": _workspace_display_name(workspace),
                    "error": catalog["error"],
                }
            )
            continue

        for report in catalog["reports"]:
            if str(report.get("id") or "").strip() != historical_item_id:
                continue

            matches.append(
                {
                    "workspaceId": workspace_id,
                    "workspaceName": _workspace_display_name(workspace),
                    "report": report,
                }
            )

    result = {"matches": matches, "errors": errors, "error": ""}
    cache[lookup_key] = result
    return result


def _match_source_report_name_in_target(paginated_infos, source_name: str):
    target_matches = [
        info
        for info in paginated_infos
        if info.item.name.strip().casefold() == source_name.strip().casefold()
    ]
    if len(target_matches) == 1:
        return target_matches[0]
    return None


def _resolve_historical_item_globally(
    fabric,
    paginated_infos,
    visual,
    target_workspace_id: str,
    source_cache: dict,
):
    """Resolve a stale itemId when its original workspaceId is no longer present."""
    if not visual.old_item_id:
        return None, "visual does not contain an itemId to search globally"

    result = _global_historical_item_lookup(
        fabric,
        visual.old_item_id,
        target_workspace_id,
        source_cache,
    )
    if result["error"]:
        return None, result["error"]

    matches = result["matches"]
    if len(matches) == 0:
        detail = "historical itemId was not found in any accessible non-target workspace"
        if result["errors"]:
            detail += f"; {len(result['errors'])} workspace catalog(s) could not be read"
        return None, detail

    if len(matches) != 1:
        locations = ", ".join(
            f"{match['workspaceName']} [{match['workspaceId']}]"
            for match in matches
        )
        return (
            None,
            f"historical itemId matched {len(matches)} paginated reports across accessible workspaces: {locations}",
        )

    source = matches[0]
    source_report = source["report"]
    source_name = str(
        source_report.get("displayName")
        or source_report.get("name")
        or ""
    ).strip()
    if not source_name:
        return None, "historical itemId was found but source displayName is empty"

    target = _match_source_report_name_in_target(paginated_infos, source_name)
    if target is None:
        exact_count = sum(
            1
            for info in paginated_infos
            if info.item.name.strip().casefold() == source_name.casefold()
        )
        return (
            None,
            f"historical itemId resolves to '{source_name}' in "
            f"{source['workspaceName']} [{source['workspaceId']}], but target has "
            f"{exact_count} exact displayName matches",
        )

    reason = (
        "historical itemId found by global workspace search: "
        f"{source['workspaceName']} [{source['workspaceId']}] / "
        f"'{source_name}' -> exact target displayName"
    )
    return target, reason


def _resolve_by_existing_reference(
    fabric, paginated_infos, visual, target_workspace_id: str, source_cache: dict
):
    """Resolve a target paginated report from persisted artifact identity.

    Resolution order:
      1. Target workspaceId + target itemId already identify the item.
      2. Different workspaceId: source workspace itemId -> source displayName ->
         exact target displayName.
      3. Hybrid reference (target workspaceId + stale itemId): search the stale
         itemId across all accessible workspaces, then map the discovered source
         displayName exactly to the target workspace.

    Page names are never used by this function.
    """
    if not visual.old_item_id or not visual.old_workspace_id:
        return None, "visual does not contain a complete workspaceId + itemId reference"

    target_by_id = [
        info for info in paginated_infos if info.item.id == visual.old_item_id
    ]

    if visual.old_workspace_id == target_workspace_id:
        if len(target_by_id) == 1:
            return (
                target_by_id[0],
                "current workspaceId + itemId directly identify target paginated report",
            ), ""

        # Hybrid references are common after Git/environment transformations:
        # workspaceId already points to target while itemId is stale.  Do not
        # scan every accessible workspace yet.  The caller first attempts the
        # target-only resolver using current folder/parameter/family metadata;
        # global historical lookup remains available as a final fallback.
        return (
            None,
            "itemId was not found in the current target workspace",
        )

    source_entry = _source_workspace_catalog(
        fabric, visual.old_workspace_id, source_cache
    )
    if source_entry["error"]:
        # The original workspace may have been deleted or may no longer be
        # readable.  Try the historical itemId globally before giving up.
        globally_resolved, global_note = _resolve_historical_item_globally(
            fabric,
            paginated_infos,
            visual,
            target_workspace_id,
            source_cache,
        )
        if globally_resolved:
            return (globally_resolved, global_note), ""
        return (
            None,
            "source workspace could not be queried: "
            + source_entry["error"]
            + "; global historical search: "
            + global_note,
        )

    source_matches = [
        report
        for report in source_entry["reports"]
        if str(report.get("id") or "") == visual.old_item_id
    ]
    if len(source_matches) != 1:
        globally_resolved, global_note = _resolve_historical_item_globally(
            fabric,
            paginated_infos,
            visual,
            target_workspace_id,
            source_cache,
        )
        if globally_resolved:
            return (globally_resolved, global_note), ""
        return (
            None,
            f"source itemId matched {len(source_matches)} paginated reports in referenced workspace; "
            f"global historical search: {global_note}",
        )

    source_report = source_matches[0]
    source_name = str(
        source_report.get("displayName")
        or source_report.get("name")
        or ""
    ).strip()
    if not source_name:
        return None, "source itemId was found but its displayName is empty"

    target = _match_source_report_name_in_target(paginated_infos, source_name)
    if target is not None:
        return (
            target,
            f"source workspace itemId resolves to '{source_name}' and target displayName matches exactly",
        ), ""

    exact_count = sum(
        1
        for info in paginated_infos
        if info.item.name.strip().casefold() == source_name.casefold()
    )
    return (
        None,
        f"source itemId resolves to '{source_name}', but target workspace has {exact_count} exact displayName matches",
    )




def _multiset_remove_prefix(candidate_tokens, prefix_tokens):
    """Remove an exact logical report-name prefix from candidate tokens."""
    if candidate_tokens[: len(prefix_tokens)] == prefix_tokens:
        return candidate_tokens[len(prefix_tokens) :]
    return candidate_tokens


def _target_workspace_discovery(paginated_infos, visual):
    """Resolve an RDL Visual using only artifacts present in the target workspace.

    This is the fallback for stale/deleted itemIds.  It deliberately does not
    depend on preconfigured GUID mappings or on another workspace being
    accessible.  Discovery uses the target folder, the main report's logical
    family, the RDL Visual parameter contract, and finally a deterministic
    variant token match between the Power BI page and the paginated report
    names that actually exist in the target workspace.

    The resolver only returns a result when the candidate is unique.  Ambiguous
    cases remain unresolved so failOnUnresolvedRdlVisual can stop the deploy.
    """
    candidates = _folder_candidates(paginated_infos, visual)
    steps = []

    if visual.report_folder_id:
        same_folder_count = sum(
            1 for info in paginated_infos
            if info.item.folder_id == visual.report_folder_id
        )
        if same_folder_count:
            steps.append(f"same-folder candidates={len(candidates)}")

    # 1) Parameter contract is strong target-only metadata.  Narrow only when
    #    at least one exact match exists; otherwise keep the current candidate set.
    if visual.parameter_names:
        exact_params = [
            info for info in candidates
            if info.parameter_names == visual.parameter_names
        ]
        if len(exact_params) == 1:
            return (
                exact_params[0],
                "target workspace discovery: exact RDL Visual/RDL parameter contract",
            )
        if len(exact_params) > 1:
            candidates = exact_params
            steps.append(f"exact-parameter candidates={len(candidates)}")

    # 2) Discover the report family from names that exist in this workspace.
    #    Example:
    #      main report: Trans Uso de Garantía por 43BIS
    #      candidates : Trans Uso de Garantía por 43BIS_Aceptado / ...
    main_tokens = _tokens(visual.report_name)
    family = []
    for info in candidates:
        candidate_tokens = _tokens(info.item.name)
        if candidate_tokens[: len(main_tokens)] == main_tokens:
            family.append(info)
        elif main_tokens and set(main_tokens).issubset(set(candidate_tokens)):
            family.append(info)

    if len(family) == 1:
        return (
            family[0],
            "target workspace discovery: main-report family uniquely identifies paginated report",
        )
    if len(family) > 1:
        candidates = family
        steps.append(f"main-report-family candidates={len(candidates)}")

    # 3) Derive the visual variant from workspace metadata.  Generic page words
    #    such as Report/Reporte/Paginado are ignored, and grammatical variants
    #    (Aceptados/Aceptada, etc.) are canonicalized by _tokens().
    page_tokens = _tokens(visual.page_name, drop_generic=True)
    main_set = set(main_tokens)
    stop_words = {"de", "del", "la", "el", "los", "las", "por", "para", "y"}
    page_variant = [
        token for token in page_tokens
        if token not in main_set and token not in stop_words
    ]

    if page_variant:
        exact_variant = []
        subset_variant = []
        page_variant_set = set(page_variant)

        for info in candidates:
            candidate_tokens = _tokens(info.item.name)
            suffix_tokens = _multiset_remove_prefix(candidate_tokens, main_tokens)
            suffix_tokens = [t for t in suffix_tokens if t not in stop_words]

            if suffix_tokens == page_variant:
                exact_variant.append(info)
            elif page_variant_set.issubset(set(suffix_tokens)):
                subset_variant.append(info)

        if len(exact_variant) == 1:
            return (
                exact_variant[0],
                "target workspace discovery: unique logical variant match inside report family",
            )
        if len(subset_variant) == 1:
            return (
                subset_variant[0],
                "target workspace discovery: unique page-variant token match inside report family",
            )
        if exact_variant:
            steps.append(f"exact-variant candidates={len(exact_variant)}")
        elif subset_variant:
            steps.append(f"variant candidates={len(subset_variant)}")

    # 4) Last target-only discriminator: token evidence from both the main
    #    report and page against candidates in the same target folder.  Resolve
    #    only when a single candidate has a strictly better score and the page
    #    contributes at least one non-generic token to that score.
    evidence = set(main_tokens) | set(page_variant)
    page_evidence = set(page_variant)
    scored = []
    for info in candidates:
        ct = set(_tokens(info.item.name))
        total = len(evidence & ct)
        page_score = len(page_evidence & ct)
        family_score = len(set(main_tokens) & ct)
        scored.append((total, page_score, family_score, info))

    if scored:
        scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        best = scored[0]
        runner = scored[1] if len(scored) > 1 else None
        best_key = best[:3]
        runner_key = runner[:3] if runner else (-1, -1, -1)
        if best[1] > 0 and best_key > runner_key:
            return (
                best[3],
                "target workspace discovery: unique highest logical token score "
                f"(score={best_key}, runner={runner_key})",
            )

    detail = ", ".join(steps) if steps else "no narrowing metadata"
    return None, (
        f"target workspace discovery remained ambiguous among {len(candidates)} candidate(s); {detail}"
    )


def _resolve_paginated(
    fabric, paginated_infos, visual, target_workspace_id: str, source_cache: dict
):
    # 1) Use persisted identity first.  For a real source workspace reference,
    # this still resolves source itemId -> exact source displayName -> target.
    # For a hybrid target-workspace + stale-itemId reference, the resolver now
    # defers the expensive global scan until after target-only discovery.
    by_reference, reference_note = _resolve_by_existing_reference(
        fabric,
        paginated_infos,
        visual,
        target_workspace_id,
        source_cache,
    )
    if by_reference:
        return by_reference

    # 2) Resolve deleted/recreated itemIds using only current target artifacts.
    discovered, discovery_note = _target_workspace_discovery(
        paginated_infos, visual
    )
    if discovered:
        return discovered, discovery_note

    # 3) Preserve the historical global-search safety net for the specific
    # hybrid case.  It is now a fallback, not the first action, which avoids
    # walking every accessible workspace when target-only evidence is unique.
    global_note = ""
    if (
        visual.old_workspace_id == target_workspace_id
        and visual.old_item_id
    ):
        historical, global_note = _resolve_historical_item_globally(
            fabric,
            paginated_infos,
            visual,
            target_workspace_id,
            source_cache,
        )
        if historical:
            return historical, global_note

    reason = discovery_note
    if reference_note:
        reason += f"; persisted reference resolution: {reference_note}"
    if global_note:
        reason += f"; historical fallback: {global_note}"
    return None, reason


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


def _patch_legacy_rdl_visual_part(
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
            part["payload"] = _encode_json_part(data)
            return

    raise RuntimeError(
        "Unable to locate legacy RDL visual in "
        f"{part.get('path')} / {visual_locator.page_name}."
    )


def _read_legacy_reference(part: dict, visual_locator):
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
                item_id = properties["reportId"]["expr"]["Literal"]["Value"].strip(
                    "'"
                )
                workspace_id = properties["workspaceId"]["expr"]["Literal"][
                    "Value"
                ].strip("'")
                return item_id, workspace_id
            except (KeyError, IndexError, TypeError, AttributeError):
                return "", ""

    return "", ""


def _read_reference_from_definition(definition_response: dict, visual_locator):
    for part in definition_response.get("definition", {}).get("parts", []):
        if part.get("path") != visual_locator.definition_part_path:
            continue
        if visual_locator.definition_format == "LegacyReportJson":
            return _read_legacy_reference(part, visual_locator)
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
    workspace_items,
    config,
    report_definition_cache: dict | None = None,
):
    unresolved = []
    plan = []
    source_workspace_cache = {}

    print(f"Workspace: {config.workspace_name} [{config.workspace_id}]")
    print(f"RDL Visuals to resolve: {len(rdl_visuals)}")
    print()

    for index, visual in enumerate(rdl_visuals, start=1):
        _print_resolution_header(index, len(rdl_visuals), visual)

        candidates = _folder_candidates(paginated_infos, visual)
        print(f"  Candidate reports  : {len(candidates)}")
        for candidate in candidates:
            print(f"    - {candidate.item.name} [{candidate.item.id}]")

        paginated, reason = _resolve_paginated(
            fabric,
            paginated_infos,
            visual,
            config.workspace_id,
            source_workspace_cache,
        )
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
                    _patch_legacy_rdl_visual_part(
                        part, visual, target.id, config.workspace_id
                    )
                else:
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
            if report_definition_cache is not None:
                report_definition_cache[report_id] = verify_definition
            for visual, target in changes:
                actual_item_id, actual_workspace_id = _read_reference_from_definition(
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
