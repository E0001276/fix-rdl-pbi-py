from pathlib import Path

import truststore

from application import run_post_deploy
from console import print_http_request_summary
from diagnostics import start_diagnostics
import argparse
from pathlib import Path

truststore.inject_into_ssl()

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "delta.yaml"


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the post-deploy application."""
    parser = argparse.ArgumentParser(
        description="Microsoft Fabric target-only workspace remediation"
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the environment configuration YAML.",
    )
    return parser


def parse_arguments():
    """Parse command-line arguments."""
    return build_argument_parser().parse_args()


def main() -> None:
    args = parse_arguments()
    project_root = Path(__file__).resolve().parent.parent
    diagnostics = start_diagnostics(project_root)

    print(f"[LOG] Detailed run directory: {diagnostics.run_dir}")
    print("[LOG] Bearer tokens are REDACTED from all saved diagnostics.")

    try:
        run_post_deploy(args.config, diagnostics)
    finally:
        print_http_request_summary(diagnostics)
        diagnostics.close()


if __name__ == "__main__":
    main()
