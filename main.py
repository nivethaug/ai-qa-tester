#!/usr/bin/env python3
"""
AI QA Tester - Main Entry Point

Usage:
    python main.py                # Start the full QA system
    python main.py --no-verify    # Create + track projects only (skip Claude verification)
    python main.py --report       # Print CLI summary report
    python main.py --verify 42    # Manually verify project #42
    python main.py --stability-suite
"""

import argparse
import asyncio
import os
import sys

from storage import init_db
from scheduler import creation_loop, status_loop
from reporter import print_cli_report
from verifier import verify_project
from project_client import get_project
from stability_suite import run_stability_suite
from config import MAX_ACTIVE_PROJECTS, CREATE_INTERVAL, STATUS_POLL_INTERVAL
from logger import log_event

# Global flag to skip Claude verification (for local testing)
SKIP_CLAUDE = os.getenv("SKIP_CLAUDE", "false").lower() in ("true", "1", "yes")


async def run_system():
    """Start both loops concurrently."""
    log_event("APP", "DreamAgent QA System starting...")
    log_event("APP", f"Create interval: {CREATE_INTERVAL}s | Status poll: {STATUS_POLL_INTERVAL}s | Max active: {MAX_ACTIVE_PROJECTS}")
    if SKIP_CLAUDE:
        log_event("APP", "⚠️  Claude verification SKIPPED (local testing mode)")

    await asyncio.gather(
        creation_loop(),
        status_loop(),
    )


async def manual_verify(project_id: int):
    """Manually trigger verification for a specific project."""
    log_event("APP", f"Manual verification for id={project_id}")

    project = await get_project(project_id)
    if not project:
        print(f"Project #{project_id} not found")
        sys.exit(1)

    domain = project.get("domain", "")
    description = project.get("description", "")

    if not domain:
        print(f"Project #{project_id} has no domain")
        sys.exit(1)

    from config import BASE_DOMAIN
    full_domain = f"https://{domain}.{BASE_DOMAIN}"
    print(f"Verifying: {full_domain}")

    await verify_project(project_id, full_domain, description)
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="DreamAgent AI QA Tester")
    parser.add_argument("--report", action="store_true", help="Print CLI summary report")
    parser.add_argument("--verify", type=int, metavar="ID", help="Manually verify project ID")
    parser.add_argument("--no-verify", action="store_true", help="Skip Claude verification (local testing)")
    parser.add_argument("--stability-suite", action="store_true", help="Run one controlled product stability suite")
    parser.add_argument(
        "--types",
        metavar="IDS",
        help="Comma-separated project type IDs for --stability-suite, e.g. 1,2,3,5",
    )
    args = parser.parse_args()

    if args.no_verify:
        os.environ["SKIP_CLAUDE"] = "true"
        global SKIP_CLAUDE
        SKIP_CLAUDE = True

    if args.report:
        init_db()
        print_cli_report()
        return

    if args.verify:
        init_db()
        asyncio.run(manual_verify(args.verify))
        return

    if args.stability_suite:
        init_db()
        project_types = None
        if args.types:
            project_types = [int(t.strip()) for t in args.types.split(",") if t.strip().isdigit()]
        report = asyncio.run(run_stability_suite(project_types))
        print()
        print("DreamAgent stability suite")
        print(f"Result: {'PASS' if report.get('ok') else 'FAIL'}")
        for item in report.get("results", []):
            status = "PASS" if item.get("ok") else "FAIL"
            print(f"- {status} {item.get('type_label')} project={item.get('project_id')} domain={item.get('domain')}")
        return

    # Default: run the full system
    init_db()
    try:
        asyncio.run(run_system())
    except KeyboardInterrupt:
        log_event("APP", "Shutting down...")
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
