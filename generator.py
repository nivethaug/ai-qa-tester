"""
AI QA Tester - Project Idea Generator
Uses GLM API to generate real-world app ideas for testing.
Supports all project types: website, telegrambot, discordbot, scheduler.
"""

import json
import random
import httpx
from typing import Optional, Dict, Any

from config import Z_AI_API_KEY, Z_AI_API_BASE, Z_AI_MODEL, ENABLED_PROJECT_TYPES
from logger import log_event, log_error

# type_id -> (label, prompt instruction)
TYPE_CONFIG = {
    "1": {
        "label": "website",
        "prompt": "Generate a creative web app idea for QA testing. Include 4 pages (home + 3 internal) with layouts, components and interactions.",
    },
    "2": {
        "label": "telegrambot",
        "prompt": "Generate a creative Telegram bot idea for QA testing. Include bot commands, inline keyboards, webhook handlers, and user interaction flows.",
    },
    "3": {
        "label": "discordbot",
        "prompt": "Generate a creative Discord bot idea for QA testing. Include slash commands, event handlers, moderation features, and server management capabilities.",
    },
    "5": {
        "label": "scheduler",
        "prompt": "Generate a creative scheduled automation idea for QA testing. Include what data to fetch (crypto, weather, news, stocks, etc), how often, and which channels to send to (telegram, discord, email).",
    },
}

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


def pick_random_type() -> str:
    """Pick a random project type_id from enabled types."""
    return random.choice(ENABLED_PROJECT_TYPES)


async def generate_project_idea(type_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Generate project idea for a given type via GLM.
    If type_id is None, picks a random enabled type.

    Returns dict with: name, description, type_id, type_label
    """
    if not Z_AI_API_KEY:
        log_error("GENERATOR", "Z_AI_API_KEY not configured")
        return None

    if not type_id:
        type_id = pick_random_type()

    cfg = TYPE_CONFIG.get(type_id, TYPE_CONFIG["1"])
    type_label = cfg["label"]

    prompt = f"""{cfg['prompt']}
Reply JSON only:
{{"name":"kebab-case-name","description":"Full description with features and functionality"}}
Rules: max 30 char name, creative and specific app, detailed description."""

    messages = [
        {"role": "system", "content": "You output valid JSON only. No explanation."},
        {"role": "user", "content": prompt},
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

    idea["type_id"] = int(type_id)
    idea["type_label"] = type_label

    log_event("GENERATOR", f"[{type_label}] Idea: {idea['name']} - {idea['description'][:80]}...")
    return idea
