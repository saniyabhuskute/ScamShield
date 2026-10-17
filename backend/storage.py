"""SQLite persistence for scan history, insights, and user feedback."""

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 3


class DatabaseError(RuntimeError):
    """Raised when ScamShield cannot safely read or write its local database."""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=15)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 15000")
            return connection
        except sqlite3.Error as exc:
            raise DatabaseError("The local ScamShield database could not be opened.") from exc

    def initialize(self) -> None:
        """Create the schema and apply forward-only, versioned migrations."""
        try:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = NORMAL")
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise DatabaseError(
                        f"Database schema version {version} is newer than this ScamShield backend supports."
                    )
                if version == 0:
                    connection.executescript("""
                        CREATE TABLE IF NOT EXISTS scans (
                            id TEXT PRIMARY KEY,
                            message TEXT NOT NULL,
                            language TEXT NOT NULL,
                            requested_language TEXT NOT NULL,
                            risk TEXT NOT NULL CHECK (risk IN ('High', 'Medium', 'Low')),
                            score REAL CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
                            signals_json TEXT NOT NULL,
                            urls_json TEXT NOT NULL,
                            mode TEXT NOT NULL,
                            analysis_status TEXT NOT NULL,
                            notice TEXT NOT NULL,
                            recommendation TEXT NOT NULL,
                            translated_message TEXT,
                            model_label TEXT,
                            score_kind TEXT,
                            created_at TEXT NOT NULL,
                            language_confidence REAL
                        );
                        CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at DESC);
                        CREATE TABLE IF NOT EXISTS feedback (
                            scan_id TEXT PRIMARY KEY REFERENCES scans(id) ON DELETE CASCADE,
                            helpful TEXT NOT NULL CHECK (helpful IN ('yes', 'somewhat', 'no')),
                            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                # Version 2 stores translations; version 3 stores classifier output.
                # This inspection also upgrades databases created before schema versioning.
                columns = {row["name"] for row in connection.execute("PRAGMA table_info(scans)")}
                for column in ("translated_message", "model_label", "score_kind"):
                    if column not in columns:
                        connection.execute(f"ALTER TABLE scans ADD COLUMN {column} TEXT")
                connection.executescript("""
                    CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at DESC);
                    CREATE TABLE IF NOT EXISTS feedback (
                        scan_id TEXT PRIMARY KEY REFERENCES scans(id) ON DELETE CASCADE,
                        helpful TEXT NOT NULL CHECK (helpful IN ('yes', 'somewhat', 'no')),
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except DatabaseError:
            raise
        except sqlite3.Error as exc:
            raise DatabaseError("The local ScamShield database could not be initialized.") from exc

    def health(self) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                check = connection.execute("PRAGMA quick_check").fetchone()[0]
                version = connection.execute("PRAGMA user_version").fetchone()[0]
            if check != "ok" or version != SCHEMA_VERSION:
                raise DatabaseError("The local ScamShield database is unhealthy or has not been initialized.")
            return {"status": "ok", "engine": "sqlite", "schema_version": version}
        except DatabaseError:
            raise
        except sqlite3.Error as exc:
            raise DatabaseError("The local ScamShield database health check failed.") from exc

    def save_scan(self, scan: dict[str, Any]) -> None:
        try:
            with self._connect() as connection:
                connection.execute("""
                    INSERT INTO scans (
                        id, message, language, requested_language, risk, score,
                        signals_json, urls_json, mode, analysis_status, notice,
                        recommendation, translated_message, model_label, score_kind,
                        created_at, language_confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scan["id"], scan["message"], scan["language"], scan["requested_language"],
                    scan["risk"], scan["score"], json.dumps(scan["signals"], ensure_ascii=False),
                    json.dumps(scan["urls"], ensure_ascii=False), scan["mode"], scan["analysis_status"],
                    scan["notice"], scan["recommendation"], scan.get("translated_message"),
                    scan.get("model_label"), scan.get("score_kind"), scan["created_at"],
                    scan["language_confidence"],
                ))
        except sqlite3.Error as exc:
            raise DatabaseError("The scan was analyzed but could not be saved to local history.") from exc

    def list_scans(self, limit: int) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM scans ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
                ).fetchall()
            return [self._scan_dict(row) for row in rows]
        except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise DatabaseError("Scan history could not be read from the local database.") from exc

    def insights(self) -> dict[str, int]:
        try:
            with self._connect() as connection:
                counts = connection.execute("""
                    SELECT COUNT(*) AS total,
                        SUM(CASE WHEN risk = 'High' THEN 1 ELSE 0 END) AS high,
                        SUM(CASE WHEN risk = 'Medium' THEN 1 ELSE 0 END) AS medium,
                        SUM(CASE WHEN risk = 'Low' THEN 1 ELSE 0 END) AS low
                    FROM scans
                """).fetchone()
                feedback_total = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            return {
                "total": counts["total"] or 0, "high": counts["high"] or 0,
                "medium": counts["medium"] or 0, "low": counts["low"] or 0,
                "feedback_total": feedback_total,
            }
        except sqlite3.Error as exc:
            raise DatabaseError("Security insights could not be read from the local database.") from exc

    def save_feedback(self, scan_id: str, helpful: str) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if not connection.execute("SELECT 1 FROM scans WHERE id = ?", (scan_id,)).fetchone():
                    return False
                connection.execute("""
                    INSERT INTO feedback (scan_id, helpful) VALUES (?, ?)
                    ON CONFLICT(scan_id) DO UPDATE
                    SET helpful = excluded.helpful, created_at = CURRENT_TIMESTAMP
                """, (scan_id, helpful))
            return True
        except sqlite3.Error as exc:
            raise DatabaseError("Feedback could not be saved to the local database.") from exc

    @staticmethod
    def _scan_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "message": row["message"], "language": row["language"],
            "requested_language": row["requested_language"], "risk": row["risk"], "score": row["score"],
            "signals": json.loads(row["signals_json"]), "urls": json.loads(row["urls_json"]),
            "mode": row["mode"], "analysis_status": row["analysis_status"], "notice": row["notice"],
            "recommendation": row["recommendation"], "translated_message": row["translated_message"],
            "model_label": row["model_label"], "score_kind": row["score_kind"],
            "created_at": row["created_at"],
            "language_confidence": row["language_confidence"],
        }
