"""《通用自然语言提示词规范》生成器。

用法:
    python -m styles.spec               # 生成 docs/通用自然语言提示词规范.md
    python -m styles.spec --refresh-vocab  # 强制重跑 LLM 词汇提取

流程:
  1. 从 DB 读语料统计与画幅比例分布
  2. 词汇库（data/spec_vocab.json 缓存；--refresh-vocab 重提取）
  3. 把 docs/spec_template.md 的 {{槽位}} 填充后写出最终文档
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

from . import paths, store

DIMENSIONS = ["媒介与风格声明", "主体与瞬间", "环境与时间", "构图与镜头", "光线",
              "材质与质感", "色彩", "精确性与可验证细节", "负面约束", "不完美与真实感"]

# 风格族归属（官方 style id -> 族名）
FAMILIES = {
    "photoreal": ["portraits", "people-in-scenes", "animals", "landscape", "interiors",
                   "food", "product", "cities", "vehicles"],
    "illustration": ["anime-manga", "flat-vector-illustration", "3d-renders", "painting",
                      "concept-art", "cartoon", "pixel", "style-switching"],
    "design": ["logos", "posters", "ui-mockups", "patterns"],
}

RATIO_LABELS = {
    "photoreal": "写实摄影族",
    "illustration": "插画绘画族",
    "design": "设计图文族",
}


def corpus_stats() -> str:
    conn = store.connect()
    styles = store.load_styles(conn)
    total_sc = sum(len(s.scenarios) for s in styles)
    lines = [
        "| 语料 | 数量 |",
        "|---|---|",
        f"| 风格（style 页） | {len(styles)} |",
        f"| 官方场景（scenario / prompt） | {total_sc} |",
        f"| 创意模板（LLM 生成） | {sum(len(sc.creative_copy or []) for s in styles for sc in s.scenarios)} |",
        "",
        "| 风格族 | 风格数 | 场景数 |",
        "|---|---|---|",
    ]
    for fam, ids in FAMILIES.items():
        ss = [s for s in styles if s.id in ids]
        lines.append(f"| {RATIO_LABELS[fam]} | {len(ss)} | {sum(len(s.scenarios) for s in ss)} |")
    return "\n".join(lines)


def ratio_table() -> str:
    conn = store.connect()
    styles = store.load_styles(conn)
    lines = [
        "| 场景类型 | 语料中的推荐比例 | 依据 |",
        "|---|---|---|",
    ]
    guidance = [
        ("人像（头像/特写）", ["portraits"], "竖幅突出人物，特写与胸像常见 2:3、4:5"),
        ("抓拍/环境人像", ["people-in-scenes"], "横向场景容纳环境，多为 3:2"),
        ("动物/微距/野生", ["animals"], "主体横向运动或环境并重，3:2 为主"),
        ("风光（山/海/林/沙漠）", ["landscape"], "横幅展开视野，3:2 为主"),
        ("城市/天际线", ["cities"], "天际线远景 16:9，街景与地标 2:3"),
        ("室内", ["interiors"], "横幅呈现空间纵深，3:2"),
        ("美食", ["food"], "俯拍/特写兼有，4:5 便于社媒，2:3 竖构图"),
        ("产品静物", ["product"], "电商主图常见 1:1 与 4:5"),
        ("载具", ["vehicles"], "横向展示车身线条，3:2"),
        ("动漫/角色立绘", ["anime-manga"], "角色多为 2:3，场景 16:9"),
        ("扁平矢量/图标", ["flat-vector-illustration"], "图标网格 1:1，插画场景 2:3"),
        ("3D 渲染", ["3d-renders"], "产品 1:1，环境 2:3"),
        ("绘画（油画/水彩/线稿）", ["painting"], "横幅构图 3:2"),
        ("概念设定", ["concept-art"], "角色 2:3，场景 2:3~3:2"),
        ("卡通/漫画", ["cartoon"], "角色 1:1，分镜 3:2"),
        ("像素", ["pixel"], "游戏资产正方形 1:1"),
        ("标志", ["logos"], "标志居中留白，1:1 与 3:2"),
        ("海报/封面", ["posters"], "竖幅印刷品 2:3，社媒封面 16:9"),
        ("UI 界面", ["ui-mockups"], "手机屏 9:16，网页 3:2，设备图 4:5"),
        ("图案/纹理", ["patterns"], "四方连续/平铺 1:1"),
    ]
    for label, ids, note in guidance:
        ratios = [sc.aspect_ratio for s in styles if s.id in ids
                  for sc in s.scenarios if sc.aspect_ratio]
        top = "、".join(f"{r}" for r, _ in Counter(ratios).most_common(2)) or "—"
        lines.append(f"| {label} | `{top}` | {note} |")
    return "\n".join(lines)


def vocab_list(dim: str, limit: int = 8) -> str:
    vocab_path = paths.spec_vocab_path()
    if not vocab_path.exists():
        return "_(词汇库未生成，运行 python -m styles.spec --refresh-vocab)_"
    data = json.loads(vocab_path.read_text(encoding="utf-8"))
    items = data.get(dim, [])
    # 优先短而通用的表达
    items = sorted(items, key=lambda i: len(i.get("en", "")))[:limit]
    if not items:
        return "（暂无）"
    return "\n".join(f"- `{i['en']}` —— {i['zh']}" for i in items)


def render_example(example_id: str) -> str:
    style_id, _, sc_id = example_id.partition("/")
    conn = store.connect()
    styles = store.load_styles(conn)
    for s in styles:
        if s.id != style_id:
            continue
        for sc in s.scenarios:
            if sc.id == sc_id:
                return (f"> {sc.prompt}\n>\n"
                        f"> —— `{style_id}/{sc_id}` · 推荐画幅 `{sc.aspect_ratio or '—'}`")
    return f"（未找到示例 {example_id}）"


def render(template: str) -> str:
    out = template
    out = out.replace("{{stats_summary}}", corpus_stats())
    out = out.replace("{{ratio_table}}", ratio_table())
    for dim in DIMENSIONS:
        out = out.replace("{{vocab:" + dim + "}}", vocab_list(dim))
    # {{example:style/scenario}}
    import re
    def _ex(m):
        return render_example(m.group(1))
    out = re.sub(r"\{\{example:([a-z0-9\-/]+)\}\}", _ex, out)
    return out


def refresh_vocab() -> None:
    """调 LLM 重新提取词汇库（分批，合并去重）。"""
    from .llm import chat_json
    conn = store.connect()
    styles = store.load_styles(conn)
    all_sc = [(s, sc) for s in styles for sc in s.scenarios]

    SYSTEM = "你是提示词工程分析师。只返回合法 JSON。"
    TASK = """下面是 {n} 条图像生成的英文提示词（来自 openrouter.ai 图像基准）。请从这些真实语料中提取写作用语，归纳到以下维度，每个维度给出 6-10 条最有代表性的用语模式：

- "媒介与风格声明"：开头如何声明媒介/风格
- "主体与瞬间"：如何写主体与动作瞬间
- "环境与时间"：如何写场景、天气、时间
- "构图与镜头"：视角、景别、镜头、景深用语
- "光线"：光源、方向、质量用语
- "材质与质感"：材质呈现、细节保留用语
- "色彩"：色彩描述用语
- "精确性与可验证细节"：如何写可检查的硬性细节
- "负面约束"：否定式约束用语
- "不完美与真实感"：保留瑕疵、对比式表达用语

每条格式 {{"en": "英文用语（原样摘录或最小改写）", "zh": "中文说明一句话"}}。

提示词列表：
{prompts}

返回 JSON：{{"媒介与风格声明": [...], "主体与瞬间": [...], ...}}"""

    results: dict = {}
    BATCH = 20
    for bi in range(0, len(all_sc), BATCH):
        batch = all_sc[bi:bi + BATCH]
        lines = [f"- [{s.id}/{sc.id}] {sc.prompt}" for s, sc in batch]
        print(f"vocab batch {bi // BATCH + 1}: {len(batch)} prompts ...", flush=True)
        r = chat_json([
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": TASK.format(n=len(batch), prompts="\n".join(lines))},
        ], max_tokens=16000)
        for k, v in r.items():
            if isinstance(v, list):
                results.setdefault(k, [])
                seen = {i["en"] for i in results[k]}
                for item in v:
                    if (isinstance(item, dict) and item.get("en")
                            and item["en"] not in seen):
                        seen.add(item["en"])
                        results[k].append(
                            {"en": str(item["en"])[:120], "zh": str(item.get("zh", ""))[:80]})
    out_path = paths.spec_vocab_path()
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {out_path}: {sum(len(v) for v in results.values())} entries")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-vocab", action="store_true", help="强制重跑 LLM 词汇提取")
    args = ap.parse_args()
    if args.refresh_vocab or not paths.spec_vocab_path().exists():
        refresh_vocab()
    template = paths.spec_template_path().read_text(encoding="utf-8")
    doc = render(template)
    out = paths.spec_output_path()
    out.write_text(doc, encoding="utf-8")
    print(f"written {out} ({len(doc)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
