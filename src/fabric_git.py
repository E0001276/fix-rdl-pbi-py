from dataclasses import dataclass

from console import print_section


@dataclass(frozen=True)
class FabricGitStatus:
    workspace_head: str
    remote_commit_hash: str
    changes: tuple
    raw: dict

    @property
    def workspace_changes(self):
        return tuple(change for change in self.changes if change.get("workspaceChange"))

    @property
    def remote_changes(self):
        return tuple(change for change in self.changes if change.get("remoteChange"))

    @property
    def conflicts(self):
        return tuple(
            change
            for change in self.changes
            if str(change.get("conflictType", "None")).lower() not in {"", "none"}
        )

    @property
    def is_head_aligned(self) -> bool:
        return bool(self.workspace_head) and (
            self.workspace_head == self.remote_commit_hash
        )


def _short_sha(value: str) -> str:
    value = str(value or "").strip()
    return value[:12] if value else "(none)"


def _display_name(change: dict) -> str:
    metadata = change.get("itemMetadata") or {}
    return str(metadata.get("displayName") or "(unnamed item)")


def get_git_connection(client, workspace_id: str) -> dict:
    response = client.get(f"workspaces/{workspace_id}/git/connection")
    data = response.json()
    state = str(data.get("gitConnectionState", "")).strip()
    if state != "ConnectedAndInitialized":
        raise RuntimeError(
            "Fabric workspace Git connection is not ready. "
            f"gitConnectionState={state or '(missing)'}. "
            "The workspace must already be connected and initialized."
        )
    return data


def validate_git_connection(
    client,
    workspace_id: str,
    expected_branch: str = "",
    expected_owner: str = "",
    expected_repository: str = "",
) -> dict:
    """Validate the Fabric Git connection against the expected GitHub target."""
    connection = get_git_connection(client, workspace_id)
    details = connection.get("gitProviderDetails") or {}
    branch = str(details.get("branchName", "")).strip()
    provider = str(details.get("gitProviderType", "")).strip()
    owner = str(details.get("ownerName", "")).strip()
    repository = str(details.get("repositoryName", "")).strip()

    print(f"[GIT] Provider   : {provider or '(unknown)'}")
    print(f"[GIT] Repository : {(owner + '/' + repository).strip('/') or '(unknown)'}")
    print(f"[GIT] Branch     : {branch or '(unknown)'}")

    expected_branch = str(expected_branch or "").strip()
    expected_owner = str(expected_owner or "").strip()
    expected_repository = str(expected_repository or "").strip()

    if (expected_owner or expected_repository) and provider.lower() != "github":
        raise RuntimeError(
            "Fabric workspace is connected to a different Git provider. "
            f"Expected GitHub, actual '{provider or '(unknown)'}'."
        )
    if expected_branch and branch != expected_branch:
        raise RuntimeError(
            "Fabric workspace is connected to a different Git branch. "
            f"Expected '{expected_branch}', actual '{branch or '(unknown)'}'."
        )
    if expected_owner and owner.lower() != expected_owner.lower():
        raise RuntimeError(
            "Fabric workspace is connected to a different GitHub owner. "
            f"Expected '{expected_owner}', actual '{owner or '(unknown)'}'."
        )
    if expected_repository and repository.lower() != expected_repository.lower():
        raise RuntimeError(
            "Fabric workspace is connected to a different GitHub repository. "
            f"Expected '{expected_repository}', actual '{repository or '(unknown)'}'."
        )
    return connection


def ensure_git_credentials(
    client,
    workspace_id: str,
    connection_id: str = "",
) -> dict:
    """Ensure Git credentials exist for the current Fabric caller.

    For GitHub + Service Principal, Microsoft Fabric requires a
    ConfiguredConnection credential source. If a connection ID is supplied,
    this method assigns it to the current caller before the Git operations.
    """
    path = f"workspaces/{workspace_id}/git/myGitCredentials"
    connection_id = str(connection_id or "").strip()

    if connection_id:
        print(
            "[GIT] Configuring caller Git credentials with Fabric connection "
            f"{connection_id}..."
        )
        response = client.patch(
            path,
            json={
                "source": "ConfiguredConnection",
                "connectionId": connection_id,
            },
        )
        credentials = response.json()
    else:
        response = client.get(path)
        credentials = response.json()

    source = str(credentials.get("source", "None")).strip() or "None"
    print(f"[GIT] Credential source: {source}")

    if source == "None":
        raise RuntimeError(
            "Git credentials are not configured for the current Fabric caller. "
            "For GitHub Actions using a Service Principal, configure a Fabric "
            "GitHub cloud connection and pass its ID with --git-connection-id "
            "or FABRIC_GIT_CONNECTION_ID."
        )
    return credentials


def get_git_status(
    client,
    workspace_id: str,
    timeout_seconds: int = 1800,
) -> FabricGitStatus:
    response = client.get(f"workspaces/{workspace_id}/git/status")
    data = client.get_json_lro_result(response, timeout_seconds=timeout_seconds)
    status = FabricGitStatus(
        workspace_head=str(data.get("workspaceHead") or "").strip(),
        remote_commit_hash=str(data.get("remoteCommitHash") or "").strip(),
        changes=tuple(data.get("changes") or []),
        raw=data,
    )
    if not status.remote_commit_hash:
        raise RuntimeError(
            "Fabric Git status did not return remoteCommitHash. "
            "Verify that the workspace Git connection is initialized."
        )
    return status


def print_git_status(status: FabricGitStatus, label: str) -> None:
    print(f"[GIT] {label}")
    print(f"[GIT] Workspace head : {_short_sha(status.workspace_head)}")
    print(f"[GIT] Remote commit  : {_short_sha(status.remote_commit_hash)}")
    print(f"[GIT] Changes        : {len(status.changes)}")
    print(f"[GIT] Workspace-only : {len(status.workspace_changes)}")
    print(f"[GIT] Remote         : {len(status.remote_changes)}")
    print(f"[GIT] Conflicts      : {len(status.conflicts)}")


def _raise_conflicts(status: FabricGitStatus, stage: str) -> None:
    if not status.conflicts:
        return
    names = ", ".join(_display_name(change) for change in status.conflicts[:10])
    raise RuntimeError(
        f"Fabric Git conflicts detected during {stage}: {names}. "
        "The deployment will not resolve conflicts automatically."
    )


def synchronize_workspace_from_git(
    client,
    workspace_id: str,
    timeout_seconds: int = 1800,
    allow_override_items: bool = True,
    require_clean_workspace_before_update: bool = True,
) -> str:
    """Synchronize the connected remote branch into the Fabric workspace.

    Returns the remote commit hash that became the deployment baseline. The
    caller can use it after the FIX to detect a concurrent push.
    """
    print_section("FABRIC GIT - UPDATE WORKSPACE FROM GIT")
    status = get_git_status(client, workspace_id, timeout_seconds)
    print_git_status(status, "Status before updateFromGit")
    _raise_conflicts(status, "pre-deploy synchronization")

    if status.is_head_aligned:
        if status.workspace_changes:
            raise RuntimeError(
                "Workspace contains uncommitted changes before the FIX even "
                "though workspaceHead already matches remoteCommitHash. "
                "Resolve or commit those changes before continuing."
            )
        print("[GIT] Workspace is already synchronized with the remote branch.")
        return status.remote_commit_hash

    if require_clean_workspace_before_update and status.workspace_changes:
        names = ", ".join(
            _display_name(change) for change in status.workspace_changes[:10]
        )
        raise RuntimeError(
            "Workspace contains uncommitted changes before updateFromGit: "
            f"{names}. The application will not overwrite them automatically."
        )

    body = {
        "remoteCommitHash": status.remote_commit_hash,
        "options": {
            "allowOverrideItems": bool(allow_override_items),
        },
    }
    if status.workspace_head:
        body["workspaceHead"] = status.workspace_head
    print(
        "[GIT] Updating workspace from remote commit "
        f"{_short_sha(status.remote_commit_hash)}..."
    )
    response = client.post(
        f"workspaces/{workspace_id}/git/updateFromGit",
        json=body,
    )
    client.wait_for_lro_completion(response, timeout_seconds=timeout_seconds)

    verified = get_git_status(client, workspace_id, timeout_seconds)
    print_git_status(verified, "Status after updateFromGit")
    _raise_conflicts(verified, "post-update verification")

    if not verified.is_head_aligned or verified.remote_changes:
        raise RuntimeError(
            "Fabric workspace did not finish synchronized with the connected "
            "remote branch after updateFromGit."
        )
    if verified.workspace_changes:
        raise RuntimeError(
            "Fabric workspace contains unexpected local changes immediately "
            "after updateFromGit. The FIX will not start."
        )

    print("[GIT] Workspace synchronization completed successfully.")
    return verified.remote_commit_hash


def commit_workspace_changes_to_git(
    client,
    workspace_id: str,
    expected_remote_commit_hash: str,
    comment: str,
    timeout_seconds: int = 1800,
) -> bool:
    """Commit FIX changes to Git only if the remote branch did not move.

    Returns True when a commit was created, False when the FIX produced no
    workspace changes.
    """
    print_section("FABRIC GIT - COMMIT FIX CHANGES TO GIT")
    status = get_git_status(client, workspace_id, timeout_seconds)
    print_git_status(status, "Status after FIX")
    _raise_conflicts(status, "post-FIX commit")

    expected = str(expected_remote_commit_hash or "").strip()
    if status.remote_commit_hash != expected:
        raise RuntimeError(
            "The remote Git branch changed while the FIX was running. "
            "The application will not commit or overwrite the newer remote "
            "revision. "
            f"Expected {_short_sha(expected)}, current "
            f"{_short_sha(status.remote_commit_hash)}."
        )

    if status.remote_changes:
        raise RuntimeError(
            "Remote Git changes appeared while the FIX was running. "
            "The application will not call commitToGit."
        )

    if not status.workspace_changes:
        print("[GIT] The FIX produced no Git-trackable workspace changes.")
        print("[GIT] commitToGit is not required.")
        return False

    body = {
        "mode": "All",
        "workspaceHead": status.workspace_head or None,
        "comment": str(comment or "").strip()[:300],
    }
    print(
        f"[GIT] Committing {len(status.workspace_changes)} workspace change(s) "
        "to the connected remote branch..."
    )
    response = client.post(
        f"workspaces/{workspace_id}/git/commitToGit",
        json=body,
    )
    client.wait_for_lro_completion(response, timeout_seconds=timeout_seconds)

    verified = get_git_status(client, workspace_id, timeout_seconds)
    print_git_status(verified, "Status after commitToGit")
    _raise_conflicts(verified, "commit verification")

    if not verified.is_head_aligned or verified.changes:
        raise RuntimeError(
            "Fabric commitToGit completed, but the workspace and remote branch "
            "are not clean and synchronized."
        )

    print("[GIT] FIX changes were committed to Git successfully.")
    return True
