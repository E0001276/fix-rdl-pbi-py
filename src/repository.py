import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoItem:
    kind: str
    display_name: str
    path: Path


@dataclass
class RdlVisual:
    report_name: str
    page_name: str
    report_path: Path
    visual_path: Path
    old_item_id: str
    old_workspace_id: str


def _platform_display_name(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("metadata", {}).get("displayName", path.parent.name)


def discover_repository(repository_root: str):
    root = Path(repository_root)
    if not root.exists():
        raise FileNotFoundError(f"Repository root not found: {root}")

    items = []
    rdl_visuals = []

    for platform in root.rglob(".platform"):
        parent = platform.parent
        suffix = parent.suffix
        if suffix == ".Report":
            kind = "Report"
        elif suffix == ".SemanticModel":
            kind = "SemanticModel"
        elif suffix == ".PaginatedReport":
            kind = "PaginatedReport"
        else:
            continue
        items.append(RepoItem(kind, _platform_display_name(platform), parent))

    reports_by_path = {item.path: item for item in items if item.kind == "Report"}

    for report_path, report_item in reports_by_path.items():
        for visual_path in report_path.rglob("visual.json"):
            try:
                data = json.loads(visual_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            visual = data.get("visual", {})
            if visual.get("visualType") != "rdlVisual":
                continue

            old_item_id = ""
            old_workspace_id = ""
            try:
                ref = visual["objects"]["reportInfo"][0]["properties"]["reference"]["byReference"]
                old_item_id = ref["itemId"]["expr"]["Literal"]["Value"].strip("'")
                old_workspace_id = ref["workspaceId"]["expr"]["Literal"]["Value"].strip("'")
            except Exception:
                pass

            page_json = visual_path.parents[2] / "page.json"
            page_name = ""
            if page_json.exists():
                try:
                    page_data = json.loads(page_json.read_text(encoding="utf-8"))
                    page_name = page_data.get("displayName") or page_data.get("name", "")
                except Exception:
                    pass

            rdl_visuals.append(
                RdlVisual(
                    report_name=report_item.display_name,
                    page_name=page_name,
                    report_path=report_path,
                    visual_path=visual_path,
                    old_item_id=old_item_id,
                    old_workspace_id=old_workspace_id,
                )
            )

    return items, rdl_visuals
