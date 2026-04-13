"""
AI QA Tester - Claude Code Runner
Thin wrapper around ClaudeCodeAgent for running QA verification prompts.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from claude_code_agent import ClaudeCodeAgent
from config import CLAUDE_CMD, CLAUDE_TIMEOUT, REPORTS_DIR
from logger import log_event, log_error

VERIFICATION_PROMPT = """You are a senior QA engineer and UX auditor.

Open: {domain}

Use devtools MCP.

Perform:

FUNCTIONAL:
- Page loads without errors
- No blank UI or placeholder content
- Navigation works between all pages
- Matches this description:
{description}

PAGE-BY-PAGE UX VALIDATION:
- Visit EVERY page listed in the description
- For each page verify:
  - Layout matches the described components
  - Key elements are visible and interactive
  - Data/charts/content renders correctly
  - Responsive layout (no horizontal overflow)
  - Micro-interactions and hover states work
  - Proper loading states

BACKEND:
- GET /api/health → must return 200

PAGES:
- Discover routes
- Visit each page
- No 404 or blank pages

SECURITY:
- No API keys exposed
- No secrets in frontend JS
- No unsafe localStorage
- No open debug/admin endpoints
- No sensitive console logs
- Check CORS issues

SNAPSHOTS:
- Capture screenshots:
  - Home page
  - At least 2 internal pages

PERFORMANCE:
- Basic load check

Save screenshots to: {screenshot_dir}

Return STRICT JSON (and nothing else):
{{
  "score": 1-10,
  "verdict": "pass" or "fail",
  "functional": true/false,
  "pages_ok": true/false,
  "pages_visited": ["Home", "Dashboard", "Settings", "Profile"],
  "page_scores": {{
    "Home": {{"ok": true, "issues": []}},
    "Dashboard": {{"ok": true, "issues": []}},
    "Settings": {{"ok": true, "issues": []}},
    "Profile": {{"ok": true, "issues": []}}
  }},
  "backend_ok": true/false,
  "security_issues": [],
  "performance_ok": true/false,
  "ux_score": 1-10,
  "issues": [],
  "screenshots": ["home.png", "page1.png", "page2.png", "page3.png"]
}}"""


async def run_verification(
    project_id: int,
    domain: str,
    description: str,
) -> Optional[str]:
    """
    Run Claude Code verification against a deployed project.

    Args:
        project_id: The project database ID
        domain: Full URL (https://project.dreambigwithai.com)
        description: Project description to verify against

    Returns:
        Raw text output from Claude, or None on failure.
    """
    screenshot_dir = str(REPORTS_DIR / str(project_id))

    prompt = VERIFICATION_PROMPT.format(
        domain=domain,
        description=description,
        screenshot_dir=screenshot_dir,
    )

    log_event("VERIFY-START", f"id={project_id}")

    # Use a temp working directory for claude
    work_dir = str(REPORTS_DIR / str(project_id))
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    try:
        async with ClaudeCodeAgent(
            repo_path=work_dir,
            claude_path=CLAUDE_CMD if CLAUDE_CMD != "claude" else None,
        ) as agent:
            result = await agent.query(prompt, timeout=CLAUDE_TIMEOUT)
            return result

    except asyncio.TimeoutError:
        log_error("VERIFY", f"id={project_id} timed out after {CLAUDE_TIMEOUT}s")
        return None
    except Exception as e:
        log_error("VERIFY", f"id={project_id} error: {e}")
        return None
