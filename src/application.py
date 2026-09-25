from pathlib import Path

from auth import get_access_token
from config import load_config
from console import print_section
from http_clients import ApiClient
from paginated import remediate_paginated_reports
from paginated_mapping import load_paginated_report_mapping
from powerbi_gateway import bind_semantic_models_to_gateway
from powerbi_paginated import bind_paginated_reports_to_semantic_models
from remediation import apply_remediation, summarize_discovery
from semantic_refresh import refresh_semantic_models
from workspace import (
    discover_paginated_report_definitions,
    discover_report_definitions,
    discover_semantic_model_definitions,
    list_fabric_workspace_items,
)


FABRIC_API_BASE_URL = "https://api.fabric.microsoft.com/v1"
POWERBI_API_BASE_URL = "https://api.powerbi.com/v1.0/myorg"
FABRIC_TOKEN_RESOURCE = "https://api.fabric.microsoft.com"
POWERBI_TOKEN_RESOURCE = "https://analysis.windows.net/powerbi/api"


def create_api_clients(diagnostics):
    """Authenticate and create the Fabric and Power BI API clients."""
    print_section("AUTHENTICATION")
    print(f"[AUTH] Fabric API    : {FABRIC_API_BASE_URL}")
    print(f"[AUTH] Power BI API  : {POWERBI_API_BASE_URL}")

    print("[AUTH] Requesting Fabric access token...")
    fabric_token = get_access_token(FABRIC_TOKEN_RESOURCE)
    print("[AUTH] Fabric access token acquired successfully.")
    fabric = ApiClient(
        FABRIC_API_BASE_URL,
        fabric_token,
        diagnostics=diagnostics,
        token_label="FABRIC_ACCESS_TOKEN",
    )
    print("[AUTH] Fabric API client initialized.")

    print("[AUTH] Requesting Power BI access token...")
    powerbi_token = get_access_token(POWERBI_TOKEN_RESOURCE)
    print("[AUTH] Power BI access token acquired successfully.")
    powerbi = ApiClient(
        POWERBI_API_BASE_URL,
        powerbi_token,
        diagnostics=diagnostics,
        token_label="POWERBI_ACCESS_TOKEN",
    )
    print("[AUTH] Power BI API client initialized.")

    return fabric, powerbi


def print_configuration(config_path: str, config, mapping) -> None:
    """Print the effective environment and mapping configuration."""
    print_section("POWER BI / MICROSOFT FABRIC POST-DEPLOY")
    print(f"[CONFIG] File        : {Path(config_path).resolve()}")
    print(f"[WORKSPACE] Name     : {config.workspace_name}")
    print(f"[WORKSPACE] Id       : {config.workspace_id}")
    print(
        f"[WORKSPACE] Oracle server      : "
        f"{config.expected_oracle_database or '(not configured)'}"
    )
    print(
        f"[WORKSPACE] Fabric connection  : "
        f"{config.semantic_model_connection_name or '(not configured)'}"
    )
    print(f"[MAPPING] File       : {config.reports_mapping_path}")
    print(f"[MAPPING] Reports    : {mapping.report_count}")
    print(f"[MAPPING] Pages      : {mapping.page_count}")


def discover_workspace_state(fabric, config):
    """Discover workspace items and all definitions needed by remediation."""
    print_section("WORKSPACE DISCOVERY")
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

    print_section("REPORT DEFINITIONS")
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

    print_section("SEMANTIC MODEL DEFINITIONS")
    print("[DISCOVERY] Reading semantic model definitions with Fabric REST...")
    discover_semantic_model_definitions(
        fabric, config.workspace_id, workspace_items
    )
    print(
        f"[DISCOVERY] Semantic model definitions logged: "
        f"{len(workspace_items.semantic_models)}"
    )

    print_section("PAGINATED REPORT DEFINITIONS")
    print("[DISCOVERY] Reading paginated report definitions with Fabric REST...")
    paginated_infos = discover_paginated_report_definitions(
        fabric, config.workspace_id, workspace_items
    )
    print(f"[DISCOVERY] Paginated report definitions loaded: {len(paginated_infos)}")

    return workspace_items, rdl_visuals, paginated_infos, report_definition_cache


def print_post_rdl_snapshot_status(paginated_infos) -> None:
    """Describe whether paginated definition snapshots are current."""
    print_section("POST-RDL SNAPSHOT STATUS")
    current_snapshots = sum(1 for info in paginated_infos if info.definition_current)
    stale_snapshots = len(paginated_infos) - current_snapshots
    print(
        "[CACHE] Paginated definitions are reused from initial discovery and "
        "refreshed only after a write or when verification could not complete."
    )
    print(f"[CACHE] Current snapshots : {current_snapshots}")
    print(f"[CACHE] Stale snapshots   : {stale_snapshots}")
    print(
        "[CACHE] Full workspace rediscovery is not required because "
        "updateDefinition preserves item identity."
    )


def execute_post_deploy_pipeline(
    fabric,
    powerbi,
    workspace_items,
    rdl_visuals,
    paginated_infos,
    report_definition_cache,
    config,
    mapping,
) -> None:
    """Execute the target-only post-deploy steps in their required order."""
    print_section("DISCOVERY SUMMARY")
    summarize_discovery(workspace_items, rdl_visuals, config, mapping)

    # Target-only strategy aligned with the working .NET implementation.
    # Paginated Report item identity is NEVER replaced. This prevents Git
    # integration from seeing DELETE + ADD pairs for the same logical report.
    #
    # 1) Semantic model -> compatible on-premises gateway.
    # 2) Semantic model refresh.
    # 3) Paginated RDL update in place (same itemId).
    # 4) Paginated runtime datasource -> target semantic model.
    # 5) Main report RDL Visual -> current target paginated itemIds.

    print_section("SEMANTIC MODEL GATEWAY BINDING")
    bind_semantic_models_to_gateway(fabric, powerbi, workspace_items, config)

    print_section("SEMANTIC MODEL REFRESH")
    refresh_semantic_models(powerbi, workspace_items, config)

    print_section("PAGINATED REPORT RDL REMEDIATION")
    remediate_paginated_reports(fabric, workspace_items, paginated_infos, config)

    print_post_rdl_snapshot_status(paginated_infos)

    print_section("PAGINATED REPORT RUNTIME DATASOURCE BINDING")
    bind_paginated_reports_to_semantic_models(
        powerbi, fabric, workspace_items, paginated_infos, config
    )

    print_section("RDL VISUAL RESOLUTION AND APPLY")
    print(
        "[CACHE] Reusing main-report definitions and RDL Visual discovery from "
        "the beginning of this execution. Earlier phases do not modify main reports."
    )
    apply_remediation(
        fabric,
        rdl_visuals,
        paginated_infos,
        config,
        mapping,
        report_definition_cache=report_definition_cache,
    )


def run_post_deploy(config_path: str, diagnostics) -> None:
    """Run the complete post-deploy application for one environment config."""
    config = load_config(config_path)
    mapping = load_paginated_report_mapping(config.reports_mapping_path)
    print_configuration(config_path, config, mapping)

    fabric, powerbi = create_api_clients(diagnostics)
    (
        workspace_items,
        rdl_visuals,
        paginated_infos,
        report_definition_cache,
    ) = discover_workspace_state(fabric, config)

    execute_post_deploy_pipeline(
        fabric,
        powerbi,
        workspace_items,
        rdl_visuals,
        paginated_infos,
        report_definition_cache,
        config,
        mapping,
    )
