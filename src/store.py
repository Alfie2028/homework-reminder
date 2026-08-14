import json
import sqlite3
from pathlib import Path


class StateStore:
    """用 SQLite 保存作业状态快照，支持'上次 vs 本次'比对。"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS homework_state (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
                """
            )

    def get(self, key: str):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM homework_state WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def set(self, key: str, payload: dict):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO homework_state (key, payload, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(payload, ensure_ascii=False)),
            )
