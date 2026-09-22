from dataclasses import dataclass
from pathlib import Path

from yaml_utils import load_yaml_mapping


REPORTS_MAPPING_PATH = Path(__file__).resolve().parent / "config" / "reports.yaml"


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
    refresh_semantic_models: bool
    wait_for_refresh: bool
    fail_on_refresh_error: bool
    refresh_poll_seconds: int
    refresh_timeout_seconds: int
    reports_mapping_path: Path


def load_config(path: str) -> PostDeployConfig:
    """Load one environment configuration from YAML."""
    config_path, data = load_yaml_mapping(path, "Post-deploy configuration")

    return PostDeployConfig(
        workspace_id=require_text(data, "workspaceId", config_path),
        workspace_name=require_text(data, "workspaceName", config_path),
        expected_oracle_database=str(data.get("expectedOracleDatabase", "")).strip(),
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
        refresh_semantic_models=data.get("refreshSemanticModels", True),
        wait_for_refresh=data.get("waitForRefresh", False),
        fail_on_refresh_error=data.get("failOnRefreshError", True),
        refresh_poll_seconds=int(data.get("refreshPollSeconds", 5)),
        refresh_timeout_seconds=int(data.get("refreshTimeoutSeconds", 1800)),
        reports_mapping_path=REPORTS_MAPPING_PATH,
    )


def require_text(data: dict, key: str, config_path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"'{key}' must be a non-empty string in configuration '{config_path}'."
        )
    return value.strip()
