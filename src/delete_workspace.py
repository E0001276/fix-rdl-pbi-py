import argparse
import sys

import truststore

from auth import get_access_token
from config import load_config
from http_clients import ApiClient
from workspace import list_all_items

truststore.inject_into_ssl()

FABRIC_API_BASE_URL = "https://api.fabric.microsoft.com/v1"
FABRIC_TOKEN_RESOURCE = "https://api.fabric.microsoft.com"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete all items from a Microsoft Fabric workspace."
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to the workspace configuration YAML.",
    )

    return parser


def create_fabric_client() -> ApiClient:
    print("[AUTH] Requesting Fabric access token...")

    token = get_access_token(FABRIC_TOKEN_RESOURCE)

    print("[AUTH] Fabric access token acquired successfully.")

    return ApiClient(
        base_url=FABRIC_API_BASE_URL,
        token=token,
        token_label="FABRIC_ACCESS_TOKEN",
    )


def list_workspace_items(
    client: ApiClient,
    workspace_id: str,
) -> list[dict]:
    print()
    print("[DISCOVERY] Loading workspace items...")

    items = list_all_items(
        client,
        f"workspaces/{workspace_id}/items",
    )

    print(f"[DISCOVERY] Items found: {len(items)}")

    return items


def print_items(items: list[dict]) -> None:
    print()

    if not items:
        print("The workspace does not contain any items.")
        return

    print("Workspace items:")
    print()

    for index, item in enumerate(items, start=1):
        item_id = item.get("id", "")
        item_name = item.get("displayName") or item.get("name") or item_id
        item_type = item.get("type", "Unknown")
        folder_id = item.get("folderId") or "(root)"

        print(f"{index:03d}. " f"{item_name} " f"[{item_type}]")
        print(f"     Id       : {item_id}")
        print(f"     Folder Id: {folder_id}")


def delete_item(
    client: ApiClient,
    workspace_id: str,
    item: dict,
) -> bool:
    item_id = item["id"]

    item_name = item.get("displayName") or item.get("name") or item_id

    item_type = item.get("type", "Unknown")

    url = client.build_url(f"workspaces/{workspace_id}/items/{item_id}")

    print(f"[DELETE] {item_name} " f"[{item_type}] " f"({item_id})")

    response = client.session.delete(url)

    client.log_http_exchange(
        "DELETE",
        url,
        None,
        response,
    )

    if response.ok:
        print("         OK")
        return True

    print(f"         ERROR HTTP " f"{response.status_code} " f"{response.reason}")

    try:
        print(f"         {response.json()}")
    except Exception:
        print(f"         {response.text}")

    return False


def main() -> None:
    args = build_argument_parser().parse_args()

    config = load_config(args.config)

    print()
    print("========================================")
    print("DELETE WORKSPACE ITEMS")
    print("========================================")
    print(f"Workspace Name : {config.workspace_name}")
    print(f"Workspace Id   : {config.workspace_id}")
    print("========================================")

    client = create_fabric_client()

    items = list_workspace_items(
        client,
        config.workspace_id,
    )

    print_items(items)

    if not items:
        return

    print()
    print("========================================")
    print("WARNING")
    print("========================================")
    print(
        f"ALL {len(items)} item(s) from workspace "
        f"'{config.workspace_name}' will be deleted."
    )
    print()
    print("This operation modifies the Fabric workspace.")
    print()

    confirmation = input(
        f"Type the workspace name " f"'{config.workspace_name}' to continue: "
    )

    if confirmation != config.workspace_name:
        print()
        print("[CANCELLED] Workspace name did not match.")
        return

    print()
    print("[DELETE] Starting deletion...")
    print()

    deleted = 0
    failed = 0

    for item in items:
        if delete_item(
            client,
            config.workspace_id,
            item,
        ):
            deleted += 1
        else:
            failed += 1

    print()
    print("========================================")
    print("RESULT")
    print("========================================")
    print(f"Workspace : {config.workspace_name}")
    print(f"Found     : {len(items)}")
    print(f"Deleted   : {deleted}")
    print(f"Failed    : {failed}")
    print("========================================")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
