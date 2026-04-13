"""
AI QA Tester - Project Idea Generator
Uses GLM API to generate real-world app ideas for testing.
"""

import json
import httpx
from typing import Optional, Dict, Any

from config import Z_AI_API_KEY, Z_AI_API_BASE, Z_AI_MODEL
from logger import log_event, log_error

IDEA_PROMPT = """Generate a creative web app idea for QA testing. Reply JSON only:
{"name":"kebab-case-name","description":"Full app description including 4 pages (home + 3 internal) with their layouts, components and interactions"}
Rules: max 30 char name, creative SaaS/dashboard/automation app, specific UX details in description."""

TIMEOUT = 60.0
MAX_TOKENS = 4096


async def _call_glm(messages: list) -> Optional[str]:
    """Single GLM API call. Returns content string or None."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{Z_AI_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {Z_AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": Z_AI_MODEL,
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": MAX_TOKENS,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    finish = data["choices"][0].get("finish_reason", "")
    usage = data.get("usage", {})
    if not content:
        log_error("GENERATOR", f"Empty content (finish={finish}, tokens={usage})")
        return None
    return content


def _extract_json(content: str) -> Optional[dict]:
    """Extract JSON from content, handling markdown code blocks."""
    content = content.strip()
    if "```" in content:
        lines = content.split("\n")
        json_lines = []
        inside = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                if inside:
                    break  # closing ```
                inside = True
                continue  # skip opening ``` or ```json
            if inside:
                json_lines.append(line)
        content = "\n".join(json_lines).strip()
    return json.loads(content)


async def generate_project_idea() -> Optional[Dict[str, Any]]:
    """Generate project idea with page details in description via single GLM call."""
    if not Z_AI_API_KEY:
        log_error("GENERATOR", "Z_AI_API_KEY not configured")
        return None

    messages = [
        {"role": "system", "content": "You output valid JSON only. No explanation."},
        {"role": "user", "content": IDEA_PROMPT},
    ]

    content = await _call_glm(messages)
    if not content:
        return None

    try:
        idea = _extract_json(content)
        assert "name" in idea and "description" in idea
    except Exception:
        log_error("GENERATOR", f"Failed to parse idea: {repr(content[:200])}")
        return None

    log_event("GENERATOR", f"Idea: {idea['name']} - {idea['description'][:80]}...")
    return idea
