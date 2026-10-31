"""Consistent human-readable remediation failure summaries.

This module contains presentation-only helpers. It does not alter remediation
flow, retry policy, API calls, or fail/continue decisions.
"""


def format_failure_details(failures):
    """Return a compact multiline list of element failures.

    Each entry is a mapping with these optional keys:
    element_type, element_name, operation, reason, page_name.
    """
    lines = []
    for index, failure in enumerate(failures, start=1):
        element_type = failure.get("element_type") or "Element"
        element_name = failure.get("element_name") or "(unknown)"
        operation = failure.get("operation") or "Remediation"
        reason = failure.get("reason") or "Unknown error"
        page_name = failure.get("page_name") or ""

        subject = f"{element_type}: {element_name}"
        if page_name:
            subject += f" / Page: {page_name}"
        lines.append(f"[{index}] {subject}")
        lines.append(f"    Operation : {operation}")
        lines.append(f"    Reason    : {reason}")
    return "\n".join(lines)


def print_failure_summary(title, failures):
    """Print a standardized failure summary without changing control flow."""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(f"Total failures : {len(failures)}")
    if failures:
        print()
        print(format_failure_details(failures))
