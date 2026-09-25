"""SpellForge 桌面入口。

用法:
    python -m desktop.main          # 打开桌面窗口
    python -m desktop.main --smoke  # 自动化冒烟：开窗 2.5s 后自动关闭并自检退出

流程：
  1. 初始化用户数据目录（styles.paths 桌面模式）
  2. 受控启动本机服务（127.0.0.1 随机端口 + 就绪探测 + 每次启动的访问令牌）
  3. 主线程打开 pywebview 窗口；窗口关闭后优雅停止服务
  4. 任何启动失败都给出可诊断信息（错误窗口 / stderr），不留白屏
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
import threading

from spellforge import __version__ as APP_VERSION

# 必须在导入任何 styles / web 模块之前声明桌面模式
os.environ.setdefault("SPELLFORGE_DESKTOP", "1")

APP_TITLE = f"咒语工坊 SpellForge v{APP_VERSION}"


def _format_exception(e: Exception) -> list[str]:
    import traceback

    return traceback.format_exception(type(e), e, e.__traceback__)


def _show_startup_error(message: str) -> None:
    """启动失败时给出可诊断信息；pywebview 不可用则退回 stderr。"""
    print(f"[desktop] 启动失败: {message}", file=sys.stderr, flush=True)
    try:
        import webview
    except ImportError:
        print("[desktop] 未安装 pywebview：pip install pywebview", file=sys.stderr)
        raise SystemExit(1)
    html = f"""
    <div style="font-family:-apple-system,'PingFang SC',sans-serif;
                padding:32px;line-height:1.7;color:#c0392b">
      <h2>SpellForge 启动失败</h2>
      <pre style="white-space:pre-wrap;color:#333">{message}</pre>
      <p style="color:#888">关闭此窗口后应用退出。</p>
    </div>"""
    webview.create_window(f"SpellForge · 启动失败", html=html, width=560, height=320)
    webview.start()


def run_gui(url: str, smoke: bool = False) -> None:
    """主线程启动 pywebview。返回后（窗口已关闭）由调用方停止服务。"""
    try:
        import webview
    except ImportError:
        print("[desktop] 缺少 pywebview：pip install pywebview", file=sys.stderr)
        raise SystemExit(1)
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.settings["ALLOW_DOWNLOADS"] = True
    window = webview.create_window(APP_TITLE, url, width=1280, height=860,
                                   min_size=(960, 640))
    if smoke:
        timer = threading.Timer(2.5, window.destroy)
        timer.daemon = True
        timer.start()
    webview.start()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SpellForge 桌面模式")
    ap.add_argument("--smoke", action="store_true",
                    help="自动化冒烟：自动开窗 2.5 秒后关闭并自检")
    args = ap.parse_args(argv)

    token = secrets.token_urlsafe(32)
    try:
        from desktop import server as srv  # noqa: E402  延迟导入：失败进错误窗口

        handle = srv.start(token=token)
    except Exception as e:  # noqa: BLE001  启动失败必须给出可诊断信息
        _show_startup_error(
            f"{''.join(_format_exception(e))}\n"
            "常见原因：pywebview 未安装、静态资源缺失、用户目录不可写。")
        return 1

    try:
        url = f"http://127.0.0.1:{handle.port}/?sf_token={handle.token}"
        run_gui(url, smoke=args.smoke)
    finally:
        srv.stop(handle)

    if args.smoke:
        released = not srv.port_is_open(handle.port)
        line = f"[smoke] port={handle.port} ready=ok stopped=ok " \
               f"port_released={'yes' if released else 'NO'}"
        print(line, flush=True)
        # 桌面模式（含 Windows windowed exe）没有可靠控制台输出，结果落盘便于验收
        try:
            from styles import paths
            (paths.user_data_dir() / "smoke_result.txt").write_text(
                line + "\n", encoding="utf-8")
        except OSError:
            pass
        return 0 if released else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
