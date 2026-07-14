"""
AI QA Tester - SQLite Storage
Tracks projects, verification results, and audit history.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import DB_PATH, REPORTS_DIR
from logger import log_event, log_error

CREATION_IN_PROGRESS_STATUSES = (
    "creating",
    "scaffolded",
    "initializing",
    "building",
    "deploying",
    "verifying",
    "provisioning",
    "infrastructure_provisioning",
    "ai_provisioning",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    domain TEXT,
    description TEXT,
    status TEXT DEFAULT 'creating',
    type_id INTEGER DEFAULT 1,
    type_label TEXT DEFAULT 'website',
    score REAL,
    verdict TEXT,
    issues TEXT,           -- JSON list
    security_issues TEXT,  -- JSON list
    screenshots TEXT,      -- JSON list of file paths
    raw_output TEXT,       -- raw claude output if parse failed
    created_at TEXT,
    verified_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_status ON projects(status);
"""


def _migrate_add_type_columns():
    """Add type_id and type_label columns if they don't exist (migration)."""
    conn = _get_conn()
    try:
        # Check if type_id column exists
        cols = conn.execute("PRAGMA table_info(projects)").fetchall()
        col_names = [c[1] for c in cols]

        if "type_id" not in col_names:
            conn.execute("ALTER TABLE projects ADD COLUMN type_id INTEGER DEFAULT 1")
            conn.commit()
            log_event("DB", "Added type_id column")

        if "type_label" not in col_names:
            conn.execute("ALTER TABLE projects ADD COLUMN type_label TEXT DEFAULT 'website'")
            conn.commit()
            log_event("DB", "Added type_label column")
    finally:
        conn.close()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize database schema."""
    conn = _get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_add_type_columns()
        log_event("DB", f"Database ready at {DB_PATH}")
    finally:
        conn.close()


def upsert_project(
    project_id: int,
    domain: str,
    description: str,
    status: str = "creating",
    type_id: int = 1,
    type_label: str = "website",
) -> None:
    """Insert or update a project."""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO projects (id, domain, description, status, type_id, type_label, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 domain=excluded.domain,
                 description=excluded.description,
                 status=excluded.status,
                 type_id=excluded.type_id,
                 type_label=excluded.type_label
            """,
            (project_id, domain, description, status, type_id, type_label, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def update_status(project_id: int, status: str) -> None:
    """Update project status."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE projects SET status = ? WHERE id = ?",
            (status, project_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_active_projects() -> List[Dict[str, Any]]:
    """Get projects with in-progress statuses."""
    conn = _get_conn()
    try:
        placeholders = ",".join("?" for _ in CREATION_IN_PROGRESS_STATUSES)
        rows = conn.execute(
            f"SELECT * FROM projects WHERE status IN ({placeholders})",
            CREATION_IN_PROGRESS_STATUSES,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_verification(
    project_id: int,
    score: float,
    verdict: str,
    functional: bool,
    pages_ok: bool,
    backend_ok: bool,
    security_ok: bool,
    performance_ok: bool,
    issues: List[str],
    security_issues: List[str],
    screenshots: List[str],
    raw_output: Optional[str] = None,
) -> None:
    """Save verification result."""
    now = datetime.utcnow().isoformat()
    report_dir = REPORTS_DIR / str(project_id)
    report_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "project_id": project_id,
        "score": score,
        "verdict": verdict,
        "functional": functional,
        "pages_ok": pages_ok,
        "backend_ok": backend_ok,
        "security_ok": security_ok,
        "performance_ok": performance_ok,
        "issues": issues,
        "security_issues": security_issues,
        "screenshots": screenshots,
        "verified_at": now,
    }

    report_path = report_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2))

    conn = _get_conn()
    try:
        conn.execute(
            """UPDATE projects SET
                 status = 'verified',
                 score = ?,
                 verdict = ?,
                 issues = ?,
                 security_issues = ?,
                 screenshots = ?,
                 raw_output = ?,
                 verified_at = ?
               WHERE id = ?
            """,
            (
                score,
                verdict,
                json.dumps(issues),
                json.dumps(security_issues),
                json.dumps(screenshots),
                raw_output,
                now,
                project_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    log_event("DB", f"Saved verification for id={project_id}")


def save_parse_failure(project_id: int, raw_output: str) -> None:
    """Store raw output when JSON parsing fails."""
    report_dir = REPORTS_DIR / str(project_id)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "raw_output.txt").write_text(raw_output)

    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE projects SET status = 'parse_failed', raw_output = ?, verified_at = ? WHERE id = ?",
            (raw_output, datetime.utcnow().isoformat(), project_id),
        )
        conn.commit()
    finally:
        conn.close()

    log_event("DB", f"Saved parse failure for id={project_id}")


def get_stats() -> Dict[str, Any]:
    """Get summary stats for CLI report."""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        verified = conn.execute("SELECT COUNT(*) FROM projects WHERE status = 'verified'").fetchone()[0]
        passed = conn.execute("SELECT COUNT(*) FROM projects WHERE verdict = 'pass'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM projects WHERE verdict = 'fail'").fetchone()[0]
        sec_issues = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE security_issues != '[]' AND security_issues IS NOT NULL"
        ).fetchone()[0]
        avg_row = conn.execute("SELECT AVG(score) FROM projects WHERE score IS NOT NULL").fetchone()[0]
        return {
            "total": total,
            "verified": verified,
            "passed": passed,
            "failed": failed,
            "security_issues": sec_issues,
            "avg_score": round(avg_row, 1) if avg_row else 0.0,
        }
    finally:
        conn.close()
