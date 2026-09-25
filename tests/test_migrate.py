"""迁移 CLI：预演、导入、不覆盖、强制备份、失败安全。"""
from __future__ import annotations

import json
import shutil
import sqlite3
import stat

import pytest

from styles import migrate


@pytest.fixture
def fake_repo(tmp_path):
    """伪造一个含旧数据的仓库根。"""
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "docs").mkdir()

    app = sqlite3.connect(root / "data" / "app.db")
    app.execute("CREATE TABLE styles (id TEXT PRIMARY KEY)")
    app.execute("INSERT INTO styles VALUES ('old-style')")
    app.commit()
    app.close()

    personal = sqlite3.connect(root / "data" / "personal.db")
    personal.execute("CREATE TABLE llm_profiles (id INTEGER PRIMARY KEY)")
    personal.commit()
    personal.close()

    (root / "data" / "styles.json").write_text('{"seed": "old"}', encoding="utf-8")
    (root / "docs" / "通用自然语言提示词规范.md").write_text(
        "# old spec\n", encoding="utf-8")
    return root


def test_dry_run_writes_nothing(desktop_env, fake_repo, capsys):
    rc = migrate.migrate(src_root=fake_repo, apply=False)
    assert rc == 0
    assert not desktop_env.userdata.exists() or not any(desktop_env.userdata.iterdir())
    out = capsys.readouterr().out
    assert "预演" in out


def test_apply_imports_all(desktop_env, fake_repo, capsys):
    app_bytes_before = (fake_repo / "data" / "app.db").read_bytes()
    rc = migrate.migrate(src_root=fake_repo, apply=True)
    assert rc == 0
    # 每个导入文件在汇报里只出现一次（回归：曾经重复打印同一个名字）
    out = capsys.readouterr().out
    imported = [ln.split("已导入 ", 1)[1] for ln in out.splitlines()
                if "已导入" in ln]
    assert imported == sorted(set(imported)), imported
    assert "data/app.db" in imported and "data/personal.db" in imported
    assert "docs/通用自然语言提示词规范.md" in imported
    db = desktop_env.userdata / "app.db"
    assert db.exists()
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0] == 1
    conn.close()
    assert (desktop_env.userdata / "personal.db").exists()
    assert (desktop_env.userdata / "styles.json").exists()
    assert (desktop_env.userdata / "docs" / "通用自然语言提示词规范.md").exists()
    # 源文件保持原样（字节级不变）
    app_src = fake_repo / "data" / "app.db"
    assert app_src.exists()
    assert app_src.read_bytes() == app_bytes_before
    conn = sqlite3.connect(app_src)
    assert conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0] == 1
    conn.close()


def test_existing_target_not_overwritten_by_default(desktop_env, fake_repo):
    target = desktop_env.userdata / "app.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    fresh = sqlite3.connect(target)
    fresh.execute("CREATE TABLE styles (id TEXT PRIMARY KEY)")
    fresh.execute("INSERT INTO styles VALUES ('new-style')")
    fresh.commit()
    fresh.close()

    rc = migrate.migrate(src_root=fake_repo, apply=True)
    assert rc == 0
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT id FROM styles").fetchone()[0] == "new-style"
    conn.close()
    assert not list(desktop_env.userdata.glob("*.bak.*"))


def test_force_backs_up_then_imports(desktop_env, fake_repo):
    target = desktop_env.userdata / "app.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    fresh = sqlite3.connect(target)
    fresh.execute("CREATE TABLE styles (id TEXT PRIMARY KEY)")
    fresh.execute("INSERT INTO styles VALUES ('new-style')")
    fresh.commit()
    fresh.close()

    rc = migrate.migrate(src_root=fake_repo, apply=True, force=True)
    assert rc == 0
    baks = list(desktop_env.userdata.glob("app.db.bak.*"))
    assert len(baks) == 1
    bak_conn = sqlite3.connect(baks[0])
    assert bak_conn.execute("SELECT id FROM styles").fetchone()[0] == "new-style"
    bak_conn.close()
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT id FROM styles").fetchone()[0] == "old-style"
    conn.close()


def test_unreadable_source_aborts_before_any_change(desktop_env, fake_repo):
    unreadable = fake_repo / "data" / "personal.db"
    unreadable.chmod(stat.S_IWUSR)  # 移除读权限
    try:
        rc = migrate.migrate(src_root=fake_repo, apply=True)
    finally:
        unreadable.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert rc == 1
    assert not desktop_env.userdata.exists() or not any(desktop_env.userdata.iterdir())
