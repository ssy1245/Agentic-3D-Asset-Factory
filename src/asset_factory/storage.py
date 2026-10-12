import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(UTC).isoformat()


def identity():
    return uuid4().hex


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.database = root / "studio.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    expires_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, request_id TEXT NOT NULL,
                    status TEXT NOT NULL, data TEXT NOT NULL,
                    UNIQUE(project_id, request_id));
                DROP INDEX IF EXISTS one_active_operation;
                DROP INDEX IF EXISTS one_active_operation_per_stage;
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_operation_per_stage_and_texture ON operations(project_id, json_extract(data, '$.stage'), coalesce(json_extract(data, '$.texture'), 0))
                WHERE status IN ('queued','running','unknown');
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(projects)")}
            if "owner_id" not in columns:
                db.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT REFERENCES users(id)")
            db.execute("CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner_id)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, project):
        with self.connect() as db:
            db.execute(
                "INSERT INTO projects (id,data,owner_id) VALUES (?,?,?)",
                (project["id"], json.dumps(project), project.get("owner_id")),
            )

    def get(self, pid, db=None):
        if db is None:
            with self.connect() as connection:
                return self.get(pid, connection)
        row = db.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()
        if row is None:
            raise KeyError("任务不存在")
        return json.loads(row["data"])

    def put(self, db, project):
        db.execute("UPDATE projects SET data=? WHERE id=?", (json.dumps(project), project["id"]))

    def projects(self, owner_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT data FROM projects WHERE owner_id=? ORDER BY rowid DESC", (owner_id,)
            ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def owns(self, pid, user_id):
        with self.connect() as db:
            return db.execute(
                "SELECT 1 FROM projects WHERE id=? AND owner_id=?", (pid, user_id)
            ).fetchone() is not None

    def operations(self, pid, db=None):
        if db is None:
            with self.connect() as connection:
                return self.operations(pid, connection)
        return [
            json.loads(r["data"])
            for r in db.execute("SELECT data FROM operations WHERE project_id=? ORDER BY rowid", (pid,))
        ]

    def operation(self, oid, db=None):
        if db is None:
            with self.connect() as connection:
                return self.operation(oid, connection)
        row = db.execute("SELECT data FROM operations WHERE id=?", (oid,)).fetchone()
        if row is None:
            raise KeyError("操作不存在")
        return json.loads(row["data"])

    def put_operation(self, db, op):
        db.execute(
            "UPDATE operations SET status=?,data=? WHERE id=?", (op["status"], json.dumps(op), op["id"])
        )

    def recover(self):
        # A restart cannot prove whether an in-flight HTTP request was billed.
        with self.connect() as db:
            rows = db.execute("SELECT data FROM operations WHERE status IN ('queued','running')").fetchall()
            for row in rows:
                op = json.loads(row["data"])
                if op["status"] == "queued":
                    op.update(status="failed", error="服务重启，未开始的操作已停止，可重新提交。")
                else:
                    op.update(
                        status="unknown", error="服务在请求期间中断，结果及扣费未知。请先核对供应商记录。"
                    )
                self.put_operation(db, op)

            # Interrupted advisory reviews never trigger a second image request.
            for row in db.execute("SELECT data FROM projects").fetchall():
                project = json.loads(row["data"])
                changed = False
                for r in project["revisions"]:
                    if r.get("quality_review", {}).get("status") == "running":
                        r["quality_review"] = {
                            "status": "unavailable",
                            "summary": "Review interrupted by restart. Inspect manually; no automatic retry.",
                            "human_review_required": True,
                        }
                        changed = True
                if changed:
                    self.put(db, project)
