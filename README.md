# Echo WeChat Skill · 下载微信公众号文章

![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Skill](https://img.shields.io/badge/Skill-Agent-111111?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square)
![Claude Code](https://img.shields.io/badge/Claude%20Code-Supported-6B5B95?style=flat-square)

> 🌏 **English version: [README.en.md](./README.en.md)**

一个适配 Claude Code / Codex 等 Agent 环境的技能，把微信公众号文章存到本地：**Markdown（Obsidian 友好）、离线 HTML、PDF**，连同文章内的**图片、视频、音频**。

核心是一句话：**免证书**。全程只对公开页面做 HTTPS GET，再读公开的合集 JSON 接口——不装证书、不架代理、不登录、不碰客户端密钥。

- **三种格式**：Markdown（YAML frontmatter + 相对路径图片，直接进 Obsidian）、离线 HTML、PDF（系统 Chrome 渲染，中文正常）
- **媒体本地化**：正文图片自动避开防盗链占位图；文章内视频（`mpvideo`）、音频（`mpvoice`/`mpaudio`）一并下载
- **合集批量**：给一个合集链接，分页拉全，逐篇落盘并生成 `index.md` 目录
- **批量列表**：一个文本文件里一行一个链接

## 30 秒开始

依赖由 [uv](https://github.com/astral-sh/uv) 按脚本内联声明自动安装，无需手动 `pip install`。PDF 复用系统已装的 Google Chrome。

```bash
# 单篇 -> Markdown（默认）
uv run scripts/wechat_dl.py "https://mp.weixin.qq.com/s/XXXX"

# 单篇 -> 三种格式 + 图片/视频/音频全下
uv run scripts/wechat_dl.py "https://mp.weixin.qq.com/s/XXXX" --format md,html,pdf --media all

# 合集（链接需含 __biz 与 album_id）
uv run scripts/wechat_dl.py --album "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=XX==&action=getalbum&album_id=NNN"

# 批量：每行一个链接
uv run scripts/wechat_dl.py --url-file links.txt --format md,pdf
```

在 Agent 里直接说「帮我把这篇公众号文章存成 markdown」并附链接即可，技能会自动被调用。

## 选项

| 选项 | 说明 | 默认 |
|------|------|------|
| `--format` | 逗号分隔：`md,html,pdf` | `md` |
| `--out` | 输出根目录 | `./wechat-download` |
| `--no-images` | 不下载正文图片 | 默认下载 |
| `--video` / `--audio` | 下载文章内视频 / 音频 | 关 |
| `--media all` | 图片 + 视频 + 音频全开 | — |
| `--limit N` | 最多处理 N 篇（合集/批量用） | 0（不限） |
| `--delay S` | 请求间隔秒数（含随机抖动） | 3 |

## 输出结构

```
wechat-download/<公众号>/<YYYY-MM-DD>_<标题>/
    <标题>.md / .html / .pdf
    assets/     # 正文图片
    media/      # 视频、音频
wechat-download/<公众号>/合集_<合集名>/
    index.md    # 目录
    01_<标题>/ ...  02_<标题>/ ...
```

Markdown frontmatter 字段：`title / author / account / account_id / biz / published / source / retrieved / tags`。

## 能做与不能做

**能做**：单篇、合集、批量 URL 列表；图片 / 视频 / 音频本地化；HTML / Markdown / PDF。

**不能做**（技术边界，非偷懒）：

- **任意公众号的全量历史消息**：macOS 上免证书做不到（Mac 版微信不把带密钥的链接落到磁盘），本技能不做。用**合集**或**批量 URL 列表**替代。
- **阅读数 / 点赞数 / 评论 / 划线**：需要客户端密钥（`key`/`pass_ticket`），等价于装证书，不支持。
- **视频号（`mp-common-videosnap`）、腾讯视频（`v.qq.com`）**：无法免证书下载，输出里留占位说明。

## 依赖

- [uv](https://github.com/astral-sh/uv)（运行脚本、自动装依赖）
- Google Chrome（仅 PDF 需要；没有就用 `--format md,html`）
- Python 依赖（uv 自动处理）：`requests`、`beautifulsoup4`、`lxml`、`markdownify`

## 自检

```bash
uv run scripts/selftest.py   # 离线，零网络
```

## 常见问题

| 症状 | 处理 |
|------|------|
| 图片是「此图片来自微信公众平台」占位图 | 别自行加外站 Referer；本工具已避免 |
| 长链跳验证码页 | 用 `/s/` 短链，或保留原始完整链接（含 `chksm`）|
| PDF 没生成 | 装 Google Chrome，或改用 `--format md,html` |
| freq control / 提示频繁 | 调大 `--delay`，隔段时间再跑 |

## License

MIT © xiangzhouEcho
