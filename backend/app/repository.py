import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.domain.errors import DomainError
from app.domain.models import SemanticModel


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return uuid4().hex


class Repository:
    """One SQLite file, immutable model versions, and atomic compare-and-swap writes."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "platform.sqlite3"
        with sqlite3.connect(self.path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, head INTEGER NOT NULL,
                    active INTEGER, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS versions (
                    project_id TEXT NOT NULL REFERENCES projects(id), number INTEGER NOT NULL,
                    model TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, number)
                );
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    view_id TEXT NOT NULL, source_name TEXT NOT NULL, row_count INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL, loaded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    base INTEGER NOT NULL, changes TEXT NOT NULL, candidate TEXT NOT NULL,
                    diff TEXT NOT NULL, report TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS regressions (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    name TEXT NOT NULL, plan TEXT NOT NULL, expected_rows TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    version INTEGER NOT NULL, question TEXT NOT NULL, result TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self, write=False):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def project(conn, project_id):
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise DomainError("Project not found.", 404)
        return dict(row)

    @staticmethod
    def version(conn, project_id, number=None):
        p = Repository.project(conn, project_id)
        number = p["head"] if number is None else number
        row = conn.execute(
            "SELECT * FROM versions WHERE project_id=? AND number=?", (project_id, number)
        ).fetchone()
        if not row:
            raise DomainError("Model version not found.", 404)
        return SemanticModel.model_validate_json(row["model"])

    @staticmethod
    def check_base(conn, project_id, base):
        if Repository.project(conn, project_id)["head"] != base:
            raise DomainError("The draft changed. Refresh and create a new proposal.", 409)

    @staticmethod
    def add_version(conn, project_id, model, reason, base):
        Repository.check_base(conn, project_id, base)
        number = base + 1
        conn.execute(
            "INSERT INTO versions VALUES(?,?,?,?,?)",
            (project_id, number, model.model_dump_json(), reason, now()),
        )
        conn.execute("UPDATE projects SET head=? WHERE id=?", (number, project_id))
        Repository.event(conn, project_id, "version_created", {"version": number, "reason": reason})
        return number

    @staticmethod
    def event(conn, project_id, kind, payload):
        conn.execute(
            "INSERT INTO events(project_id,kind,payload,created_at) VALUES(?,?,?,?)",
            (project_id, kind, json.dumps(payload, allow_nan=False), now()),
        )
