---
name: echo-wechat-skill
description: Use when downloading a WeChat Official Account article (微信公众号文章) for offline reading, archiving, or an Obsidian vault; when someone pastes an mp.weixin.qq.com link and wants it saved as Markdown, HTML, or PDF; when a whole 合集/album needs bulk downloading; or when the article's images, video, or audio must be saved locally. Works without any certificate, proxy, or login. Also triggers on Chinese phrasings such as 下载公众号文章, 保存微信文章, 公众号文章转 markdown, 下载公众号合集, 存到 Obsidian, 微信文章存 PDF.
---

# Echo WeChat Skill — 下载微信公众号文章

## Overview

把微信公众号文章存到本地：Markdown（Obsidian 友好）、离线 HTML、PDF，连同文章内的图片、视频、音频。

**Core principle:** 免证书。全程只是对公开页面做 HTTPS GET + 读公开的合集 JSON 接口，不装证书、不架代理、不登录、不碰客户端密钥。

## When to Use

- 有一个或多个 `mp.weixin.qq.com/s/...` 文章链接，想存成 Markdown / HTML / PDF
- 要整份**合集（album）**批量下载
- 需要把文章图片/视频/音频一起保存到本地做离线归档
- 想把公众号文章导入 Obsidian（带 YAML frontmatter + 相对路径图片）

**Not for:**
- 任意公众号的**全量历史消息**批量抓取 —— macOS 上免证书做不到（Mac 版微信不落带密钥的链接），本 skill 不做；用**合集**或**批量 URL 列表**替代
- 阅读数 / 点赞数 / 评论 / 划线 —— 需要客户端密钥（等价于装证书），不支持
- 视频号（`mp-common-videosnap`）、腾讯视频（`v.qq.com`）—— 无法免证书下载，输出里会留占位说明

## Quick Start

**执行位置**：下列命令用相对路径 `scripts/...`，须先 `cd` 到本 SKILL.md 所在目录（本机安装为 `~/.claude/skills/echo-wechat-skill`）再运行；或把命令里的 `scripts/` 换成该目录的绝对路径。

依赖由 uv 按脚本内联声明自动安装，无需手动 pip。PDF 复用系统 Chrome。`--format`/`--media`/`--out` 等所有选项对单篇、合集、批量三种模式通用。

```bash
# 单篇 -> Markdown（默认）
uv run scripts/wechat_dl.py "https://mp.weixin.qq.com/s/XXXX"

# 单篇 -> 三种格式 + 图片/视频/音频全下
uv run scripts/wechat_dl.py "https://mp.weixin.qq.com/s/XXXX" --format md,html,pdf --media all

# 合集：链接需含 __biz 与 album_id
uv run scripts/wechat_dl.py --album "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=XX==&action=getalbum&album_id=NNN"

# 批量：每行一个链接
uv run scripts/wechat_dl.py --url-file links.txt --format md,pdf
```

## Options

| 选项 | 说明 | 默认 |
|------|------|------|
| `--format` | 逗号分隔：`md,html,pdf` | `md` |
| `--out` | 输出根目录 | `./wechat-download` |
| `--no-images` | 不下载正文图片 | 默认下载 |
| `--video` / `--audio` | 下载文章内视频 / 音频 | 关 |
| `--media all` | 图片 + 视频 + 音频全开 | — |
| `--limit N` | 最多处理 N 篇（合集/批量用） | 0（不限） |
| `--delay S` | 请求间隔秒数（含随机抖动） | 3 |

## Output Layout

```
wechat-download/<公众号>/<YYYY-MM-DD>_<标题>/
    <标题>.md / .html / .pdf
    assets/     # 正文图片
    media/      # 视频、音频
wechat-download/<公众号>/合集_<合集名>/
    index.md    # 目录
    01_<标题>/ ...  02_<标题>/ ...
```

Markdown 带 Obsidian frontmatter（title/author/account/account_id/biz/published/source/retrieved/tags），正文图片写成 `![](assets/xxx)` 相对路径。

## How It Works

1. **抓取**：桌面 UA 直接 GET 文章页。长链保留 `chksm` 以避开验证码页；识别「已删除/违规」死链与「环境异常」验证页（后者会退避重试）。
2. **解析**：从页面 JS 正则取标题/作者/公众号/时间/biz；`#js_content` 去掉 `visibility:hidden`，`data-src` 转 `src`；收集图片（含 `background-image`）、视频（`mp_video_trans_info`）、音频（`voice_encode_fileid`）。
3. **媒体**：图片下载**不带外站 Referer**（否则拿到 2KB 占位图），按 Content-Type / magic bytes 定扩展名、去 `tp=webp`；视频取最高清、还原 `\x26amp;` 转义、即时下载（URL 有时效）；音频走 `res.wx.qq.com/voice/getvoice`。
4. **导出**：Markdown 用 markdownify + frontmatter；HTML 离线本地化 + `no-referrer`；PDF 用系统 Chrome `--headless --print-to-pdf` 渲染离线 HTML（CJK 正常）。

## Common Mistakes

| 症状 | 原因 / 处理 |
|------|------|
| 图片是「此图片来自微信公众平台」占位图 | 带了外站 Referer；本工具已避免，勿自行加 Referer |
| 长链跳验证码页 | 缺 `chksm`；用 `/s/` 短链，或保留原始完整链接 |
| PDF 没生成 | 未找到系统 Chrome；装 Google Chrome，或改用 `--format md,html` |
| 视频/音频没下 | 默认关；加 `--video --audio` 或 `--media all` |
| 合集只有部分文章 | 用了 `--limit`；去掉即可拉全 |
| freq control / 频繁 | 调大 `--delay`，隔一段时间再跑 |

## Verify

```bash
uv run scripts/selftest.py   # 离线自检，零网络
```
