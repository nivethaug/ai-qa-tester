"""
AI QA Tester - Reporter
Generates structured audit reports and CLI summaries.
"""

import json
from pathlib import Path
from typing import Dict, Any

from config import REPORTS_DIR
from storage import get_stats
from logger import log_event


def generate_report_file(project_id: int) -> Path:
    """Return path to the report JSON for a project."""
    return REPORTS_DIR / str(project_id) / "report.json"


def print_cli_report():
    """Print summary report to stdout."""
    stats = get_stats()

    print()
    print("=" * 45)
    print("  DreamAgent QA Report")
    print("=" * 45)
    print(f"  Total:           {stats['total']}")
    print(f"  Verified:        {stats['verified']}")
    print(f"  Passed:          {stats['passed']}")
    print(f"  Failed:          {stats['failed']}")
    print(f"  Security Issues: {stats['security_issues']}")
    print(f"  Avg Score:       {stats['avg_score']}")
    print("=" * 45)
    print()
