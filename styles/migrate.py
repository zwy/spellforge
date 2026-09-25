"""一次性迁移：把开发仓库里的旧数据导入桌面用户数据目录。

用法:
    python -m styles.migrate                # 预演（不写任何文件）
    python -m styles.migrate --apply        # 真正执行
    python -m styles.migrate --apply --force
                                            # 已存在的目标先做时间戳备份再导入

规则：
- 只读取当前项目根目录（styles 包所在仓库）的 data/ 与 docs/，不扫描其他位置。
- 目标是 platformdirs 用户数据目录（SpellForge 桌面版数据目录；
  可用 SPELLFORGE_DATA_DIR 覆盖；源码模式下也指向 platformdirs，
  避免把仓库 data/ 复制到自身）。
- 默认「不覆盖」：目标已存在的同名文件直接跳过并报告。
- --force 时先备份目标（*.bak.YYYYmmdd-HHMMSS）再导入，旧数据永不丢失。
- 迁移前先校验所有源文件可读；任何失败都不会改动目标目录。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from . import paths

REPO_ROOT = Path(__file__).resolve().parent.parent

# (源相对路径, 目标相对路径)
FILES: list[tuple[str, str]] = [
    ("data/app.db", "app.db"),
    ("data/personal.db", "personal.db"),
    ("data/styles.json", "styles.json"),
    ("data/subjects.json", "subjects.json"),
    ("data/spec_vocab.json", "spec_vocab.json"),
    ("data/creative_templates.json", "creative_templates.json"),
    (f"docs/{paths.SPEC_DOC_NAME}", f"docs/{paths.SPEC_DOC_NAME}"),
]


def _check_sources(src_root: Path) -> list[str]:
    problems: list[str] = []
    for src_rel, _ in FILES:
        src = src_root / src_rel
        if not src.exists():
            continue
        if src.suffix == ".db":
            try:
                conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                conn.execute("SELECT 1")
                conn.close()
            except sqlite3.Error as e:
                problems.append(f"无法读取数据库 {src}: {e}")
        else:
            try:
                src.read_bytes()
            except OSError as e:
                problems.append(f"无法读取文件 {src}: {e}")
    return problems


def _backup(target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = target.with_name(target.name + f".bak.{stamp}")
    shutil.copy2(target, bak)
    return bak


def _target_dir() -> Path:
    """迁移目标：桌面用户数据目录（与源码模式回退无关）。"""
    override = os.environ.get("SPELLFORGE_DATA_DIR")
    if override:
        return Path(override)
    from platformdirs import user_data_dir as _udd

    return Path(_udd(paths.APP_NAME, appauthor=False))


def migrate(src_root: Path = REPO_ROOT, apply: bool = False,
            force: bool = False) -> int:
    dest_dir = _target_dir()
    src_root = Path(src_root).resolve()
    problems = _check_sources(src_root)
    if problems:
        for p in problems:
            print(f"[migrate] 校验失败：{p}", file=sys.stderr)
        print("[migrate] 已中止，目标目录未做任何改动", file=sys.stderr)
        return 1

    plan: list[tuple[str, Path, Path]] = []
    skipped: list[str] = []
    for src_rel, dst_rel in FILES:
        src = src_root / src_rel
        if not src.exists():
            continue
        dst = dest_dir / dst_rel
        if src.resolve() == dst.resolve():
            skipped.append(f"{src_rel}（源与目标相同）")
            continue
        if dst.exists() and not force:
            skipped.append(src_rel)
            continue
        plan.append((src_rel, src, dst))

    if not apply:
        print(f"[migrate] 预演（目标目录 {dest_dir}）")
        for src_rel, src, dst in plan:
            print(f"  copy {src} -> {dst}")
        if skipped:
            print("  跳过（目标已存在，未用 --force）：", ", ".join(skipped))
        print("[migrate] 未写入任何文件。确认无误后加 --apply 执行。")
        return 0

    backed_up: list[str] = []
    copied: list[str] = []
    errors: list[str] = []
    for src_rel, src, dst in plan:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():  # force 模式下
                bak = _backup(dst)
                backed_up.append(f"{dst.name} -> {bak.name}")
            if src.suffix == ".db":
                # 只读打开源库，避免 WAL checkpoint 改动旧文件
                source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                target = sqlite3.connect(dst)
                try:
                    source.backup(target)
                finally:
                    source.close()
                    target.close()
            else:
                shutil.copy2(src, dst)
            copied.append(src_rel)
        except OSError as e:
            errors.append(f"{src}: {e}")
        except sqlite3.Error as e:
            errors.append(f"{src}: {e}")

    for c in copied:
        print(f"[migrate] 已导入 {c}")
    for b in backed_up:
        print(f"[migrate] 已备份 {b}")
    for s in skipped:
        print(f"[migrate] 跳过（目标已存在）: {s}")
    if errors:
        for e in errors:
            print(f"[migrate] 失败：{e}", file=sys.stderr)
        print("[migrate] 部分文件已导入；源文件未被修改。", file=sys.stderr)
        return 1
    if not copied and not skipped:
        print(f"[migrate] 在 {src_root} 没有找到可迁移的数据文件。")
    print(f"[migrate] 完成。用户数据目录: {dest_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="旧开发目录数据 -> 用户目录 迁移")
    ap.add_argument("--apply", action="store_true", help="真正执行（默认仅预演）")
    ap.add_argument("--force", action="store_true",
                    help="目标已存在时先备份再导入（默认跳过）")
    ap.add_argument("--source", default=None, help="源仓库根目录（默认当前仓库）")
    args = ap.parse_args()
    if args.force and not args.apply:
        ap.error("--force 需要配合 --apply 使用")
    return migrate(
        src_root=Path(args.source) if args.source else REPO_ROOT,
        apply=args.apply, force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
