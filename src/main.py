import argparse
from pathlib import Path

import truststore

truststore.inject_into_ssl()

from auth import get_access_token
from config import load_config
from fabric_connections import bind_semantic_models_to_connections
from http_clients import ApiClient
from paginated import remediate_paginated_reports
from remediation import apply_remediation, summarize_discovery
from workspace import (
    discover_paginated_report_definitions,
    discover_report_definitions,
    list_fabric_workspace_items,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Microsoft Fabric target-only workspace remediation"
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "postdeploy-alpha-cicd.json"),
        help="Path to the environment configuration JSON.",
    )
    return parser


def _section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)

    _section("POWER BI / MICROSOFT FABRIC POST-DEPLOY")
    print(f"[CONFIG] File       : {Path(args.config).resolve()}")
    print(f"[WORKSPACE] Name    : {config.workspace_name}")
    print(f"[WORKSPACE] Id      : {config.workspace_id}")
    print(
        f"[WORKSPACE] Database: "
        f"{config.expected_oracle_database or '(not configured)'}"
    )

    _section("AUTHENTICATION")
    print("[AUTH] API family   : Microsoft Fabric REST API v1")
    print("[AUTH] Base URL     : https://api.fabric.microsoft.com/v1")
    print("[AUTH] Requesting Fabric access token...")
    fabric_token = get_access_token("https://api.fabric.microsoft.com")
    print("[AUTH] Fabric access token acquired successfully.")
    fabric = ApiClient("https://api.fabric.microsoft.com/v1", fabric_token)
    print("[AUTH] Fabric API client initialized.")
    print("[AUTH] Power BI REST API token is NOT requested by this version.")

    _section("WORKSPACE DISCOVERY")
    print(
        f"[DISCOVERY] Reading items from workspace "
        f"'{config.workspace_name}' [{config.workspace_id}]..."
    )
    workspace_items = list_fabric_workspace_items(fabric, config.workspace_id)

    print()
    print("[DISCOVERY] Workspace totals")
    print(f"  Reports           : {len(workspace_items.reports)}")
    print(f"  Semantic Models   : {len(workspace_items.semantic_models)}")
    print(f"  Paginated Reports : {len(workspace_items.paginated_reports)}")
    print(f"  Total items       : {len(workspace_items)}")

    _section("REPORT DEFINITIONS")
    print("[DISCOVERY] Reading report definitions and RDL Visuals with Fabric REST...")
    rdl_visuals = discover_report_definitions(
        fabric, config.workspace_id, workspace_items
    )
    print(f"[DISCOVERY] RDL Visuals found: {len(rdl_visuals)}")

    _section("PAGINATED REPORT DEFINITIONS")
    print("[DISCOVERY] Reading paginated report definitions with Fabric REST...")
    paginated_infos = discover_paginated_report_definitions(
        fabric, config.workspace_id, workspace_items
    )
    print(
        f"[DISCOVERY] Paginated report definitions loaded: {len(paginated_infos)}"
    )

    _section("DISCOVERY SUMMARY")
    summarize_discovery(workspace_items, rdl_visuals, config)

    _section("PAGINATED REPORT REMEDIATION")
    remediate_paginated_reports(
        fabric, workspace_items, paginated_infos, config
    )

    _section("RDL VISUAL RESOLUTION AND APPLY")
    apply_remediation(
        fabric, rdl_visuals, paginated_infos, workspace_items, config
    )

    _section("SEMANTIC MODEL CONNECTION BINDING")
    bind_semantic_models_to_connections(fabric, workspace_items, config)


if __name__ == "__main__":
    main()
