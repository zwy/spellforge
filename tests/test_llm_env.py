"""llm：.env 加载位置与兼容行为。"""
from __future__ import annotations

from styles import llm, paths


def test_apply_env_file_sets_missing_keys(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_BASE_URL=https://example.com/v1\n"
        "LLM_MODEL=test-model\n"
        "LLM_API_KEY=secret\n",
        encoding="utf-8")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    llm._apply_env_file(env_file)
    import os
    assert os.environ["LLM_MODEL"] == "test-model"


def test_apply_env_file_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=from-file\n", encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "from-env")
    llm._apply_env_file(env_file)
    import os
    assert os.environ["LLM_MODEL"] == "from-env"


def test_env_file_path_none_in_frozen_without_user_env(desktop_env):
    assert paths.env_file_path() is None
