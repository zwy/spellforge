"""个人数据库（data/personal.db）：LLM 设置与生成历史。

与共享库 app.db 分离：app.db 存共享数据（风格/场景/创意模板/主体），
随项目分发；personal.db 存私有数据（API Key、生成历史），已加入 .gitignore。
"""
from __future__ import annotations

import sqlite3

from .store import DATA_DIR, utcnow

PERSONAL_DB_PATH = DATA_DIR / "personal.db"
APP_DB_PATH = DATA_DIR / "app.db"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(PERSONAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    _migrate_from_appdb(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS llm_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        base_url TEXT NOT NULL,
        api_key TEXT NOT NULL,
        model TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        style_id TEXT NOT NULL,
        scenario_id TEXT NOT NULL,
        template_label TEXT NOT NULL,
        subject TEXT NOT NULL,
        subject_id INTEGER,
        subject_name TEXT,
        prompt_zh TEXT NOT NULL,
        prompt_en TEXT NOT NULL,
        aspect_ratio TEXT,
        notes TEXT,
        model TEXT,
        created_at TEXT NOT NULL
    );
    """)


def _migrate_from_appdb(conn: sqlite3.Connection) -> None:
    """一次性迁移：app.db 里的 generations 整体搬到 personal.db 后从共享库删除。"""
    if not APP_DB_PATH.exists():
        return
    app = sqlite3.connect(APP_DB_PATH)
    app.row_factory = sqlite3.Row
    try:
        exists = app.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='generations'"
        ).fetchone()
        if not exists:
            return
        rows = [dict(r) for r in app.execute("SELECT * FROM generations").fetchall()]
        if rows:
            cols = list(rows[0].keys())
            conn.executemany(
                f"INSERT OR IGNORE INTO generations ({','.join(cols)}) "
                f"VALUES ({','.join('?' * len(cols))})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        app.execute("DROP TABLE generations")
        app.commit()
        conn.commit()
        if rows:
            print(f"[personal.db] migrated {len(rows)} generation rows from app.db")
    finally:
        app.close()


# ---------- LLM 配置 ----------

def list_profiles(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM llm_profiles ORDER BY is_active DESC, id")]


def get_active_profile(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM llm_profiles WHERE is_active=1 LIMIT 1").fetchone()
    return dict(row) if row else None


def get_profile(conn: sqlite3.Connection, pid: int) -> dict | None:
    row = conn.execute("SELECT * FROM llm_profiles WHERE id=?", (pid,)).fetchone()
    return dict(row) if row else None


def add_profile(conn: sqlite3.Connection, name: str, base_url: str,
                api_key: str, model: str) -> int:
    """新增配置；若为第一条则自动设为使用中。"""
    first = conn.execute("SELECT COUNT(*) c FROM llm_profiles").fetchone()["c"] == 0
    now = utcnow()
    cur = conn.execute(
        """INSERT INTO llm_profiles (name, base_url, api_key, model, is_active, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?)""",
        (name, base_url, api_key, model, 1 if first else 0, now, now),
    )
    conn.commit()
    return cur.lastrowid


def update_profile(conn: sqlite3.Connection, pid: int, name: str, base_url: str,
                   api_key: str | None, model: str) -> None:
    if api_key:
        conn.execute(
            "UPDATE llm_profiles SET name=?, base_url=?, api_key=?, model=?, updated_at=? WHERE id=?",
            (name, base_url, api_key, model, utcnow(), pid),
        )
    else:
        conn.execute(
            "UPDATE llm_profiles SET name=?, base_url=?, model=?, updated_at=? WHERE id=?",
            (name, base_url, model, utcnow(), pid),
        )
    conn.commit()


def delete_profile(conn: sqlite3.Connection, pid: int) -> None:
    conn.execute("DELETE FROM llm_profiles WHERE id=?", (pid,))
    conn.commit()


def activate_profile(conn: sqlite3.Connection, pid: int) -> None:
    conn.execute("UPDATE llm_profiles SET is_active=0")
    conn.execute("UPDATE llm_profiles SET is_active=1 WHERE id=?", (pid,))
    conn.commit()


# ---------- 生成历史 ----------

def save_generation(conn: sqlite3.Connection, g: dict) -> int:
    cur = conn.execute(
        """INSERT INTO generations
             (style_id, scenario_id, template_label, subject, subject_id, subject_name,
              prompt_zh, prompt_en, aspect_ratio, notes, model, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (g["style_id"], g["scenario_id"], g["template_label"], g["subject"],
         g.get("subject_id"), g.get("subject_name"),
         g["prompt_zh"], g["prompt_en"], g.get("aspect_ratio"),
         g.get("notes"), g.get("model"), utcnow()),
    )
    conn.commit()
    return cur.lastrowid


def load_generations(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    """按时间倒序取生成历史；subject_type 联查共享库（主体可能已删除）。"""
    subject_types: dict[int, str] = {}
    if APP_DB_PATH.exists():
        try:
            app = sqlite3.connect(APP_DB_PATH)
            app.row_factory = sqlite3.Row
            for r in app.execute("SELECT id, type FROM subjects"):
                subject_types[r["id"]] = r["type"]
            app.close()
        except sqlite3.Error:
            pass
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM generations ORDER BY id DESC LIMIT ?", (limit,))]
    for r in rows:
        if r.get("subject_id"):
            r["subject_type"] = subject_types.get(r["subject_id"])
    return rows
