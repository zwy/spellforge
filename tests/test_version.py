"""应用版本号元数据与展示接口。"""
from __future__ import annotations

from fastapi.testclient import TestClient

import spellforge
import web.app as webapp


def test_version_api_returns_single_source(desktop_env):
    client = TestClient(webapp.app)
    r = client.get("/api/version")
    assert r.status_code == 200
    assert r.json() == {
        "app": "SpellForge",
        "version": spellforge.__version__,
        "display_version": f"v{spellforge.__version__}",
    }
