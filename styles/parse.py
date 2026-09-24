"""解析 Next.js RSC flight 数据，提取 styles 列表与每个页面的 scenario。"""
from __future__ import annotations

import json
import re

from .fetch import BASE, STYLES_LENS
from .schema import Scenario, Style


def extract_flight(html: str) -> str:
    """从页面中解出 RSC flight 数据流（self.__next_f.push 的拼接结果）。"""
    pieces: list[str] = []
    for quoted in re.findall(r'self\.__next_f\.push\(\[1,(".*?")\]\)', html, flags=re.S):
        try:
            pieces.append(json.loads(quoted))
        except json.JSONDecodeError:
            continue
    return "".join(pieces)


def _balanced_json(stream: str, start: int) -> str | None:
    """从 start 处的 '{' 开始，按括号配平截出完整 JSON 对象。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(stream)):
        ch = stream[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return stream[start:i + 1]
    return None


def _balanced_array(stream: str, start: int) -> str | None:
    """从 start 处的 '[' 开始，按方括号配平截出完整 JSON 数组。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(stream)):
        ch = stream[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return stream[start:i + 1]
    return None


def parse_style_list(flight: str) -> list[dict]:
    """从任意 styles 页 flight 数据中解出全部 style 项（含分组）。

    导航数据形如 {"lens":...,"items":[{"id","label","href","group"},...],"activeId":...}
    items 前是 lenses 数组，因此从 "items": 后的 '[' 起截取数组本身。
    """
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r'"items":(\[\{"id":".*?\])', flight):
        try:
            arr = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for item in arr:
            # 只要 style 页项：href 形如 /benchmarks/media/images/<slug>
            href = item.get("href", "")
            if (item.get("id") and item["id"] not in seen
                    and href.startswith(STYLES_LENS + "/")
                    and "/" not in href[len(STYLES_LENS) + 1:]):
                seen.add(item["id"])
                out.append(item)
    return out


def parse_challenge(flight: str) -> dict | None:
    m = re.search(r'\{"challenge":\{', flight)
    if not m:
        return None
    snippet = _balanced_json(flight, m.start())
    if not snippet:
        return None
    try:
        obj = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    return obj.get("challenge")


def parse_scenarios(flight: str) -> list[dict]:
    """解出页面内全部 {"scenario":{...}} 对象（括号配平截取）。"""
    out: list[dict] = []
    for m in re.finditer(r'\{"scenario":\{', flight):
        snippet = _balanced_json(flight, m.start())
        if not snippet:
            continue
        try:
            obj = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        sc = obj.get("scenario")
        if sc and sc.get("id"):
            out.append(sc)
    return out


def scenario_from_raw(raw: dict, style_slug: str) -> Scenario:
    """把 flight 里的 scenario 原始对象转成 schema 的 Scenario。

    一个 scenario 可能含多个 variant，取第一个（与站点展示一致，
    URL 的 ?variant= 即 scenario id）。prompt 取 variants[0].prompt。
    """
    variants = raw.get("variants") or []
    prompt = ""
    if variants and isinstance(variants, list):
        prompt = variants[0].get("prompt", "")
    return Scenario(
        id=raw["id"],
        label=raw.get("label") or raw.get("heading") or raw["id"],
        heading=raw.get("heading", ""),
        caption=raw.get("caption", ""),
        prompt=prompt,
        url=f"{BASE}{STYLES_LENS}/{style_slug}?variant={raw['id']}",
    )


def parse_style_page(slug: str, group: str, html: str) -> Style | None:
    """从单个 style 页 HTML 提取 Style 对象。"""
    flight = extract_flight(html)
    challenge = parse_challenge(flight)
    if not challenge:
        return None
    style = Style(
        id=challenge["slug"],
        group=group,
        name=challenge.get("name") or slug,
        url=f"{BASE}{STYLES_LENS}/{slug}",
        why_chosen=challenge.get("description", ""),
        variant_axis_name=challenge.get("variantAxisName", ""),
    )
    for raw in parse_scenarios(flight):
        style.scenarios.append(scenario_from_raw(raw, slug))
    return style
