import argparse
from pathlib import Path

import truststore

from application import FABRIC_API_BASE_URL, FABRIC_TOKEN_RESOURCE, run_post_deploy
from auth import get_access_token
from config import load_config
from console import print_http_request_summary, print_section
from diagnostics import start_diagnostics
from fabric_git import (
    commit_workspace_changes_to_git,
    ensure_git_credentials,
    synchronize_workspace_from_git,
    validate_git_connection,
)
from git_config import load_fabric_git_config
from http_clients import ApiClient

truststore.inject_into_ssl()

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "ws-dev-cicd.yaml"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Microsoft Fabric deployment orchestrator: Git -> Workspace -> "
            "existing FIX -> Git"
        )
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the existing environment configuration YAML.",
    )
    parser.add_argument(
        "--expected-branch",
        default="",
        help=(
            "Optional branch name expected in the Fabric Git connection. "
            "GitHub Actions should pass the target branch that triggered the push workflow."
        ),
    )
    parser.add_argument(
        "--expected-owner",
        default="",
        help="Optional GitHub owner expected in the Fabric Git connection.",
    )
    parser.add_argument(
        "--expected-repository",
        default="",
        help="Optional GitHub repository expected in the Fabric Git connection.",
    )
    parser.add_argument(
        "--git-connection-id",
        default="",
        help=(
            "Optional Fabric cloud connection ID used as Git credentials for "
            "the current caller. Can also be supplied with "
            "FABRIC_GIT_CONNECTION_ID."
        ),
    )
    return parser


def create_fabric_client(diagnostics) -> ApiClient:
    token = get_access_token(FABRIC_TOKEN_RESOURCE)
    return ApiClient(
        FABRIC_API_BASE_URL,
        token,
        diagnostics=diagnostics,
        token_label="FABRIC_ACCESS_TOKEN",
    )


def main() -> None:
    args = build_argument_parser().parse_args()
    project_root = Path(__file__).resolve().parent.parent
    diagnostics = start_diagnostics(project_root)

    print(f"[LOG] Detailed run directory: {diagnostics.run_dir}")
    print("[LOG] Bearer tokens are REDACTED from all saved diagnostics.")

    try:
        config = load_config(args.config)
        git_config = load_fabric_git_config(
            args.config,
            connection_id_override=args.git_connection_id,
        )

        baseline_remote_commit = ""

        if git_config.enabled:
            print_section("FABRIC GIT - PRE-DEPLOY VALIDATION")
            fabric_git_client = create_fabric_client(diagnostics)
            validate_git_connection(
                fabric_git_client,
                config.workspace_id,
                expected_branch=args.expected_branch,
                expected_owner=args.expected_owner,
                expected_repository=args.expected_repository,
            )
            ensure_git_credentials(
                fabric_git_client,
                config.workspace_id,
                connection_id=git_config.connection_id,
            )
            baseline_remote_commit = synchronize_workspace_from_git(
                fabric_git_client,
                config.workspace_id,
                timeout_seconds=git_config.lro_timeout_seconds,
                allow_override_items=git_config.allow_override_items,
                require_clean_workspace_before_update=(
                    git_config.require_clean_workspace_before_update
                ),
            )
        else:
            print_section("FABRIC GIT AUTOMATION")
            print("[GIT] Disabled by configuration. Running FIX only.")

        # IMPORTANT: this is the existing, already-tested FIX pipeline.
        # No internal FIX step is changed by this orchestrator.
        run_post_deploy(args.config, diagnostics)

        if git_config.enabled:
            # Acquire a fresh token/client in case the FIX took long enough for
            # the pre-deploy access token to approach expiration.
            fabric_git_client = create_fabric_client(diagnostics)
            validate_git_connection(
                fabric_git_client,
                config.workspace_id,
                expected_branch=args.expected_branch,
                expected_owner=args.expected_owner,
                expected_repository=args.expected_repository,
            )
            ensure_git_credentials(
                fabric_git_client,
                config.workspace_id,
                connection_id=git_config.connection_id,
            )
            commit_workspace_changes_to_git(
                fabric_git_client,
                config.workspace_id,
                expected_remote_commit_hash=baseline_remote_commit,
                comment=git_config.commit_message,
                timeout_seconds=git_config.lro_timeout_seconds,
            )
    finally:
        print_http_request_summary(diagnostics)
        diagnostics.close()


if __name__ == "__main__":
    main()
