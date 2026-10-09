from dataclasses import dataclass

from paginated import resolve_semantic_models_for_rdl
from paginated_mapping import normalize_mapping_name
from workspace import WorkspaceItems


@dataclass(frozen=True)
class ScopeItemStatus:
    item_type: str
    name: str
    status: str


@dataclass
class RemediationScope:
    rdl_visuals: list
    paginated_infos: list
    semantic_model_items: WorkspaceItems
    statuses: list[ScopeItemStatus]
    configured_report_names: set[str]
    configured_paginated_report_names: set[str]


def _group_by_normalized_name(items):
    grouped = {}
    for item in items:
        grouped.setdefault(normalize_mapping_name(item.name), []).append(item)
    return grouped


def _configured_report_names(mapping) -> set[str]:
    return {
        normalize_mapping_name(relation.report)
        for relation in mapping.relations
    }


def _configured_paginated_report_names(mapping) -> set[str]:
    return {
        normalize_mapping_name(relation.paginated_report)
        for relation in mapping.relations
    }


def build_remediation_scope(workspace_items, rdl_visuals, paginated_infos, mapping):
    """Build the post-discovery remediation scope from reports mapping.

    Workspace discovery remains complete.  This scope is applied only after all
    Reports, Semantic Models, Paginated Reports and their definitions have been
    discovered.  Main reports and paginated reports are selected explicitly by
    the configured mapping.  Semantic Models are selected only when they are a
    dependency of a selected item.
    """
    configured_reports = _configured_report_names(mapping)
    configured_paginated = _configured_paginated_report_names(mapping)

    workspace_reports = _group_by_normalized_name(workspace_items.reports)
    workspace_paginated = _group_by_normalized_name(workspace_items.paginated_reports)

    statuses = []

    for name in sorted(configured_reports):
        matches = workspace_reports.get(name, [])
        if not matches:
            status = "NOT FOUND IN WORKSPACE"
        elif len(matches) > 1:
            status = "AMBIGUOUS IN WORKSPACE"
        else:
            status = "MATCHED"
        statuses.append(ScopeItemStatus("Report", name, status))

    for name in sorted(workspace_reports):
        if name not in configured_reports:
            for item in workspace_reports[name]:
                statuses.append(
                    ScopeItemStatus(
                        "Report",
                        item.name,
                        "NOT FOUND IN CONFIGURATION FILE",
                    )
                )

    for name in sorted(configured_paginated):
        matches = workspace_paginated.get(name, [])
        if not matches:
            status = "NOT FOUND IN WORKSPACE"
        elif len(matches) > 1:
            status = "AMBIGUOUS IN WORKSPACE"
        else:
            status = "MATCHED"
        statuses.append(ScopeItemStatus("Paginated Report", name, status))

    for name in sorted(workspace_paginated):
        if name not in configured_paginated:
            for item in workspace_paginated[name]:
                statuses.append(
                    ScopeItemStatus(
                        "Paginated Report",
                        item.name,
                        "NOT FOUND IN CONFIGURATION FILE",
                    )
                )

    selected_rdl_visuals = [
        visual
        for visual in rdl_visuals
        if normalize_mapping_name(visual.report_name) in configured_reports
        and len(workspace_reports.get(normalize_mapping_name(visual.report_name), [])) == 1
    ]

    selected_paginated_infos = [
        info
        for info in paginated_infos
        if normalize_mapping_name(info.item.name) in configured_paginated
        and len(workspace_paginated.get(normalize_mapping_name(info.item.name), [])) == 1
    ]

    semantic_model_ids = set()

    # A configured main report normally shares its display name with its model.
    # Select such a model only when the configured report itself exists uniquely.
    semantic_models_by_name = _group_by_normalized_name(workspace_items.semantic_models)
    for report_name in configured_reports:
        if len(workspace_reports.get(report_name, [])) != 1:
            continue
        model_matches = semantic_models_by_name.get(report_name, [])
        if len(model_matches) == 1:
            semantic_model_ids.add(model_matches[0].id)

    # Also include every model resolved as a datasource dependency of a selected
    # paginated report.  Resolution uses the existing proven RDL logic.
    for info in selected_paginated_infos:
        resolved, _failures = resolve_semantic_models_for_rdl(
            workspace_items,
            info.item,
            info.datasource_names,
        )
        for model, _reason in resolved.values():
            semantic_model_ids.add(model.id)

    semantic_model_items = WorkspaceItems(
        item
        for item in workspace_items.semantic_models
        if item.id in semantic_model_ids
    )

    return RemediationScope(
        rdl_visuals=selected_rdl_visuals,
        paginated_infos=selected_paginated_infos,
        semantic_model_items=semantic_model_items,
        statuses=statuses,
        configured_report_names=configured_reports,
        configured_paginated_report_names=configured_paginated,
    )


def print_scope_summary(scope, title: str) -> None:
    print("=" * 80)
    print(title)
    print("=" * 80)

    report_statuses = [s for s in scope.statuses if s.item_type == "Report"]
    paginated_statuses = [
        s for s in scope.statuses if s.item_type == "Paginated Report"
    ]

    print("Reports")
    for status in report_statuses:
        print(f"- {status.name}: {status.status}")

    print()
    print("Paginated Reports")
    for status in paginated_statuses:
        print(f"- {status.name}: {status.status}")

    print()
    print("Selected remediation scope")
    print(f"- RDL Visuals          : {len(scope.rdl_visuals)}")
    print(f"- Paginated Reports    : {len(scope.paginated_infos)}")
    print(f"- Semantic Models      : {len(scope.semantic_model_items.semantic_models)}")
