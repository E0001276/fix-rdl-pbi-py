import argparse
from pathlib import Path

import truststore

truststore.inject_into_ssl()

from auth import get_access_token
from config import load_config
from diagnostics import start_diagnostics
from powerbi_gateway import bind_semantic_models_to_gateway
from semantic_refresh import refresh_semantic_models
from http_clients import ApiClient
from paginated import remediate_paginated_reports
from powerbi_paginated import bind_paginated_reports_to_semantic_models
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
        default=str(Path(__file__).parent / "config" / "postdeploy-dev-cicd.json"),
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
    project_root = Path(__file__).resolve().parent.parent
    diagnostics = start_diagnostics(project_root)
    print(f"[LOG] Detailed run directory: {diagnostics.run_dir}")
    print("[LOG] Bearer tokens are REDACTED from all saved diagnostics.")

    try:
        _main(args, diagnostics)
    finally:
        counts = diagnostics.request_counts
        print()
        print("=" * 80)
        print("HTTP REQUEST SUMMARY")
        print("=" * 80)
        print(f"Total requests : {diagnostics.request_count}")
        print(f"GET            : {counts.get('GET', 0)}")
        print(f"POST           : {counts.get('POST', 0)}")
        print(f"[LOG] Detailed run directory: {diagnostics.run_dir}")
        diagnostics.close()


def _main(args, diagnostics) -> None:
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
    print("[AUTH] Fabric API    : https://api.fabric.microsoft.com/v1")
    print("[AUTH] Power BI API  : https://api.powerbi.com/v1.0/myorg")
    print("[AUTH] Requesting Fabric access token...")
    fabric_token = get_access_token("https://api.fabric.microsoft.com")
    print("[AUTH] Fabric access token acquired successfully.")
    fabric = ApiClient(
        "https://api.fabric.microsoft.com/v1",
        fabric_token,
        diagnostics=diagnostics,
        token_label="FABRIC_ACCESS_TOKEN",
    )
    print("[AUTH] Fabric API client initialized.")

    print("[AUTH] Requesting Power BI access token...")
    powerbi_token = get_access_token("https://analysis.windows.net/powerbi/api")
    print("[AUTH] Power BI access token acquired successfully.")
    powerbi = ApiClient(
        "https://api.powerbi.com/v1.0/myorg",
        powerbi_token,
        diagnostics=diagnostics,
        token_label="POWERBI_ACCESS_TOKEN",
    )
    print("[AUTH] Power BI API client initialized.")

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
    report_definition_cache = {}
    rdl_visuals = discover_report_definitions(
        fabric,
        config.workspace_id,
        workspace_items,
        definition_cache=report_definition_cache,
    )
    print(f"[DISCOVERY] RDL Visuals found: {len(rdl_visuals)}")
    print(
        f"[CACHE] Report definitions retained for this run: "
        f"{len(report_definition_cache)}"
    )

    _section("PAGINATED REPORT DEFINITIONS")
    print("[DISCOVERY] Reading paginated report definitions with Fabric REST...")
    paginated_infos = discover_paginated_report_definitions(
        fabric, config.workspace_id, workspace_items
    )
    print(f"[DISCOVERY] Paginated report definitions loaded: {len(paginated_infos)}")

    _section("DISCOVERY SUMMARY")
    summarize_discovery(workspace_items, rdl_visuals, config)

    # Target-only post-deploy order.
    #
    # Target-only strategy aligned with the working .NET implementation.
    # Paginated Report item identity is NEVER replaced. This prevents Git
    # integration from seeing DELETE + ADD pairs for the same logical report.
    #
    # 1) Semantic model -> compatible on-premises gateway.
    # 2) Paginated RDL update in place (same itemId).
    # 3) Paginated runtime datasource -> target semantic model.
    # 4) Main report RDL Visual -> current target paginated itemIds.

    _section("SEMANTIC MODEL GATEWAY BINDING")
    # IMPORTANT: this is the exact pre-v22/v21 binding flow. Do not reinterpret
    # or replace the semantic model datasource as part of refresh.
    bind_semantic_models_to_gateway(powerbi, workspace_items, config)

    _section("SEMANTIC MODEL REFRESH")
    # Programmatic equivalent of Power BI Service > Semantic model > "Actualizar ahora".
    # This is intentionally an additional step AFTER the existing gateway binding.
    refresh_semantic_models(powerbi, workspace_items, config)

    _section("PAGINATED REPORT RDL REMEDIATION")
    remediate_paginated_reports(fabric, workspace_items, paginated_infos, config)

    _section("POST-RDL SNAPSHOT STATUS")
    current_snapshots = sum(1 for info in paginated_infos if info.definition_current)
    stale_snapshots = len(paginated_infos) - current_snapshots
    print(
        "[CACHE] Paginated definitions are reused from initial discovery and "
        "refreshed only after a write or when verification could not complete."
    )
    print(f"[CACHE] Current snapshots : {current_snapshots}")
    print(f"[CACHE] Stale snapshots   : {stale_snapshots}")
    print("[CACHE] Full workspace rediscovery is not required because updateDefinition preserves item identity.")

    _section("PAGINATED REPORT RUNTIME DATASOURCE BINDING")
    bind_paginated_reports_to_semantic_models(
        powerbi, fabric, workspace_items, paginated_infos, config
    )

    _section("RDL VISUAL RESOLUTION AND APPLY")
    print(
        "[CACHE] Reusing main-report definitions and RDL Visual discovery from "
        "the beginning of this execution. Earlier phases do not modify main reports."
    )
    apply_remediation(
        fabric,
        rdl_visuals,
        paginated_infos,
        workspace_items,
        config,
        report_definition_cache=report_definition_cache,
    )


if __name__ == "__main__":
    main()
