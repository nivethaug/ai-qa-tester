"""
AI QA Tester - Configuration
All settings loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env before reading any env vars
load_dotenv()

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DB_PATH = BASE_DIR / "qa_tester.db"

# ── Backend API ────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8002")
BACKEND_AUTH_TOKEN = os.getenv("BACKEND_AUTH_TOKEN", os.getenv("AUTH_TOKEN", ""))
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "dreamagent.cloud")

# ── LLM (GLM for project idea generation) ──────────────
Z_AI_API_KEY = os.getenv("Z_AI_API_KEY", "")
Z_AI_API_BASE = os.getenv("Z_AI_API_BASE", "https://api.z.ai/api/coding/paas/v4")
Z_AI_MODEL = os.getenv("Z_AI_MODEL", "GLM-4.5-Air")

# ── Claude Code ────────────────────────────────────────
CLAUDE_CMD = os.getenv("CLAUDE_CMD", "claude")
CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "600"))  # 10 minutes

# ── Scheduler ──────────────────────────────────────────
CREATE_INTERVAL = int(os.getenv("CREATE_INTERVAL", "900"))     # 15 min
STATUS_POLL_INTERVAL = int(os.getenv("STATUS_POLL_INTERVAL", "12"))  # 12 sec
MAX_ACTIVE_PROJECTS = int(os.getenv("MAX_ACTIVE_PROJECTS", "15"))
PROJECTS_PER_CYCLE = int(os.getenv("PROJECTS_PER_CYCLE", "1"))

# ── Verification ───────────────────────────────────────
VERIFY_RETRIES = int(os.getenv("VERIFY_RETRIES", "2"))
VERIFY_DELAY = int(os.getenv("VERIFY_DELAY", "30"))  # seconds between retries

# ── SMTP (Email) ──────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TO = os.getenv("SMTP_TO", "")  # comma-separated

EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASS and SMTP_TO)

# ── Telegram ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# ── Discord ───────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

DISCORD_ENABLED = bool(DISCORD_WEBHOOK_URL)

# ── Project Creation ──────────────────────────────────
DEFAULT_USER_ID = int(os.getenv("DEFAULT_USER_ID", "1"))
DEFAULT_TEMPLATE_ID = os.getenv("DEFAULT_TEMPLATE_ID", "blank-template")

# ── Project Types ─────────────────────────────────────
# Enable/disable project types for random testing
# type_id: 1=website, 2=telegrambot, 3=discordbot, 5=scheduler
ENABLED_PROJECT_TYPES = [
    t.strip()
    for t in os.getenv("ENABLED_PROJECT_TYPES", "1,2,3,5").split(",")
    if t.strip().isdigit()
]

# ── Test Credentials (for bot/scheduler creation) ──────
# Telegram bot projects need a bot token
TEST_TELEGRAM_BOT_TOKEN = os.getenv("TEST_TELEGRAM_BOT_TOKEN", "")

# Discord bot projects need a bot token
TEST_DISCORD_BOT_TOKEN = os.getenv("TEST_DISCORD_BOT_TOKEN", "")

# Scheduler projects need sender channels
TEST_SCHEDULER_TELEGRAM_TOKEN = os.getenv("TEST_SCHEDULER_TELEGRAM_TOKEN", TELEGRAM_BOT_TOKEN)
TEST_SCHEDULER_CHAT_ID = os.getenv("TEST_SCHEDULER_CHAT_ID", TELEGRAM_CHAT_ID)
TEST_SCHEDULER_DISCORD_WEBHOOK = os.getenv("TEST_SCHEDULER_DISCORD_WEBHOOK", DISCORD_WEBHOOK_URL)
TEST_SCHEDULER_EMAIL_TO = os.getenv("TEST_SCHEDULER_EMAIL_TO", SMTP_TO.split(",")[0] if SMTP_TO else "")

# ── Misc ──────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Product stability suite
# Explicit release-style suite. It creates projects, waits for readiness, then
# optionally runs one add-feature session against each created project.
STABILITY_PROJECT_TYPES = [
    int(t.strip())
    for t in os.getenv("STABILITY_PROJECT_TYPES", "1,2,3,5").split(",")
    if t.strip().isdigit()
]
STABILITY_EDIT_PROJECT_TYPES = [
    int(t.strip())
    for t in os.getenv("STABILITY_EDIT_PROJECT_TYPES", "1,2,3,5").split(",")
    if t.strip().isdigit()
]
STABILITY_WAIT_TIMEOUT = int(os.getenv("STABILITY_WAIT_TIMEOUT", "2400"))
STABILITY_POLL_INTERVAL = int(os.getenv("STABILITY_POLL_INTERVAL", "20"))
STABILITY_RUN_FEATURE_EDIT = os.getenv("STABILITY_RUN_FEATURE_EDIT", "true").lower() in ("true", "1", "yes")
STABILITY_USE_INITIAL_ENV = os.getenv("STABILITY_USE_INITIAL_ENV", "false").lower() in ("true", "1", "yes")

# Up to two generic create-time env vars. Docs URL is required by DreamAgent
# creation rules so Project AI can verify the integration before using it.
STABILITY_ENV_VARS = []
for _idx in ("1", "2"):
    _key = os.getenv(f"STABILITY_ENV{_idx}_KEY", "").strip()
    _value = os.getenv(f"STABILITY_ENV{_idx}_VALUE", "").strip()
    _docs_url = os.getenv(f"STABILITY_ENV{_idx}_DOCS_URL", "").strip()
    _description = os.getenv(f"STABILITY_ENV{_idx}_DESCRIPTION", "").strip()
    if _key or _value or _docs_url or _description:
        STABILITY_ENV_VARS.append({
            "key": _key,
            "value": _value,
            "docs_url": _docs_url,
            "description": _description,
        })
