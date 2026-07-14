"""
Product stability suite for DreamAgent.

This is a controlled release test, separate from the random background creator.
It covers:
- New project creation across supported project types.
- Optional create-time environment variables with docs URLs.
- Add-feature/edit session chat through the same backend endpoint as the web UI.
- A JSON report under reports/stability_<timestamp>.json.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    REPORTS_DIR,
    STABILITY_PROJECT_TYPES,
    STABILITY_EDIT_PROJECT_TYPES,
    STABILITY_WAIT_TIMEOUT,
    STABILITY_POLL_INTERVAL,
    STABILITY_RUN_FEATURE_EDIT,
    STABILITY_USE_INITIAL_ENV,
    STABILITY_ENV_VARS,
)
from logger import log_event, log_error
from project_client import (
    create_project,
    create_session,
    get_project_status,
    get_session_messages,
    send_session_message,
)
from storage import upsert_project, update_status


TYPE_LABELS = {
    1: "website",
    2: "telegrambot",
    3: "discordbot",
    5: "scheduler",
}


CREATE_SCENARIOS = {
    1: {
        "name": "qa-premium-site",
        "description": (
            "Create a premium DreamAgent QA website for an AI operations studio. "
            "Include a cinematic hero, feature sections, pricing preview, FAQ, "
            "mobile-first layout, polished interactions, and clear production-ready UI."
        ),
    },
    2: {
        "name": "qa-telegram-helper",
        "description": (
            "Create a Telegram bot that helps a community run daily check-ins. "
            "Include practical commands, helpful onboarding, graceful error handling, "
            "admin-friendly flows, and concise bot responses."
        ),
    },
    3: {
        "name": "qa-discord-control",
        "description": (
            "Create a Discord bot for community moderation and announcements. "
            "Include slash commands, permission checks, logging, welcome events, "
            "and clear responses for failed permissions."
        ),
    },
    5: {
        "name": "qa-daily-brief",
        "description": (
            "Create a scheduler automation that sends a daily operations brief. "
            "Include job configuration, retry behavior, notification channels, "
            "monitoring logs, and failure recovery notes."
        ),
    },
}


FEATURE_PROMPTS = {
    1: (
        "Add a small QA release notes section to the homepage with three polished cards: "
        "Project creation, AI edit sessions, and env integrations. Preserve the existing "
        "visual style and keep the section mobile-friendly."
    ),
    2: (
        "Add a /qa_status command that returns a short health summary, explains whether "
        "required environment variables are configured, and fails gracefully if anything "
        "is missing."
    ),
    3: (
        "Add a /qa_health slash command that reports bot readiness, permissions status, "
        "and configured integration state without exposing secrets."
    ),
    5: (
        "Add a QA heartbeat job example that can run on a short interval and logs a clear "
        "success or failure message without exposing secrets."
    ),
}


TERMINAL_SUCCESS = {"ready", "verified", "running"}
TERMINAL_FAILURE = {"failed", "error", "deleted"}


def _timestamp_suffix() -> str:
    return datetime.utcnow().strftime("%m%d%H%M%S")


def _valid_env_vars() -> List[Dict[str, str]]:
    """Return complete env-var rows only; incomplete rows are reported as skipped."""
    if not STABILITY_USE_INITIAL_ENV:
        return []

    valid = []
    for item in STABILITY_ENV_VARS[:2]:
        key = (item.get("key") or "").strip()
        value = (item.get("value") or "").strip()
        docs_url = (item.get("docs_url") or "").strip()
        description = (item.get("description") or "").strip()
        if key and value and docs_url:
            valid.append({
                "key": key,
                "value": value,
                "docs_url": docs_url,
                "description": description or "QA integration provided during project creation",
            })
        else:
            log_error("STABILITY", f"Skipping incomplete env row: key={bool(key)} value={bool(value)} docs_url={bool(docs_url)}")
    return valid


async def _wait_for_ready(project_id: int) -> Dict[str, Any]:
    started = time.time()
    last_status = None

    while time.time() - started < STABILITY_WAIT_TIMEOUT:
        status = await get_project_status(project_id)
        if status and status != last_status:
            log_event("STABILITY", f"project={project_id} status={status}")
            update_status(project_id, status)
            last_status = status

        if status in TERMINAL_SUCCESS:
            return {"ok": True, "status": status, "elapsed_seconds": round(time.time() - started, 1)}
        if status in TERMINAL_FAILURE:
            return {"ok": False, "status": status, "elapsed_seconds": round(time.time() - started, 1)}

        await asyncio.sleep(STABILITY_POLL_INTERVAL)

    return {"ok": False, "status": last_status or "timeout", "elapsed_seconds": round(time.time() - started, 1)}


def _response_looks_successful(response: Optional[Dict[str, Any]]) -> bool:
    if not response:
        return False
    text = json.dumps(response).lower()
    failure_markers = [
        "could not initialize",
        "error:",
        "traceback",
        "failed",
        "insufficient_credits",
        "session_message_in_progress",
    ]
    return not any(marker in text for marker in failure_markers)


async def _run_feature_edit(project: Dict[str, Any], type_id: int) -> Dict[str, Any]:
    prompt = FEATURE_PROMPTS.get(type_id, FEATURE_PROMPTS[1])
    project_id = int(project["id"])

    session = await create_session(project_id, f"QA add feature {datetime.utcnow().strftime('%H%M%S')}")
    if not session:
        return {"ok": False, "stage": "create_session", "message": "Session creation failed"}

    response = await send_session_message(session["session_key"], prompt, acp_mode=True, mode="dream")
    messages = await get_session_messages(int(session["id"]))
    ok = _response_looks_successful(response) and len(messages) >= 2

    return {
        "ok": ok,
        "stage": "feature_edit",
        "session_id": session.get("id"),
        "session_key": session.get("session_key"),
        "messages_count": len(messages),
        "response_preview": json.dumps(response)[:600] if response else None,
    }


async def run_stability_suite(project_types: Optional[List[int]] = None) -> Dict[str, Any]:
    """Run the release stability suite once and write a JSON report."""
    selected_types = project_types or STABILITY_PROJECT_TYPES
    env_vars = _valid_env_vars()
    suffix = _timestamp_suffix()
    report: Dict[str, Any] = {
        "started_at": datetime.utcnow().isoformat(),
        "project_types": selected_types,
        "env_test_enabled": STABILITY_USE_INITIAL_ENV,
        "env_keys": [item["key"] for item in env_vars],
        "run_feature_edit": STABILITY_RUN_FEATURE_EDIT,
        "results": [],
    }

    log_event("STABILITY", f"Starting suite for types={selected_types}, env_keys={report['env_keys']}")

    for type_id in selected_types:
        scenario = CREATE_SCENARIOS.get(type_id)
        if not scenario:
            report["results"].append({"type_id": type_id, "ok": False, "stage": "scenario", "message": "Unsupported type"})
            continue

        type_label = TYPE_LABELS.get(type_id, f"type_{type_id}")
        name = f"{scenario['name']}-{suffix}"
        result: Dict[str, Any] = {
            "type_id": type_id,
            "type_label": type_label,
            "name": name,
            "created": False,
            "ready": False,
            "feature_edit": None,
        }

        project = await create_project(
            name=name,
            description=scenario["description"],
            type_id=type_id,
            environment_variables=env_vars if env_vars else None,
        )
        if not project:
            result.update({"ok": False, "stage": "create_project", "message": "Project creation failed"})
            report["results"].append(result)
            continue

        result["created"] = True
        result["project_id"] = project.get("id")
        result["domain"] = project.get("domain")
        upsert_project(
            int(project["id"]),
            project.get("domain", name),
            scenario["description"],
            project.get("status", "creating"),
            type_id=type_id,
            type_label=type_label,
        )

        ready = await _wait_for_ready(int(project["id"]))
        result["ready_status"] = ready
        result["ready"] = bool(ready.get("ok"))

        if ready.get("ok") and STABILITY_RUN_FEATURE_EDIT and type_id in STABILITY_EDIT_PROJECT_TYPES:
            result["feature_edit"] = await _run_feature_edit(project, type_id)

        result["ok"] = bool(
            result["created"]
            and result["ready"]
            and (
                not STABILITY_RUN_FEATURE_EDIT
                or type_id not in STABILITY_EDIT_PROJECT_TYPES
                or (result.get("feature_edit") or {}).get("ok")
            )
        )
        report["results"].append(result)

    report["finished_at"] = datetime.utcnow().isoformat()
    report["ok"] = all(item.get("ok") for item in report["results"])

    path = REPORTS_DIR / f"stability_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    Path(path).write_text(json.dumps(report, indent=2))
    log_event("STABILITY", f"Report written: {path}")
    return report
