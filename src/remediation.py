import re
import unicodedata


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
        suffix_tokens = _tokens(_strip_report_prefix(info.item.name, visual.report_name))
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
    used_folder = bool(visual.report_folder_id) and len(candidates) < len(paginated_infos)

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

    # If folder context was too broad or missing, try the entire workspace using
    # strong signals only. This is useful when all Power BI items live at root.
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

    print("Workspace discovery:")
    print(f"  Reports: {counts['Report']}")
    print(f"  Semantic Models: {counts['SemanticModel']}")
    print(f"  Paginated Reports: {counts['PaginatedReport']}")
    print(f"  RDL Visuals: {len(rdl_visuals)}")
    print()
    print(f"Target workspace: {config.workspace_name} ({config.workspace_id})")
    print(f"Workspace items discovered: {len(workspace_items)}")
    print()


def apply_remediation(rdl_visuals, paginated_infos, workspace_items, config):
    # Target-only: all discovery and relationship resolution comes from the
    # target workspace. No repository folder and no source workspace are read.
    unresolved = []
    resolved = []

    for visual in rdl_visuals:
        paginated, reason = _resolve_paginated(paginated_infos, visual)
        if paginated is None:
            unresolved.append(visual)
            print(
                f"[UNRESOLVED] {visual.report_name} / {visual.page_name} ({reason})"
            )
            continue

        resolved.append((visual, paginated.item))
        print(
            f"[RESOLVED] {visual.report_name} / {visual.page_name} -> "
            f"{paginated.item.name} [{paginated.item.id}] ({reason})"
        )

    print()
    print(f"RDL Visual relationships resolved: {len(resolved)}/{len(rdl_visuals)}")

    if unresolved and config.fail_on_unresolved_rdl_visual:
        raise RuntimeError(
            f"Unable to resolve {len(unresolved)} RDL Visual relationship(s) safely."
        )

    print("Workspace-only discovery and safety checks completed.")
