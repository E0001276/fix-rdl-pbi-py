import argparse
from pathlib import Path

from auth import get_access_token
from config import load_config, override_repository_root
from http_clients import ApiClient
from repository import discover_repository
from remediation import apply_remediation, summarize_discovery
from workspace import list_powerbi_workspace_items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Power BI target-only post-deploy remediation"
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "postdeploy-beta.json"),
        help="Path to the environment configuration JSON.",
    )
    parser.add_argument(
        "--repository-root",
        help=(
            "Optional path to the Power BI report source folder. "
            "Overrides repositoryRoot from the JSON configuration."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = override_repository_root(load_config(args.config), args.repository_root)

    if not config.repository_root:
        raise ValueError(
            "repositoryRoot is empty. Set it in the JSON config or pass --repository-root."
        )

    repo_items, rdl_visuals = discover_repository(config.repository_root)

    token = get_access_token("https://analysis.windows.net/powerbi/api")
    pbi = ApiClient("https://api.powerbi.com/v1.0/myorg", token)
    workspace_items = list_powerbi_workspace_items(pbi, config.workspace_id)

    summarize_discovery(repo_items, rdl_visuals, workspace_items, config)
    apply_remediation(repo_items, rdl_visuals, workspace_items, config)


if __name__ == "__main__":
    main()
