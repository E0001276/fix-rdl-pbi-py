def print_section(title: str) -> None:
    """Print a consistent console section header."""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_http_request_summary(diagnostics) -> None:
    """Print the HTTP request totals collected by diagnostics."""
    counts = diagnostics.request_counts
    print_section("HTTP REQUEST SUMMARY")
    print(f"Total requests : {diagnostics.request_count}")
    print(f"GET            : {counts.get('GET', 0)}")
    print(f"POST           : {counts.get('POST', 0)}")
    print(f"[LOG] Detailed run directory: {diagnostics.run_dir}")
