from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

_INVALID = re.compile(r'[\\/:*?"<>|\n\r\t]+')


def slugify(text: str, limit: int = 60) -> str:
    text = (text or "").strip()
    text = _INVALID.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" ", "_")
    if len(text) > limit:
        text = text[:limit].rstrip("_")
    return text or "untitled"


def _yaml_escape(value: str) -> str:
    value = (value or "").replace('"', '\\"')
    return f'"{value}"'


def build_frontmatter(article: dict) -> str:
    dt = article.get("publish_dt")
    published = dt.strftime("%Y-%m-%d %H:%M") if isinstance(dt, datetime) else ""
    tags = ["wechat"]
    if article.get("nickname"):
        tags.append(article["nickname"])
    lines = ["---"]
    lines.append(f"title: {_yaml_escape(article.get('title', ''))}")
    lines.append(f"author: {_yaml_escape(article.get('author', ''))}")
    lines.append(f"account: {_yaml_escape(article.get('nickname', ''))}")
    lines.append(f"account_id: {_yaml_escape(article.get('user_name', ''))}")
    lines.append(f"biz: {_yaml_escape(article.get('biz', ''))}")
    lines.append(f"published: {_yaml_escape(published)}")
    lines.append(f"source: {_yaml_escape(article.get('source_url', ''))}")
    lines.append(f"retrieved: {_yaml_escape(datetime.now().strftime('%Y-%m-%d %H:%M'))}")
    lines.append("tags:")
    for t in tags:
        lines.append(f"  - {t}")
    lines.append("---")
    return "\n".join(lines)


def _rewrite_images(node, img_map: dict[str, str]):
    if node is None:
        return
    for img in node.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if src in img_map:
            img["src"] = f"assets/{img_map[src]}"
            if img.has_attr("data-src"):
                del img["data-src"]


def _media_section_md(article: dict, media_map: dict) -> str:
    parts = []
    vids = [media_map[v["url"]] for v in article.get("videos", []) if v["url"] in media_map]
    auds = [(a["name"], media_map[a["url"]]) for a in article.get("audios", []) if a["url"] in media_map]
    if vids or auds or article.get("notes"):
        parts.append("\n\n## 媒体附件\n")
    for name in vids:
        parts.append(f"- 🎬 [{name}](media/{name})")
    for label, name in auds:
        parts.append(f"- 🔊 [{label}](media/{name})")
    for note in article.get("notes", []):
        parts.append(f"- ⚠️ {note}")
    return "\n".join(parts)


def to_markdown(article: dict, img_map: dict, media_map: dict, out_path: Path) -> Path:
    node = article.get("content_node")
    if node is not None:
        soup = BeautifulSoup(str(node), "lxml")
        inner = soup.body or soup
        _rewrite_images(inner, img_map)
        body_md = markdownify(str(inner), heading_style="ATX", strip=["script", "style"])
    else:
        body_md = article.get("content_html", "")
    body_md = re.sub(r"\n{3,}", "\n\n", body_md).strip()
    parts = [build_frontmatter(article), "", f"# {article.get('title', '')}", "", body_md]
    parts.append(_media_section_md(article, media_map))
    out_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return out_path


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body{{max-width:720px;margin:0 auto;padding:24px 18px;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.75;color:#222;font-size:17px;}}
h1{{font-size:22px;line-height:1.4;}}
img{{max-width:100%;height:auto;}}
.meta{{color:#888;font-size:14px;margin-bottom:8px;}}
.meta a{{color:#576b95;}}
hr{{border:none;border-top:1px solid #eee;margin:24px 0;}}
.attach{{margin-top:28px;font-size:15px;}}
.attach li{{margin:4px 0;}}
blockquote{{color:#666;border-left:3px solid #ddd;padding-left:12px;margin-left:0;}}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">{meta}</div>
<hr>
{content}
{attach}
</body>
</html>
"""


def _media_section_html(article: dict, media_map: dict) -> str:
    items = []
    for v in article.get("videos", []):
        if v["url"] in media_map:
            n = media_map[v["url"]]
            items.append(f'<li>🎬 <a href="media/{n}">{n}</a></li>')
    for a in article.get("audios", []):
        if a["url"] in media_map:
            n = media_map[a["url"]]
            items.append(f'<li>🔊 <a href="media/{n}">{a["name"]}</a></li>')
    for note in article.get("notes", []):
        items.append(f"<li>⚠️ {note}</li>")
    if not items:
        return ""
    return '<div class="attach"><h2>媒体附件</h2><ul>' + "".join(items) + "</ul></div>"


def to_html(article: dict, img_map: dict, media_map: dict, out_path: Path) -> Path:
    node = article.get("content_node")
    if node is not None:
        soup = BeautifulSoup(str(node), "lxml")
        inner = soup.body or soup
        _rewrite_images(inner, img_map)
        content = "".join(str(c) for c in (inner.contents if inner.name == "body" else [inner]))
    else:
        content = article.get("content_html", "")
    dt = article.get("publish_dt")
    published = dt.strftime("%Y-%m-%d %H:%M") if isinstance(dt, datetime) else ""
    meta_bits = [b for b in [article.get("nickname"), article.get("author"), published] if b]
    meta = " · ".join(meta_bits)
    if article.get("source_url"):
        meta += f' · <a href="{article["source_url"]}">原文</a>'
    doc = _HTML_TEMPLATE.format(
        title=article.get("title", ""),
        meta=meta,
        content=content,
        attach=_media_section_html(article, media_map),
    )
    out_path.write_text(doc, encoding="utf-8")
    return out_path


_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)


def _find_chrome() -> str | None:
    for path in _CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def to_pdf(html_path: Path, pdf_path: Path) -> Path | None:
    chrome = _find_chrome()
    if not chrome:
        return None
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        f"--print-to-pdf={pdf_path}",
        html_path.resolve().as_uri(),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
    except (subprocess.SubprocessError, OSError):
        return None
    return pdf_path if pdf_path.exists() and pdf_path.stat().st_size > 0 else None
