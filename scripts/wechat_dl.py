# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "lxml",
#   "markdownify",
# ]
# ///
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import export
import fetcher
import media
import parser as wxparser


def _sanitize_account(name: str) -> str:
    return export.slugify(name, limit=40) if name else "unknown"


def _article_dirname(article: dict) -> str:
    dt = article.get("publish_dt")
    prefix = dt.strftime("%Y-%m-%d_") if dt else ""
    return prefix + export.slugify(article.get("title", ""))


def _download_media(article: dict, art_dir: Path, session, want_images, want_video, want_audio):
    img_map: dict[str, str] = {}
    media_map: dict[str, str] = {}
    if want_images and article.get("images"):
        assets = art_dir / "assets"
        for url in article["images"]:
            name = media.download_image(url, assets, session, seed=article.get("biz", ""))
            if name:
                img_map[url] = name
    media_dir = art_dir / "media"
    if want_video:
        for v in article.get("videos", []):
            name = media.download_media(v["url"], media_dir, session, "video", seed=article.get("biz", ""))
            if name:
                media_map[v["url"]] = name
    if want_audio:
        for a in article.get("audios", []):
            name = media.download_media(a["url"], media_dir, session, "audio", seed=a.get("fileid", ""))
            if name:
                media_map[a["url"]] = name
    return img_map, media_map


def process_article(url, out_root, formats, session, want_images, want_video, want_audio, delay, subdir=None, index=None):
    try:
        html, final_url = fetcher.get_article_html(url, session=session, delay=delay)
    except (fetcher.ArticleUnavailable, fetcher.CaptchaTriggered) as exc:
        print(f"  跳过: {exc} ({url})", file=sys.stderr)
        return None
    article = wxparser.parse_article(html, source_url=fetcher.normalize_article_url(url))
    account = _sanitize_account(article.get("nickname"))
    base = out_root / account
    if subdir:
        base = base / subdir
    dirname = _article_dirname(article)
    if index is not None:
        dirname = f"{index:02d}_{export.slugify(article.get('title', ''))}"
    art_dir = base / dirname
    art_dir.mkdir(parents=True, exist_ok=True)
    img_map, media_map = _download_media(article, art_dir, session, want_images, want_video, want_audio)
    stem = export.slugify(article.get("title", ""))
    if "md" in formats:
        export.to_markdown(article, img_map, media_map, art_dir / f"{stem}.md")
    html_path = art_dir / f"{stem}.html"
    need_html = "html" in formats or "pdf" in formats
    if need_html:
        export.to_html(article, img_map, media_map, html_path)
    if "pdf" in formats:
        pdf = export.to_pdf(html_path, art_dir / f"{stem}.pdf")
        if pdf is None:
            print("  PDF 生成失败(未找到 Chrome 或渲染出错)", file=sys.stderr)
    if need_html and "html" not in formats:
        html_path.unlink(missing_ok=True)
    print(f"  ✓ {article.get('title', '')} -> {art_dir}")
    return {"title": article.get("title"), "dir": art_dir, "url": article.get("source_url")}


def process_album(album_url, out_root, formats, session, want_images, want_video, want_audio, delay, limit=0):
    biz, album_id = fetcher.parse_album_url(album_url)
    base_info, items = fetcher.get_album(biz, album_id, session=session, delay=max(delay, 1.0))
    album_title = base_info.get("title") or f"album_{album_id}"
    if limit and limit > 0:
        items = items[:limit]
    print(f"合集《{album_title}》共 {len(items)} 篇")
    subdir = "合集_" + export.slugify(album_title, limit=40)
    results = []
    for i, item in enumerate(items, 1):
        art_url = fetcher.upgrade_link(item.get("url", ""))
        if not art_url:
            continue
        res = process_article(
            art_url, out_root, formats, session, want_images, want_video, want_audio, delay,
            subdir=subdir, index=i,
        )
        if res:
            results.append(res)
        fetcher.polite_sleep(delay)
    _write_album_index(base_info, results)
    return results


def _write_album_index(base_info, results):
    if not results:
        return
    album_dir = results[0]["dir"].parent
    lines = [f"# 合集：{base_info.get('title', '')}", ""]
    if base_info.get("nickname"):
        lines.append(f"公众号：{base_info['nickname']}")
    lines.append(f"文章数：{len(results)}")
    lines.append("")
    for i, r in enumerate(results, 1):
        rel = r["dir"].name
        lines.append(f"{i}. [{r['title']}]({rel}/)")
    (album_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_url_file(path: str) -> list[str]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="wechat_dl.py",
        description="下载微信公众号文章为 HTML/Markdown/PDF，含图片、视频、音频；支持单篇、合集、批量。免证书。",
    )
    ap.add_argument("urls", nargs="*", help="一个或多个公众号文章链接")
    ap.add_argument("--album", help="合集链接(含 __biz 与 album_id)")
    ap.add_argument("--url-file", help="每行一个链接的文本文件")
    ap.add_argument("--format", default="md", help="输出格式，逗号分隔: md,html,pdf (默认 md)")
    ap.add_argument("--out", default="./wechat-download", help="输出目录 (默认 ./wechat-download)")
    ap.add_argument("--no-images", action="store_true", help="不下载正文图片")
    ap.add_argument("--video", action="store_true", help="下载文章内视频")
    ap.add_argument("--audio", action="store_true", help="下载文章内音频")
    ap.add_argument("--media", choices=["all"], help="--media all 等同同时开启图片/视频/音频")
    ap.add_argument("--delay", type=float, default=3.0, help="请求间隔秒数 (默认 3)")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少篇 (0 表示不限)")
    args = ap.parse_args(argv)

    formats = {f.strip() for f in args.format.split(",") if f.strip()}
    want_images = not args.no_images
    want_video = args.video
    want_audio = args.audio
    if args.media == "all":
        want_images = want_video = want_audio = True

    out_root = Path(args.out).expanduser()
    session = fetcher._build_session()

    urls = list(args.urls)
    if args.url_file:
        urls.extend(_read_url_file(args.url_file))

    if not urls and not args.album:
        ap.error("请提供文章链接、--url-file 或 --album")

    if args.album:
        process_album(args.album, out_root, formats, session, want_images, want_video, want_audio, args.delay, limit=args.limit)

    if args.limit and args.limit > 0:
        urls = urls[: args.limit]
    for i, url in enumerate(urls):
        print(f"[{i + 1}/{len(urls)}] {url}")
        process_article(url, out_root, formats, session, want_images, want_video, want_audio, args.delay)
        if i < len(urls) - 1:
            fetcher.polite_sleep(args.delay)


if __name__ == "__main__":
    main()
