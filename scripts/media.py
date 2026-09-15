from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlunparse

import requests

from fetcher import DESKTOP_UA

IMG_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
}

MEDIA_EXT_BY_TYPE = {
    "video/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/x-m4a": ".m4a",
    "audio/mp4": ".m4a",
    "audio/amr": ".amr",
    "audio/silk": ".silk",
}

_MAGIC = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
    (b"BM", ".bmp"),
    (b"ID3", ".mp3"),
    (b"\x00\x00\x00\x18ftyp", ".mp4"),
    (b"\x00\x00\x00\x1cftyp", ".mp4"),
    (b"#!SILK", ".silk"),
    (b"#!AMR", ".amr"),
)

PLACEHOLDER_MAX = 4096


class MediaError(Exception):
    pass


def _hash_name(url: str, seed: str = "") -> str:
    return hashlib.md5((seed + url).encode("utf-8")).hexdigest()[:16]


def _strip_webp(url: str) -> str:
    parts = urlparse(url)
    q = parse_qs(parts.query, keep_blank_values=True)
    q.pop("tp", None)
    new_q = "&".join(f"{k}={v[0]}" for k, v in q.items())
    return urlunparse(parts._replace(query=new_q))


def _ext_from(content_type: str, body: bytes, table: dict, default: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in table:
        return table[ct]
    for magic, ext in _MAGIC:
        if body.startswith(magic):
            if magic == b"RIFF" and body[8:12] != b"WEBP":
                continue
            return ext
    return default


def download_image(url: str, dest_dir: Path, session: requests.Session, seed: str = "") -> str | None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    clean = _strip_webp(url)
    try:
        resp = session.get(
            clean,
            headers={"User-Agent": DESKTOP_UA, "Referer": "https://mp.weixin.qq.com/"},
            timeout=30,
        )
    except requests.RequestException:
        return None
    body = resp.content
    ct = resp.headers.get("Content-Type", "")
    if not ct.lower().startswith("image") and not any(body.startswith(m) for m, _ in _MAGIC):
        return None
    if len(body) <= PLACEHOLDER_MAX and b"\xff\xd8\xff" == body[:3] and ct.startswith("image/jpeg"):
        if len(body) < 2500:
            return None
    ext = _ext_from(ct, body, IMG_EXT_BY_TYPE, ".jpg")
    name = _hash_name(url, seed) + ext
    (dest_dir / name).write_bytes(body)
    return name


def download_media(url: str, dest_dir: Path, session: requests.Session, kind: str, seed: str = "") -> str | None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": DESKTOP_UA,
        "Referer": "https://mp.weixin.qq.com/",
        "Origin": "https://mp.weixin.qq.com",
    }
    if kind == "video":
        headers["Sec-Fetch-Site"] = "cross-site"
    try:
        resp = session.get(url, headers=headers, timeout=120)
    except requests.RequestException:
        return None
    if resp.status_code >= 400:
        return None
    body = resp.content
    if not body:
        return None
    ct = resp.headers.get("Content-Type", "")
    default = ".mp4" if kind == "video" else ".mp3"
    ext = _ext_from(ct, body, MEDIA_EXT_BY_TYPE, default)
    src_name = ""
    m = re.search(r"/([^/?]+\.(?:mp4|m4a|mp3))", url)
    if m:
        src_name = m.group(1)
    name = (src_name or (_hash_name(url, seed) + ext))
    if not name.lower().endswith(ext) and not src_name:
        name = _hash_name(url, seed) + ext
    (dest_dir / name).write_bytes(body)
    return name
