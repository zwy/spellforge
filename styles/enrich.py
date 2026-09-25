"""LLM 扩展流程：为每条 scenario 推测 aspect_ratio 并生成创意文案模板。

用法:
    python -m styles.enrich                  # 补全所有未处理的 scenario
    python -m styles.enrich --limit 3        # 只处理 3 条（测试用）
    python -m styles.enrich --style portraits
    python -m styles.enrich --force          # 已补全的也重跑

单次 LLM 调用同时返回 aspect_ratio 与 creative_copy（JSON），结果写回
SQLite 并同步 styles.json；另导出 data/creative_templates.json
（创意模版数据，按风格分组，供用户选择）。
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import paths, store
from .llm import chat_json

ASPECT_RATIOS = ["1:1", "2:3", "3:2", "4:5", "5:4", "3:4", "4:3", "9:16", "16:9"]

SYSTEM = "你是资深提示词工程与视觉设计专家，熟悉 Midjourney / DALL·E / FLUX 等图像生成模型的提示词写法。只返回合法 JSON。"

PROMPT_TMPL = """下面是 openrouter.ai 图像基准里的一个风格场景。

风格：{style_name}（分组：{group}）
该风格官方选用说明：{why_chosen}
场景：{label}（变体轴：{variant_axis}）
官方 Prompt：{prompt}

请完成两件事，只返回 JSON：

1. "aspect_ratio"：从这些比例中选一个最适合此场景成图的比例：{ratios}

2. "creative_copy"：生成 4 条创意文案模板。这些模板用于：用户之后带着自己的主体（人物/产品/景物等），让 LLM 参照本场景的风格要素生成新 prompt。每条格式为 {{"label": "...", "value": "..."}}：
   - label：2-4 字中文用例名（如 头像、证件照、角色设计、场景图、海报、壁纸、图标 等，要贴合此风格实际可用的用途）
   - value：120-220 字中文模板说明，要求写明：以「所选主体」为核心如何应用本场景的构图、光线、质感、色彩、氛围等风格要素；包含保持主体身份与关键特征一致的约束；结尾包含"不出现文字、Logo、水印、边框或乱码"一类负面约束。语气直接、可执行，像给绘图模型的指令。

参考文风（仅参考写法，不要照抄内容）：
{{"label": "头像", "value": "生成一张以所选主体为唯一焦点的头像肖像。采用肩部以上的近景特写或标准胸像构图，人物面部占据画面主要区域，头顶、发型、双耳和肩部边缘完整可见，不裁切额头、下巴或关键发饰。人物正视镜头或轻微三分之二侧脸，清晰突出五官、发型、肤质与自然神态。保持主体身份和关键外貌特征一致，使用简洁柔和、不过度抢眼的背景，不出现文字、Logo、水印、边框或乱码。"}}

返回：
{{"aspect_ratio": "2:3", "creative_copy": [{{"label": "...", "value": "..."}}, ...]}}"""


_lock = threading.Lock()
_progress = {"done": 0, "total": 0, "failed": 0}


def build_messages(style, sc) -> list[dict]:
    user = PROMPT_TMPL.format(
        style_name=style.name,
        group=style.group,
        why_chosen=style.why_chosen,
        label=sc.label,
        variant_axis=style.variant_axis_name,
        prompt=sc.prompt,
        ratios="、".join(ASPECT_RATIOS),
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


def validate_result(result: dict) -> tuple[str | None, list | None]:
    ar = result.get("aspect_ratio")
    if not (isinstance(ar, str) and ar in ASPECT_RATIOS):
        ar = None
    cc = result.get("creative_copy")
    if isinstance(cc, list):
        cc = [
            {"label": str(i.get("label", "")).strip(), "value": str(i.get("value", "")).strip()}
            for i in cc
            if isinstance(i, dict) and str(i.get("label", "")).strip() and str(i.get("value", "")).strip()
        ] or None
    else:
        cc = None
    return ar, cc


def enrich_one(conn, style, sc, force: bool = False) -> bool:
    """补全单条 scenario。返回是否成功。"""
    if not force and sc.aspect_ratio and sc.creative_copy:
        return True
    try:
        result = chat_json(build_messages(style, sc))
        ar, cc = validate_result(result)
        if not ar or not cc:
            raise ValueError(f"invalid result: ar={ar}, cc={bool(cc)}")
        with _lock:
            store.update_scenario_enrichment(conn, style.id, sc.id, ar, "llm", cc)
            _progress["done"] += 1
        print(f"  ok {style.id}/{sc.id}: {ar}, {len(cc)} templates", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        with _lock:
            _progress["done"] += 1
            _progress["failed"] += 1
        print(f"  FAIL {style.id}/{sc.id}: {e}", flush=True)
        return False


def run(force: bool = False, limit: int | None = None, style_id: str | None = None,
        workers: int = 6, verbose: bool = True) -> dict:
    conn = store.connect()
    try:
        styles = store.load_styles(conn)
        jobs: list[tuple] = []
        for style in styles:
            if style_id and style.id != style_id:
                continue
            for sc in style.scenarios:
                if not force and sc.aspect_ratio and sc.creative_copy:
                    continue
                jobs.append((style, sc))
        if limit:
            jobs = jobs[:limit]

        _progress.update(done=0, total=len(jobs), failed=0)
        if verbose:
            print(f"enriching {len(jobs)} scenarios with {workers} workers ...")

        # 每个工作线程持有独立连接，避免 sqlite 跨线程问题
        def worker(pair):
            style, sc = pair
            thread_conn = store.connect()
            try:
                return enrich_one(thread_conn, style, sc, force=force)
            finally:
                thread_conn.close()

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(worker, jobs))

        # 同步导出
        store.export_json(conn)
        export_creative_templates(conn)
        return dict(_progress)
    finally:
        conn.close()


def export_creative_templates(conn, path=None) -> None:
    """导出创意模版数据 data/creative_templates.json（用户选择用）。"""
    from pathlib import Path
    path = path or paths.creative_templates_path()
    styles = store.load_styles(conn)
    out = {
        "version": "1.0",
        "updated_at": store.utcnow(),
        "description": "创意模版数据：按风格分组的创意文案，供用户选择后让 LLM 生成新 prompt",
        "styles": [
            {
                "id": s.id,
                "name": s.name,
                "group": s.group,
                "url": s.url,
                "why_chosen": s.why_chosen,
                "scenarios": [
                    {
                        "id": sc.id,
                        "label": sc.label,
                        "url": sc.url,
                        "aspect_ratio": sc.aspect_ratio,
                        "templates": [
                            {"label": t.label if isinstance(t, object) and not isinstance(t, dict) else t["label"],
                             "value": t.value if isinstance(t, object) and not isinstance(t, dict) else t["value"]}
                            for t in (sc.creative_copy or [])
                        ],
                    }
                    for sc in s.scenarios
                ],
            }
            for s in styles
        ],
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM 扩展：推测比例 + 生成创意文案")
    ap.add_argument("--force", action="store_true", help="已补全的也重跑")
    ap.add_argument("--limit", type=int, default=None, help="最多处理 N 条")
    ap.add_argument("--style", default=None, help="只处理指定 style id")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    try:
        prog = run(force=args.force, limit=args.limit, style_id=args.style,
                   workers=args.workers)
    except Exception as e:  # noqa: BLE001
        print(f"enrich failed: {e}", file=sys.stderr)
        return 1
    print(f"\nOK: {prog['total'] - prog['failed']}/{prog['total']} enriched"
          + (f" ({prog['failed']} failed)" if prog['failed'] else ""))
    return 0 if prog["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
