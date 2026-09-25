"""store：首启种子、二次启动不覆盖用户修改、export_json。"""
from __future__ import annotations

import json

from styles import store
from tests.conftest import SUBJECTS_JSON, make_styles_json


def _styles_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) c FROM styles").fetchone()["c"]


def test_first_init_seeds_from_bundle(desktop_env):
    conn = store.connect()
    try:
        assert _styles_count(conn) == 1
        rows = conn.execute("SELECT COUNT(*) c FROM subjects").fetchone()
        assert rows["c"] == 1
        sc = conn.execute(
            "SELECT prompt FROM scenarios WHERE style_id='portraits'"
        ).fetchone()
        assert sc["prompt"] == "prompt v1"
    finally:
        conn.close()


def test_second_start_keeps_user_changes(desktop_env):
    conn = store.connect()
    try:
        store.add_subject(conn, "人物", "我的主体", "描述")
    finally:
        conn.close()

    # 模拟再次启动
    conn = store.connect()
    try:
        assert _styles_count(conn) == 1  # 种子不重复导入
        subs = store.list_subjects(conn)
        names = [s["name"] for s in subs]
        assert "我的主体" in names and "测试主体" in names
    finally:
        conn.close()


def test_export_json_matches_seed_format(desktop_env):
    conn = store.connect()
    try:
        store.update_scenario_enrichment(
            conn, "portraits", "candid-outdoors", "4:5", "manual",
            [{"label": "头像", "value": "模板内容"}])
        out = store.export_json(conn)
    finally:
        conn.close()

    assert out == desktop_env.userdata / "styles.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == "1.0"
    assert data["source"] == "openrouter.ai/benchmarks/media/images"
    style = data["styles"][0]
    assert style["id"] == "portraits"
    sc = style["scenarios"][0]
    assert sc["aspect_ratio"] == "4:5"
    assert sc["aspect_ratio_source"] == "manual"
    assert sc["creative_copy"] == [{"label": "头像", "value": "模板内容"}]


def test_seeded_json_read_from_user_copy(desktop_env):
    """种子读的是用户副本：改用户副本会反映到首启建库。"""
    desktop_env.userdata.mkdir(parents=True, exist_ok=True)
    user_json = desktop_env.userdata / "styles.json"
    user_json.write_text(
        json.dumps(make_styles_json(styles_version="v2"), ensure_ascii=False),
        encoding="utf-8")
    conn = store.connect()
    try:
        sc = conn.execute("SELECT prompt FROM scenarios LIMIT 1").fetchone()
        assert sc["prompt"] == "prompt v2"
    finally:
        conn.close()
