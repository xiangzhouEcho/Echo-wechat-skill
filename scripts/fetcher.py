from __future__ import annotations

import random
import re
import time
from urllib.parse import parse_qs, urlparse, urlunparse

import requests

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

CAPTCHA_MARKERS = ("wappoc_appmsgcaptcha", "环境异常", "完成验证后即可继续访问", "secitptpage")
DELETED_MARKERS = ("该内容已被发布者删除", "此内容因违规无法查看", "该内容暂时无法查看")

KEEP_PARAMS = ("__biz", "mid", "idx", "sn", "chksm")


class ArticleUnavailable(Exception):
    pass


class CaptchaTriggered(Exception):
    pass


def _build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": DESKTOP_UA,
            "Referer": "https://mp.weixin.qq.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    return s


def normalize_article_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    parts = urlparse(url)
    if "/s/" in parts.path:
        clean = parts._replace(query="", fragment="")
        return urlunparse(clean)
    q = parse_qs(parts.query, keep_blank_values=True)
    kept = []
    for name in KEEP_PARAMS:
        if name in q and q[name] and q[name][0]:
            kept.append(f"{name}={q[name][0]}")
    new_query = "&".join(kept)
    clean = parts._replace(query=new_query, fragment="")
    return urlunparse(clean)


def _classify(html: str, final_url: str) -> None:
    if any(m in html for m in DELETED_MARKERS):
        raise ArticleUnavailable("article deleted or removed")
    if "wappoc_appmsgcaptcha" in final_url or any(m in html for m in CAPTCHA_MARKERS):
        raise CaptchaTriggered("captcha / environment verification page returned")
    if 'id="js_content"' not in html and 'id="js_article"' not in html:
        raise ArticleUnavailable("no article content found in page")


def polite_sleep(delay: float) -> None:
    if delay <= 0:
        return
    time.sleep(delay + random.uniform(0, delay * 0.5))


def get_article_html(
    url: str,
    session: requests.Session | None = None,
    retries: int = 3,
    delay: float = 3.0,
) -> tuple[str, str]:
    session = session or _build_session()
    target = normalize_article_url(url)
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(target, timeout=30)
            resp.encoding = resp.apparent_encoding or "utf-8"
            html = resp.text
            _classify(html, resp.url)
            return html, resp.url
        except CaptchaTriggered as exc:
            last_exc = exc
            polite_sleep(delay * (attempt + 2))
        except requests.RequestException as exc:
            last_exc = exc
            polite_sleep(delay * (attempt + 1))
    raise last_exc or ArticleUnavailable("failed to fetch article")


def parse_album_url(url: str) -> tuple[str, str]:
    parts = urlparse(url.strip().strip('"').strip("'"))
    q = parse_qs(parts.query, keep_blank_values=True)
    biz = (q.get("__biz") or [""])[0]
    album_id = (q.get("album_id") or [""])[0]
    if not biz or not album_id:
        raise ValueError("album url must contain __biz and album_id parameters")
    return biz, album_id


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def get_album(
    biz: str,
    album_id: str,
    session: requests.Session | None = None,
    is_reverse: int = 0,
    delay: float = 1.0,
) -> tuple[dict, list[dict]]:
    session = session or _build_session()
    base = "https://mp.weixin.qq.com/mp/appmsgalbum"
    articles: list[dict] = []
    base_info: dict = {}
    begin_msgid = ""
    begin_itemidx = ""
    while True:
        params = {
            "action": "getalbum",
            "__biz": biz,
            "album_id": album_id,
            "count": "20",
            "is_reverse": str(is_reverse),
            "f": "json",
        }
        if begin_msgid:
            params["begin_msgid"] = begin_msgid
            params["begin_itemidx"] = begin_itemidx
        resp = session.get(base, params=params, timeout=30)
        data = resp.json()
        ret = (data.get("base_resp") or {}).get("ret")
        if ret not in (0, None):
            raise RuntimeError(f"album api error ret={ret}: {data.get('base_resp')}")
        album_resp = data.get("getalbum_resp") or {}
        if not base_info:
            base_info = album_resp.get("base_info") or {}
        page_items = _as_list(album_resp.get("article_list"))
        if not page_items:
            break
        articles.extend(page_items)
        last = page_items[-1]
        begin_msgid = last.get("msgid", "")
        begin_itemidx = last.get("itemidx", "")
        if str(album_resp.get("continue_flag", "0")) == "0":
            break
        polite_sleep(delay)
    _dedupe(articles)
    return base_info, articles


def _dedupe(articles: list[dict]) -> None:
    seen = set()
    out = []
    for a in articles:
        key = (a.get("msgid"), a.get("itemidx"))
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    articles[:] = out


def upgrade_link(url: str) -> str:
    url = (url or "").replace("&amp;", "&")
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url.split("#")[0]
