"""桌面服务：随机端口、就绪、优雅停止、连续两次启动。"""
from __future__ import annotations

import urllib.error
import urllib.request

# 与被测逻辑同课：本机回环请求必须绕开任何代理
_direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get_status(port: int) -> int:
    try:
        with _direct_opener.open(f"http://127.0.0.1:{port}/", timeout=2) as r:
            return r.status
    except (urllib.error.URLError, OSError):
        return -1


def test_start_behind_hostile_proxy_env(desktop_env, monkeypatch):
    """回归：GUI 启动时 urllib 走系统/环境代理，探测必须强制直连。

    http://127.0.0.1:9 是死端口；若探测仍走代理（未用 ProxyHandler({})），
    服务会误判就绪探测失败。
    """
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)

    from desktop import server as srv

    h = srv.start(token="t")
    try:
        assert _get_status(h.port) == 200
    finally:
        srv.stop(h)
    assert not srv.port_is_open(h.port)


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
