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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import export
import parser as wxparser

FIXTURE = """<!doctype html><html><head>
<meta property="og:title" content="OG标题">
</head><body>
<script>
var msg_title = '测试文章标题';
var author = "张三";
var user_name = "gh_abcdef123456";
var ct = "1700000000";
var biz = "" || "MzTESTBIZ==";
var nickname = htmlDecode("测试公众号");
var item_show_type = '0';
window.__mpVideoTransInfo = [{format_id:'10102',url:('http://mpvideo.qpic.cn/vid.f10102.mp4?dis_k=a\\x26amp;dis_t=1')}];
</script>
<div id="js_content" style="visibility: hidden; opacity: 0;">
<p>正文第一段。</p>
<img data-src="https://mmbiz.qpic.cn/pic/640?wx_fmt=png&tp=webp" />
<p style="background-image:url('https://mmbiz.qpic.cn/bg/999?wx_fmt=jpeg')">带背景图</p>
<mpvoice voice_encode_fileid="VOICEFILEID123" name="配音"></mpvoice>
<iframe class="video_iframe" data-src="//v.qq.com/iframe/player.html?vid=xyz"></iframe>
</div>
</body></html>"""


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  ok: {msg}")


def main():
    a = wxparser.parse_article(FIXTURE, source_url="https://mp.weixin.qq.com/s/TEST")
    check(a["title"] == "测试文章标题", "标题抽取 msg_title 优先于 og:title")
    check(a["author"] == "张三", "作者抽取")
    check(a["nickname"] == "测试公众号", "公众号名 htmlDecode 抽取")
    check(a["user_name"] == "gh_abcdef123456", "gh_id 抽取")
    check(a["biz"] == "MzTESTBIZ==", "非空 biz 抽取")
    check(a["publish_ts"] == 1700000000, "发布时间戳抽取")
    check(a["item_show_type_name"] == "article", "item_show_type 映射 0->article")
    check(len(a["images"]) == 2, f"图片引用发现(含背景图), got {len(a['images'])}")
    check(len(a["videos"]) == 1 and "mpvideo.qpic.cn" in a["videos"][0]["url"], "视频 URL 发现")
    check("&" in a["videos"][0]["url"] and "\\x26" not in a["videos"][0]["url"], "视频 URL 转义还原")
    check(len(a["audios"]) == 1 and a["audios"][0]["fileid"] == "VOICEFILEID123", "音频 fileid 发现")
    check(any("腾讯视频" in n for n in a["notes"]), "腾讯视频占位提示")
    check("visibility: hidden" not in a["content_html"], "js_content 隐藏样式已去除")

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="wxselftest_"))
    img_map = {a["images"][0]: "img0.png", a["images"][1]: "img1.jpg"}
    media_map = {a["videos"][0]["url"]: "vid.mp4", a["audios"][0]["url"]: "voice.mp3"}
    md = export.to_markdown(a, img_map, media_map, tmp / "out.md")
    text = md.read_text(encoding="utf-8")
    check(text.startswith("---\n"), "Markdown 以 YAML frontmatter 开头")
    check('title: "测试文章标题"' in text, "frontmatter 含标题")
    check("account_id: \"gh_abcdef123456\"" in text, "frontmatter 含 gh_id")
    check("assets/img0.png" in text, "Markdown 图片改写为本地相对路径")
    check("media/vid.mp4" in text and "media/voice.mp3" in text, "媒体附件区列出音视频")

    html = export.to_html(a, img_map, media_map, tmp / "out.html")
    htext = html.read_text(encoding="utf-8")
    check('content="no-referrer"' in htext, "HTML 含 no-referrer meta")
    check("assets/img0.png" in htext, "HTML 图片改写为本地相对路径")

    check(export.slugify("a/b:c*d?e") == "a_b_c_d_e", "slugify 清洗非法字符")
    print("\nselftest: ALL PASS")


if __name__ == "__main__":
    main()
