"""桌面模式模拟环境：SPELLFORGE_DESKTOP=1 + 注入式目录。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def make_styles_json(styles_version: str = "v1") -> dict:
    return {
        "version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "source": "openrouter.ai/benchmarks/media/images",
        "styles": [
            {
                "id": "portraits",
                "group": "Photoreal",
                "name": "Portraits",
                "url": "https://example.com/portraits",
                "why_chosen": "test",
                "variant_axis_name": "Scene",
                "scenarios": [
                    {
                        "id": "candid-outdoors",
                        "label": "Candid outdoors",
                        "heading": "Candid outdoors",
                        "caption": "cap",
                        "prompt": f"prompt {styles_version}",
                        "url": "https://example.com/portraits?variant=candid-outdoors",
                        "aspect_ratio": "3:2",
                        "aspect_ratio_source": "llm",
                        "creative_copy": None,
                        "enriched_at": "2026-01-01T00:00:00Z",
                    }
                ],
            }
        ],
    }


SUBJECTS_JSON = {
    "version": "1.0",
    "updated_at": "2026-01-01T00:00:00Z",
    "subjects": [
        {
            "id": 1,
            "type": "人物",
            "name": "测试主体",
            "description": "测试主体描述",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ],
}


@pytest.fixture
def desktop_env(tmp_path, monkeypatch):
    """模拟打包桌面模式：注入 bundle 与用户数据目录。"""
    bundle = tmp_path / "bundle"
    userdata = tmp_path / "userdata"
    (bundle / "data").mkdir(parents=True)
    (bundle / "docs").mkdir()
    # web 静态资源也是包内只读资源；真实文件才能让服务器测试通过就绪探测
    shutil.copytree(_REPO_ROOT / "web" / "static", bundle / "web" / "static")

    (bundle / "data" / "styles.json").write_text(
        json.dumps(make_styles_json(), ensure_ascii=False), encoding="utf-8")
    (bundle / "data" / "subjects.json").write_text(
        json.dumps(SUBJECTS_JSON, ensure_ascii=False), encoding="utf-8")
    (bundle / "data" / "spec_vocab.json").write_text(
        json.dumps({"媒介与风格声明": [{"en": "test en", "zh": "测试"}]},
                   ensure_ascii=False), encoding="utf-8")
    (bundle / "docs" / "spec_template.md").write_text(
        "# template {{stats_summary}}\n", encoding="utf-8")
    (bundle / "docs" / "通用自然语言提示词规范.md").write_text(
        "# bundled default spec\n", encoding="utf-8")

    monkeypatch.setenv("SPELLFORGE_DESKTOP", "1")
    monkeypatch.setenv("SPELLFORGE_DATA_DIR", str(userdata))
    monkeypatch.setenv("SPELLFORGE_BUNDLED_DIR", str(bundle))
    return SimpleNamespace(bundle=bundle, userdata=userdata, tmp=tmp_path)
