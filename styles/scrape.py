"""抓取主流程入口。

用法:
    python -m styles.scrape            # 全量抓取 -> SQLite -> styles.json
    python -m styles.scrape --dry-run  # 只抓取并打印统计，不落库

流程:
  1. 请求任意一个 styles 页，从导航数据解出全部 style 列表（含分组）
  2. 逐个抓取 style 页，解析 challenge（页面级信息）+ scenarios（各场景 prompt）
  3. 写入 SQLite（保留 aspect_ratio / creative_copy 等扩展字段）
  4. 同步导出 data/styles.json
"""
from __future__ import annotations

import argparse
import sys
import time

from . import parse as parser
from . import store
from .fetch import fetch_page, STYLES_LENS
from pathlib import Path

from .schema import Style


def scrape_all(verbose: bool = True) -> list[Style]:
    items: list[dict] = []
    styles: list[Style] = []

    # 1) 用第一个 style 页拿导航列表。若尚未知道 slug，先抓默认跳转页。
    first_path = f"{STYLES_LENS}/portraits"  # 任一 style 页都含完整导航列表
    html = fetch_page(first_path)
    flight = parser.extract_flight(html)
    items = parser.parse_style_list(flight)
    if verbose:
        print(f"[list] styles found: {len(items)}")

    # 2) 逐个抓取
    for i, item in enumerate(items, 1):
        slug = item["id"]
        group = item.get("group", "")
        if verbose:
            print(f"[{i}/{len(items)}] {group} / {item.get('label', slug)} ...", end=" ")
        try:
            page_html = fetch_page(f"{STYLES_LENS}/{slug}")
        except Exception as e:  # noqa: BLE001 —— 单页失败不中断整体
            print(f"FAILED: {e}")
            continue
        style = parser.parse_style_page(slug, group, page_html)
        if style is None:
            print("no challenge data")
            continue
        styles.append(style)
        if verbose:
            print(f"{len(style.scenarios)} scenarios")

    return styles


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取 openrouter styles 数据")
    ap.add_argument("--dry-run", action="store_true", help="只抓取统计，不写库")
    ap.add_argument("--json-out", default=None, help="styles.json 输出路径覆盖")
    args = ap.parse_args()

    conn = store.connect()
    run_id = conn.execute(
        "INSERT INTO scrape_runs (started_at, status) VALUES (?, 'running')",
        (store.utcnow(),),
    ).lastrowid
    conn.commit()

    try:
        styles = scrape_all()
        total_scenarios = sum(len(s.scenarios) for s in styles)
        if not styles:
            raise RuntimeError("no styles parsed")
        if not args.dry_run:
            store.save_scrape(conn, styles)
            out_path = store.export_json(
                conn, Path(args.json_out) if args.json_out else None
            )
            print(f"\nOK: {len(styles)} styles / {total_scenarios} scenarios")
            print(f"  db   -> {store.DB_PATH}")
            print(f"  json -> {out_path}")
        else:
            print(f"\n(dry-run) would save {len(styles)} styles / {total_scenarios} scenarios")

        conn.execute(
            """UPDATE scrape_runs SET finished_at=?, styles_count=?,
               scenarios_count=?, status='ok' WHERE id=?""",
            (store.utcnow(), len(styles), total_scenarios, run_id),
        )
        conn.commit()
        return 0
    except Exception as e:  # noqa: BLE001
        conn.execute(
            "UPDATE scrape_runs SET finished_at=?, status='error', error=? WHERE id=?",
            (store.utcnow(), str(e), run_id),
        )
        conn.commit()
        print(f"scrape failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
