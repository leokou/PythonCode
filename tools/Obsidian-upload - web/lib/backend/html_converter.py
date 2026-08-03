# -*- coding: utf-8 -*-
"""HTML 内容节点 → Obsidian Markdown 转换模块。

输入：clipboard_parser.parse_html 产出的节点列表（保持 DOM 顺序）
输出：Markdown 字符串

转换规则：
- 图片节点 → ![[filename]]（Obsidian 内部附件引用，不输出 <img> / ![](url)）
- 标题文本 → # / ## / ... ###### 前缀
- 列表项 → - 前缀
- 链接文本 → [text](href)
- 普通文本 → 原样输出
- 保持节点顺序（图片不会被挪到末尾）

image_filenames 参数：{src: filename} 映射，未保存成功的图片跳过。
无 UI 依赖，可独立测试。
"""
import re

from commands.logger import log_warn


def nodes_to_markdown(nodes, image_filenames):
    """把节点列表转为 Obsidian Markdown。

    nodes: parse_html 返回的节点列表
    image_filenames: {src: filename} 映射（已成功保存的图片）
    返回 Markdown 字符串。
    """
    if not nodes:
        return ""
    parts = []
    skipped_images = 0
    for node in nodes:
        if node["type"] == "image":
            src = node.get("src", "")
            filename = image_filenames.get(src)
            if filename:
                parts.append("\n\n![[%s]]\n" % filename)
            else:
                skipped_images += 1
        elif node["type"] == "text":
            md = _format_text(node)
            if md:
                parts.append(md)
    md = "".join(parts)
    # 规整连续空行（最多保留两个换行）
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = md.strip()
    if skipped_images:
        log_warn("html_converter: %d 张图片未保存（已跳过）" % skipped_images)
    return md


def _format_text(node):
    """把单个文本节点格式化为 Markdown 片段。

    根据 heading / link / list_item 上下文应用前缀。
    """
    text = node.get("content", "")
    if not text:
        return ""
    heading = node.get("heading", 0)
    link = node.get("link")
    list_item = node.get("list_item", False)

    # 按行处理（保留内部换行）
    lines = [ln for ln in text.split("\n")]
    # 行内空白规整：每行 strip，空行保留为段落分隔
    cleaned = []
    for ln in lines:
        if ln.strip():
            cleaned.append(ln.strip())
        else:
            cleaned.append("")

    # 合并连续空行
    result_lines = []
    prev_empty = False
    for ln in cleaned:
        if not ln:
            if prev_empty:
                continue
            prev_empty = True
            result_lines.append("")
        else:
            prev_empty = False
            result_lines.append(ln)

    body = "\n".join(result_lines).strip()
    if not body:
        return ""

    # 应用格式前缀
    if heading:
        prefix = "#" * heading + " "
        body = "\n".join(prefix + ln if ln else ln for ln in body.split("\n"))
    elif list_item:
        body = "\n".join(("- " + ln) if ln else ln for ln in body.split("\n"))

    # 链接包裹（整段当作链接文字）
    if link:
        body = "[%s](%s)" % (body, link)

    return "\n" + body + "\n"


if __name__ == "__main__":
    nodes = [
        {"type": "image", "src": "https://a.com/1.png", "alt": ""},
        {"type": "text", "content": "标题文字", "heading": 2, "link": None, "list_item": False},
        {"type": "text", "content": "描述", "heading": 0, "link": "https://x.com", "list_item": False},
        {"type": "text", "content": "列表项", "heading": 0, "link": None, "list_item": True},
    ]
    print(nodes_to_markdown(nodes, {"https://a.com/1.png": "Pasted-image-1.png"}))
