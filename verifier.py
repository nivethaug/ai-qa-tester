"""
AI QA Tester - Verifier
Orchestrates verification: runs Claude, parses result, stores in DB.
"""

import asyncio
import json
import re
from typing import Optional, Dict, Any

from claude_runner import run_verification
from config import VERIFY_RETRIES, VERIFY_DELAY
from storage import save_verification, save_parse_failure, update_status
from logger import log_event, log_error


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object from Claude's raw text output.
    Handles markdown code blocks and surrounding text.
    """
    if not text:
        return None

    # Try to find JSON in code block
    json_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_block:
        try:
            return json.loads(json_block.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_match = re.search(r"\{[^{}]*\"score\"[^{}]*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Last resort: try the whole text
    cleaned = text.strip()
    if cleaned.startswith("{"):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    return None


async def verify_project(
    project_id: int,
    domain: str,
    description: str,
) -> None:
    """
    Run full verification pipeline for a project.
    Retries on failure, stores result or raw output.
    """
    update_status(project_id, "verifying")

    raw_output = None

    for attempt in range(1, VERIFY_RETRIES + 2):  # 1 initial + retries
        try:
            result = await run_verification(project_id, domain, description)

            if not result:
                log_error("VERIFY", f"id={project_id} no output (attempt {attempt})")
                if attempt <= VERIFY_RETRIES:
                    await asyncio.sleep(VERIFY_DELAY)
                    continue
                save_parse_failure(project_id, "No output from Claude")
                return

            raw_output = result
            parsed = _extract_json(result)

            if not parsed:
                log_error("VERIFY", f"id={project_id} JSON parse failed (attempt {attempt})")
                if attempt <= VERIFY_RETRIES:
                    await asyncio.sleep(VERIFY_DELAY)
                    continue
                save_parse_failure(project_id, raw_output)
                return

            # Valid result — store it
            score = float(parsed.get("score", 0))
            verdict = "pass" if parsed.get("verdict", "").lower() == "pass" else "fail"
            issues = parsed.get("issues", [])
            security_issues = parsed.get("security_issues", [])
            screenshots = parsed.get("screenshots", [])

            if score >= 6:
                verdict = "pass"

            # Log security issues individually
            for sec in security_issues:
                log_event("SECURITY", f"id={project_id} {sec}")

            save_verification(
                project_id=project_id,
                score=score,
                verdict=verdict,
                functional=parsed.get("functional", False),
                pages_ok=parsed.get("pages_ok", False),
                backend_ok=parsed.get("backend_ok", False),
                security_ok=len(security_issues) == 0,
                performance_ok=parsed.get("performance_ok", False),
                issues=issues,
                security_issues=security_issues,
                screenshots=screenshots,
                raw_output=raw_output,
            )

            log_event("VERIFY-DONE", f"id={project_id} score={score} {verdict.upper()}")
            return

        except Exception as e:
            log_error("VERIFY", f"id={project_id} exception (attempt {attempt}): {e}")
            if attempt <= VERIFY_RETRIES:
                await asyncio.sleep(VERIFY_DELAY)
                continue
            save_parse_failure(project_id, str(e))
            return
