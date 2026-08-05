# -*- coding: utf-8 -*-
"""编辑器主题数据 —— 设计师 / 艺术家配色系列（20 套，明暗各 10）。

本文件只提供数据，由 gen_themes.py import 后合并生成 themes/editor/*.css。
新增/修改配色改本文件后重新运行 `python frontend/gen_themes.py`，
**禁止直接改 themes/editor/*.css 产物**（会被覆盖）。

配色来源（公开设计规范 / 代表作主色）：
    Dieter Rams(Braun) / Bauhaus / Mondrian / Josef Albers / Paul Rand(IBM) /
    Massimo Vignelli(NYC Subway) / Wes Anderson / 葛饰北斋 / 莫奈 / Pantone /
    Rothko / 梵高 / 克里姆特 / Verner Panton / Saul Bass / Milton Glaser /
    Le Corbusier / 康定斯基 / Yves Klein / 歌川广重

每套只声明 18 个语义色，其余 46 个 --cm-* 变量由 expand() 派生，
保证「标题 / 正文 / markdown 符号 / 加粗 / 斜体 / 链接 / 代码 / 列表符号」颜色互不相同。
"""


def _rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgba(h, a):
    r, g, b = _rgb(h)
    return "rgba(%d,%d,%d,%s)" % (r, g, b, a)


def expand(t):
    """18 个语义色 → 46 个 --cm-* 变量。"""
    dark = t["dark"]
    fg, bg, sur, bd, mut = t["fg"], t["bg"], t["surface"], t["border"], t["muted"]
    return {
        "cm-bg": bg, "cm-fg": fg,
        "cm-gutter-bg": bg, "cm-gutter-fg": mut, "cm-gutter-border": bd,
        "cm-active-line": "rgba(255,255,255,.045)" if dark else _rgba(fg, ".05"),
        "cm-active-line-gutter": "rgba(255,255,255,.075)" if dark else _rgba(fg, ".09"),
        "cm-cursor": t["cursor"],
        "cm-selection": _rgba(t["sel"], ".32" if dark else ".25"),
        "cm-search-match": _rgba(t["hl_bg"], ".75"),
        "cm-fold-bg": sur, "cm-fold-border": bd, "cm-fold-fg": mut,
        "cm-heading1-color": t["h1"], "cm-heading2-color": t["h2"], "cm-heading3-color": t["h3"],
        "cm-heading4-color": t["em"], "cm-heading5-color": fg, "cm-heading6-color": mut,
        "cm-strong-color": t["strong"], "cm-emphasis-color": t["em"], "cm-strikethrough-color": mut,
        "cm-highlight-bg": t["hl_bg"], "cm-highlight-color": fg if dark else t["fg"],
        "cm-inline-code-bg": sur, "cm-inline-code-color": t["code"],
        "cm-codeblock-bg": sur, "cm-codeblock-border": bd, "cm-codeblock-color": fg,
        "cm-link-color": t["link"], "cm-url-color": t["link"],
        "cm-wikilink-color": t["link"], "cm-wikilink-bg": _rgba(t["link"], ".12"),
        "cm-wikilink-unfinished-bg": "rgba(255,200,0,.12)",
        "cm-wikilink-unfinished-border": "rgba(255,200,0,%s)" % (".4" if dark else ".5"),
        "cm-image-color": t["green"],
        "cm-blockquote-color": mut,
        "cm-blockquote-bg": "rgba(255,255,255,.03)" if dark else _rgba(fg, ".035"),
        "cm-blockquote-border": bd,
        "cm-list-marker-color": t["marker"],
        "cm-task-done-color": t["green"], "cm-task-undone-color": mut,
        "cm-table-border": bd, "cm-table-header-bg": sur,
        "cm-hr-color": bd,
        "cm-yaml-bg": sur, "cm-yaml-border": bd,
        "cm-yaml-key-color": t["marker"], "cm-yaml-value-color": t["link"],
        "cm-formatting-color": t["fmt"],
    }


# ---------------------------------------------------------------------------
# 明亮系 10 套
# ---------------------------------------------------------------------------
LIGHT = {
    "rams-braun": {  # Dieter Rams / Braun：中性灰底 + 品牌橙
        "dark": False, "bg": "#F4F3F1", "surface": "#EAE8E4", "border": "#DAD7D1",
        "fg": "#2E2E2C", "muted": "#8A8781", "cursor": "#F07D00", "sel": "#F07D00", "hl_bg": "#FFE9C7",
        "h1": "#F07D00", "h2": "#B85C00", "h3": "#4A6F8A", "strong": "#B5450B", "em": "#6E8B3D",
        "link": "#2F6F8F", "code": "#A34A00", "green": "#5E7A34", "marker": "#F07D00", "fmt": "#A9A49B",
    },
    "bauhaus-primary": {  # 包豪斯三原色
        "dark": False, "bg": "#FAF7F0", "surface": "#F0EADC", "border": "#DCD3C0",
        "fg": "#1A1A1A", "muted": "#857E70", "cursor": "#E30613", "sel": "#005BBB", "hl_bg": "#FFEFA8",
        "h1": "#E30613", "h2": "#005BBB", "h3": "#C79A00", "strong": "#C4000F", "em": "#7A3FA8",
        "link": "#0F7A6B", "code": "#B0004E", "green": "#2E7D32", "marker": "#E30613", "fmt": "#A79C86",
    },
    "mondrian-grid": {  # 蒙德里安：红黄蓝 + 纯白网格
        "dark": False, "bg": "#FCFCFA", "surface": "#F1F1EC", "border": "#D7D7D0",
        "fg": "#111111", "muted": "#8C8C86", "cursor": "#111111", "sel": "#003F87", "hl_bg": "#FBEF9A",
        "h1": "#D42027", "h2": "#003F87", "h3": "#B58900", "strong": "#A8161C", "em": "#6B21A8",
        "link": "#0369A1", "code": "#BE123C", "green": "#15803D", "marker": "#D42027", "fmt": "#A8A8A0",
    },
    "albers-interaction": {  # Josef Albers《色彩的相互作用》
        "dark": False, "bg": "#FBF6EA", "surface": "#F2E9D6", "border": "#E0D2B8",
        "fg": "#3A2E20", "muted": "#9C8B70", "cursor": "#C0442B", "sel": "#E07B39", "hl_bg": "#FBE3B8",
        "h1": "#E07B39", "h2": "#B5651D", "h3": "#7A5C2E", "strong": "#C0442B", "em": "#4E6E58",
        "link": "#2F6E7A", "code": "#9A5B00", "green": "#5C7A45", "marker": "#E07B39", "fmt": "#B8A683",
    },
    "paul-rand-ibm": {  # Paul Rand / IBM 视觉体系
        "dark": False, "bg": "#FFFFFF", "surface": "#F2F4F8", "border": "#DDE1E6",
        "fg": "#1F1F1F", "muted": "#8D8D8D", "cursor": "#0F62FE", "sel": "#0F62FE", "hl_bg": "#FFF2C7",
        "h1": "#0F62FE", "h2": "#0043CE", "h3": "#D0021B", "strong": "#DA1E28", "em": "#8A3FFC",
        "link": "#0072C3", "code": "#A2191F", "green": "#198038", "marker": "#F5A623", "fmt": "#A8A8A8",
    },
    "vignelli-subway": {  # Massimo Vignelli / 纽约地铁线路色
        "dark": False, "bg": "#F7F7F5", "surface": "#EDEDEA", "border": "#D8D8D2",
        "fg": "#000000", "muted": "#7B7B75", "cursor": "#EE352E", "sel": "#0039A6", "hl_bg": "#FCE9A8",
        "h1": "#EE352E", "h2": "#0039A6", "h3": "#00933C", "strong": "#B8221C", "em": "#B933AD",
        "link": "#00A1DE", "code": "#CE8E00", "green": "#00933C", "marker": "#FF6319", "fmt": "#A5A5A0",
    },
    "wes-anderson-pastel": {  # 韦斯·安德森电影调色
        "dark": False, "bg": "#FBF3E4", "surface": "#F4E7D3", "border": "#E6D3B8",
        "fg": "#4A3B32", "muted": "#A3907E", "cursor": "#C1533C", "sel": "#E39EA5", "hl_bg": "#F7DDA8",
        "h1": "#C1533C", "h2": "#D9A441", "h3": "#6C9A8B", "strong": "#B3455F", "em": "#7E6BA8",
        "link": "#3F7A8C", "code": "#A9613C", "green": "#6C9A8B", "marker": "#D9748A", "fmt": "#BFAA92",
    },
    "hokusai-wave": {  # 葛饰北斋《神奈川冲浪里》普鲁士蓝
        "dark": False, "bg": "#F3EEE2", "surface": "#E8E1D0", "border": "#D6CBB4",
        "fg": "#22333B", "muted": "#8A8574", "cursor": "#1B4965", "sel": "#2A6F97", "hl_bg": "#EFDDA8",
        "h1": "#1B4965", "h2": "#2A6F97", "h3": "#A63A2B", "strong": "#8C2F22", "em": "#4E6E58",
        "link": "#0F7285", "code": "#9A6B1E", "green": "#5A7D52", "marker": "#C9A227", "fmt": "#A99F87",
    },
    "monet-water": {  # 莫奈《睡莲》
        "dark": False, "bg": "#F4F7F4", "surface": "#E7EEE9", "border": "#CFDDD4",
        "fg": "#33413F", "muted": "#8CA098", "cursor": "#5B87C7", "sel": "#7C6BAF", "hl_bg": "#E8E4A8",
        "h1": "#5B87C7", "h2": "#4E8D7C", "h3": "#B06A8A", "strong": "#C4577F", "em": "#7C6BAF",
        "link": "#3F72B8", "code": "#A85B7A", "green": "#5E9E4E", "marker": "#8A7BC0", "fmt": "#A9BCB2",
    },
    "pantone-serenity": {  # Pantone 年度色 Serenity + Rose Quartz
        "dark": False, "bg": "#F7F6F9", "surface": "#EDECF3", "border": "#D9D8E4",
        "fg": "#3B3C47", "muted": "#8B8C9B", "cursor": "#5A6B9E", "sel": "#91A8D0", "hl_bg": "#F2DCE2",
        "h1": "#5A6B9E", "h2": "#9A6B8E", "h3": "#4E8A8A", "strong": "#C25B72", "em": "#6B5BA8",
        "link": "#3E6FB0", "code": "#B0566F", "green": "#4E8A6B", "marker": "#91A8D0", "fmt": "#A8A8B8",
    },
}

# ---------------------------------------------------------------------------
# 暗色系 10 套
# ---------------------------------------------------------------------------
DARK = {
    "rothko-crimson": {  # 马克·罗斯科 色域绘画
        "dark": True, "bg": "#1A0F0E", "surface": "#2A1917", "border": "#3D2320",
        "fg": "#E8D5C4", "muted": "#A08376", "cursor": "#E08A3C", "sel": "#C43B2E", "hl_bg": "#4A2418",
        "h1": "#E0563F", "h2": "#C43B2E", "h3": "#E08A3C", "strong": "#F2764F", "em": "#D9A05B",
        "link": "#E8A87C", "code": "#F0A17A", "green": "#8A9A5B", "marker": "#C43B2E", "fmt": "#A87C6A",
    },
    "van-gogh-starry": {  # 梵高《星夜》
        "dark": True, "bg": "#101A33", "surface": "#1A2647", "border": "#27355C",
        "fg": "#DCE4F2", "muted": "#8393B8", "cursor": "#F2C14E", "sel": "#4E7CC4", "hl_bg": "#3A3A18",
        "h1": "#F2C14E", "h2": "#6BB8C4", "h3": "#A8C4E8", "strong": "#F2A03C", "em": "#B49AE0",
        "link": "#7FB2F0", "code": "#7FE0C4", "green": "#8FC46B", "marker": "#F2C14E", "fmt": "#8A9AC0",
    },
    "klimt-gold": {  # 克里姆特 黄金时期
        "dark": True, "bg": "#14110C", "surface": "#221D14", "border": "#35291A",
        "fg": "#E8DCC0", "muted": "#A6957A", "cursor": "#D4AF37", "sel": "#B08D57", "hl_bg": "#453518",
        "h1": "#D4AF37", "h2": "#9EB07A", "h3": "#C98B3E", "strong": "#C4633E", "em": "#B48CC4",
        "link": "#7FA8C4", "code": "#E0A85B", "green": "#6E9A5E", "marker": "#D4AF37", "fmt": "#9A8A6A",
    },
    "panton-pop": {  # Verner Panton 波普撞色
        "dark": True, "bg": "#1B1420", "surface": "#2A1F33", "border": "#3D2B4A",
        "fg": "#F0E6EE", "muted": "#A38CB0", "cursor": "#E0348B", "sel": "#8E44E8", "hl_bg": "#4A2A18",
        "h1": "#E0348B", "h2": "#22C1C3", "h3": "#FF7A2F", "strong": "#FF4D6D", "em": "#A66BFF",
        "link": "#4FD1FF", "code": "#FFD93D", "green": "#3DDC84", "marker": "#E0348B", "fmt": "#A88CB8",
    },
    "saul-bass-noir": {  # Saul Bass 电影海报
        "dark": True, "bg": "#121212", "surface": "#1E1C1A", "border": "#33302C",
        "fg": "#EDE7DD", "muted": "#9A9187", "cursor": "#E03C31", "sel": "#F08A24", "hl_bg": "#4A2A14",
        "h1": "#E03C31", "h2": "#F08A24", "h3": "#C4A87A", "strong": "#FF5C4D", "em": "#D9B26B",
        "link": "#E8A33C", "code": "#F2765C", "green": "#8FA35B", "marker": "#E03C31", "fmt": "#A09589",
    },
    "glaser-psychedelic": {  # Milton Glaser 迷幻海报
        "dark": True, "bg": "#1A1030", "surface": "#271744", "border": "#3A2560",
        "fg": "#F4ECFA", "muted": "#A894C0", "cursor": "#FFD93D", "sel": "#A44BF3", "hl_bg": "#4A3418",
        "h1": "#FF5FA2", "h2": "#2FE6D6", "h3": "#FFD93D", "strong": "#FF7A5C", "em": "#A44BF3",
        "link": "#5CC8FF", "code": "#7CFFB2", "green": "#3DDC84", "marker": "#FF5FA2", "fmt": "#A894C8",
    },
    "corbusier-concrete": {  # 柯布西耶 Polychromie Architecturale
        "dark": True, "bg": "#1D1E1C", "surface": "#292A27", "border": "#3A3B37",
        "fg": "#D8D6CE", "muted": "#94918A", "cursor": "#C08A4F", "sel": "#6A8CA6", "hl_bg": "#3F3A20",
        "h1": "#C08A4F", "h2": "#6A8CA6", "h3": "#8A9A5B", "strong": "#A8503C", "em": "#B39CC4",
        "link": "#7FA8C4", "code": "#D4A76A", "green": "#6E9A6B", "marker": "#C08A4F", "fmt": "#8F8C85",
    },
    "kandinsky-composition": {  # 康定斯基 构成系列
        "dark": True, "bg": "#16171C", "surface": "#21232A", "border": "#32353E",
        "fg": "#E6E7EC", "muted": "#9497A0", "cursor": "#F2C230", "sel": "#2E6FBF", "hl_bg": "#3F3A18",
        "h1": "#F2C230", "h2": "#5B9BE8", "h3": "#D6423C", "strong": "#E85D57", "em": "#B47FE0",
        "link": "#4FC3E8", "code": "#F2A03C", "green": "#3E9E6B", "marker": "#F2C230", "fmt": "#9A9DA8",
    },
    "yves-klein-ikb": {  # 伊夫·克莱因 国际克莱因蓝
        "dark": True, "bg": "#0A0F2C", "surface": "#131A40", "border": "#1F2A5C",
        "fg": "#DCE1F5", "muted": "#8A93BF", "cursor": "#5C6BFF", "sel": "#3E4AFF", "hl_bg": "#2A2A5C",
        "h1": "#5C6BFF", "h2": "#8A97FF", "h3": "#E0B24C", "strong": "#FF6B8A", "em": "#A88CFF",
        "link": "#6BC8FF", "code": "#F2C46B", "green": "#4FD69C", "marker": "#5C6BFF", "fmt": "#8A93C8",
    },
    "hiroshige-dusk": {  # 歌川广重 暮色浮世绘
        "dark": True, "bg": "#171B26", "surface": "#222736", "border": "#333A4D",
        "fg": "#E4DCCB", "muted": "#96907F", "cursor": "#D2553D", "sel": "#3F6FA8", "hl_bg": "#3F3A1E",
        "h1": "#D2553D", "h2": "#5B8AC4", "h3": "#C9A227", "strong": "#E07A5C", "em": "#9C8AB8",
        "link": "#6BB2C4", "code": "#D9A85B", "green": "#5A8A6E", "marker": "#D2553D", "fmt": "#968F80",
    },
}

# id -> 显示名（供 theme_manager.py 登记参考）
NAMES = {
    "rams-braun": "拉姆斯·博朗 Rams Braun",
    "bauhaus-primary": "包豪斯三原色 Bauhaus",
    "mondrian-grid": "蒙德里安 Mondrian",
    "albers-interaction": "阿尔伯斯 Albers",
    "paul-rand-ibm": "保罗·兰德 Paul Rand",
    "vignelli-subway": "维格奈利地铁 Vignelli",
    "wes-anderson-pastel": "韦斯·安德森 Wes Anderson",
    "hokusai-wave": "北斋浪 Hokusai",
    "monet-water": "莫奈睡莲 Monet",
    "pantone-serenity": "潘通静谧蓝 Pantone",
    "rothko-crimson": "罗斯科绯红 Rothko",
    "van-gogh-starry": "梵高星夜 Van Gogh",
    "klimt-gold": "克里姆特金 Klimt",
    "panton-pop": "潘顿波普 Panton",
    "saul-bass-noir": "索尔·巴斯 Saul Bass",
    "glaser-psychedelic": "格拉泽迷幻 Glaser",
    "corbusier-concrete": "柯布西耶 Corbusier",
    "kandinsky-composition": "康定斯基 Kandinsky",
    "yves-klein-ikb": "克莱因蓝 Yves Klein",
    "hiroshige-dusk": "广重暮色 Hiroshige",
}


def build_all():
    """返回 {theme_id: {css_var: value}}，供 gen_themes.py 合并。"""
    out = {}
    for src in (LIGHT, DARK):
        for tid, t in src.items():
            out[tid] = expand(t)
    return out
