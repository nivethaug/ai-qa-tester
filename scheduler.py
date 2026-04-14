"""
AI QA Tester - Scheduler
Main async loops: project creation + status polling + verification dispatch.
Supports all project types: website, telegrambot, discordbot, scheduler.
"""

import asyncio
import os
import traceback
from typing import Optional

from generator import generate_project_idea
from project_client import create_project, get_project_status, get_project_domain
from storage import upsert_project, update_status, get_active_projects
from verifier import verify_project
from notifier import send_email, send_telegram, send_discord
from config import (
    CREATE_INTERVAL, STATUS_POLL_INTERVAL, MAX_ACTIVE_PROJECTS,
    PROJECTS_PER_CYCLE, REPORTS_DIR,
)
from logger import log_event, log_error

# Track which projects have already triggered verification
_verification_triggered: set = set()

# type_id values that support Claude website verification
WEBSITE_VERIFICATION_TYPES = {1}


async def creation_loop():
    """
    Create 1-2 new projects every CREATE_INTERVAL seconds.
    Uses GLM to generate ideas for random project types, then POSTs to backend API.
    """
    while True:
        try:
            active = get_active_projects()
            active_count = len(active)

            if active_count >= MAX_ACTIVE_PROJECTS:
                log_event("CREATE", f"Skipped — {active_count}/{MAX_ACTIVE_PROJECTS} active")
            else:
                for _ in range(PROJECTS_PER_CYCLE):
                    idea = await generate_project_idea()
                    if not idea:
                        log_error("CREATE", "No idea generated, skipping")
                        continue

                    type_id = idea.get("type_id", 1)
                    type_label = idea.get("type_label", "website")

                    project = await create_project(
                        idea["name"],
                        idea["description"],
                        type_id=type_id,
                    )
                    if project:
                        pid = project.get("id")
                        domain = project.get("domain", idea["name"])
                        upsert_project(
                            pid, domain, idea["description"], "creating",
                            type_id=type_id, type_label=type_label,
                        )

        except Exception as e:
            log_error("CREATE", f"Loop error: {e}\n{traceback.format_exc()}")

        await asyncio.sleep(CREATE_INTERVAL)


async def status_loop():
    """
    Poll active projects every STATUS_POLL_INTERVAL seconds.
    When status becomes 'ready', trigger verification (website only)
    or mark as verified directly (bot/scheduler types).
    """
    global _verification_triggered

    while True:
        try:
            active = get_active_projects()
            for proj in active:
                pid = proj["id"]
                current_status = proj["status"]

                # Skip if already triggered verification
                if pid in _verification_triggered:
                    continue

                # Fetch latest status from API
                api_status = await get_project_status(pid)
                if not api_status:
                    continue

                if api_status != current_status:
                    log_event("STATUS", f"id={pid} -> {api_status}")
                    update_status(pid, api_status)

                if api_status == "ready":
                    _verification_triggered.add(pid)

                    type_id = proj.get("type_id", 1)
                    type_label = proj.get("type_label", "website")

                    # Skip Claude verification if SKIP_CLAUDE env is set
                    skip_claude = os.getenv("SKIP_CLAUDE", "false").lower() in ("true", "1", "yes")

                    # Non-website types don't have frontend to verify with Claude
                    if type_id not in WEBSITE_VERIFICATION_TYPES:
                        update_status(pid, "verified")
                        log_event("VERIFY-SKIP", f"id={pid} [{type_label}] (no frontend to verify)")
                        # Still send notification for non-website projects
                        asyncio.create_task(
                            _send_creation_notification(pid, type_label, proj.get("description", ""))
                        )
                        continue

                    if skip_claude:
                        update_status(pid, "verified")
                        log_event("VERIFY-SKIP", f"id={pid} (SKIP_CLAUDE mode)")
                        continue

                    domain = get_project_domain(proj)
                    description = proj.get("description", "")

                    # Fire verification as background task (non-blocking)
                    asyncio.create_task(
                        _run_verification_with_notifications(pid, domain, description)
                    )

                elif api_status == "failed":
                    _verification_triggered.add(pid)
                    log_event("FAILED", f"id={pid}")

        except Exception as e:
            log_error("STATUS", f"Loop error: {e}")

        await asyncio.sleep(STATUS_POLL_INTERVAL)


async def _send_creation_notification(
    project_id: int,
    type_label: str,
    description: str,
):
    """Send notification that a non-website project was created successfully."""
    try:
        msg = f"Project {project_id} [{type_label}] created successfully: {description[:100]}"

        # Send telegram
        await send_telegram(
            project_id,
            score=10,
            verdict="created",
            issues=[],
        )

        # Send discord
        await send_discord(
            project_id,
            score=10,
            verdict="created",
            issues=[],
            security_issues=[],
        )

    except Exception as e:
        log_error("NOTIFY", f"id={project_id} creation notification error: {e}")


async def _run_verification_with_notifications(
    project_id: int,
    domain: str,
    description: str,
):
    """Run verification and send notifications on completion."""
    try:
        await verify_project(project_id, domain, description)

        # Read saved report for notifications
        report_path = REPORTS_DIR / str(project_id) / "report.json"
        if report_path.exists():
            import json
            report = json.loads(report_path.read_text())

            # Send email (sync, in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, send_email, project_id,
                                       report.get("score", 0),
                                       report.get("verdict", "unknown"),
                                       report.get("issues", []),
                                       report.get("security_issues", []))

            # Send telegram (async)
            await send_telegram(
                project_id,
                report.get("score", 0),
                report.get("verdict", "unknown"),
                report.get("issues", []),
            )

            # Send discord (async)
            await send_discord(
                project_id,
                report.get("score", 0),
                report.get("verdict", "unknown"),
                report.get("issues", []),
                report.get("security_issues", []),
            )

    except Exception as e:
        log_error("NOTIFY", f"id={project_id} notification error: {e}")
