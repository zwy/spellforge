"""LLM 客户端（OpenAI 规范 chat completions，兼容任意 provider）。

配置解析优先级：设置库（personal.db 启用中的配置）> 环境变量 > 项目根目录 .env。
环境变量：LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
（兼容旧名 OPENROUTER_API_KEY / OPENROUTER_MODEL）。
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# 直连会话（忽略本机失效代理变量），与 fetch.py 同策略
_session = requests.Session()
_session.trust_env = False


def _load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_env_file()

DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"


def get_llm_config() -> dict:
    """解析当前生效的 LLM 配置。

    优先级：personal.db 中启用中的配置 > 环境变量 / .env。
    """
    try:
        from . import personal
        prof = personal.get_active_profile(personal.connect())
        if prof:
            return {
                "source": "settings",
                "profile_id": prof["id"],
                "profile_name": prof["name"],
                "base_url": prof["base_url"].rstrip("/"),
                "api_key": prof["api_key"],
                "model": prof["model"],
            }
    except Exception:  # noqa: BLE001 —— 设置库不可用时回退环境变量
        pass
    return {
        "source": "env",
        "profile_id": None,
        "profile_name": None,
        "base_url": (os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        "api_key": (os.environ.get("LLM_API_KEY")
                    or os.environ.get("OPENROUTER_API_KEY") or ""),
        "model": (os.environ.get("LLM_MODEL")
                  or os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL),
    }


class LLMError(RuntimeError):
    pass


def chat(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 4000,
    json_mode: bool = True,
    retries: int = 3,
) -> str:
    """调用一次 chat completion，返回 assistant 文本。

    json_mode=True 时请求 JSON 输出并关闭 reasoning 回显。
    带指数退避重试。
    """
    cfg = get_llm_config()
    api_key = cfg["api_key"]
    if not api_key:
        raise LLMError(
            "缺少 API Key：请在左上角 ⚙ 设置里添加 LLM 配置，"
            "或设置环境变量 LLM_API_KEY / .env 文件")
    url = cfg["base_url"] + "/chat/completions"

    body: dict = {
        "model": model or cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "reasoning": {"exclude": True},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            try:
                resp = _session.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=180,
                )
            except requests.RequestException:
                # 直连失败时回退走环境代理
                resp = requests.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=180,
                )
            if resp.status_code == 429:
                wait = 2 ** attempt * 3
                time.sleep(wait)
                last_err = LLMError("rate limited")
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"].get("content")
            if not content:
                raise LLMError(f"empty content: {json.dumps(data.get('usage', {}))}")
            return content
        except (requests.RequestException, KeyError, LLMError) as e:  # noqa: PERF203
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
    raise LLMError(f"LLM call failed after {retries} attempts: {last_err}")


def chat_json(messages: list[dict], **kw) -> dict:
    """调用并解析 JSON 输出；解析失败时尝试从文本中截取第一个 JSON 对象。"""
    text = chat(messages, json_mode=True, **kw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{", text)
        if m:
            try:
                return json.loads(text[m.start():text.rfind("}") + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"invalid JSON response: {text[:200]}")
