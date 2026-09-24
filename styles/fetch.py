"""HTTP 抓取 openrouter.ai styles 页面。"""
from __future__ import annotations

import requests

BASE = "https://openrouter.ai"
STYLES_LENS = "/benchmarks/media/images"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 直连会话（忽略环境代理变量，避免本机失效的 ALL_PROXY 劫持请求）
_session = requests.Session()
_session.trust_env = False
_session.headers.update({"User-Agent": UA})


def fetch_page(path: str, timeout: int = 30) -> str:
    """抓取任意 openrouter 页面 HTML。

    默认直连；若直连失败（如网络需要代理），回退到走环境代理再试一次。
    """
    url = BASE + path
    try:
        resp = _session.get(url, timeout=timeout)
    except requests.RequestException:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def style_url(slug: str) -> str:
    return f"{BASE}{STYLES_LENS}/{slug}"
