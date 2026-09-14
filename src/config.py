import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PostDeployConfig:
    workspace_id: str
    workspace_name: str
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
        expected_oracle_database=data.get("expectedOracleDatabase", ""),
        refresh_semantic_models=data.get("refreshSemanticModels", True),
        wait_for_refresh=data.get("waitForRefresh", False),
        fail_on_unresolved_rdl_visual=data.get("failOnUnresolvedRdlVisual", True),
    )
