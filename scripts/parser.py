from __future__ import annotations

import html as htmlmod
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

_JS_STRING = {
    "title": r"var\s+msg_title\s*=\s*(['\"])(.*?)\1",
    "author": r"var\s+author\s*=\s*(['\"])(.*?)\1",
    "user_name": r"var\s+user_name\s*=\s*(['\"])(.*?)\1",
}


def _first_group2(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(2) if m else None


def _extract_ct(text: str) -> int | None:
    m = re.search(r'var\s+ct\s*=\s*"(\d+)"', text)
    if m:
        return int(m.group(1))
    m = re.search(r'var\s+create_time\s*=\s*"(\d+)"', text)
    return int(m.group(1)) if m else None


def _extract_biz(text: str) -> str | None:
    m = re.search(r"var\s+biz\s*=\s*([^;\n]+)", text)
    if not m:
        return None
    for q in re.findall(r'"([^"]*)"', m.group(1)):
        if q:
            return q
    return None


def _extract_nickname(text: str) -> str | None:
    m = re.search(r'var\s+nickname\s*=\s*htmlDecode\(\s*(["\'])(.*?)\1', text)
    if m:
        return htmlmod.unescape(m.group(2))
    m = re.search(r'var\s+nickname\s*=\s*(["\'])(.*?)\1', text)
    return htmlmod.unescape(m.group(2)) if m else None


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


ITEM_SHOW_TYPE = {
    0: "article",
    5: "video_share",
    6: "music_share",
    7: "audio_share",
    8: "image_post",
    10: "text_post",
    11: "article_share",
    17: "short_post",
}


def _item_show_type(text: str) -> int | None:
    m = re.search(r"var\s+item_show_type\s*=\s*['\"]?(\d+)", text)
    return int(m.group(1)) if m else None


def _clean_content(soup: BeautifulSoup):
    node = soup.find(id="js_content")
    if node is None:
        return None
    style = node.get("style", "")
    style = re.sub(r"visibility\s*:\s*hidden;?", "", style)
    style = re.sub(r"opacity\s*:\s*0;?", "", style)
    node["style"] = style.strip()
    for img in node.find_all("img"):
        ds = img.get("data-src")
        if ds:
            img["src"] = ds
    for tag in node.find_all(["script", "style"]):
        tag.decompose()
    for sel in ("wx_expand_article", "js_article_bottom_bar", "bottom_bar_wrp", "share_media"):
        for el in node.find_all(class_=sel):
            el.decompose()
    return node


def _collect_images(node) -> list[str]:
    urls: list[str] = []
    if node is None:
        return urls
    for img in node.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src and "mmbiz" in src:
            urls.append(src)
    for el in node.find_all(style=True):
        for m in re.finditer(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", el["style"]):
            u = m.group(2)
            if "mmbiz" in u:
                urls.append(u)
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _collect_audio(soup: BeautifulSoup) -> list[dict]:
    out = []
    seen = set()
    for tag in soup.find_all(["mpvoice", "mp-common-mpaudio"]):
        fid = tag.get("voice_encode_fileid") or tag.get("voice_encode_fileID")
        if fid and fid not in seen:
            seen.add(fid)
            out.append(
                {
                    "fileid": fid,
                    "name": tag.get("name") or tag.get("title") or fid,
                    "url": f"https://res.wx.qq.com/voice/getvoice?mediaid={fid}",
                }
            )
    for fid in re.findall(r'"voice_encode_fileid"\s*:\s*"([\w-]+)"', str(soup)):
        if fid not in seen:
            seen.add(fid)
            out.append(
                {
                    "fileid": fid,
                    "name": fid,
                    "url": f"https://res.wx.qq.com/voice/getvoice?mediaid={fid}",
                }
            )
    return out


def _pick_best_video_url(block: str) -> str | None:
    candidates = []
    for m in re.finditer(
        r"format_id\s*:\s*'?(\d+)'?.*?url\s*:\s*\(?'([^']*mpvideo\.qpic\.cn[^']*)'",
        block,
        re.DOTALL,
    ):
        candidates.append((int(m.group(1)), m.group(2)))
    if not candidates:
        for m in re.finditer(r"'([^']*mpvideo\.qpic\.cn[^']*\.mp4[^']*)'", block):
            candidates.append((0, m.group(1)))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    raw = candidates[0][1]
    return raw.replace("\\x26amp;", "&").replace("\\x26", "&").replace("&amp;", "&")


def _collect_videos(text: str, soup: BeautifulSoup) -> tuple[list[dict], list[str]]:
    videos = []
    notes = []
    for m in re.finditer(r"mp_video_trans_info\s*:\s*\[(.*?)\]", text, re.DOTALL):
        url = _pick_best_video_url(m.group(1))
        if url:
            videos.append({"url": url})
    if not videos:
        m = re.search(r"window\.__mpVideoTransInfo\s*=\s*(\[.*?\])\s*;", text, re.DOTALL)
        if m:
            url = _pick_best_video_url(m.group(1))
            if url:
                videos.append({"url": url})
    seen = set()
    uniq = []
    for v in videos:
        if v["url"] not in seen:
            seen.add(v["url"])
            uniq.append(v)
    if soup.find("mp-common-videosnap") or soup.find(class_=re.compile("videosnap")):
        notes.append("视频号内容无法免证书下载，已跳过")
    for frame in soup.find_all("iframe", class_="video_iframe"):
        src = frame.get("data-src") or frame.get("src") or ""
        if "v.qq.com" in src:
            notes.append("腾讯视频内容无法下载，仅保留页面引用")
            break
    return uniq, notes


def parse_article(html: str, source_url: str = "") -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = _first_group2(_JS_STRING["title"], html) or _og(soup, "og:title")
    if title:
        title = htmlmod.unescape(title).strip()
    author = _first_group2(_JS_STRING["author"], html)
    user_name = _first_group2(_JS_STRING["user_name"], html)
    nickname = _extract_nickname(html) or _og(soup, "og:article:author")
    ct = _extract_ct(html)
    publish_dt = (
        datetime.fromtimestamp(ct, tz=timezone.utc).astimezone()
        if ct
        else None
    )
    biz = _extract_biz(html)
    ist = _item_show_type(html)
    content = _clean_content(soup)
    videos, video_notes = _collect_videos(html, soup)
    return {
        "title": title or "未命名文章",
        "author": (author or "").strip(),
        "nickname": (nickname or "").strip(),
        "user_name": (user_name or "").strip(),
        "biz": biz or "",
        "publish_ts": ct,
        "publish_dt": publish_dt,
        "item_show_type": ist,
        "item_show_type_name": ITEM_SHOW_TYPE.get(ist if ist is not None else -1, "unknown"),
        "source_url": source_url,
        "content_node": content,
        "content_html": str(content) if content is not None else "",
        "images": _collect_images(content),
        "videos": videos,
        "audios": _collect_audio(soup),
        "notes": video_notes,
    }
