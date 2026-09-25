#!/usr/bin/env python3
"""从 desktop/assets/icon.png 生成本平台所需的图标文件。

- macOS：desktop/assets/icon.iconset/ 与 icon.icns（供 .app 使用）
- Windows：desktop/assets/icon.ico（供 PyInstaller EXE 使用）

用法：python3 scripts/make_icons.py
若无 icon.png 则安静退出（退出码 0），构建脚本可无条件调用。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "desktop" / "assets"
SRC = ASSETS / "icon.png"

ICONSET_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def make_icns() -> Path | None:
    iconset = ASSETS / "icon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    for px in ICONSET_SIZES:
        for half, name in ((px, f"icon_{px}x{px}.png"),
                           (px // 2, f"icon_{px // 2}x{px // 2}@2x.png")):
            out = iconset / name
            subprocess.run(
                ["sips", "-z", str(px), str(px), str(SRC),
                 "--out", str(out)],
                check=True, capture_output=True)
    icns = ASSETS / "icon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset),
                    "-o", str(icns)], check=True, capture_output=True)
    return icns


def make_ico() -> Path:
    from PIL import Image

    img = Image.open(SRC)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
             (128, 128), (256, 256)]
    out = ASSETS / "icon.ico"
    img.save(out, format="ICO", sizes=sizes)
    return out


def main() -> int:
    if not SRC.exists():
        print(f"[icons] 未找到 {SRC}，跳过（使用系统默认图标）")
        return 0
    ASSETS.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        icns = make_icns()
        print(f"[icons] 已生成 {icns}")
    elif sys.platform == "win32":
        try:
            ico = make_ico()
            print(f"[icons] 已生成 {ico}")
        except ImportError:
            print("[icons] 需要 Pillow 生成 .ico：pip install pillow")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
