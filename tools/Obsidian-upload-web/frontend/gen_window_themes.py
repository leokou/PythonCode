# -*- coding: utf-8 -*-
"""窗口主题 CSS 生成器（第二批 20 套：大厂设计规范 + 半透明玻璃创意）。

数据源唯一性：本文件是这 20 套窗口主题的唯一数据源，
生成产物 frontend/themes/window/<id>.css **禁止手改**（下次生成会覆盖）。
第一批 20 套（github-light / glass-mint 等）是手写文件，本脚本不触碰、不覆盖。

用法：
    python frontend/gen_window_themes.py

派生规则（减少重复书写）：
    --h1-color        = title
    --accent-soft     = rgba(accent, .12)
    --accent-gutter   = rgba(accent, .18)
    --hover-overlay   = 深色 rgba(255,255,255,.07) / 浅色 rgba(0,0,0,.06)
    --shadow          = 深色重投影 / 浅色轻投影（可用 shadow 字段覆盖）
    --glass-*         = 由 bg_2 / border 按透明度派生（可用字段覆盖）
"""
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes", "window")
os.makedirs(OUT_DIR, exist_ok=True)


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgba(hex_color, alpha):
    r, g, b = _rgb(hex_color)
    return "rgba(%d,%d,%d,%s)" % (r, g, b, alpha)


# ---------------------------------------------------------------------------
# 20 套主题定义
#   dark        深色主题标记（影响 hover-overlay / shadow / glass 派生）
#   glass_alpha 玻璃面板不透明度（越低越通透）
# ---------------------------------------------------------------------------
THEMES = {
    # ===== Apple =====
    "apple-sonoma": {
        "name": "苹果 Sonoma Light", "dark": False,
        "bg_main": "#F5F5F7", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#EFEFF4", "bg_3": "#E3E3E8", "hover_bg": "#E8E8ED",
        "text": "#1D1D1F", "title": "#000000", "dim": "#86868B",
        "border": "#D2D2D7", "quote": "#C7C7CC", "scroll": "#C7C7CC",
        "accent": "#0071E3", "accent_strong": "#0058B9",
        "success": "#1D8A45", "error": "#D70015",
        "code_bg": "#F2F2F7", "code_text": "#1D1D1F", "toast_bg": "#1D1D1F",
        "glass_alpha": ".78",
    },
    "apple-visionos": {
        "name": "苹果 visionOS 玻璃", "dark": False,
        "bg_main": "#EDEEF2", "bg_editor": "#FBFCFE", "bg_preview": "#FDFDFF",
        "bg_2": "#E4E7EE", "bg_3": "#D9DDE7", "hover_bg": "#E9ECF3",
        "text": "#22242B", "title": "#0F1116", "dim": "#7C8296",
        "border": "#CBD1DE", "quote": "#B8C0D2", "scroll": "#B4BCCC",
        "accent": "#2C7BE5", "accent_strong": "#1B5FBF",
        "success": "#1F8A54", "error": "#D93F42",
        "code_bg": "#E8EBF2", "code_text": "#2A2D36", "toast_bg": "#22242B",
        "glass_alpha": ".55",
        "shadow": "0 10px 40px rgba(30,40,70,.16)",
    },
    "apple-graphite": {
        "name": "苹果石墨 Graphite Dark", "dark": True,
        "bg_main": "#1C1C1E", "bg_editor": "#1C1C1E", "bg_preview": "#161618",
        "bg_2": "#2C2C2E", "bg_3": "#3A3A3C", "hover_bg": "#3A3A3C",
        "text": "#E5E5EA", "title": "#F2F2F7", "dim": "#8E8E93",
        "border": "#3A3A3C", "quote": "#48484A", "scroll": "#5A5A5E",
        "accent": "#0A84FF", "accent_strong": "#409CFF",
        "success": "#30D158", "error": "#FF453A",
        "code_bg": "#2C2C2E", "code_text": "#E5E5EA", "toast_bg": "#3A3A3C",
        "glass_alpha": ".72",
    },
    "apple-liquid-glass": {
        "name": "苹果液态玻璃 Liquid Glass", "dark": False,
        "bg_main": "#EAF0FA", "bg_editor": "#FAFCFF", "bg_preview": "#FFFFFF",
        "bg_2": "#DEE8F8", "bg_3": "#CDDDF4", "hover_bg": "#E4EDFB",
        "text": "#1F2A3C", "title": "#0B1524", "dim": "#6C7C94",
        "border": "#BFD2EE", "quote": "#9FB9E0", "scroll": "#A8C0E4",
        "accent": "#0A84FF", "accent_strong": "#0060DF",
        "success": "#00A06B", "error": "#E5484D",
        "code_bg": "#E2ECFB", "code_text": "#1F2A3C", "toast_bg": "#123055",
        "glass_alpha": ".45",
        "shadow": "0 12px 44px rgba(20,60,120,.20)",
        "glass_border": "rgba(255,255,255,.75)",
    },
    # ===== Microsoft =====
    "fluent-mica": {
        "name": "微软 Fluent Mica", "dark": False,
        "bg_main": "#F3F3F3", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#EDEDED", "bg_3": "#E1E1E1", "hover_bg": "#EAEAEA",
        "text": "#242424", "title": "#1B1B1B", "dim": "#616161",
        "border": "#D1D1D1", "quote": "#C6C6C6", "scroll": "#BDBDBD",
        "accent": "#0F6CBD", "accent_strong": "#115EA3",
        "success": "#0E700E", "error": "#C50F1F",
        "code_bg": "#F0F0F0", "code_text": "#242424", "toast_bg": "#242424",
        "glass_alpha": ".70",
    },
    "fluent-acrylic-dark": {
        "name": "微软 Fluent 亚克力暗", "dark": True,
        "bg_main": "#202020", "bg_editor": "#1B1B1B", "bg_preview": "#181818",
        "bg_2": "#2B2B2B", "bg_3": "#333333", "hover_bg": "#383838",
        "text": "#E4E4E4", "title": "#FFFFFF", "dim": "#9A9A9A",
        "border": "#3D3D3D", "quote": "#4A4A4A", "scroll": "#5C5C5C",
        "accent": "#479EF5", "accent_strong": "#62ABF5",
        "success": "#54B054", "error": "#FF5A5F",
        "code_bg": "#2B2B2B", "code_text": "#E4E4E4", "toast_bg": "#333333",
        "glass_alpha": ".62",
    },
    "midnight-glass": {
        "name": "午夜玻璃 Midnight Glass", "dark": True,
        "bg_main": "#0F1420", "bg_editor": "#131A28", "bg_preview": "#10161F",
        "bg_2": "#182030", "bg_3": "#232E44", "hover_bg": "#1E2839",
        "text": "#D7E1F2", "title": "#F2F6FF", "dim": "#7D8CA8",
        "border": "#2A3549", "quote": "#3A4863", "scroll": "#3F4E6B",
        "accent": "#6EA8FE", "accent_strong": "#93C0FF",
        "success": "#3DD68C", "error": "#FF6B81",
        "code_bg": "#18202F", "code_text": "#CBD8EE", "toast_bg": "#232E44",
        "glass_alpha": ".48",
        "glass_border": "rgba(120,160,255,.30)",
        "shadow": "0 12px 40px rgba(0,10,30,.62)",
    },
    # ===== Google =====
    "material3-purple": {
        "name": "Material 3 淡紫", "dark": False,
        "bg_main": "#FEF7FF", "bg_editor": "#FFFBFF", "bg_preview": "#FFFFFF",
        "bg_2": "#F3EDF7", "bg_3": "#E8DEF8", "hover_bg": "#EFE7F6",
        "text": "#1D1B20", "title": "#21005D", "dim": "#79747E",
        "border": "#CAC4D0", "quote": "#B9B2C4", "scroll": "#CAC4D0",
        "accent": "#6750A4", "accent_strong": "#4F378B",
        "success": "#146C2E", "error": "#B3261E",
        "code_bg": "#F0EAF6", "code_text": "#1D1B20", "toast_bg": "#322F35",
        "glass_alpha": ".80",
    },
    "material3-dark": {
        "name": "Material 3 暗色", "dark": True,
        "bg_main": "#141218", "bg_editor": "#1D1B20", "bg_preview": "#17151C",
        "bg_2": "#211F26", "bg_3": "#2B2930", "hover_bg": "#332F37",
        "text": "#E6E0E9", "title": "#EADDFF", "dim": "#938F99",
        "border": "#49454F", "quote": "#5A555F", "scroll": "#5F5A66",
        "accent": "#D0BCFF", "accent_strong": "#E8DEF8",
        "success": "#79DD8F", "error": "#F2B8B5",
        "code_bg": "#231F27", "code_text": "#E6E0E9", "toast_bg": "#332F37",
        "glass_alpha": ".72",
    },
    # ===== IBM =====
    "ibm-carbon": {
        "name": "IBM Carbon White", "dark": False,
        "bg_main": "#F4F4F4", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#E0E0E0", "bg_3": "#D8D8D8", "hover_bg": "#E8E8E8",
        "text": "#161616", "title": "#161616", "dim": "#6F6F6F",
        "border": "#C6C6C6", "quote": "#8D8D8D", "scroll": "#A8A8A8",
        "accent": "#0F62FE", "accent_strong": "#0043CE",
        "success": "#24A148", "error": "#DA1E28",
        "code_bg": "#F4F4F4", "code_text": "#161616", "toast_bg": "#393939",
        "glass_alpha": ".88",
        "shadow": "0 4px 16px rgba(0,0,0,.16)",
    },
    "ibm-carbon-g100": {
        "name": "IBM Carbon Gray 100", "dark": True,
        "bg_main": "#161616", "bg_editor": "#161616", "bg_preview": "#121212",
        "bg_2": "#262626", "bg_3": "#393939", "hover_bg": "#353535",
        "text": "#F4F4F4", "title": "#FFFFFF", "dim": "#8D8D8D",
        "border": "#393939", "quote": "#525252", "scroll": "#6F6F6F",
        "accent": "#4589FF", "accent_strong": "#78A9FF",
        "success": "#42BE65", "error": "#FA4D56",
        "code_bg": "#262626", "code_text": "#F4F4F4", "toast_bg": "#393939",
        "glass_alpha": ".84",
    },
    # ===== Adobe / Atlassian / Shopify =====
    "adobe-spectrum": {
        "name": "Adobe Spectrum", "dark": False,
        "bg_main": "#F5F5F5", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#EAEAEA", "bg_3": "#E1E1E1", "hover_bg": "#E9E9E9",
        "text": "#2C2C2C", "title": "#1A1A1A", "dim": "#707070",
        "border": "#D3D3D3", "quote": "#C4C4C4", "scroll": "#B3B3B3",
        "accent": "#1473E6", "accent_strong": "#0D66D0",
        "success": "#2D9D78", "error": "#D7373F",
        "code_bg": "#F0F0F0", "code_text": "#2C2C2C", "toast_bg": "#2C2C2C",
        "glass_alpha": ".84",
    },
    "atlassian-cloud": {
        "name": "Atlassian Cloud", "dark": False,
        "bg_main": "#F4F5F7", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#EBECF0", "bg_3": "#DFE1E6", "hover_bg": "#E9EBEF",
        "text": "#172B4D", "title": "#091E42", "dim": "#6B778C",
        "border": "#DFE1E6", "quote": "#C1C7D0", "scroll": "#B3BAC5",
        "accent": "#0052CC", "accent_strong": "#0747A6",
        "success": "#006644", "error": "#DE350B",
        "code_bg": "#F4F5F7", "code_text": "#172B4D", "toast_bg": "#253858",
        "glass_alpha": ".85",
    },
    "sunset-glass": {
        "name": "暮色玻璃 Sunset Glass", "dark": False,
        "bg_main": "#FDF0EC", "bg_editor": "#FFFBF9", "bg_preview": "#FFFFFF",
        "bg_2": "#FAE3DC", "bg_3": "#F6D2C7", "hover_bg": "#FBE8E2",
        "text": "#3E2A29", "title": "#26120F", "dim": "#9A7A72",
        "border": "#EFC9BC", "quote": "#E0A996", "scroll": "#E5B4A4",
        "accent": "#E8622C", "accent_strong": "#C44A1B",
        "success": "#3E8E62", "error": "#C9304A",
        "code_bg": "#FAE7E0", "code_text": "#3E2A29", "toast_bg": "#5A2A1E",
        "glass_alpha": ".52",
        "shadow": "0 10px 36px rgba(150,60,30,.18)",
    },
    "shopify-polaris": {
        "name": "Shopify Polaris", "dark": False,
        "bg_main": "#F6F6F7", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#F1F2F3", "bg_3": "#E3E5E7", "hover_bg": "#EDEEEF",
        "text": "#202223", "title": "#111213", "dim": "#6D7175",
        "border": "#D5D7DA", "quote": "#C9CCCF", "scroll": "#BABEC3",
        "accent": "#008060", "accent_strong": "#004C3F",
        "success": "#008060", "error": "#D72C0D",
        "code_bg": "#F1F2F3", "code_text": "#202223", "toast_bg": "#202223",
        "glass_alpha": ".86",
    },
    # ===== 国内大厂 =====
    "ant-design": {
        "name": "蚂蚁 Ant Design", "dark": False,
        "bg_main": "#F5F5F5", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#FAFAFA", "bg_3": "#F0F0F0", "hover_bg": "#F5F5F5",
        "text": "#000000D9", "title": "#000000E0", "dim": "#00000073",
        "border": "#D9D9D9", "quote": "#D9D9D9", "scroll": "#BFBFBF",
        "accent": "#1677FF", "accent_strong": "#0958D9",
        "success": "#52C41A", "error": "#FF4D4F",
        "code_bg": "#F5F5F5", "code_text": "#000000D9", "toast_bg": "#262626",
        "glass_alpha": ".88",
        "shadow": "0 6px 16px rgba(0,0,0,.08)",
    },
    "tdesign-blue": {
        "name": "腾讯 TDesign", "dark": False,
        "bg_main": "#F3F3F3", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#F5F5F5", "bg_3": "#EAEAEA", "hover_bg": "#F0F1F5",
        "text": "#2B2E33", "title": "#181B21", "dim": "#767C86",
        "border": "#DCDCDC", "quote": "#C5C7CB", "scroll": "#C0C3C9",
        "accent": "#0052D9", "accent_strong": "#003CAB",
        "success": "#2BA471", "error": "#D54941",
        "code_bg": "#F3F3F3", "code_text": "#2B2E33", "toast_bg": "#242933",
        "glass_alpha": ".86",
    },
    "arco-blue": {
        "name": "字节 Arco Design", "dark": False,
        "bg_main": "#F7F8FA", "bg_editor": "#FFFFFF", "bg_preview": "#FFFFFF",
        "bg_2": "#F2F3F5", "bg_3": "#E5E6EB", "hover_bg": "#F2F3F5",
        "text": "#1D2129", "title": "#131721", "dim": "#86909C",
        "border": "#E5E6EB", "quote": "#C9CDD4", "scroll": "#C9CDD4",
        "accent": "#165DFF", "accent_strong": "#0E42D2",
        "success": "#00B42A", "error": "#F53F3F",
        "code_bg": "#F2F3F5", "code_text": "#1D2129", "toast_bg": "#1D2129",
        "glass_alpha": ".86",
    },
    # ===== 创意 =====
    "frosted-aurora": {
        "name": "极光磨砂 Frosted Aurora", "dark": False,
        "bg_main": "#EAF3F3", "bg_editor": "#F9FDFD", "bg_preview": "#FFFFFF",
        "bg_2": "#DDEFEE", "bg_3": "#C8E6E4", "hover_bg": "#E2F2F1",
        "text": "#1E3A3A", "title": "#0C2626", "dim": "#6E8E8E",
        "border": "#B9DCDA", "quote": "#8FC6C4", "scroll": "#9FD0CE",
        "accent": "#00A6A6", "accent_strong": "#007C7C",
        "success": "#12996B", "error": "#D3455B",
        "code_bg": "#E1F1F0", "code_text": "#1E3A3A", "toast_bg": "#0F3B3B",
        "glass_alpha": ".50",
        "shadow": "0 10px 38px rgba(0,90,90,.16)",
    },
    "neumorph-soft": {
        "name": "新拟态 Neumorphism", "dark": False,
        "bg_main": "#E0E5EC", "bg_editor": "#E6EBF2", "bg_preview": "#EDF1F7",
        "bg_2": "#DAE0E8", "bg_3": "#CFD6E0", "hover_bg": "#E6EBF2",
        "text": "#3C4759", "title": "#26303F", "dim": "#8A94A6",
        "border": "#C8D0DC", "quote": "#B3BDCC", "scroll": "#BAC4D2",
        "accent": "#5B7CFA", "accent_strong": "#3F5FD8",
        "success": "#3EA47A", "error": "#D95C6A",
        "code_bg": "#DCE2EA", "code_text": "#3C4759", "toast_bg": "#3C4759",
        "glass_alpha": ".74",
        "shadow": "6px 6px 16px rgba(163,177,198,.55), -6px -6px 16px rgba(255,255,255,.85)",
        "glass_shadow": "6px 6px 18px rgba(163,177,198,.50), -6px -6px 18px rgba(255,255,255,.90)",
    },
}

TEMPLATE = """/* 窗口主题 —— {name}（由 gen_window_themes.py 生成，勿手改） */
body[data-window-theme="{id}"] {{
{vars}
}}
"""

ORDER = [
    ("bg-main", "窗口主背景"), ("bg-editor", "编辑区背景"), ("bg-preview", "预览区背景"),
    ("bg-2", "顶栏/底栏/面板标题背景"), ("bg-3", "标签页/滚动条/下拉背景"), ("hover-bg", "悬浮背景"),
    ("text-color", "普通正文"), ("title-color", "标题文字"), ("h1-color", "一级标题"), ("text-dim", "辅助文字"),
    ("border-color", "边框"), ("quote-color", "引用竖线"), ("scroll-thumb", "滚动条"),
    ("accent", "强调色"), ("accent-strong", "强调色加深"),
    ("accent-soft", "当前行高亮"), ("accent-gutter", "当前行行号高亮"), ("hover-overlay", "图标按钮悬浮"),
    ("success", "成功色"), ("error", "错误色"),
    ("code-bg", "代码块背景"), ("code-text", "代码块文字"), ("toast-bg", "Toast 背景"),
    ("shadow", "阴影"), ("glass-bg", "玻璃面板背景"), ("glass-border", "玻璃面板边框"), ("glass-shadow", "玻璃面板阴影"),
]


def build(t):
    dark = t.get("dark", False)
    accent = t["accent"]
    shadow = t.get("shadow") or (
        "0 10px 32px rgba(0,0,0,.50)" if dark else "0 6px 24px rgba(0,0,0,.10)")
    galpha = t.get("glass_alpha", ".80" if not dark else ".70")
    glass_bg = t.get("glass_bg") or rgba(t["bg_2"][:7], galpha)
    glass_border = t.get("glass_border") or rgba(t["border"][:7], ".70")
    return {
        "bg-main": t["bg_main"], "bg-editor": t["bg_editor"], "bg-preview": t["bg_preview"],
        "bg-2": t["bg_2"], "bg-3": t["bg_3"], "hover-bg": t["hover_bg"],
        "text-color": t["text"], "title-color": t["title"], "h1-color": t["title"], "text-dim": t["dim"],
        "border-color": t["border"], "quote-color": t["quote"], "scroll-thumb": t["scroll"],
        "accent": accent, "accent-strong": t["accent_strong"],
        "accent-soft": rgba(accent, ".12"), "accent-gutter": rgba(accent, ".18"),
        "hover-overlay": "rgba(255,255,255,.07)" if dark else "rgba(0,0,0,.06)",
        "success": t["success"], "error": t["error"],
        "code-bg": t["code_bg"], "code-text": t["code_text"], "toast-bg": t["toast_bg"],
        "shadow": shadow, "glass-bg": glass_bg, "glass-border": glass_border,
        "glass-shadow": t.get("glass_shadow") or shadow,
    }


def main():
    for tid, t in THEMES.items():
        values = build(t)
        lines = []
        for key, comment in ORDER:
            lines.append("  --%s: %s;%s" % (key, values[key], "  /* %s */" % comment))
        content = TEMPLATE.format(id=tid, name=t["name"], vars="\n".join(lines))
        path = os.path.join(OUT_DIR, tid + ".css")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Created:", path)
    print("\nDone! %d window themes." % len(THEMES))


if __name__ == "__main__":
    main()
