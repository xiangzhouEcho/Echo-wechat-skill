# Echo WeChat Skill · Download WeChat Official Account Articles

![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Skill](https://img.shields.io/badge/Skill-Agent-111111?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square)
![Claude Code](https://img.shields.io/badge/Claude%20Code-Supported-6B5B95?style=flat-square)

> 🌏 **中文版：[README.md](./README.md)**

A skill for Claude Code / Codex and similar agents that saves WeChat Official Account (微信公众号) articles locally as **Markdown (Obsidian-friendly), offline HTML, and PDF**, together with the article's **images, video, and audio**.

The core idea: **no certificate needed**. It only does plain HTTPS GETs on public pages plus the public album JSON endpoint — no MITM certificate, no proxy, no login, no client-side keys.

- **Three formats**: Markdown (YAML frontmatter + relative-path images, drops straight into Obsidian), offline HTML, PDF (rendered by system Chrome, CJK renders correctly)
- **Local media**: body images automatically dodge the anti-hotlink placeholder; in-article video (`mpvideo`) and audio (`mpvoice`/`mpaudio`) are downloaded too
- **Album bulk download**: give one album link, it pages through the whole thing, saves every article, and writes an `index.md`
- **Batch list**: one link per line in a text file

## 30-Second Start

Dependencies are declared inline (PEP 723) and installed automatically by [uv](https://github.com/astral-sh/uv) — no manual `pip install`. PDF reuses your installed Google Chrome.

```bash
# Single article -> Markdown (default)
uv run scripts/wechat_dl.py "https://mp.weixin.qq.com/s/XXXX"

# Single article -> all three formats + images/video/audio
uv run scripts/wechat_dl.py "https://mp.weixin.qq.com/s/XXXX" --format md,html,pdf --media all

# Album (link must contain __biz and album_id)
uv run scripts/wechat_dl.py --album "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=XX==&action=getalbum&album_id=NNN"

# Batch: one link per line
uv run scripts/wechat_dl.py --url-file links.txt --format md,pdf
```

Inside an agent, just say "save this WeChat article as markdown" with the link — the skill triggers automatically.

## Options

| Option | Meaning | Default |
|--------|---------|---------|
| `--format` | Comma-separated: `md,html,pdf` | `md` |
| `--out` | Output root directory | `./wechat-download` |
| `--no-images` | Skip body images | images on |
| `--video` / `--audio` | Download in-article video / audio | off |
| `--media all` | Images + video + audio | — |
| `--limit N` | Process at most N articles (album/batch) | 0 (unlimited) |
| `--delay S` | Seconds between requests (with jitter) | 3 |

## Output Layout

```
wechat-download/<account>/<YYYY-MM-DD>_<title>/
    <title>.md / .html / .pdf
    assets/     # body images
    media/      # video, audio
wechat-download/<account>/合集_<album>/
    index.md    # table of contents
    01_<title>/ ...  02_<title>/ ...
```

Markdown frontmatter fields: `title / author / account / account_id / biz / published / source / retrieved / tags`.

## What It Can and Can't Do

**Can**: single article, album, batch URL list; local images / video / audio; HTML / Markdown / PDF.

**Can't** (technical limits, not laziness):

- **Full message history of an arbitrary account**: impossible without a certificate on macOS (WeChat for Mac does not persist key-bearing links to disk). Use an **album** or a **batch URL list** instead.
- **Read counts / likes / comments / highlights**: require client-side keys (`key`/`pass_ticket`), equivalent to installing a certificate. Not supported.
- **Channels video (`mp-common-videosnap`), Tencent Video (`v.qq.com`)**: cannot be downloaded without a certificate; a placeholder note is left in the output.

## Dependencies

- [uv](https://github.com/astral-sh/uv) (runs the scripts, auto-installs deps)
- Google Chrome (only for PDF; without it use `--format md,html`)
- Python deps (handled by uv): `requests`, `beautifulsoup4`, `lxml`, `markdownify`

## Self-Test

```bash
uv run scripts/selftest.py   # offline, no network
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Image is the "此图片来自微信公众平台" placeholder | Don't add a foreign Referer; this tool already avoids it |
| Long link redirects to a captcha page | Use the `/s/` short link, or keep the original full link (with `chksm`) |
| No PDF produced | Install Google Chrome, or use `--format md,html` |
| freq control / rate limited | Increase `--delay`, retry later |

## License

MIT © xiangzhouEcho
