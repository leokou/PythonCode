# -*- coding: utf-8 -*-
"""剪贴板 HTML 解析模块：HTML 字符串 → 结构化内容节点列表。

按 DOM 顺序遍历，输出节点列表（保持网页复制时的内容顺序）：
    [
      {"type": "image", "src": "...", "alt": ""},
      {"type": "text", "content": "标题文字", "heading": 2, "link": None, "list_item": False},
      {"type": "text", "content": "描述文字", "heading": 0, "link": "https://...", "list_item": False},
      {"type": "text", "content": "列表项", "heading": 0, "link": None, "list_item": True},
    ]

支持的 <img> 属性：src / data-src / data-original / data-lazy-src
支持的 src 格式：data: / http(s): / blob: / file: / 本地路径

基于标准库 html.parser，无第三方依赖；无 UI 依赖，可独立测试。
"""
from html.parser import HTMLParser

from commands.logger import log_error

# 块级分隔标签（前后插入换行，避免段间粘连）
_BLOCK_TAGS = {
    "p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "table", "ul", "ol", "blockquote", "hr",
    "section", "article", "header", "footer", "main", "figure",
}

# 忽略的标签（脚本/样式/元数据，内容不提取）
# 非空元素标签（有开闭标签，需栈式跳过整个内容）
_IGNORE_CONTAINER_TAGS = {"script", "style", "head", "title", "noscript"}
# 空元素标签（自闭合无闭合标签，直接跳过单个标签）
_IGNORE_VOID_TAGS = {"meta", "link", "base", "col", "area", "param", "source", "track", "wbr"}

# img 可用属性（按优先级排序）
_IMG_SRC_ATTRS = ("src", "data-src", "data-original", "data-lazy-src", "data-actualsrc")


class _HtmlWalker(HTMLParser):
    """SAX 式 HTML 遍历器：按 DOM 顺序产出 text / image 节点。

    text 节点携带上下文信息（heading 级别 / link href / list_item），
    供 html_converter 应用 Markdown 格式。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self._stack = []          # 标签栈：[(tag, attrs_dict)]
        self._skip_stack = []     # 忽略标签栈

    # ---- 上下文查询 ----
    def _heading_level(self):
        for tag, _ in reversed(self._stack):
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                return int(tag[1])
        return 0

    def _in_list_item(self):
        for tag, _ in reversed(self._stack):
            if tag == "li":
                return True
        return False

    def _link_href(self):
        for tag, attrs in reversed(self._stack):
            if tag == "a" and attrs.get("href"):
                return attrs.get("href")
        return None

    # ---- 事件处理 ----
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = {k: (v or "") for k, v in attrs}
        if tag in _IGNORE_VOID_TAGS:
            return
        if tag in _IGNORE_CONTAINER_TAGS:
            self._skip_stack.append(tag)
            return
        if self._skip_stack:
            return
        self._stack.append((tag, attrs_dict))
        if tag == "img":
            src = None
            for key in _IMG_SRC_ATTRS:
                v = attrs_dict.get(key)
                if v and v.strip():
                    src = v.strip()
                    break
            alt = attrs_dict.get("alt", "")
            if src:
                self.nodes.append({"type": "image", "src": src, "alt": alt})
        elif tag == "br":
            self.nodes.append({"type": "text", "content": "\n",
                               "heading": 0, "link": None, "list_item": False})
        elif tag in _BLOCK_TAGS:
            self._push_block_break()

    def handle_startendtag(self, tag, attrs):
        # 自闭合标签如 <img /> / <br /> / <meta />
        tag = tag.lower()
        if tag in _IGNORE_VOID_TAGS:
            return
        if tag in _IGNORE_CONTAINER_TAGS:
            return
        if self._skip_stack:
            return
        # 对于 img/br 等自闭合标签，复用 starttag 逻辑（不压栈等待 endtag）
        if tag == "img":
            attrs_dict = {k: (v or "") for k, v in attrs}
            src = None
            for key in _IMG_SRC_ATTRS:
                v = attrs_dict.get(key)
                if v and v.strip():
                    src = v.strip()
                    break
            alt = attrs_dict.get("alt", "")
            if src:
                self.nodes.append({"type": "image", "src": src, "alt": alt})
        elif tag == "br":
            self.nodes.append({"type": "text", "content": "\n",
                               "heading": 0, "link": None, "list_item": False})
        elif tag in _BLOCK_TAGS:
            self._push_block_break()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _IGNORE_VOID_TAGS:
            return
        if tag in _IGNORE_CONTAINER_TAGS:
            if self._skip_stack and self._skip_stack[-1] == tag:
                self._skip_stack.pop()
            return
        if self._skip_stack:
            return
        # 弹栈到匹配标签
        if self._stack:
            if self._stack[-1][0] == tag:
                self._stack.pop()
            else:
                while self._stack and self._stack[-1][0] != tag:
                    self._stack.pop()
                if self._stack:
                    self._stack.pop()
        if tag in _BLOCK_TAGS:
            self._push_block_break()

    def handle_data(self, data):
        if self._skip_stack:
            return
        if not data:
            return
        self.nodes.append({
            "type": "text",
            "content": data,
            "heading": self._heading_level(),
            "link": self._link_href(),
            "list_item": self._in_list_item(),
        })

    def _push_block_break(self):
        """块级元素边界：在末尾补换行，避免与下一段粘连。"""
        if self.nodes and self.nodes[-1]["type"] == "text":
            last = self.nodes[-1]
            if not last["content"].endswith("\n"):
                last["content"] += "\n"


def parse_html(html):
    """解析 HTML 字符串，返回结构化内容节点列表（按 DOM 顺序）。

    失败返回空列表。节点类型见模块文档。
    """
    if not html or not html.strip():
        return []
    try:
        walker = _HtmlWalker()
        walker.feed(html)
        walker.close()
        return _merge_text_nodes(walker.nodes)
    except Exception as e:
        log_error("解析 HTML 失败: %s" % e)
        return []


def _merge_text_nodes(nodes):
    """合并上下文相同的相邻文本节点，移除空文本节点。

    上下文相同 = heading / link / list_item 三元组相同。
    """
    merged = []
    for node in nodes:
        if node["type"] == "text":
            if not node["content"]:
                continue
            ctx = (node["heading"], node["link"], node["list_item"])
            if merged and merged[-1]["type"] == "text":
                last = merged[-1]
                last_ctx = (last["heading"], last["link"], last["list_item"])
                if last_ctx == ctx:
                    last["content"] += node["content"]
                    continue
            merged.append(dict(node))
        else:
            merged.append(node)
    # 清理首尾纯空白文本
    while merged and merged[0]["type"] == "text" and not merged[0]["content"].strip():
        merged.pop(0)
    while merged and merged[-1]["type"] == "text" and not merged[-1]["content"].strip():
        merged.pop()
    return merged


if __name__ == "__main__":
    # 简单自测
    test = '<h1>标题</h1><p>描述文字 <a href="https://x.com">链接</a></p><img src="https://a.com/1.png"><p>尾部</p>'
    for n in parse_html(test):
        print(n)
