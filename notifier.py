"""
AI QA Tester - Notifier
Sends QA reports via Email (SMTP), Telegram, and Discord.
"""

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, Any, List

import httpx

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO,
    EMAIL_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED,
    DISCORD_WEBHOOK_URL, DISCORD_ENABLED,
    REPORTS_DIR, BASE_DOMAIN,
)
from logger import log_event, log_error


# ── Email ──────────────────────────────────────────────

def send_email(
    project_id: int,
    score: float,
    verdict: str,
    issues: List[str],
    security_issues: List[str],
) -> bool:
    """Send QA report via SMTP."""
    if not EMAIL_ENABLED:
        return False

    recipients = [addr.strip() for addr in SMTP_TO.split(",")]

    msg = MIMEMultipart()
    msg["Subject"] = f"DreamAgent QA Report - Project #{project_id}"
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(recipients)

    # Plain text fallback
    body = f"""Project #{project_id} QA Report
{'='*40}

Score: {score}/10
Verdict: {verdict.upper()}

Issues:
{chr(10).join(f'  - {i}' for i in issues) if issues else '  None'}

Security Issues:
{chr(10).join(f'  - {i}' for i in security_issues) if security_issues else '  None'}
"""

    # HTML version
    issues_html = "".join(f"<li>{i}</li>" for i in issues) if issues else "<li>None</li>"
    sec_html = "".join(f"<li style='color:#e74c3c'>{i}</li>" for i in security_issues) if security_issues else "<li>None</li>"
    verdict_color = "#27ae60" if verdict == "pass" else "#e74c3c"
    verdict_icon = "✅" if verdict == "pass" else "❌"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; color: white;">
            <h2 style="margin:0;">DreamAgent QA Report</h2>
            <p style="margin:5px 0 0; opacity:0.9;">Project #{project_id}</p>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <table style="width:100%; border-collapse: collapse; margin-bottom: 15px;">
                <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Score</strong></td><td style="padding:8px; border-bottom:1px solid #eee; font-size:18px;">{score}/10</td></tr>
                <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Verdict</strong></td><td style="padding:8px; border-bottom:1px solid #eee; color:{verdict_color}; font-weight:bold;">{verdict_icon} {verdict.upper()}</td></tr>
            </table>
            <h3 style="color:#333;">Issues ({len(issues)})</h3>
            <ul style="background:white; padding:10px 20px; border-radius:6px; border:1px solid #eee;">{issues_html}</ul>
            <h3 style="color:#e74c3c; margin-top:15px;">Security Issues ({len(security_issues)})</h3>
            <ul style="background:white; padding:10px 20px; border-radius:6px; border:1px solid #eee;">{sec_html}</ul>
        </div>
        <div style="padding: 10px 20px; background: #eee; font-size: 12px; color: #888; text-align: center;">
            DreamAgent AI QA System
        </div>
    </div>
    """

    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html, "html"))

    # Attach report.json if exists
    report_path = REPORTS_DIR / str(project_id) / "report.json"
    if report_path.exists():
        try:
            part = MIMEBase("application", "json")
            part.set_payload(report_path.read_bytes())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename=report_{project_id}.json")
            msg.attach(part)
        except Exception as e:
            log_error("EMAIL", f"Failed to attach report: {e}")

    # Attach screenshots
    report_dir = REPORTS_DIR / str(project_id)
    if report_dir.exists():
        for img_file in report_dir.glob("*.png"):
            try:
                part = MIMEBase("image", "png")
                part.set_payload(img_file.read_bytes())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={img_file.name}")
                msg.attach(part)
            except Exception:
                pass

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, recipients, msg.as_string())
        log_event("EMAIL", "sent")
        return True
    except Exception as e:
        log_error("EMAIL", f"Failed: {e}")
        return False


# ── Telegram ───────────────────────────────────────────

async def send_telegram(
    project_id: int,
    score: float,
    verdict: str,
    issues: List[str],
) -> bool:
    """Send QA summary + screenshots via Telegram Bot API."""
    if not TELEGRAM_ENABLED:
        return False

    text = (
        f"📋 *Project #{project_id} Verified*\n\n"
        f"Score: {score}/10\n"
        f"Verdict: {'✅ PASS' if verdict == 'pass' else '❌ FAIL'}\n"
    )
    if issues:
        text += f"\nIssues ({len(issues)}):\n"
        for i in issues[:5]:
            text += f"  • {i}\n"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Send text message
            await client.post(
                "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN),
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )

            # Send screenshots
            report_dir = REPORTS_DIR / str(project_id)
            if report_dir.exists():
                for img_file in sorted(report_dir.glob("*.png"))[:3]:
                    try:
                        await client.post(
                            "https://api.telegram.org/bot{}/sendPhoto".format(TELEGRAM_BOT_TOKEN),
                            data={
                                "chat_id": TELEGRAM_CHAT_ID,
                                "caption": f"Screenshot: {img_file.name}",
                            },
                            files={"photo": (img_file.name, img_file.read_bytes(), "image/png")},
                        )
                    except Exception:
                        pass

        log_event("TELEGRAM", "sent")
        return True

    except Exception as e:
        log_error("TELEGRAM", f"Failed: {e}")
        return False


# ── Discord ────────────────────────────────────────────

async def send_discord(
    project_id: int,
    score: float,
    verdict: str,
    issues: List[str],
    security_issues: List[str],
) -> bool:
    """Send QA report via Discord webhook."""
    if not DISCORD_ENABLED:
        return False

    verdict_color = 0x27AE60 if verdict == "pass" else 0xE74C3C  # green / red
    verdict_icon = "✅" if verdict == "pass" else "❌"

    fields = [
        {"name": "Score", "value": f"{score}/10", "inline": True},
        {"name": "Verdict", "value": f"{verdict_icon} {verdict.upper()}", "inline": True},
    ]

    if issues:
        issues_text = "\n".join(f"• {i}" for i in issues[:5])
        if len(issues) > 5:
            issues_text += f"\n... and {len(issues)-5} more"
        fields.append({"name": f"Issues ({len(issues)})", "value": issues_text, "inline": False})

    if security_issues:
        sec_text = "\n".join(f"• {i}" for i in security_issues[:5])
        fields.append({"name": f"🔒 Security ({len(security_issues)})", "value": sec_text, "inline": False})

    # Attach screenshots as files
    files = []
    report_dir = REPORTS_DIR / str(project_id)
    if report_dir.exists():
        for img_file in sorted(report_dir.glob("*.png"))[:3]:
            try:
                files.append({
                    "name": img_file.name,
                    "data": img_file.read_bytes(),
                })
            except Exception:
                pass

    payload = {
        "username": "DreamAgent QA",
        "embeds": [{
            "title": f"📋 QA Report — Project #{project_id}",
            "color": verdict_color,
            "fields": fields,
            "footer": {"text": "DreamAgent AI QA System"},
        }],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if files:
                # Multipart upload with files
                import io
                form_data = {}
                form_data["payload_json"] = json.dumps(payload)
                file_objects = []
                for i, f in enumerate(files):
                    file_objects.append(
                        ("files[{i}]", (f["name"], io.BytesIO(f["data"]), "image/png"))
                    )
                await client.post(
                    DISCORD_WEBHOOK_URL,
                    data=form_data,
                    files=file_objects,
                )
            else:
                await client.post(DISCORD_WEBHOOK_URL, json=payload)

        log_event("DISCORD", "sent")
        return True

    except Exception as e:
        log_error("DISCORD", f"Failed: {e}")
        return False
