import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PostDeployConfig:
    workspace_id: str
    workspace_name: str
    expected_oracle_database: str
    fail_on_unresolved_rdl_visual: bool
    apply_rdl_visual_fix: bool
    apply_paginated_report_fix: bool
    fail_on_unresolved_paginated_report: bool
    bind_semantic_models_to_connection: bool
    fail_on_unresolved_connection_binding: bool
    bind_paginated_reports_to_semantic_models: bool
    fail_on_unresolved_paginated_datasource_binding: bool
    recreate_paginated_on_definition_mismatch: bool


def load_config(path: str) -> PostDeployConfig:
    config_path = Path(path).expanduser().resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return PostDeployConfig(
        workspace_id=data["workspaceId"],
        workspace_name=data["workspaceName"],
        expected_oracle_database=data.get("expectedOracleDatabase", ""),
        fail_on_unresolved_rdl_visual=data.get("failOnUnresolvedRdlVisual", True),
        apply_rdl_visual_fix=data.get("applyRdlVisualFix", True),
        apply_paginated_report_fix=data.get("applyPaginatedReportFix", True),
        fail_on_unresolved_paginated_report=data.get(
            "failOnUnresolvedPaginatedReport", True
        ),
        bind_semantic_models_to_connection=data.get(
            "bindSemanticModelsToConnection",
            data.get("bindSemanticModelsToGateway", True),
        ),
        fail_on_unresolved_connection_binding=data.get(
            "failOnUnresolvedConnectionBinding",
            data.get("failOnUnresolvedGatewayBinding", True),
        ),
        bind_paginated_reports_to_semantic_models=data.get(
            "bindPaginatedReportsToSemanticModels", True
        ),
        fail_on_unresolved_paginated_datasource_binding=data.get(
            "failOnUnresolvedPaginatedDatasourceBinding", True
        ),
        recreate_paginated_on_definition_mismatch=data.get(
            "recreatePaginatedOnDefinitionMismatch", True
        ),
    )
