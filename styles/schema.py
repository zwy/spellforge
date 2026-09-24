"""数据模型与 JSON Schema 定义。

抓取自 https://openrouter.ai/benchmarks/media/images 下的 Styles 页面。
每个 style 页含若干 scenario（即 URL 中的 ?variant=），每个 scenario
的 prompt 为官方示例提示词。

LLM 扩展字段（aspect_ratio / creative_copy）初始为 null，由第二步
LLM 流程补全后写回。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CreativeCopyItem:
    """一条创意文案：label 为用户可选项名，value 为提示词模板。"""
    label: str
    value: str


@dataclass
class Scenario:
    """style 页下的一个场景/变体，含官方 prompt 与 LLM 扩展字段。"""
    id: str
    label: str
    heading: str
    caption: str
    prompt: str
    url: str
    # ---- LLM 扩展字段（抓取时为 null，由 enrich 流程填写） ----
    aspect_ratio: Optional[str] = None          # 如 '2:3'、'1:1'
    aspect_ratio_source: Optional[str] = None   # 'llm' / 'manual'
    creative_copy: Optional[list[CreativeCopyItem]] = None  # 创意文案模板
    enriched_at: Optional[str] = None           # LLM 补全时间


@dataclass
class Style:
    """一个风格页（challenge），如 Portraits / Anime & manga。"""
    id: str
    group: str                 # Photoreal / Illustration / Design
    name: str
    url: str
    why_chosen: str            # "Why we chose this prompt" 说明
    variant_axis_name: str     # 如 Scene / Subject
    scenarios: list[Scenario] = field(default_factory=list)


@dataclass
class ScrapeResult:
    updated_at: str
    styles: list[Style] = field(default_factory=list)


def to_dict(obj) -> dict:
    return asdict(obj)


JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "OpenRouter Styles Dataset",
    "type": "object",
    "required": ["version", "updated_at", "styles"],
    "properties": {
        "version": {"type": "string", "const": "1.0"},
        "updated_at": {"type": "string", "format": "date-time"},
        "styles": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "group", "name", "url", "why_chosen",
                              "variant_axis_name", "scenarios"],
                "properties": {
                    "id": {"type": "string"},
                    "group": {"type": "string"},
                    "name": {"type": "string"},
                    "url": {"type": "string", "format": "uri"},
                    "why_chosen": {"type": "string"},
                    "variant_axis_name": {"type": "string"},
                    "scenarios": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "label", "url", "prompt"],
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "url": {"type": "string", "format": "uri"},
                                "prompt": {"type": "string"},
                                "aspect_ratio": {
                                    "type": ["string", "null"],
                                    "pattern": "^[0-9]+:[0-9]+$",
                                    "description": "LLM 推测的宽高比，如 2:3、1:1",
                                },
                                "aspect_ratio_source": {
                                    "type": ["string", "null"],
                                    "enum": [None, "llm", "manual"],
                                },
                                "creative_copy": {
                                    "type": ["array", "null"],
                                    "items": {
                                        "type": "object",
                                        "required": ["label", "value"],
                                        "properties": {
                                            "label": {"type": "string"},
                                            "value": {"type": "string"},
                                        },
                                    },
                                    "description": "LLM 生成的创意文案模板",
                                },
                                "enriched_at": {"type": ["string", "null"]},
                            },
                        },
                    },
                },
            },
        },
    },
}
