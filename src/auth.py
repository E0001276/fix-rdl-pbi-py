import json
import os
import shutil
import subprocess
from pathlib import Path


def _find_azure_cli() -> str:
    """Return an Azure CLI command that works on Windows and Linux."""
    names = ["az.cmd", "az.exe", "az"] if os.name == "nt" else ["az"]
    for name in names:
        candidate = shutil.which(name)
        if candidate:
            return candidate

    if os.name == "nt":
        common_paths = [
            Path(r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"),
            Path(r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"),
        ]
        for candidate in common_paths:
            if candidate.exists():
                return str(candidate)

    raise FileNotFoundError(
        "Azure CLI was not found. Install Azure CLI and make sure 'az' is available in PATH."
    )


def get_access_token(resource: str) -> str:
    az_command = _find_azure_cli()
    result = subprocess.run(
        [
            az_command,
            "account",
            "get-access-token",
            "--resource",
            resource,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
        shell=os.name == "nt" and az_command.lower().endswith(".cmd"),
    )
    return json.loads(result.stdout)["accessToken"]
