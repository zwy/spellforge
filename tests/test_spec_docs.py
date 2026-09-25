"""规范文档：默认资源 + 用户覆盖的读取顺序。"""
from __future__ import annotations

from styles import paths


def test_frozen_defaults_to_bundled_spec(desktop_env):
    assert paths.spec_doc_path() == desktop_env.bundle / "docs" / "通用自然语言提示词规范.md"


def test_user_regen_writes_user_dir_and_wins(desktop_env):
    out = paths.spec_output_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("# regenerated\n", encoding="utf-8")
    assert paths.spec_doc_path() == out


def test_source_mode_spec_paths_unchanged(monkeypatch):
    repo = paths._repo_root
    monkeypatch.delenv("SPELLFORGE_DESKTOP", raising=False)
    monkeypatch.delenv("SPELLFORGE_DATA_DIR", raising=False)
    monkeypatch.delenv("SPELLFORGE_BUNDLED_DIR", raising=False)
    assert paths.spec_template_path() == repo / "docs" / "spec_template.md"
    assert paths.spec_doc_path() == repo / "docs" / "通用自然语言提示词规范.md"
    assert paths.spec_output_path() == repo / "docs" / "通用自然语言提示词规范.md"
    assert paths.spec_vocab_path() == repo / "data" / "spec_vocab.json"
