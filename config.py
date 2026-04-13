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
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "dreambigwithai.com")

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

# ── Misc ──────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
