# -*- coding: utf-8 -*-
"""Markdown 预览主题 CSS 生成器（第二批 20 套：知名 Markdown 展示样式复刻）。

数据源唯一性：本文件是这 20 套预览主题的唯一数据源，
产物 frontend/themes/preview/<id>.css **禁止手改**（下次生成会覆盖）。
第一批 40 套（github / notion / tufte 等）是手写文件，本脚本不触碰。

参考样式来源：Typora 官方主题（Newsprint / Pixyll / Whitey / Vue / Gothic / Night /
Academic）、Markdown Nice 社区主题（Lapis / Maize / 橙心 / 全栈蓝 / 兰青）、
掘金、知乎、微信公众号、LaTeX article、Nord、Dracula、Rosé Pine、MkDocs Material。

用法：python frontend/gen_preview_themes.py
"""
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes", "preview")
os.makedirs(OUT_DIR, exist_ok=True)

SANS = '-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
SERIF = 'Georgia, "Songti SC", "Noto Serif SC", serif'
MONO = '"JetBrains Mono", Consolas, "Courier New", monospace'

# 默认值：未声明的字段走这里
DEFAULTS = {
    "font": SANS, "line_height": "1.7", "padding": "36px 44px",
    "h1_size": "2.0em", "h2_size": "1.55em", "h3_size": "1.25em",
    "h1_border": "none", "h2_border": "none",
    "h1_align": "left", "h1_weight": "700", "h2_weight": "700", "h3_weight": "600",
    "h456_style": "normal",
    "radius": "6px", "img_radius": "6px",
    "code_font_size": "85%", "quote_style": "normal",
    "list_pad": "1.9em", "li_margin": "4px 0",
    "table_width": "100%", "pre_pad": "16px",
}

THEMES = {
    # ================= Typora 官方主题系 =================
    "typora-newsprint": {
        "name": "Typora Newsprint 报纸",
        "bg": "#F7F5EE", "fg": "#2B2B2B", "font": SERIF, "line_height": "1.75",
        "padding": "40px 56px",
        "h1": "#1A1A1A", "h2": "#1A1A1A", "h3": "#1A1A1A", "h456": "#333333",
        "h1_border": "2px solid #2B2B2B", "h2_border": "1px solid #C9C4B4",
        "link": "#A00000", "strong": "#000000", "em": "#4A4A4A",
        "code_bg": "#EDE9DC", "code_fg": "#A00000",
        "pre_bg": "#EFEBDE", "pre_border": "1px solid #D8D2BE", "pre_fg": "#2B2B2B",
        "quote_border": "4px solid #C9C4B4", "quote_bg": "#F1EDE0", "quote_fg": "#4A4A4A",
        "quote_style": "italic",
        "th_bg": "#EDE9DC", "th_fg": "#1A1A1A", "td_border": "#D8D2BE",
        "hr": "#C9C4B4", "scroll": "#C9C4B4", "radius": "2px", "img_radius": "2px",
    },
    "typora-pixyll": {
        "name": "Typora Pixyll",
        "bg": "#FFFFFF", "fg": "#333333", "font": '"Palatino Linotype", Palatino, Georgia, serif',
        "line_height": "1.85", "padding": "44px 72px",
        "h1": "#111111", "h2": "#111111", "h3": "#111111", "h456": "#333333",
        "h1_size": "2.4em", "h2_size": "1.8em", "h1_weight": "800",
        "link": "#0076DF", "strong": "#111111", "em": "#555555",
        "code_bg": "#F5F5F5", "code_fg": "#C7254E",
        "pre_bg": "#F8F8F8", "pre_border": "1px solid #E8E8E8", "pre_fg": "#333333",
        "quote_border": "4px solid #E8E8E8", "quote_bg": "none", "quote_fg": "#666666",
        "quote_style": "italic",
        "th_bg": "#F5F5F5", "th_fg": "#111111", "td_border": "#E8E8E8",
        "hr": "#E8E8E8", "scroll": "#D6D6D6", "radius": "3px",
    },
    "typora-whitey": {
        "name": "Typora Whitey 素白",
        "bg": "#FFFFFF", "fg": "#3A3A3A", "font": '"Helvetica Neue", Helvetica, Arial, sans-serif',
        "line_height": "1.7", "padding": "36px 60px",
        "h1": "#222222", "h2": "#222222", "h3": "#333333", "h456": "#555555",
        "h1_size": "1.9em", "h2_size": "1.5em",
        "h2_border": "1px solid #EDEDED",
        "link": "#4183C4", "strong": "#222222", "em": "#5A5A5A",
        "code_bg": "#F5F5F5", "code_fg": "#D14",
        "pre_bg": "#FAFAFA", "pre_border": "1px solid #EDEDED", "pre_fg": "#3A3A3A",
        "quote_border": "4px solid #DDDDDD", "quote_bg": "#FAFAFA", "quote_fg": "#666666",
        "th_bg": "#F7F7F7", "th_fg": "#222222", "td_border": "#EDEDED",
        "hr": "#EDEDED", "scroll": "#DADADA", "radius": "3px",
    },
    "typora-vue": {
        "name": "Typora Vue 绿",
        "bg": "#FFFFFF", "fg": "#2C3E50", "line_height": "1.75", "padding": "36px 48px",
        "h1": "#2C3E50", "h2": "#2C3E50", "h3": "#42B983", "h456": "#2C3E50",
        "h2_border": "1px solid #ECEFF1",
        "link": "#42B983", "strong": "#2C3E50", "em": "#7F8C8D",
        "code_bg": "#F8F8F8", "code_fg": "#E96900",
        "pre_bg": "#282C34", "pre_border": "none", "pre_fg": "#ABB2BF",
        "quote_border": "4px solid #42B983", "quote_bg": "#F3F5F7", "quote_fg": "#3A5169",
        "th_bg": "#F3F5F7", "th_fg": "#2C3E50", "td_border": "#E3E8EC",
        "hr": "#ECEFF1", "scroll": "#CFD8DC", "radius": "4px",
    },
    "typora-gothic": {
        "name": "Typora Gothic 哥特无衬线",
        "bg": "#FCFCFC", "fg": "#1F1F1F", "font": '"Century Gothic", "Futura", "Avenir", sans-serif',
        "line_height": "1.6", "padding": "34px 46px",
        "h1": "#000000", "h2": "#000000", "h3": "#1F1F1F", "h456": "#3D3D3D",
        "h1_weight": "800", "h1_size": "2.1em", "h1_border": "3px solid #000000",
        "link": "#005B99", "strong": "#000000", "em": "#4A4A4A",
        "code_bg": "#F0F0F0", "code_fg": "#B3005B",
        "pre_bg": "#F4F4F4", "pre_border": "1px solid #E2E2E2", "pre_fg": "#1F1F1F",
        "quote_border": "3px solid #1F1F1F", "quote_bg": "none", "quote_fg": "#4A4A4A",
        "th_bg": "#F0F0F0", "th_fg": "#000000", "td_border": "#E2E2E2",
        "hr": "#E2E2E2", "scroll": "#D2D2D2", "radius": "0", "img_radius": "0",
    },
    "typora-night": {
        "name": "Typora Night 夜间",
        "bg": "#363B40", "fg": "#B8BFC6", "line_height": "1.7", "padding": "36px 44px",
        "h1": "#DDE4EB", "h2": "#DDE4EB", "h3": "#C6CFD8", "h456": "#B8BFC6",
        "h2_border": "1px solid #4A5058",
        "link": "#6DB3F2", "strong": "#E8EEF4", "em": "#9BA6B2",
        "code_bg": "#2F3438", "code_fg": "#E88388",
        "pre_bg": "#2F3438", "pre_border": "1px solid #4A5058", "pre_fg": "#B8BFC6",
        "quote_border": "4px solid #6DB3F2", "quote_bg": "#3B4147", "quote_fg": "#A7B0BA",
        "th_bg": "#2F3438", "th_fg": "#DDE4EB", "td_border": "#4A5058",
        "hr": "#4A5058", "scroll": "#565D66",
    },
    "typora-academic": {
        "name": "Typora Academic 学术",
        "bg": "#FFFFFF", "fg": "#1A1A1A", "font": '"Latin Modern Roman", "Times New Roman", Georgia, serif',
        "line_height": "1.8", "padding": "48px 84px",
        "h1": "#000000", "h2": "#000000", "h3": "#000000", "h456": "#1A1A1A",
        "h1_align": "center", "h1_size": "2.1em", "h2_size": "1.5em", "h456_style": "italic",
        "link": "#00477F", "strong": "#000000", "em": "#1A1A1A",
        "code_bg": "#F2F2F2", "code_fg": "#8B0000",
        "pre_bg": "#F7F7F7", "pre_border": "1px solid #E0E0E0", "pre_fg": "#1A1A1A",
        "quote_border": "2px solid #999999", "quote_bg": "none", "quote_fg": "#333333",
        "quote_style": "italic",
        "th_bg": "none", "th_fg": "#000000", "td_border": "#BBBBBB",
        "hr": "#BBBBBB", "scroll": "#CCCCCC", "radius": "0", "img_radius": "0",
        "table_width": "auto",
    },
    # ================= Markdown Nice 中文社区主题 =================
    "lapis": {
        "name": "Lapis 青金石",
        "bg": "#FFFFFF", "fg": "#40464F", "line_height": "1.8", "padding": "36px 44px",
        "h1": "#4870AC", "h2": "#4870AC", "h3": "#5B8AC8", "h456": "#40464F",
        "h1_align": "center", "h1_size": "1.9em", "h2_border": "1px solid #DDE4EE",
        "link": "#4870AC", "strong": "#2F4E7E", "em": "#7A8899",
        "code_bg": "#EEF3FA", "code_fg": "#4870AC",
        "pre_bg": "#F6F8FC", "pre_border": "1px solid #DDE4EE", "pre_fg": "#40464F",
        "quote_border": "4px solid #4870AC", "quote_bg": "#F3F7FC", "quote_fg": "#5A6472",
        "th_bg": "#EEF3FA", "th_fg": "#2F4E7E", "td_border": "#DDE4EE",
        "hr": "#DDE4EE", "scroll": "#C4D2E6", "radius": "5px",
    },
    "maize": {
        "name": "Maize 玉米黄",
        "bg": "#FFFEFA", "fg": "#3F3B32", "line_height": "1.8", "padding": "36px 44px",
        "h1": "#B8860B", "h2": "#C99A2E", "h3": "#8A6D1F", "h456": "#3F3B32",
        "h1_border": "3px solid #FFC83D",
        "link": "#D48806", "strong": "#8A6D1F", "em": "#7A7160",
        "code_bg": "#FFF6DC", "code_fg": "#B8860B",
        "pre_bg": "#FFFBEE", "pre_border": "1px solid #F0E2B8", "pre_fg": "#3F3B32",
        "quote_border": "4px solid #FFC83D", "quote_bg": "#FFFAE8", "quote_fg": "#6B6250",
        "th_bg": "#FFF6DC", "th_fg": "#8A6D1F", "td_border": "#F0E2B8",
        "hr": "#F0E2B8", "scroll": "#E8D79A", "radius": "5px",
    },
    "orange-heart": {
        "name": "橙心 Orange Heart",
        "bg": "#FFFFFF", "fg": "#3E3E3E", "line_height": "1.8", "padding": "36px 44px",
        "h1": "#FF7B54", "h2": "#FF9B70", "h3": "#E2603A", "h456": "#3E3E3E",
        "h1_align": "center", "h1_border": "2px solid #FFD3B5",
        "link": "#FF7B54", "strong": "#E2603A", "em": "#8A8A8A",
        "code_bg": "#FFF2EC", "code_fg": "#E2603A",
        "pre_bg": "#FFF8F4", "pre_border": "1px solid #FFDCCB", "pre_fg": "#3E3E3E",
        "quote_border": "4px solid #FF7B54", "quote_bg": "#FFF6F1", "quote_fg": "#6B6B6B",
        "th_bg": "#FFF2EC", "th_fg": "#E2603A", "td_border": "#FFDCCB",
        "hr": "#FFDCCB", "scroll": "#FFC7AE", "radius": "6px",
    },
    "channing-cyan": {
        "name": "全栈蓝 Channing Cyan",
        "bg": "#FFFFFF", "fg": "#333333", "line_height": "1.8", "padding": "36px 44px",
        "h1": "#0F4C81", "h2": "#12689E", "h3": "#1B87C4", "h456": "#333333",
        "h2_border": "1px solid #D6E4F0",
        "link": "#1B87C4", "strong": "#0F4C81", "em": "#5A6B7A",
        "code_bg": "#EAF3FA", "code_fg": "#0F4C81",
        "pre_bg": "#F4F9FD", "pre_border": "1px solid #D6E4F0", "pre_fg": "#333333",
        "quote_border": "4px solid #0F4C81", "quote_bg": "#F2F8FC", "quote_fg": "#556370",
        "th_bg": "#EAF3FA", "th_fg": "#0F4C81", "td_border": "#D6E4F0",
        "hr": "#D6E4F0", "scroll": "#BBD5EA", "radius": "5px",
    },
    "purple-mdnice": {
        "name": "兰青紫 Purple",
        "bg": "#FFFFFF", "fg": "#3C3C43", "line_height": "1.8", "padding": "36px 44px",
        "h1": "#8064A2", "h2": "#9A7CB8", "h3": "#6A5188", "h456": "#3C3C43",
        "h1_align": "center", "h1_border": "2px solid #E3D9EE",
        "link": "#8064A2", "strong": "#6A5188", "em": "#7E7E8C",
        "code_bg": "#F3EEF9", "code_fg": "#8064A2",
        "pre_bg": "#F8F5FC", "pre_border": "1px solid #E3D9EE", "pre_fg": "#3C3C43",
        "quote_border": "4px solid #8064A2", "quote_bg": "#F7F3FB", "quote_fg": "#63636E",
        "th_bg": "#F3EEF9", "th_fg": "#6A5188", "td_border": "#E3D9EE",
        "hr": "#E3D9EE", "scroll": "#D3C4E4", "radius": "5px",
    },
    # ================= 中文内容平台 =================
    "juejin-default": {
        "name": "掘金 Juejin",
        "bg": "#FFFFFF", "fg": "#252933", "line_height": "1.75", "padding": "32px 40px",
        "h1": "#1D2129", "h2": "#1D2129", "h3": "#1D2129", "h456": "#252933",
        "h1_size": "1.85em", "h2_border": "1px solid #E5E6EB",
        "link": "#1E80FF", "strong": "#1D2129", "em": "#515767",
        "code_bg": "#F2F3F5", "code_fg": "#C7254E",
        "pre_bg": "#2B2B2B", "pre_border": "none", "pre_fg": "#E6E6E6",
        "quote_border": "4px solid #1E80FF", "quote_bg": "#F7F8FA", "quote_fg": "#515767",
        "th_bg": "#F2F3F5", "th_fg": "#1D2129", "td_border": "#E5E6EB",
        "hr": "#E5E6EB", "scroll": "#C9CDD4", "radius": "4px",
    },
    "zhihu-style": {
        "name": "知乎 Zhihu",
        "bg": "#FFFFFF", "fg": "#1A1A1A", "line_height": "1.8", "padding": "32px 40px",
        "h1": "#1A1A1A", "h2": "#1A1A1A", "h3": "#1A1A1A", "h456": "#444444",
        "h1_size": "1.8em", "h1_weight": "600", "h2_weight": "600",
        "link": "#175199", "strong": "#121212", "em": "#646464",
        "code_bg": "#F6F6F6", "code_fg": "#C0341D",
        "pre_bg": "#F6F6F6", "pre_border": "1px solid #EBEBEB", "pre_fg": "#1A1A1A",
        "quote_border": "3px solid #D8D8D8", "quote_bg": "#FCFCFC", "quote_fg": "#646464",
        "th_bg": "#F6F6F6", "th_fg": "#1A1A1A", "td_border": "#EBEBEB",
        "hr": "#EBEBEB", "scroll": "#D8D8D8", "radius": "3px",
    },
    "wechat-green": {
        "name": "公众号绿意 WeChat",
        "bg": "#FFFFFF", "fg": "#3F3F3F", "line_height": "1.85", "padding": "32px 36px",
        "h1": "#27AE60", "h2": "#2ECC71", "h3": "#1E8449", "h456": "#3F3F3F",
        "h1_align": "center", "h1_size": "1.7em", "h1_border": "2px solid #A9DFBF",
        "link": "#27AE60", "strong": "#1E8449", "em": "#7B7B7B",
        "code_bg": "#EDF7F0", "code_fg": "#1E8449",
        "pre_bg": "#F5FAF7", "pre_border": "1px solid #CFE9DA", "pre_fg": "#3F3F3F",
        "quote_border": "4px solid #27AE60", "quote_bg": "#F3FAF6", "quote_fg": "#5E6E64",
        "th_bg": "#EDF7F0", "th_fg": "#1E8449", "td_border": "#CFE9DA",
        "hr": "#CFE9DA", "scroll": "#B7E0C6", "radius": "5px",
    },
    "latex-article": {
        "name": "LaTeX Article 论文",
        "bg": "#FDFDFB", "fg": "#111111", "font": '"Computer Modern", "Latin Modern Roman", "Times New Roman", serif',
        "line_height": "1.75", "padding": "52px 96px",
        "h1": "#000000", "h2": "#000000", "h3": "#000000", "h456": "#111111",
        "h1_align": "center", "h1_size": "2.0em", "h2_size": "1.45em", "h3_size": "1.2em",
        "h456_style": "italic",
        "link": "#0B5394", "strong": "#000000", "em": "#111111",
        "code_bg": "#F0F0EC", "code_fg": "#7A0000",
        "pre_bg": "#F6F6F2", "pre_border": "1px solid #DDDDD6", "pre_fg": "#111111",
        "quote_border": "2px solid #AAAAAA", "quote_bg": "none", "quote_fg": "#333333",
        "quote_style": "italic",
        "th_bg": "none", "th_fg": "#000000", "td_border": "#999999",
        "hr": "#999999", "scroll": "#C8C8C0", "radius": "0", "img_radius": "0",
        "table_width": "auto",
    },
    # ================= 经典配色方案（暗） =================
    "nord-preview": {
        "name": "Nord 北欧",
        "bg": "#2E3440", "fg": "#D8DEE9", "line_height": "1.75", "padding": "36px 44px",
        "h1": "#88C0D0", "h2": "#81A1C1", "h3": "#8FBCBB", "h456": "#D8DEE9",
        "h2_border": "1px solid #434C5E",
        "link": "#88C0D0", "strong": "#ECEFF4", "em": "#B48EAD",
        "code_bg": "#3B4252", "code_fg": "#EBCB8B",
        "pre_bg": "#3B4252", "pre_border": "1px solid #434C5E", "pre_fg": "#D8DEE9",
        "quote_border": "4px solid #5E81AC", "quote_bg": "#353C4A", "quote_fg": "#AEB8C8",
        "th_bg": "#3B4252", "th_fg": "#ECEFF4", "td_border": "#434C5E",
        "hr": "#434C5E", "scroll": "#4C566A", "radius": "5px",
    },
    "dracula-preview": {
        "name": "Dracula 德古拉",
        "bg": "#282A36", "fg": "#F8F8F2", "line_height": "1.75", "padding": "36px 44px",
        "h1": "#BD93F9", "h2": "#FF79C6", "h3": "#8BE9FD", "h456": "#F8F8F2",
        "h2_border": "1px solid #44475A",
        "link": "#8BE9FD", "strong": "#FFB86C", "em": "#F1FA8C",
        "code_bg": "#44475A", "code_fg": "#50FA7B",
        "pre_bg": "#21222C", "pre_border": "1px solid #44475A", "pre_fg": "#F8F8F2",
        "quote_border": "4px solid #BD93F9", "quote_bg": "#31333F", "quote_fg": "#BFC0C7",
        "th_bg": "#44475A", "th_fg": "#F8F8F2", "td_border": "#44475A",
        "hr": "#44475A", "scroll": "#6272A4", "radius": "5px",
    },
    "rose-pine-preview": {
        "name": "Rosé Pine 玫瑰松",
        "bg": "#191724", "fg": "#E0DEF4", "line_height": "1.8", "padding": "36px 44px",
        "h1": "#EBBCBA", "h2": "#C4A7E7", "h3": "#9CCFD8", "h456": "#E0DEF4",
        "h2_border": "1px solid #26233A",
        "link": "#9CCFD8", "strong": "#F6C177", "em": "#EB6F92",
        "code_bg": "#26233A", "code_fg": "#EBBCBA",
        "pre_bg": "#1F1D2E", "pre_border": "1px solid #26233A", "pre_fg": "#E0DEF4",
        "quote_border": "4px solid #C4A7E7", "quote_bg": "#1F1D2E", "quote_fg": "#908CAA",
        "th_bg": "#26233A", "th_fg": "#E0DEF4", "td_border": "#26233A",
        "hr": "#26233A", "scroll": "#403D52", "radius": "6px",
    },
    "mkdocs-material": {
        "name": "MkDocs Material",
        "bg": "#FFFFFF", "fg": "#2E303E", "line_height": "1.7", "padding": "32px 44px",
        "h1": "#4051B5", "h2": "#2E303E", "h3": "#2E303E", "h456": "#42465C",
        "h1_size": "1.9em", "h1_weight": "300", "h2_border": "1px solid #E4E6EF",
        "link": "#4051B5", "strong": "#1F2233", "em": "#5E6272",
        "code_bg": "#F2F3F8", "code_fg": "#E0426A",
        "pre_bg": "#F5F5F9", "pre_border": "1px solid #E4E6EF", "pre_fg": "#2E303E",
        "quote_border": "4px solid #7986CB", "quote_bg": "#F4F5FB", "quote_fg": "#5E6272",
        "th_bg": "#F2F3F8", "th_fg": "#1F2233", "td_border": "#E4E6EF",
        "hr": "#E4E6EF", "scroll": "#C9CCE0", "radius": "4px",
    },
}

TPL = """/* 预览主题 —— {name}（由 gen_preview_themes.py 生成，勿手改） */
{S} .preview-body {{
  background: {bg};
  color: {fg};
  font-family: {font};
  line-height: {line_height};
  padding: {padding};
}}
{S} .preview-body h1 {{ color: {h1}; font-size: {h1_size}; font-weight: {h1_weight}; text-align: {h1_align}; border-bottom: {h1_border}; padding-bottom: {h1_pad}; }}
{S} .preview-body h2 {{ color: {h2}; font-size: {h2_size}; font-weight: {h2_weight}; border-bottom: {h2_border}; padding-bottom: {h2_pad}; }}
{S} .preview-body h3 {{ color: {h3}; font-size: {h3_size}; font-weight: {h3_weight}; }}
{S} .preview-body h4,
{S} .preview-body h5,
{S} .preview-body h6 {{ color: {h456}; font-style: {h456_style}; }}
{S} .preview-body a {{ color: {link}; text-decoration: underline; }}
{S} .preview-body strong {{ color: {strong}; }}
{S} .preview-body em {{ color: {em}; }}
{S} .preview-body code {{ background: {code_bg}; color: {code_fg}; padding: 0.2em 0.4em; border-radius: {radius}; font-size: {code_font_size}; font-family: {mono}; }}
{S} .preview-body pre {{ background: {pre_bg}; border: {pre_border}; border-radius: {radius}; padding: {pre_pad}; overflow-x: auto; }}
{S} .preview-body pre code {{ background: none; padding: 0; color: {pre_fg}; font-size: {code_font_size}; }}
{S} .preview-body blockquote {{ border-left: {quote_border}; background: {quote_bg}; color: {quote_fg}; padding: 10px 18px; margin: 16px 0; border-radius: 0 {radius} {radius} 0; font-style: {quote_style}; }}
{S} .preview-body table {{ border-collapse: collapse; margin: 16px 0; width: {table_width}; }}
{S} .preview-body th {{ background: {th_bg}; color: {th_fg}; border: 1px solid {td_border}; padding: 8px 13px; font-weight: 600; }}
{S} .preview-body td {{ border: 1px solid {td_border}; padding: 8px 13px; }}
{S} .preview-body hr {{ border: none; border-top: 1px solid {hr}; margin: 24px 0; }}
{S} .preview-body ul,
{S} .preview-body ol {{ padding-left: {list_pad}; }}
{S} .preview-body li {{ margin: {li_margin}; }}
{S} .preview-body img {{ max-width: 100%; border-radius: {img_radius}; }}
{S} .preview-body::-webkit-scrollbar-thumb {{ background: {scroll}; }}
"""


def main():
    for tid, raw in THEMES.items():
        t = dict(DEFAULTS)
        t.update(raw)
        t["S"] = 'body[data-preview-theme="%s"]' % tid
        t["mono"] = MONO
        t["h1_pad"] = "0.3em" if t["h1_border"] != "none" else "0"
        t["h2_pad"] = "0.25em" if t["h2_border"] != "none" else "0"
        path = os.path.join(OUT_DIR, tid + ".css")
        with open(path, "w", encoding="utf-8") as f:
            f.write(TPL.format(**t))
        print("Created:", path)
    print("\nDone! %d preview themes." % len(THEMES))


if __name__ == "__main__":
    main()
