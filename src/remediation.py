import re
import unicodedata


_GENERIC_PAGE_WORDS = {"reporte", "report", "paginado", "paginada", "paginated"}

# Canonicalize the business labels currently used by the reports. This deliberately
# handles gender and number differences without hard-coding report/visual paths.
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


def _repo_paginated_siblings(repo_items, visual):
    return [
        item
        for item in repo_items
        if item.kind == "PaginatedReport" and item.path.parent == visual.report_path.parent
    ]


def _resolve_repo_paginated(repo_items, visual):
    siblings = _repo_paginated_siblings(repo_items, visual)
    if not siblings:
        return None, "no sibling paginated reports"

    if len(siblings) == 1:
        return siblings[0], "single sibling paginated report"

    page_tokens = _tokens(visual.page_name, drop_generic=True)
    page_key = " ".join(page_tokens)

    if page_key:
        exact = []
        for candidate in siblings:
            suffix = _strip_report_prefix(candidate.display_name, visual.report_name)
            if suffix == page_key:
                exact.append(candidate)
        if len(exact) == 1:
            return exact[0], "page label matches sibling report suffix"

        scored = []
        page_set = set(page_tokens)
        for candidate in siblings:
            suffix_tokens = _tokens(
                _strip_report_prefix(candidate.display_name, visual.report_name)
            )
            candidate_set = set(suffix_tokens)
            score = len(page_set & candidate_set)
            if score:
                scored.append((score, candidate))

        if scored:
            max_score = max(score for score, _ in scored)
            best = [candidate for score, candidate in scored if score == max_score]
            if len(best) == 1:
                return best[0], "page label uniquely matches sibling report"

    return None, f"{len(siblings)} sibling candidates"


def _workspace_paginated_by_name(workspace_items, display_name):
    target = _plain(display_name)
    matches = [
        item
        for item in workspace_items
        if item.kind == "PaginatedReport" and _plain(item.name) == target
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def summarize_discovery(repo_items, rdl_visuals, workspace_items, config):
    counts = {"Report": 0, "SemanticModel": 0, "PaginatedReport": 0}
    for item in repo_items:
        counts[item.kind] += 1

    print("Repository discovery:")
    print(f"  Reports: {counts['Report']}")
    print(f"  Semantic Models: {counts['SemanticModel']}")
    print(f"  Paginated Reports: {counts['PaginatedReport']}")
    print(f"  RDL Visuals: {len(rdl_visuals)}")
    print()
    print(f"Target workspace: {config.workspace_name} ({config.workspace_id})")
    print(f"Workspace items discovered: {len(workspace_items)}")
    print()


def apply_remediation(repo_items, rdl_visuals, workspace_items, config):
    # Target-only: never query or compare a DEV workspace.
    unresolved = []
    resolved = []

    for visual in rdl_visuals:
        repo_paginated, reason = _resolve_repo_paginated(repo_items, visual)
        if repo_paginated is None:
            unresolved.append(visual)
            print(
                f"[UNRESOLVED] {visual.report_name} / {visual.page_name} ({reason})"
            )
            continue

        workspace_paginated = _workspace_paginated_by_name(
            workspace_items, repo_paginated.display_name
        )
        if workspace_paginated is None:
            unresolved.append(visual)
            print(
                f"[UNRESOLVED] {visual.report_name} / {visual.page_name} -> "
                f"{repo_paginated.display_name} (not uniquely found in ws-beta)"
            )
            continue

        resolved.append((visual, workspace_paginated))
        print(
            f"[RESOLVED] {visual.report_name} / {visual.page_name} -> "
            f"{workspace_paginated.name} [{workspace_paginated.id}] ({reason})"
        )

    print()
    print(f"RDL Visual relationships resolved: {len(resolved)}/{len(rdl_visuals)}")

    if unresolved and config.fail_on_unresolved_rdl_visual:
        raise RuntimeError(
            f"Unable to resolve {len(unresolved)} RDL Visual relationship(s) safely."
        )

    print("Post-deploy discovery and safety checks completed.")
