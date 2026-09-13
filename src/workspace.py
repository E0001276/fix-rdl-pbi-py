from dataclasses import dataclass


@dataclass
class WorkspaceItem:
    id: str
    name: str
    kind: str


def list_powerbi_workspace_items(client, workspace_id: str):
    items = []

    datasets = client.get(f"groups/{workspace_id}/datasets").json().get("value", [])
    for item in datasets:
        items.append(WorkspaceItem(item["id"], item["name"], "SemanticModel"))

    reports = client.get(f"groups/{workspace_id}/reports").json().get("value", [])
    for item in reports:
        kind = "PaginatedReport" if item.get("reportType") == "PaginatedReport" else "Report"
        items.append(WorkspaceItem(item["id"], item["name"], kind))

    return items
