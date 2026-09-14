import argparse
import truststore
from pathlib import Path

try:
    truststore.inject_into_ssl()
    from auth import get_access_token
    from config import load_config
    from http_clients import ApiClient
    from remediation import apply_remediation, summarize_discovery
    from workspace import (
        discover_paginated_report_definitions,
        discover_report_definitions,
        list_fabric_workspace_items,
    )
except ImportError:

    from auth import get_access_token
    from config import load_config
    from http_clients import ApiClient
    from remediation import apply_remediation, summarize_discovery
    from workspace import (
        discover_paginated_report_definitions,
        discover_report_definitions,
        list_fabric_workspace_items,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Power BI target-only workspace remediation"
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "postdeploy-beta.json"),
        help="Path to the environment configuration JSON.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    print("=" * 80)
    print("POWER BI POST-DEPLOY")
    print("=" * 80)

    print(f"[WORKSPACE] Name : {config.workspace_name}")
    print(f"[WORKSPACE] Id   : {config.workspace_id}")
    print()
    fabric_token = get_access_token("https://api.fabric.microsoft.com")
    fabric = ApiClient("https://api.fabric.microsoft.com/v1", fabric_token)

    workspace_items = list_fabric_workspace_items(fabric, config.workspace_id)
    print(f"  Reports           : {len(workspace_items.reports)}")
    print(f"  Semantic Models   : {len(workspace_items.semantic_models)}")
    print(f"  Paginated Reports : {len(workspace_items.paginated_reports)}")
    print()
    rdl_visuals = discover_report_definitions(
        fabric, config.workspace_id, workspace_items
    )
    paginated_infos = discover_paginated_report_definitions(
        fabric, config.workspace_id, workspace_items
    )

    summarize_discovery(workspace_items, rdl_visuals, config)
    apply_remediation(rdl_visuals, paginated_infos, workspace_items, config)


if __name__ == "__main__":
    main()
