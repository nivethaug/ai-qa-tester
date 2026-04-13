"""
AI QA Tester - Backend API Client
Creates projects and polls their status via the DreamAgent backend API.
"""

import httpx
from typing import Optional, Dict, Any

from config import BACKEND_URL, DEFAULT_USER_ID, DEFAULT_TEMPLATE_ID, BASE_DOMAIN
from logger import log_event, log_error

TIMEOUT = 30.0


async def create_project(name: str, description: str) -> Optional[Dict[str, Any]]:
    """
    POST /projects — create a new website project.
    Returns the project dict with id, domain, status, etc.
    """
    payload = {
        "name": name,
        "description": description,
        "user_id": DEFAULT_USER_ID,
        "type_id": 1,
        "template_id": DEFAULT_TEMPLATE_ID,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{BACKEND_URL}/projects",
                json=payload,
            )
            resp.raise_for_status()
            project = resp.json()

            pid = project.get("id")
            domain = project.get("domain", name)
            log_event("CREATE", f"id={pid} domain={domain}")
            return project

    except httpx.HTTPStatusError as e:
        log_error("CREATE", f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        log_error("CREATE", f"Failed: {e}")

    return None


async def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    """GET /projects/{id} — fetch a single project."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{BACKEND_URL}/projects/{project_id}")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        log_error("API", f"GET /projects/{project_id} failed: {e}")
        return None


async def get_project_status(project_id: int) -> Optional[str]:
    """GET /projects/{id}/status — fetch just the status field."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{BACKEND_URL}/projects/{project_id}/status")
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
