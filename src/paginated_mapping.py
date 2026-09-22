from dataclasses import dataclass
from pathlib import Path

from yaml_utils import load_yaml_mapping


def normalize_mapping_name(value: str) -> str:
    """Remove accidental leading/trailing whitespace from mapping names."""
    return value.strip()


@dataclass(frozen=True)
class PaginatedReportRelation:
    report: str
    page: str
    paginated_report: str


class PaginatedReportMapping:
    """Explicit Report + Page -> PaginatedReport relationships.

    Version 1 intentionally supports one paginated report per report page.
    Names are matched deterministically after trimming leading/trailing spaces.
    """

    def __init__(self, version: int, relations: list[PaginatedReportRelation]):
        self.version = version
        self.relations = relations
        self.relations_by_report_page: dict[
            tuple[str, str], PaginatedReportRelation
        ] = {}
        self.build_index()

    def build_index(self) -> None:
        for relation in self.relations:
            key = self.create_key(relation.report, relation.page)
            if key in self.relations_by_report_page:
                existing = self.relations_by_report_page[key]
                raise ValueError(
                    "Duplicate paginated report mapping after normalization. "
                    f"report={relation.report!r}, page={relation.page!r}, "
                    f"existingPaginatedReport={existing.paginated_report!r}, "
                    f"duplicatePaginatedReport={relation.paginated_report!r}."
                )
            self.relations_by_report_page[key] = relation

    @staticmethod
    def create_key(report: str, page: str) -> tuple[str, str]:
        return (
            normalize_mapping_name(report),
            normalize_mapping_name(page),
        )

    @property
    def report_count(self) -> int:
        return len(
            {
                normalize_mapping_name(relation.report)
                for relation in self.relations
            }
        )

    @property
    def page_count(self) -> int:
        return len(self.relations)

    def find(self, report: str, page: str) -> PaginatedReportRelation | None:
        return self.relations_by_report_page.get(self.create_key(report, page))

    def keys(self) -> set[tuple[str, str]]:
        return set(self.relations_by_report_page)


def load_paginated_report_mapping(path: str | Path) -> PaginatedReportMapping:
    """Load and validate reports.yaml."""
    mapping_path, data = load_yaml_mapping(path, "Reports mapping")

    version = data.get("version")
    if version != 1:
        raise ValueError(
            f"Unsupported reports mapping version: {version!r}. Expected 1."
        )

    reports = data.get("reports")
    if not isinstance(reports, list):
        raise ValueError("'reports' must be an array in reports mapping.")

    relations: list[PaginatedReportRelation] = []
    seen_reports: set[str] = set()

    for report_entry in reports:
        if not isinstance(report_entry, dict):
            raise ValueError("Each reports mapping entry must be an object.")

        report_name = require_text(report_entry, "report", "report entry")
        normalized_report_name = normalize_mapping_name(report_name)

        if normalized_report_name in seen_reports:
            raise ValueError(
                "Duplicate report entry in reports mapping: "
                f"{report_name!r}. File: {mapping_path}"
            )
        seen_reports.add(normalized_report_name)

        pages = report_entry.get("pages")
        if not isinstance(pages, list):
            raise ValueError(f"'pages' must be an array for report {report_name!r}.")

        for page_entry in pages:
            if not isinstance(page_entry, dict):
                raise ValueError(
                    f"Each page mapping for report {report_name!r} must be an object."
                )

            page_name = require_text(
                page_entry,
                "page",
                f"report {report_name!r} page entry",
            )
            paginated_report_name = require_text(
                page_entry,
                "paginatedReport",
                f"report {report_name!r}, page {page_name!r}",
            )

            relations.append(
                PaginatedReportRelation(
                    report=report_name,
                    page=page_name,
                    paginated_report=paginated_report_name,
                )
            )

    return PaginatedReportMapping(version=version, relations=relations)


def require_text(data: dict, key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string in {context}.")

    normalized_value = normalize_mapping_name(value)
    if not normalized_value:
        raise ValueError(f"'{key}' must be a non-empty string in {context}.")

    return normalized_value
