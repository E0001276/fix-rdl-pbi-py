import os
from dataclasses import dataclass
from pathlib import Path

from yaml_utils import load_yaml_mapping


@dataclass(frozen=True)
class FabricGitAutomationConfig:
    enabled: bool
    connection_id: str
    lro_timeout_seconds: int
    commit_message: str
    allow_override_items: bool
    require_clean_workspace_before_update: bool


def load_fabric_git_config(
    path: str,
    connection_id_override: str = "",
) -> FabricGitAutomationConfig:
    """Load optional Fabric Git automation settings from the environment YAML.

    The existing post-deploy configuration remains untouched. The optional
    ``gitAutomation`` section is consumed only by ``deploy.py``.

    Connection ID precedence:
      1. --git-connection-id CLI override
      2. FABRIC_GIT_CONNECTION_ID environment variable
      3. gitAutomation.connectionId in YAML
    """
    config_path, data = load_yaml_mapping(path, "Post-deploy configuration")
    section = data.get("gitAutomation", {})
    if section is None:
        section = {}
    if not isinstance(section, dict):
        raise ValueError(
            f"'gitAutomation' must be a mapping in configuration '{config_path}'."
        )

    override = str(connection_id_override or "").strip()
    env_value = os.getenv("FABRIC_GIT_CONNECTION_ID", "").strip()
    yaml_value = str(section.get("connectionId", "")).strip()

    return FabricGitAutomationConfig(
        enabled=bool(section.get("enabled", True)),
        connection_id=override or env_value or yaml_value,
        lro_timeout_seconds=max(30, int(section.get("lroTimeoutSeconds", 1800))),
        commit_message=str(
            section.get(
                "commitMessage",
                "chore(fabric): apply Power BI post-deploy fixes",
            )
        ).strip()
        or "chore(fabric): apply Power BI post-deploy fixes",
        allow_override_items=bool(section.get("allowOverrideItems", True)),
        require_clean_workspace_before_update=bool(
            section.get("requireCleanWorkspaceBeforeUpdate", True)
        ),
    )
