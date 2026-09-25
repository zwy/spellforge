"""paths 模块：模式切换、首启复制、用户覆盖优先级。"""
from __future__ import annotations

import json

from styles import paths


def test_user_data_dir_created_when_missing(desktop_env):
    d = paths.user_data_dir()
    assert d.exists() and d.is_dir()
    assert d == desktop_env.userdata


def test_frozen_paths_live_in_user_dir(desktop_env):
    assert paths.db_path() == desktop_env.userdata / "app.db"
    assert paths.personal_db_path() == desktop_env.userdata / "personal.db"


def test_source_mode_uses_repo_dirs():
    repo = paths._repo_root
    assert paths.db_path() == repo / "data" / "app.db"
    assert paths.static_dir() == repo / "web" / "static"
    assert paths.env_file_path() == repo / ".env"


def test_styles_json_copied_from_bundle_once(desktop_env):
    user_json = paths.styles_json_path()
    assert user_json == desktop_env.userdata / "styles.json"
    assert user_json.exists()
    data = json.loads(user_json.read_text(encoding="utf-8"))
    assert data["styles"][0]["id"] == "portraits"

    # 用户修改副本后再次访问不得被包内默认覆盖
    user_json.write_text('{"styles": "user-edited"}', encoding="utf-8")
    assert paths.styles_json_path() == user_json
    assert json.loads(user_json.read_text(encoding="utf-8"))["styles"] == "user-edited"


def test_spec_doc_user_override_wins(desktop_env):
    bundled = paths.spec_doc_path()
    assert bundled == desktop_env.bundle / "docs" / "通用自然语言提示词规范.md"

    user_doc = desktop_env.userdata / "docs" / "通用自然语言提示词规范.md"
    user_doc.parent.mkdir(parents=True, exist_ok=True)
    user_doc.write_text("# user regenerated\n", encoding="utf-8")
    assert paths.spec_doc_path() == user_doc


def test_spec_output_path_by_mode(desktop_env, monkeypatch):
    assert paths.spec_output_path() == desktop_env.userdata / "docs" / "通用自然语言提示词规范.md"
    # 源码模式（清空注入变量）写回仓库 docs/
    monkeypatch.delenv("SPELLFORGE_DESKTOP", raising=False)
    monkeypatch.delenv("SPELLFORGE_DATA_DIR", raising=False)
    monkeypatch.delenv("SPELLFORGE_BUNDLED_DIR", raising=False)
    assert paths.spec_output_path() == paths._repo_root / "docs" / "通用自然语言提示词规范.md"


def test_env_file_in_frozen_mode_reads_user_dir(desktop_env):
    assert paths.env_file_path() is None
    env_file = desktop_env.userdata / ".env"
    env_file.write_text("LLM_API_KEY=test-key\n", encoding="utf-8")
    assert paths.env_file_path() == env_file


def test_first_init_with_read_only_bundle(desktop_env):
    """模拟只读的内置资源目录，首启初始化必须成功。"""
    import os
    import stat
    os.chmod(desktop_env.bundle, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
    try:
        user_json = paths.styles_json_path()
        assert user_json.exists()
    finally:
        os.chmod(desktop_env.bundle, stat.S_IRWXU)
