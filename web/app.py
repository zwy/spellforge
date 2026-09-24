"""Web 管理端：查看 / 更新 / 编辑 / （预留）LLM 优化。

启动:
    python -m web.app            # http://127.0.0.1:8765
    uvicorn web.app:app --reload
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from styles import personal, store
from styles.enrich import run as enrich_run
from styles.generate import generate
from styles.llm import get_llm_config
from styles.schema import CreativeCopyItem
from styles.scrape import scrape_all

# 后台 LLM 补全状态（单实例运行）
_enrich_state = {"running": False, "done": 0, "total": 0, "failed": 0, "error": None}

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"

app = FastAPI(title="咒语工坊 SpellForge")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:  # type: ignore[name-defined]
    from fastapi.responses import FileResponse
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/spec.md")
def spec_markdown() -> FileResponse:  # type: ignore[name-defined]
    """《通用自然语言提示词规范》markdown 原文。"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    doc = Path(__file__).resolve().parent.parent / "docs" / "通用自然语言提示词规范.md"
    if not doc.exists():
        raise HTTPException(404, "规范文档未生成，运行 python -m styles.spec")
    return FileResponse(doc, media_type="text/markdown")


@app.get("/api/styles")
def api_styles() -> dict:
    with store.connect() as conn:
        styles = store.load_styles(conn)
    return {
        "updated_at": store.utcnow(),
        "styles": [store.style_to_dict(s) for s in styles],
    }


@app.post("/api/scrape")
def api_scrape() -> dict:
    """触发一次重新抓取（同步执行，约 20 秒）。"""
    styles = scrape_all(verbose=False)
    if not styles:
        raise HTTPException(502, "抓取失败：未解析到数据")
    conn = store.connect()
    try:
        store.save_scrape(conn, styles)
        store.export_json(conn)
        return {
            "ok": True,
            "styles": len(styles),
            "scenarios": sum(len(s.scenarios) for s in styles),
            "updated_at": store.utcnow(),
        }
    finally:
        conn.close()


class ScenarioPatch(BaseModel):
    aspect_ratio: str | None = None
    aspect_ratio_source: str | None = "manual"
    creative_copy: list[CreativeCopyItem] | None = None


@app.patch("/api/scenarios/{style_id}/{scenario_id}")
def api_patch_scenario(style_id: str, scenario_id: str, patch: ScenarioPatch) -> dict:
    conn = store.connect()
    try:
        cur = conn.execute(
            "SELECT id FROM scenarios WHERE style_id=? AND id=?",
            (style_id, scenario_id),
        )
        if cur.fetchone() is None:
            raise HTTPException(404, "scenario not found")
        store.update_scenario_enrichment(
            conn, style_id, scenario_id,
            patch.aspect_ratio, patch.aspect_ratio_source,
            patch.creative_copy,
        )
        store.export_json(conn)
        return {"ok": True, "synced_json": str(store.JSON_PATH)}
    finally:
        conn.close()


@app.post("/api/enrich")
def api_enrich() -> dict:
    """后台触发 LLM 补全（跳过已补全的）。"""
    if _enrich_state["running"]:
        return {"ok": False, "detail": "已有任务在运行", **_enrich_state}

    def worker():
        _enrich_state.update(running=True, done=0, total=0, failed=0, error=None)
        try:
            # enrich.run 更新 styles.enrich._progress，这里轮询共享进度
            from styles import enrich as enrich_mod
            result = enrich_run(force=False)
            _enrich_state.update(running=False, **{
                "done": result["done"], "total": result["total"], "failed": result["failed"],
            })
        except Exception as e:  # noqa: BLE001
            _enrich_state.update(running=False, error=str(e))

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True, "started": True}


@app.get("/api/enrich/status")
def api_enrich_status() -> dict:
    from styles import enrich as enrich_mod
    p = enrich_mod._progress
    return {
        "running": _enrich_state["running"],
        "done": p.get("done", 0),
        "total": p.get("total", 0),
        "failed": p.get("failed", 0),
        "error": _enrich_state["error"],
    }


class GenerateRequest(BaseModel):
    style_id: str
    scenario_id: str
    template_label: str
    subject: str = ""
    aspect_ratio: str | None = None
    subject_id: int | None = None


@app.post("/api/generate")
def api_generate(req: GenerateRequest) -> dict:
    """按 风格 + 场景 + 模板 + 主体 生成新提示词（同步，约 1-3 分钟）。"""
    try:
        rec = generate(
            req.style_id, req.scenario_id, req.template_label,
            req.subject, req.aspect_ratio,
            subject_id=req.subject_id,
        )
        return rec
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"生成失败: {e}")


@app.get("/api/generations")
def api_generations(limit: int = 30) -> list[dict]:
    conn = personal.connect()
    try:
        return personal.load_generations(conn, limit)
    finally:
        conn.close()


class SubjectIn(BaseModel):
    type: str
    name: str
    description: str


@app.get("/api/subjects")
def api_subjects() -> list[dict]:
    conn = store.connect()
    try:
        return store.list_subjects(conn)
    finally:
        conn.close()


@app.post("/api/subjects")
def api_add_subject(body: SubjectIn) -> dict:
    if body.type not in store.SUBJECT_TYPES:
        raise HTTPException(400, f"类型应为 {'、'.join(store.SUBJECT_TYPES)} 之一")
    if not body.name.strip():
        raise HTTPException(400, "主体名称不能为空")
    if not body.description.strip():
        raise HTTPException(400, "主体描述不能为空")
    conn = store.connect()
    try:
        dup = store.find_subject(conn, body.type, body.name.strip())
        if dup:
            raise HTTPException(400, f"已存在同类型同名主体「{body.name.strip()}」（#{dup['id']}），请直接编辑使用")
        sid = store.add_subject(conn, body.type, body.name.strip(),
                                body.description.strip())
        return {"ok": True, "id": sid}
    finally:
        conn.close()


@app.patch("/api/subjects/{subject_id}")
def api_update_subject(subject_id: int, body: SubjectIn) -> dict:
    if body.type not in store.SUBJECT_TYPES:
        raise HTTPException(400, f"类型应为 {'、'.join(store.SUBJECT_TYPES)} 之一")
    if not body.name.strip() or not body.description.strip():
        raise HTTPException(400, "名称与描述不能为空")
    conn = store.connect()
    try:
        if store.get_subject(conn, subject_id) is None:
            raise HTTPException(404, "主体不存在")
        dup = store.find_subject(conn, body.type, body.name.strip())
        if dup and dup["id"] != subject_id:
            raise HTTPException(400, f"已存在同类型同名主体「{body.name.strip()}」（#{dup['id']}）")
        store.update_subject(conn, subject_id, body.type, body.name.strip(),
                             body.description.strip())
        store.export_subjects(conn)
        return {"ok": True}
    finally:
        conn.close()


@app.delete("/api/subjects/{subject_id}")
def api_delete_subject(subject_id: int) -> dict:
    conn = store.connect()
    try:
        if store.get_subject(conn, subject_id) is None:
            raise HTTPException(404, "主体不存在")
        store.delete_subject(conn, subject_id)
        store.export_subjects(conn)
        return {"ok": True}
    finally:
        conn.close()


def mask_key(k: str) -> str:
    if not k:
        return ""
    if len(k) <= 8:
        return k[:2] + "****"
    return k[:5] + "****" + k[-4:]


class LLMProfileIn(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: str | None = None  # 编辑时留空 = 不修改 key


@app.get("/api/llm/profiles")
def api_llm_profiles() -> list[dict]:
    conn = personal.connect()
    try:
        return [
            {**p, "api_key": None, "api_key_masked": mask_key(p["api_key"])}
            for p in personal.list_profiles(conn)
        ]
    finally:
        conn.close()


@app.get("/api/llm/current")
def api_llm_current() -> dict:
    cfg = get_llm_config()
    return {
        "source": cfg["source"],
        "profile_name": cfg.get("profile_name"),
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "api_key_masked": mask_key(cfg["api_key"]),
    }


@app.post("/api/llm/profiles")
def api_add_profile(body: LLMProfileIn) -> dict:
    name = body.name.strip()
    base_url = body.base_url.strip().rstrip("/")
    model = body.model.strip()
    api_key = (body.api_key or "").strip()
    if not name:
        raise HTTPException(400, "配置名称不能为空")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "BASE_URL 需以 http(s):// 开头")
    if not model:
        raise HTTPException(400, "模型不能为空")
    if not api_key:
        raise HTTPException(400, "API Key 不能为空")
    conn = personal.connect()
    try:
        if any(p["name"] == name for p in personal.list_profiles(conn)):
            raise HTTPException(400, f"已存在同名配置「{name}」")
        pid = personal.add_profile(conn, name, base_url, api_key, model)
        return {"ok": True, "id": pid}
    finally:
        conn.close()


@app.patch("/api/llm/profiles/{pid}")
def api_update_profile(pid: int, body: LLMProfileIn) -> dict:
    name = body.name.strip()
    base_url = body.base_url.strip().rstrip("/")
    model = body.model.strip()
    api_key = (body.api_key or "").strip() or None
    if not name or not base_url or not model:
        raise HTTPException(400, "名称 / BASE_URL / 模型不能为空")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "BASE_URL 需以 http(s):// 开头")
    conn = personal.connect()
    try:
        if personal.get_profile(conn, pid) is None:
            raise HTTPException(404, "配置不存在")
        if any(p["name"] == name and p["id"] != pid for p in personal.list_profiles(conn)):
            raise HTTPException(400, f"已存在同名配置「{name}」")
        personal.update_profile(conn, pid, name, base_url, api_key, model)
        return {"ok": True}
    finally:
        conn.close()


@app.delete("/api/llm/profiles/{pid}")
def api_delete_profile(pid: int) -> dict:
    conn = personal.connect()
    try:
        if personal.get_profile(conn, pid) is None:
            raise HTTPException(404, "配置不存在")
        personal.delete_profile(conn, pid)
        return {"ok": True}
    finally:
        conn.close()


@app.post("/api/llm/profiles/{pid}/activate")
def api_activate_profile(pid: int) -> dict:
    conn = personal.connect()
    try:
        if personal.get_profile(conn, pid) is None:
            raise HTTPException(404, "配置不存在")
        personal.activate_profile(conn, pid)
        return {"ok": True}
    finally:
        conn.close()


@app.get("/api/stats")
def api_stats() -> dict:
    conn = store.connect()
    try:
        styles = conn.execute("SELECT COUNT(*) c FROM styles").fetchone()["c"]
        scenarios = conn.execute("SELECT COUNT(*) c FROM scenarios").fetchone()["c"]
        enriched = conn.execute(
            "SELECT COUNT(*) c FROM scenarios WHERE enriched_at IS NOT NULL"
        ).fetchone()["c"]
        last_run = conn.execute(
            "SELECT started_at, finished_at, status FROM scrape_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "styles": styles,
            "scenarios": scenarios,
            "enriched": enriched,
            "last_run": dict(last_run) if last_run else None,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
