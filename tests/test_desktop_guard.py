"""桌面防护中间件：Host / Origin / 令牌。"""
from __future__ import annotations

from fastapi.testclient import TestClient

import web.app as webapp

TOKEN = "test-token-123"
HOSTS = ["127.0.0.1:8765", "localhost:8765"]


def _client(base_url: str = "http://127.0.0.1:8765") -> TestClient:
    wrapped = webapp.install_desktop_guard(webapp.app, token=TOKEN)
    wrapped.set_allowed_hosts(HOSTS)
    return TestClient(wrapped, base_url=base_url)


def test_get_allowed_without_token(desktop_env):
    r = _client().get("/api/styles")
    assert r.status_code == 200


def test_post_without_token_rejected(desktop_env):
    r = _client().post("/api/scrape")
    assert r.status_code == 403
    assert "令牌" in r.json()["detail"]


def test_post_with_wrong_token_rejected(desktop_env):
    r = _client().post("/api/scrape", headers={"X-SF-Token": "bad"})
    assert r.status_code == 403


def test_post_with_token_passes_guard(desktop_env):
    # 场景不存在：通过防护进入业务层（404），证明令牌校验已放行
    r = _client().patch(
        "/api/scenarios/none/none",
        json={"aspect_ratio": "1:1"},
        headers={"X-SF-Token": TOKEN},
    )
    assert r.status_code == 404


def test_foreign_origin_rejected_even_with_token(desktop_env):
    r = _client().post(
        "/api/scrape",
        headers={"X-SF-Token": TOKEN, "Origin": "http://evil.example"},
    )
    assert r.status_code == 403
    assert "Origin" in r.json()["detail"]


def test_same_origin_accepted(desktop_env):
    # 用不触发网络的写接口验证同源放行（进入业务层 -> 404 场景不存在）
    r = _client().patch(
        "/api/scenarios/none/none",
        json={"aspect_ratio": "1:1"},
        headers={"X-SF-Token": TOKEN, "Origin": "http://127.0.0.1:8765"},
    )
    assert r.status_code == 404


def test_dns_rebinding_host_rejected(desktop_env):
    r = _client(base_url="http://attacker.example:8765").get("/api/styles")
    assert r.status_code == 403
