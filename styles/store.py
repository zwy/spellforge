"""SQLite 持久存储 + styles.json 同步导出。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import CreativeCopyItem, Scenario, Style

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "app.db"
JSON_PATH = DATA_DIR / "styles.json"
SUBJECTS_JSON_PATH = DATA_DIR / "subjects.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    _seed_if_empty(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS styles (
        id TEXT PRIMARY KEY,
        "group" TEXT NOT NULL,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        why_chosen TEXT NOT NULL,
        variant_axis_name TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS scenarios (
        id TEXT NOT NULL,
        style_id TEXT NOT NULL REFERENCES styles(id) ON DELETE CASCADE,
        label TEXT NOT NULL,
        heading TEXT NOT NULL,
        caption TEXT NOT NULL,
        url TEXT NOT NULL,
        prompt TEXT NOT NULL,
        aspect_ratio TEXT,
        aspect_ratio_source TEXT,
        creative_copy TEXT,          -- JSON: [{label,value}]
        enriched_at TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (style_id, id)
    );
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,              -- 人物 / 产品 / 景物 / 品牌
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS scrape_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        styles_count INTEGER,
        scenarios_count INTEGER,
        status TEXT NOT NULL,        -- running / ok / error
        error TEXT
    );
    """)


def save_scrape(conn: sqlite3.Connection, styles: list[Style]) -> None:
    """整库替换抓取数据，但保留人工/LLM 扩展字段（aspect_ratio、creative_copy）。

    合并策略：scenario 主键为 (style_id, id)；已存在的行保留扩展字段，
    仅更新抓取侧字段；新行插入（扩展字段为空）。
    """
    now = utcnow()
    for style in styles:
        conn.execute(
            """INSERT INTO styles (id, "group", name, url, why_chosen, variant_axis_name, updated_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 "group"=excluded."group", name=excluded.name, url=excluded.url,
                 why_chosen=excluded.why_chosen,
                 variant_axis_name=excluded.variant_axis_name,
                 updated_at=excluded.updated_at""",
            (style.id, style.group, style.name, style.url, style.why_chosen,
             style.variant_axis_name, now),
        )
        for sc in style.scenarios:
            conn.execute(
                """INSERT INTO scenarios
                     (id, style_id, label, heading, caption, url, prompt,
                      aspect_ratio, aspect_ratio_source, creative_copy, enriched_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,?)
               ON CONFLICT(style_id, id) DO UPDATE SET
                     label=excluded.label, heading=excluded.heading,
                     caption=excluded.caption, url=excluded.url,
                     prompt=excluded.prompt, updated_at=excluded.updated_at""",
                (sc.id, style.id, sc.label, sc.heading, sc.caption, sc.url, sc.prompt, now),
            )
    conn.commit()


def update_scenario_enrichment(
    conn: sqlite3.Connection, style_id: str, scenario_id: str,
    aspect_ratio: str | None, aspect_ratio_source: str | None,
    creative_copy: list[CreativeCopyItem] | None,
) -> None:
    conn.execute(
        """UPDATE scenarios
           SET aspect_ratio=?, aspect_ratio_source=?, creative_copy=?, enriched_at=?
           WHERE style_id=? AND id=?""",
        (aspect_ratio, aspect_ratio_source,
         None if creative_copy is None else json.dumps(creative_copy, ensure_ascii=False),
         utcnow(), style_id, scenario_id),
    )
    conn.commit()


def load_styles(conn: sqlite3.Connection) -> list[Style]:
    """从 DB 读出完整数据（含扩展字段），按 group 与名称排序。"""
    styles: list[Style] = []
    style_rows = conn.execute(
        """SELECT id, "group", name, url, why_chosen, variant_axis_name
           FROM styles
           ORDER BY CASE "group" WHEN 'Photoreal' THEN 0 WHEN 'Illustration' THEN 1 ELSE 2 END,
                    CASE id WHEN 'portraits' THEN 0 ELSE 1 END, name"""
    ).fetchall()
    for row in style_rows:
        style = Style(
            id=row["id"], group=row["group"], name=row["name"], url=row["url"],
            why_chosen=row["why_chosen"], variant_axis_name=row["variant_axis_name"],
        )
        sc_rows = conn.execute(
            """SELECT * FROM scenarios WHERE style_id=? ORDER BY id""",
            (row["id"],),
        ).fetchall()
        for sc in sc_rows:
            style.scenarios.append(Scenario(
                id=sc["id"], label=sc["label"], heading=sc["heading"],
                caption=sc["caption"], prompt=sc["prompt"], url=sc["url"],
                aspect_ratio=sc["aspect_ratio"],
                aspect_ratio_source=sc["aspect_ratio_source"],
                creative_copy=(
                    [CreativeCopyItem(**c) for c in json.loads(sc["creative_copy"])]
                    if sc["creative_copy"] else None
                ),
                enriched_at=sc["enriched_at"],
            ))
        styles.append(style)
    return styles


SUBJECT_TYPES = ["人物", "产品", "景物", "品牌"]


def list_subjects(conn: sqlite3.Connection, limit: int = 500) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM subjects ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_subject(conn: sqlite3.Connection, subject_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
    return dict(row) if row else None


def find_subject(conn: sqlite3.Connection, type_: str, name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM subjects WHERE type=? AND name=?", (type_, name)
    ).fetchone()
    return dict(row) if row else None


def add_subject(conn: sqlite3.Connection, type_: str, name: str, description: str) -> int:
    now = utcnow()
    cur = conn.execute(
        "INSERT INTO subjects (type, name, description, created_at, updated_at) VALUES (?,?,?,?,?)",
        (type_, name, description, now, now),
    )
    conn.commit()
    return cur.lastrowid


def update_subject(conn: sqlite3.Connection, subject_id: int,
                   type_: str, name: str, description: str) -> None:
    conn.execute(
        "UPDATE subjects SET type=?, name=?, description=?, updated_at=? WHERE id=?",
        (type_, name, description, utcnow(), subject_id),
    )
    conn.commit()


def delete_subject(conn: sqlite3.Connection, subject_id: int) -> None:
    conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
    conn.commit()
    export_subjects(conn)


def export_subjects(conn: sqlite3.Connection) -> Path:
    """导出主体库为 data/subjects.json（共享种子数据）。"""
    payload = {
        "version": "1.0",
        "updated_at": utcnow(),
        "subjects": list_subjects(conn),
    }
    SUBJECTS_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return SUBJECTS_JSON_PATH


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    """首次运行（空库）时，从随仓库分发的 JSON 种子数据导入。"""
    try:
        if conn.execute("SELECT COUNT(*) c FROM styles").fetchone()["c"] == 0 \
                and JSON_PATH.exists():
            data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
            for s in data.get("styles", []):
                conn.execute(
                    """INSERT OR IGNORE INTO styles
                         (id, "group", name, url, why_chosen, variant_axis_name, updated_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (s["id"], s["group"], s["name"], s["url"], s["why_chosen"],
                     s["variant_axis_name"], s.get("updated_at") or utcnow()),
                )
                for sc in s.get("scenarios", []):
                    conn.execute(
                        """INSERT OR IGNORE INTO scenarios
                             (id, style_id, label, heading, caption, url, prompt,
                              aspect_ratio, aspect_ratio_source, creative_copy,
                              enriched_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (sc["id"], s["id"], sc["label"], sc.get("heading", ""),
                         sc.get("caption", ""), sc["url"], sc["prompt"],
                         sc.get("aspect_ratio"), sc.get("aspect_ratio_source"),
                         json.dumps(sc["creative_copy"], ensure_ascii=False)
                         if sc.get("creative_copy") else None,
                         sc.get("enriched_at"), utcnow()),
                    )
            conn.commit()
        if conn.execute("SELECT COUNT(*) c FROM subjects").fetchone()["c"] == 0 \
                and SUBJECTS_JSON_PATH.exists():
            data = json.loads(SUBJECTS_JSON_PATH.read_text(encoding="utf-8"))
            for s in data.get("subjects", []):
                conn.execute(
                    """INSERT OR IGNORE INTO subjects (id, type, name, description, created_at, updated_at)
                       VALUES (?,?,?,?,?,?)""",
                    (s["id"], s["type"], s["name"], s["description"],
                     s.get("created_at") or utcnow(), s.get("updated_at") or utcnow()),
                )
            conn.commit()
    except Exception as e:  # noqa: BLE001 —— 种子失败不阻塞启动
        print(f"[seed] skipped: {e}")


def style_to_dict(style: Style) -> dict:
    return {
        "id": style.id,
        "group": style.group,
        "name": style.name,
        "url": style.url,
        "why_chosen": style.why_chosen,
        "variant_axis_name": style.variant_axis_name,
        "scenarios": [
            {
                "id": sc.id,
                "label": sc.label,
                "heading": sc.heading,
                "caption": sc.caption,
                "prompt": sc.prompt,
                "url": sc.url,
                "aspect_ratio": sc.aspect_ratio,
                "aspect_ratio_source": sc.aspect_ratio_source,
                "creative_copy": (
                    [{"label": c["label"] if isinstance(c, dict) else c.label,
                      "value": c["value"] if isinstance(c, dict) else c.value}
                     for c in sc.creative_copy]
                    if sc.creative_copy else None
                ),
                "enriched_at": sc.enriched_at,
            }
            for sc in style.scenarios
        ],
    }
