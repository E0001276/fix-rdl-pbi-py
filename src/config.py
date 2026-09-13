import json
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass
class PostDeployConfig:
    workspace_id: str
    workspace_name: str
    repository_root: str
    expected_oracle_database: str
    refresh_semantic_models: bool
    wait_for_refresh: bool
    fail_on_unresolved_rdl_visual: bool


def load_config(path: str) -> PostDeployConfig:
    config_path = Path(path).expanduser().resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return PostDeployConfig(
        workspace_id=data["workspaceId"],
        workspace_name=data["workspaceName"],
        repository_root=data.get("repositoryRoot", ""),
        expected_oracle_database=data["expectedOracleDatabase"],
        refresh_semantic_models=data.get("refreshSemanticModels", True),
        wait_for_refresh=data.get("waitForRefresh", False),
        fail_on_unresolved_rdl_visual=data.get("failOnUnresolvedRdlVisual", True),
    )


def override_repository_root(config: PostDeployConfig, repository_root: str | None) -> PostDeployConfig:
    if repository_root:
        return replace(config, repository_root=repository_root)
    return config
