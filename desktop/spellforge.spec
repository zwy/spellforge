# -*- mode: python ; coding: utf-8 -*-
"""SpellForge 打包规格：--onedir --windowed。

- macOS：产出 dist/SpellForge.app（已在本机验证）。
- Windows：产出 dist/SpellForge/SpellForge.exe —— 未验证，
  待有 Windows 环境时用 scripts/build_windows.bat 构建并按 README 清单验收。

资源收集原则（阶段 A 审计结论）：
- 打包内置只读资源：web/static、种子 JSON（styles/subjects/spec_vocab）、
  docs 规范模板与默认规范文档。
- 不打包：.env、data/*.db（个人数据）、docs/需求-benchmarks.md、
  docs/screenshots、README 等开发文档。
- 用户数据一律写到 platformdirs 用户目录（styles.paths 桌面模式），
  与 .app 所在位置无关。
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve()   # spec 所在目录 = repo/desktop
REPO = ROOT.parent                 # 仓库根

# 统一应用版本来源；PyInstaller 的 macOS / Windows 资源信息和运行时 API 都用它。
sys.path.insert(0, str(REPO))
from spellforge.__version__ import __version__ as APP_VERSION

datas = [
    (str(REPO / "web" / "static"), "web/static"),
    (str(REPO / "data" / "styles.json"), "data"),
    (str(REPO / "data" / "subjects.json"), "data"),
    (str(REPO / "data" / "spec_vocab.json"), "data"),
    (str(REPO / "docs" / "spec_template.md"), "docs"),
    (str(REPO / "docs" / "通用自然语言提示词规范.md"), "docs"),
]

# 可选应用图标：desktop/assets/icon.png -> icns (macOS) / ico (Windows)
# 由 scripts/make_icons.py 在构建脚本里生成；缺省时使用系统默认图标。
ICON_PNG = ROOT / "assets" / "icon.png"
ICON_ICNS = ROOT / "assets" / "icon.icns"
ICON_ICO = ROOT / "assets" / "icon.ico"

hiddenimports = [
    # uvicorn 的动态加载模块（hooks-contrib 通常已覆盖，显式声明更稳）
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(REPO)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 这些包只被环境里的其他库条件性引用，SpellForge 运行时不需要
    excludes=[
        "pytest", "numpy", "PIL", "matplotlib", "pandas",
        "IPython", "jupyter", "rich", "tkinter",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Windows EXE 版本资源：右键 -> 属性 -> 详细信息。
# macOS 不需要；导入也仅在 Windows 分支执行，避免跨平台依赖。
def _version_tuple_for_windows(version: str) -> tuple[int, int, int, int]:
    numbers = []
    for part in version.split("."):
        digits = ""
        for char in part:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        numbers.append(int(digits))
    numbers.extend([0] * (4 - len(numbers)))
    return tuple(numbers[:4])


if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    file_version_tuple = _version_tuple_for_windows(APP_VERSION)
    windows_version = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=file_version_tuple,
            prodvers=file_version_tuple,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "080404b0",
                        [
                            StringStruct("CompanyName", "SpellForge"),
                            StringStruct("FileDescription", "咒语工坊 SpellForge"),
                            StringStruct("FileVersion", APP_VERSION),
                            StringStruct("InternalName", "SpellForge"),
                            StringStruct("LegalCopyright", "MIT License"),
                            StringStruct("OriginalFilename", "SpellForge.exe"),
                            StringStruct("ProductName", "咒语工坊 SpellForge"),
                            StringStruct("ProductVersion", APP_VERSION),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [2052, 1200])]),
        ],
    )
else:
    windows_version = None


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpellForge",
    version=windows_version,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_ICO) if (sys.platform == "win32" and ICON_ICO.exists()) else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SpellForge",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SpellForge.app",
        icon=str(ICON_ICNS) if ICON_ICNS.exists() else None,
        info_plist={
            "CFBundleName": "SpellForge",
            "CFBundleDisplayName": "咒语工坊 SpellForge",
            "CFBundleIdentifier": "com.spellforge.desktop",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHumanReadableCopyright": "MIT License",
        },
    )
elif sys.platform == "win32":
    # Windows：COLLECT 目录 dist/SpellForge 下的 SpellForge.exe 即可双击运行。
    # 未验证：需在真实 Windows 环境构建并按 README 清单验收（WebView2、
    # 退出无残留进程、%APPDATA%\SpellForge 持久化、移动目录后数据保留）。
    pass
