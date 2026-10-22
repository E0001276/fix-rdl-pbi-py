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
        description=(
            "Delete all items and folders from " "a Microsoft Fabric workspace."
        )
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to the workspace configuration YAML.",
    )

    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        help="Confirm deletion without interactive input.",
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


def list_workspace_folders(
    client: ApiClient,
    workspace_id: str,
) -> list[dict]:
    print()
    print("[DISCOVERY] Loading workspace folders...")

    folders = list_all_items(
        client,
        f"workspaces/{workspace_id}/folders",
    )

    print(f"[DISCOVERY] Folders found: {len(folders)}")

    return folders


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


def print_folders(folders: list[dict]) -> None:
    print()

    if not folders:
        print("The workspace does not contain any folders.")
        return

    print("Workspace folders:")
    print()

    for index, folder in enumerate(folders, start=1):
        folder_id = folder.get("id", "")

        folder_name = folder.get("displayName") or folder.get("name") or folder_id

        parent_folder_id = folder.get("parentFolderId") or "(root)"

        print(f"{index:03d}. " f"{folder_name}")

        print(f"     Id        : {folder_id}")
        print(f"     Parent Id : {parent_folder_id}")


def delete_item(
    client: ApiClient,
    workspace_id: str,
    item: dict,
) -> bool:
    item_id = item["id"]

    item_name = item.get("displayName") or item.get("name") or item_id

    item_type = item.get("type", "Unknown")

    url = client.build_url(f"workspaces/{workspace_id}/items/{item_id}")

    print(f"[DELETE ITEM] " f"{item_name} " f"[{item_type}] " f"({item_id})")

    response = client.session.delete(url)

    client.log_http_exchange(
        "DELETE",
        url,
        None,
        response,
    )

    if response.ok:
        print("              OK")
        return True

    print(f"              ERROR HTTP " f"{response.status_code} " f"{response.reason}")

    try:
        print(f"              {response.json()}")
    except Exception:
        print(f"              {response.text}")

    return False


def delete_folder(
    client: ApiClient,
    workspace_id: str,
    folder: dict,
) -> bool:
    folder_id = folder["id"]

    folder_name = folder.get("displayName") or folder.get("name") or folder_id

    url = client.build_url(f"workspaces/{workspace_id}/folders/{folder_id}")

    print(f"[DELETE FOLDER] " f"{folder_name} " f"({folder_id})")

    response = client.session.delete(url)

    client.log_http_exchange(
        "DELETE",
        url,
        None,
        response,
    )

    if response.ok:
        print("                OK")
        return True

    print(
        f"                ERROR HTTP " f"{response.status_code} " f"{response.reason}"
    )

    try:
        print(f"                {response.json()}")
    except Exception:
        print(f"                {response.text}")

    return False


def get_folder_depth(
    folder: dict,
    folder_by_id: dict[str, dict],
) -> int:
    depth = 0

    parent_id = folder.get("parentFolderId")

    visited = set()

    while parent_id:
        if parent_id in visited:
            break

        visited.add(parent_id)

        parent = folder_by_id.get(parent_id)

        if not parent:
            break

        depth += 1
        parent_id = parent.get("parentFolderId")

    return depth


def sort_folders_for_deletion(
    folders: list[dict],
) -> list[dict]:
    folder_by_id = {folder["id"]: folder for folder in folders if folder.get("id")}

    return sorted(
        folders,
        key=lambda folder: get_folder_depth(
            folder,
            folder_by_id,
        ),
        reverse=True,
    )


def confirm_deletion(
    config,
    item_count: int,
    folder_count: int,
    confirm_delete: bool,
) -> bool:
    print()
    print("========================================")
    print("WARNING")
    print("========================================")

    print(
        f"ALL {item_count} item(s) and "
        f"{folder_count} folder(s) from workspace "
        f"'{config.workspace_name}' will be deleted."
    )

    print()
    print("This operation modifies the Fabric workspace.")
    print()

    if confirm_delete:
        print("[CONFIRMATION] Deletion confirmed " "by --confirm-delete.")
        return True

    try:
        confirmation = input(
            f"Type the workspace name " f"'{config.workspace_name}' to continue: "
        )

    except EOFError:
        print()
        print("[ERROR] Interactive confirmation " "is not available.")

        print(
            "Use --confirm-delete when running "
            "from Jenkins or another "
            "non-interactive environment."
        )

        return False

    if confirmation != config.workspace_name:
        print()
        print("[CANCELLED] Workspace name " "did not match.")

        return False

    return True


def main() -> None:
    args = build_argument_parser().parse_args()

    config = load_config(args.config)

    print()
    print("========================================")
    print("DELETE WORKSPACE CONTENT")
    print("========================================")
    print(f"Workspace Name : {config.workspace_name}")
    print(f"Workspace Id   : {config.workspace_id}")
    print("========================================")

    client = create_fabric_client()

    items = list_workspace_items(
        client,
        config.workspace_id,
    )

    folders = list_workspace_folders(
        client,
        config.workspace_id,
    )

    print_items(items)
    print_folders(folders)

    if not items and not folders:
        print()
        print("[INFO] Nothing to delete.")
        return

    confirmed = confirm_deletion(
        config=config,
        item_count=len(items),
        folder_count=len(folders),
        confirm_delete=args.confirm_delete,
    )

    if not confirmed:
        sys.exit(1)

    #
    # Delete items first.
    #
    print()
    print("========================================")
    print("DELETE ITEMS")
    print("========================================")
    print()

    deleted_items = 0
    failed_items = 0

    for item in items:
        if delete_item(
            client,
            config.workspace_id,
            item,
        ):
            deleted_items += 1
        else:
            failed_items += 1

    #
    # Delete folders.
    #
    # Nested folders must be deleted first.
    #
    print()
    print("========================================")
    print("DELETE FOLDERS")
    print("========================================")
    print()

    sorted_folders = sort_folders_for_deletion(folders)

    deleted_folders = 0
    failed_folders = 0

    for folder in sorted_folders:
        if delete_folder(
            client,
            config.workspace_id,
            folder,
        ):
            deleted_folders += 1
        else:
            failed_folders += 1

    print()
    print("========================================")
    print("RESULT")
    print("========================================")

    print(f"Workspace       : {config.workspace_name}")

    print()
    print("Items")
    print(f"  Found         : {len(items)}")
    print(f"  Deleted       : {deleted_items}")
    print(f"  Failed        : {failed_items}")

    print()
    print("Folders")
    print(f"  Found         : {len(folders)}")
    print(f"  Deleted       : {deleted_folders}")
    print(f"  Failed        : {failed_folders}")

    print()
    print(f"Total failed    : " f"{failed_items + failed_folders}")

    print("========================================")

    if failed_items > 0 or failed_folders > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
