"""
AI QA Tester - Backend API Client
Creates projects and polls their status via the DreamAgent backend API.
Supports active project types: website, telegrambot, discordbot, scheduler.
"""

import httpx
import json
from typing import Optional, Dict, Any

from config import (
    BACKEND_URL, BACKEND_AUTH_TOKEN, DEFAULT_USER_ID, DEFAULT_TEMPLATE_ID, BASE_DOMAIN,
    TEST_TELEGRAM_BOT_TOKEN, TEST_DISCORD_BOT_TOKEN,
    TEST_SCHEDULER_TELEGRAM_TOKEN, TEST_SCHEDULER_CHAT_ID,
    TEST_SCHEDULER_DISCORD_WEBHOOK, TEST_SCHEDULER_EMAIL_TO,
)
from logger import log_event, log_error

TIMEOUT = 30.0
CHAT_TIMEOUT = 1200.0


def _auth_headers() -> Optional[Dict[str, str]]:
    """Return auth headers required by current backend project routes."""
    if not BACKEND_AUTH_TOKEN:
        log_error("API", "BACKEND_AUTH_TOKEN or AUTH_TOKEN is required for authenticated backend routes")
        return None
    return {"Authorization": f"Bearer {BACKEND_AUTH_TOKEN}"}


def _build_payload(
    name: str,
    description: str,
    type_id: int,
    environment_variables: Optional[list[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Build creation payload with type-specific fields."""
    payload = {
        "name": name,
        "description": description,
        # Current backend derives user_id from Authorization; keep this only for
        # compatibility with older local builds that still accept it.
        "user_id": DEFAULT_USER_ID,
        "type_id": type_id,
    }

    if type_id == 1:
        payload["template_id"] = DEFAULT_TEMPLATE_ID

    elif type_id == 2:
        if not TEST_TELEGRAM_BOT_TOKEN:
            log_error("CREATE", "TEST_TELEGRAM_BOT_TOKEN not configured, skipping telegram bot")
            return None
        payload["bot_token"] = TEST_TELEGRAM_BOT_TOKEN

    elif type_id == 3:
        if not TEST_DISCORD_BOT_TOKEN:
            log_error("CREATE", "TEST_DISCORD_BOT_TOKEN not configured, skipping discord bot")
            return None
        payload["bot_token"] = TEST_DISCORD_BOT_TOKEN

    elif type_id == 5:
        if TEST_SCHEDULER_TELEGRAM_TOKEN and TEST_SCHEDULER_CHAT_ID:
            payload["telegram_bot_token"] = TEST_SCHEDULER_TELEGRAM_TOKEN
            payload["telegram_chat_id"] = TEST_SCHEDULER_CHAT_ID
        if TEST_SCHEDULER_DISCORD_WEBHOOK:
            payload["discord_webhook_url"] = TEST_SCHEDULER_DISCORD_WEBHOOK
        if TEST_SCHEDULER_EMAIL_TO:
            payload["email_to"] = TEST_SCHEDULER_EMAIL_TO

        has_channel = any([
            payload.get("telegram_bot_token"),
            payload.get("discord_webhook_url"),
            payload.get("email_to"),
        ])
        if not has_channel:
            log_error("CREATE", "No scheduler sender channels configured, skipping scheduler")
            return None

    if environment_variables:
        payload["environment_variables"] = environment_variables[:2]

    return payload


async def create_project(
    name: str,
    description: str,
    type_id: int = 1,
    environment_variables: Optional[list[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    POST /projects - create a new project of any active supported type.
    Returns the project dict with id, domain, status, etc.
    """
    payload = _build_payload(name, description, type_id, environment_variables=environment_variables)
    if not payload:
        return None

    headers = _auth_headers()
    if not headers:
        return None

    type_labels = {1: "website", 2: "telegrambot", 3: "discordbot", 5: "scheduler"}
    type_label = type_labels.get(type_id, f"type_{type_id}")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{BACKEND_URL}/projects",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            project = resp.json()

            pid = project.get("id")
            domain = project.get("domain", name)
            log_event("CREATE", f"[{type_label}] id={pid} domain={domain}")
            return project

    except httpx.HTTPStatusError as e:
        log_error("CREATE", f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        log_error("CREATE", f"Failed: {e}")

    return None


async def list_sessions(project_id: int) -> list[Dict[str, Any]]:
    """GET /projects/{id}/sessions."""
    headers = _auth_headers()
    if not headers:
        return []

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{BACKEND_URL}/projects/{project_id}/sessions", headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        log_error("SESSION", f"GET /projects/{project_id}/sessions failed: {e}")
        return []


async def create_session(project_id: int, label: str) -> Optional[Dict[str, Any]]:
    """POST /projects/{id}/sessions."""
    headers = _auth_headers()
    if not headers:
        return None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{BACKEND_URL}/projects/{project_id}/sessions",
                json={"label": label, "project_id": project_id},
                headers=headers,
            )
            resp.raise_for_status()
            session = resp.json()
            log_event("SESSION", f"Created session id={session.get('id')} project={project_id}")
            return session
    except httpx.HTTPStatusError as e:
        log_error("SESSION", f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        log_error("SESSION", f"Create session failed: {e}")
    return None


async def send_session_message(
    session_key: str,
    message: str,
    mode: str = "dream",
    acp_mode: bool = True,
    stream: bool = True,
) -> Optional[Dict[str, Any]]:
    """POST /chat using the same session chat endpoint as the web editor."""
    headers = _auth_headers()
    if not headers:
        return None

    payload = {
        "session_key": session_key,
        "messages": [{"role": "user", "content": message}],
        "stream": stream,
        "acp_mode": acp_mode,
        "mode": mode,
    }

    try:
        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT) as client:
            if not stream:
                resp = await client.post(f"{BACKEND_URL}/chat", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                log_event("CHAT", f"Session message completed key={session_key} bytes={len(json.dumps(data))}")
                return data

            chunks = []
            errors = []
            async with client.stream("POST", f"{BACKEND_URL}/chat", json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[len("data:"):].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        chunks.append(raw)
                        continue

                    if event.get("error"):
                        errors.append(str(event["error"]))
                        continue

                    choices = event.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            chunks.append(content)

            content = "".join(chunks).strip()
            data = {
                "id": 0,
                "role": "assistant",
                "content": content,
                "stream": True,
                "errors": errors,
            }
            log_event("CHAT", f"Streaming session message completed key={session_key} chars={len(content)} errors={len(errors)}")
            return data
    except httpx.HTTPStatusError as e:
        log_error("CHAT", f"HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        error_text = f"{type(e).__name__}: {repr(e)}"
        log_error("CHAT", f"Session message failed: {error_text}")
        return {
            "id": 0,
            "role": "assistant",
            "content": "",
            "stream": stream,
            "transport_error": True,
            "errors": [error_text],
        }
    return None


async def get_session_messages(session_id: int) -> list[Dict[str, Any]]:
    """GET /sessions/{id}/messages."""
    headers = _auth_headers()
    if not headers:
        return []

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{BACKEND_URL}/sessions/{session_id}/messages", headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        log_error("SESSION", f"GET /sessions/{session_id}/messages failed: {e}")
    return []


async def release_session_lock(session_id: int) -> bool:
    """POST /sessions/{id}/release-lock so QA runs do not leave projects blocked."""
    headers = _auth_headers()
    if not headers:
        return False

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(f"{BACKEND_URL}/sessions/{session_id}/release-lock", headers=headers)
            resp.raise_for_status()
            log_event("SESSION", f"Released session lock id={session_id}")
            return True
    except httpx.HTTPStatusError as e:
        log_error("SESSION", f"Release lock HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        log_error("SESSION", f"Release lock failed for {session_id}: {e}")
    return False


async def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    """Resolve one project from the authenticated GET /projects list."""
    headers = _auth_headers()
    if not headers:
        return None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{BACKEND_URL}/projects", headers=headers)
            resp.raise_for_status()
            for project in resp.json():
                if int(project.get("id", 0)) == int(project_id):
                    return project
            log_error("API", f"Project {project_id} not found in authenticated project list")
    except Exception as e:
        log_error("API", f"GET /projects failed while resolving {project_id}: {e}")
    return None


async def get_project_status(project_id: int) -> Optional[str]:
    """GET /projects/{id}/status - fetch just the status field."""
    headers = _auth_headers()
    if not headers:
        return None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{BACKEND_URL}/projects/{project_id}/status", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("status")
    except Exception as e:
        log_error("API", f"GET /projects/{project_id}/status failed: {e}")
        return None


def get_project_domain(project: Dict[str, Any]) -> str:
    """Build full domain URL from project data."""
    domain = project.get("domain", "")
    if domain and BASE_DOMAIN:
        return f"https://{domain}.{BASE_DOMAIN}"
    return ""
