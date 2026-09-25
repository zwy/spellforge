"""桌面模式本机服务：受控启动 / 就绪探测 / 优雅停止。

- 只监听 127.0.0.1，端口由系统分配（port=0），避免固定端口冲突，
  也避免「先测空闲再绑定」的竞态。
- uvicorn 跑在受控的非主线程；webview 要求主线程，因此服务必须后台化。
- stop() 先优雅停止，超时后强制退出，最终兜底直接结束进程，不留孤儿。
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import uvicorn

import web.app as webapp


@dataclass
class ServerHandle:
    server: uvicorn.Server
    thread: threading.Thread
    port: int
    token: str
    stopped: threading.Event = field(default_factory=threading.Event)


class StartError(RuntimeError):
    """服务启动失败（绑定失败 / 启动超时 / 就绪探测失败）。"""


def start(token: str, timeout: float = 15.0) -> ServerHandle:
    """启动本机服务并等待就绪。失败抛 StartError，信息可直接展示给用户。"""
    guard = webapp.install_desktop_guard(webapp.app, token=token)
    config = uvicorn.Config(
        guard, host="127.0.0.1", port=0,
        log_level="warning", access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True,
                              name="spellforge-server")
    thread.start()

    deadline = time.monotonic() + timeout
    while not server.started:
        if not thread.is_alive():
            raise StartError("后端服务启动失败（进程提前退出），请查看日志输出")
        if time.monotonic() > deadline:
            server.should_exit = True
            thread.join(timeout=2)
            raise StartError(f"后端服务启动超时（>{timeout:.0f}s）")
        time.sleep(0.05)

    try:
        port = server.servers[0].sockets[0].getsockname()[1]
    except (IndexError, AttributeError, OSError) as e:
        server.should_exit = True
        thread.join(timeout=2)
        raise StartError(f"无法确定服务端口: {e}") from e

    # 先放行本机 Host 再探测，否则防护会把就绪探测本身拦下
    guard.set_allowed_hosts([f"127.0.0.1:{port}", f"localhost:{port}"])
    if not _wait_ready(port, deadline):
        server.should_exit = True
        thread.join(timeout=2)
        raise StartError(f"服务已绑定端口 {port} 但就绪探测失败（HTTP 请求无响应）")

    return ServerHandle(server=server, thread=thread, port=port, token=token)


def _wait_ready(port: int, deadline: float) -> bool:
    """就绪探测：真实 HTTP 请求拿到 2xx 才算就绪（比 TCP 可通更强）。"""
    url = f"http://127.0.0.1:{port}/"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, socket.timeout, OSError):
            pass
        time.sleep(0.1)
    return False


def stop(handle: ServerHandle, timeout: float = 5.0) -> None:
    """优雅停止：先 should_exit，超时 force_exit，最终兜底结束进程。"""
    if handle.stopped.is_set():
        return
    handle.stopped.set()
    handle.server.should_exit = True
    handle.thread.join(timeout)
    if handle.thread.is_alive():
        handle.server.force_exit = True
        handle.thread.join(2)
    if handle.thread.is_alive():
        print("[desktop] 服务线程未能退出，强制结束进程", flush=True)
        os._exit(1)


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0
