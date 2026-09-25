"""桌面服务：随机端口、就绪、优雅停止、连续两次启动。"""
from __future__ import annotations

import urllib.request


def _get_status(port: int) -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
            return r.status
    except OSError:
        return -1


def test_start_ready_stop_release_and_restart(desktop_env):
    from desktop import server as srv

    h1 = srv.start(token="t1")
    try:
        assert h1.port > 0
        assert srv.port_is_open(h1.port)
        assert _get_status(h1.port) == 200
    finally:
        srv.stop(h1)
    assert not srv.port_is_open(h1.port)

    # 连续第二次启动：随机端口不冲突，服务照常就绪
    h2 = srv.start(token="t2")
    try:
        assert h2.port > 0
        assert _get_status(h2.port) == 200
    finally:
        srv.stop(h2)
    assert not srv.port_is_open(h2.port)
