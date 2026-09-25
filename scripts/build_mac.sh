#!/usr/bin/env bash
# SpellForge macOS 打包：产出 dist/SpellForge.app（--onedir --windowed）。
# 用法：bash scripts/build_mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/make_icons.py
python3 -m PyInstaller --noconfirm --clean desktop/spellforge.spec
echo
echo "构建完成: dist/SpellForge.app"
echo "冒烟自检: dist/SpellForge.app/Contents/MacOS/SpellForge --smoke"
