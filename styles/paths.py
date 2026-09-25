"""统一资源 / 用户数据路径。

设计原则：
- 源码开发模式（默认）：一切路径与历史行为一致——内置资源读仓库，
  用户数据写在仓库 data/ 与 docs/，python -m web.app 等用法不变。
- 桌面打包模式（检测 sys.frozen，或 SPELLFORGE_DESKTOP=1 模拟）：
  内置资源从打包目录读取（PyInstaller _MEIPASS），用户数据一律写到
  platformdirs 用户目录，与程序所在位置无关，升级/移动不丢失。
- 测试可注入：SPELLFORGE_DATA_DIR 重定向用户数据目录，
  SPELLFORGE_BUNDLED_DIR 重定向内置资源目录。

双角色文件策略（既是种子又会在运行时更新，如 data/styles.json）：
包内默认值只读；首次访问复制到用户目录（已存在则绝不覆盖），
之后读写均用用户副本。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "SpellForge"
SPEC_DOC_NAME = "通用自然语言提示词规范.md"

_repo_root = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """是否按打包桌面模式解析路径。"""
    if os.environ.get("SPELLFORGE_DESKTOP") == "1":
        return True
    return bool(getattr(sys, "frozen", False))


def bundled_root() -> Path:
    """内置只读资源根目录。

    PyInstaller 打包：_MEIPASS（onefile/onedir 都会提供）；
    源码/开发期桌面模式（SPELLFORGE_DESKTOP=1 但未打包）：仓库根。
    """
    override = os.environ.get("SPELLFORGE_BUNDLED_DIR")
    if override:
        return Path(override)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _repo_root


def bundled_resource(*parts: str) -> Path:
    """内置只读资源路径（如 bundled_resource("web", "static")）。"""
    return bundled_root().joinpath(*parts)


def user_data_dir() -> Path:
    """用户可写持久数据目录（不存在则创建）。"""
    override = os.environ.get("SPELLFORGE_DATA_DIR")
    if override:
        d = Path(override)
    elif is_frozen():
        from platformdirs import user_data_dir as _udd

        d = Path(_udd(APP_NAME, appauthor=False))
    else:
        d = _repo_root / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def user_data_path(*parts: str) -> Path:
    """用户数据目录下的路径。"""
    return user_data_dir().joinpath(*parts)


def ensure_user_copy(user_rel: tuple[str, ...],
                     bundled_rel: tuple[str, ...]) -> Path:
    """首启把包内默认资源复制到用户目录（不覆盖已有），返回用户副本路径。"""
    dst = user_data_path(*user_rel)
    if not dst.exists():
        src = bundled_resource(*bundled_rel)
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return dst


def resource_with_user_override(user_rel: tuple[str, ...],
                                bundled_rel: tuple[str, ...]) -> Path:
    """读取顺序：用户覆盖副本 > 包内默认资源。不主动复制。"""
    user = user_data_path(*user_rel)
    if user.exists():
        return user
    return bundled_resource(*bundled_rel)


# ---------- 语义化接口 ----------

def db_path() -> Path:
    """共享库 app.db。"""
    return user_data_path("app.db")


def personal_db_path() -> Path:
    """私有库 personal.db（LLM 配置与生成历史）。"""
    return user_data_path("personal.db")


def styles_json_path() -> Path:
    """styles.json：种子 + 运行时导出，读写的都是用户副本。"""
    return ensure_user_copy(("styles.json",), ("data", "styles.json"))


def subjects_json_path() -> Path:
    """subjects.json：种子 + 运行时导出，读写的都是用户副本。"""
    return ensure_user_copy(("subjects.json",), ("data", "subjects.json"))


def spec_vocab_path() -> Path:
    """spec_vocab.json：包内默认缓存；刷新时写用户副本。"""
    return ensure_user_copy(("spec_vocab.json",),
                            ("data", "spec_vocab.json"))


def creative_templates_path() -> Path:
    """creative_templates.json：运行时导出产物，只写用户目录。"""
    return user_data_path("creative_templates.json")


def spec_template_path() -> Path:
    """规范模板：内置只读资源。"""
    return bundled_resource("docs", "spec_template.md")


def spec_doc_path() -> Path:
    """《通用自然语言提示词规范》：用户重生成的版本优先，包内默认兜底。"""
    return resource_with_user_override(("docs", SPEC_DOC_NAME),
                                       ("docs", SPEC_DOC_NAME))


def spec_output_path() -> Path:
    """规范文档写出位置：桌面模式写用户目录，源码模式保持仓库 docs/。"""
    if is_frozen():
        return user_data_path("docs", SPEC_DOC_NAME)
    return bundled_resource("docs", SPEC_DOC_NAME)


def static_dir() -> Path:
    """前端静态资源目录。"""
    return bundled_resource("web", "static")


def env_file_path() -> Path | None:
    """.env 位置：源码模式读仓库根；打包模式只读用户目录（用户自放才生效）。

    返回 None 表示不加载任何 .env。
    """
    if is_frozen():
        candidate = user_data_path(".env")
        return candidate if candidate.exists() else None
    return _repo_root / ".env"
