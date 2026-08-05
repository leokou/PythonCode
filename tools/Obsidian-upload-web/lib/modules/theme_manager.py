# -*- coding: utf-8 -*-
"""主题系统：per-window 主题（四个窗口各自独立设置 window / editor / preview 三组主题）。

- window   窗口主题：覆盖 theme.css 的全局变量（工具栏/Tab/按钮/面板/背景）
- editor   编辑区主题：定义 --cm-* 变量，script.js 的 EditorView.theme 用 var() 引用
- preview  Markdown 预览主题：覆盖 .preview-body 渲染区域

主题本体是 web/themes/<类型>/<id>.css 文件；本模块只负责主题配置的读取/保存/校验。
新增主题：在 web/themes/<类型>/ 添加同名 CSS 文件，并在下方 THEMES 登记即可。

存储结构（settings.json）：
  {
    "theme_flash": {"window": "...", "editor": "...", "preview": "..."},
    "theme_inbox": {"window": "...", "editor": "...", "preview": "..."},
    ...
  }
  旧版单套 theme 字段会在首次读取时自动迁移。
"""
import json
import os

from lib.core.settings import settings_path

WINDOW_TYPES = ("flash", "inbox", "log", "capture")

DEFAULT_PER_WINDOW = {
    "flash":   {"window": "github-light", "editor": "github-light", "preview": "github"},
    "inbox":   {"window": "github-light", "editor": "github-light", "preview": "github"},
    "log":     {"window": "github-light", "editor": "github-light", "preview": "github"},
    "capture": {"window": "github-light", "editor": "github-light", "preview": "github"},
}

# 可用主题（id -> 显示名）。id 与 web/themes/<类型>/<id>.css 文件名一致。
THEMES = {
    "window": [
        {"id": "github-light", "name": "GitHub Light"},
        {"id": "notion-light", "name": "Notion Light"},
        {"id": "obsidian-dark", "name": "Obsidian Dark"},
        {"id": "solarized-light", "name": "Solarized Light"},
        {"id": "dracula-dark", "name": "Dracula Dark"},
        {"id": "nord-dark", "name": "Nord Dark"},
        {"id": "material-light", "name": "Material Light"},
        {"id": "one-dark", "name": "One Dark"},
        {"id": "monokai-dark", "name": "Monokai Dark"},
        {"id": "github-dark", "name": "GitHub Dark"},
        {"id": "glass-mint", "name": "玻璃薄荷 Glass Mint"},
        {"id": "tech-cyan", "name": "科技青 Tech Cyan"},
        {"id": "frost-white", "name": "霜白 Frost White"},
        {"id": "aurora-light", "name": "极光浅 Aurora Light"},
        {"id": "crystal-blue", "name": "水晶蓝 Crystal Blue"},
        {"id": "mos-fog", "name": "莫斯雾 Mos Fog"},
        {"id": "neon-light", "name": "霓虹浅 Neon Light"},
        {"id": "porcelain", "name": "瓷釉 Porcelain"},
        {"id": "cyber-light", "name": "赛博浅 Cyber Light"},
        {"id": "sakura-mist", "name": "樱雾 Sakura Mist"},
        # ===== 第二批 20 套：大厂规范 + 半透明玻璃创意 =====
        {"id": "apple-sonoma", "name": "苹果 Sonoma Light"},
        {"id": "apple-visionos", "name": "苹果 visionOS 玻璃"},
        {"id": "apple-graphite", "name": "苹果石墨 Graphite Dark"},
        {"id": "apple-liquid-glass", "name": "苹果液态玻璃 Liquid Glass"},
        {"id": "fluent-mica", "name": "微软 Fluent Mica"},
        {"id": "fluent-acrylic-dark", "name": "微软 Fluent 亚克力暗"},
        {"id": "midnight-glass", "name": "午夜玻璃 Midnight Glass"},
        {"id": "material3-purple", "name": "Material 3 淡紫"},
        {"id": "material3-dark", "name": "Material 3 暗色"},
        {"id": "ibm-carbon", "name": "IBM Carbon White"},
        {"id": "ibm-carbon-g100", "name": "IBM Carbon Gray 100"},
        {"id": "adobe-spectrum", "name": "Adobe Spectrum"},
        {"id": "atlassian-cloud", "name": "Atlassian Cloud"},
        {"id": "sunset-glass", "name": "暮色玻璃 Sunset Glass"},
        {"id": "shopify-polaris", "name": "Shopify Polaris"},
        {"id": "ant-design", "name": "蚂蚁 Ant Design"},
        {"id": "tdesign-blue", "name": "腾讯 TDesign"},
        {"id": "arco-blue", "name": "字节 Arco Design"},
        {"id": "frosted-aurora", "name": "极光磨砂 Frosted Aurora"},
        {"id": "neumorph-soft", "name": "新拟态 Neumorphism"},
    ],
    "editor": [
        {"id": "github-light", "name": "GitHub Light"},
        {"id": "github-dark", "name": "GitHub Dark"},
        {"id": "monokai", "name": "Monokai"},
        {"id": "one-dark", "name": "One Dark"},
        {"id": "dracula", "name": "Dracula"},
        {"id": "nord", "name": "Nord"},
        {"id": "solarized-light", "name": "Solarized Light"},
        {"id": "solarized-dark", "name": "Solarized Dark"},
        {"id": "material-light", "name": "Material Light"},
        {"id": "material-dark", "name": "Material Dark"},
        {"id": "gruvbox-dark", "name": "Gruvbox Dark"},
        {"id": "gruvbox-light", "name": "Gruvbox Light"},
        {"id": "tokyo-night", "name": "Tokyo Night"},
        {"id": "catppuccin-mocha", "name": "Catppuccin Mocha"},
        {"id": "catppuccin-latte", "name": "Catppuccin Latte"},
        {"id": "ayu-dark", "name": "Ayu Dark"},
        {"id": "ayu-light", "name": "Ayu Light"},
        {"id": "synthwave-84", "name": "Synthwave 84"},
        {"id": "rose-pine", "name": "Rosé Pine"},
        {"id": "atom-one-light", "name": "Atom One Light"},
        {"id": "neon-cyber", "name": "霓虹赛博 Neon Cyber"},
        {"id": "vivid-sunset", "name": "鲜艳日落 Vivid Sunset"},
        {"id": "electric-blue", "name": "电流蓝 Electric Blue"},
        {"id": "lava-flow", "name": "熔岩流 Lava Flow"},
        {"id": "toxic-green", "name": "毒液绿 Toxic Green"},
        {"id": "magenta-burst", "name": "品红爆发 Magenta Burst"},
        {"id": "solar-flare", "name": "太阳耀斑 Solar Flare"},
        {"id": "ice-fire", "name": "冰火 Ice Fire"},
        {"id": "jungle-vivid", "name": "鲜艳丛林 Jungle Vivid"},
        {"id": "crimson-night", "name": "绯红之夜 Crimson Night"},
        {"id": "paper-white", "name": "纯净纸白 Paper White"},
        {"id": "warm-beige", "name": "温暖米色 Warm Beige"},
        {"id": "soft-gray", "name": "柔和灰 Soft Gray"},
        {"id": "milk-tea", "name": "奶茶色 Milk Tea"},
        {"id": "sage-light", "name": "鼠尾草浅绿 Sage Light"},
        {"id": "lavender-mist", "name": "薰衣草雾 Lavender Mist"},
        {"id": "sky-dawn", "name": "晨空 Sky Dawn"},
        {"id": "peach-blossom", "name": "桃花 Peach Blossom"},
        {"id": "porcelain", "name": "青瓷 Porcelain"},
        {"id": "cream-sand", "name": "奶油沙 Cream Sand"},
        # ===== 第二批 20 套：设计师 / 艺术家配色（明暗各 10）=====
        {"id": "rams-braun", "name": "拉姆斯·博朗 Rams Braun"},
        {"id": "bauhaus-primary", "name": "包豪斯三原色 Bauhaus"},
        {"id": "mondrian-grid", "name": "蒙德里安 Mondrian"},
        {"id": "albers-interaction", "name": "阿尔伯斯 Albers"},
        {"id": "paul-rand-ibm", "name": "保罗·兰德 Paul Rand"},
        {"id": "vignelli-subway", "name": "维格奈利地铁 Vignelli"},
        {"id": "wes-anderson-pastel", "name": "韦斯·安德森 Wes Anderson"},
        {"id": "hokusai-wave", "name": "北斋浪 Hokusai"},
        {"id": "monet-water", "name": "莫奈睡莲 Monet"},
        {"id": "pantone-serenity", "name": "潘通静谧蓝 Pantone"},
        {"id": "rothko-crimson", "name": "罗斯科绯红 Rothko"},
        {"id": "van-gogh-starry", "name": "梵高星夜 Van Gogh"},
        {"id": "klimt-gold", "name": "克里姆特金 Klimt"},
        {"id": "panton-pop", "name": "潘顿波普 Panton"},
        {"id": "saul-bass-noir", "name": "索尔·巴斯 Saul Bass"},
        {"id": "glaser-psychedelic", "name": "格拉泽迷幻 Glaser"},
        {"id": "corbusier-concrete", "name": "柯布西耶 Corbusier"},
        {"id": "kandinsky-composition", "name": "康定斯基 Kandinsky"},
        {"id": "yves-klein-ikb", "name": "克莱因蓝 Yves Klein"},
        {"id": "hiroshige-dusk", "name": "广重暮色 Hiroshige"},
    ],
    "preview": [
        {"id": "github", "name": "GitHub"},
        {"id": "notion", "name": "Notion"},
        {"id": "medium", "name": "Medium"},
        {"id": "stack-overflow", "name": "Stack Overflow"},
        {"id": "gitlab", "name": "GitLab"},
        {"id": "vuepress", "name": "VuePress"},
        {"id": "docusaurus", "name": "Docusaurus"},
        {"id": "readthedocs", "name": "ReadTheDocs"},
        {"id": "tufte", "name": "Tufte"},
        {"id": "pandoc", "name": "Pandoc"},
        {"id": "bear", "name": "Bear"},
        {"id": "ghost", "name": "Ghost"},
        {"id": "substack", "name": "Substack"},
        {"id": "wordpress", "name": "WordPress"},
        {"id": "hacker-news", "name": "Hacker News"},
        {"id": "reddit", "name": "Reddit"},
        {"id": "mdn", "name": "MDN"},
        {"id": "apple-docs", "name": "Apple Docs"},
        {"id": "microsoft-docs", "name": "Microsoft Docs"},
        {"id": "stripe", "name": "Stripe"},
        {"id": "tailwind", "name": "Tailwind"},
        {"id": "vercel", "name": "Vercel"},
        {"id": "linear", "name": "Linear"},
        {"id": "obsidian-light", "name": "Obsidian Light"},
        {"id": "solarized-light", "name": "Solarized Light"},
        {"id": "material-light", "name": "Material Light"},
        {"id": "minimal", "name": "Minimal"},
        {"id": "elegant", "name": "Elegant"},
        {"id": "classic", "name": "Classic"},
        {"id": "modern", "name": "Modern"},
        {"id": "neon", "name": "霓虹 Neon"},
        {"id": "sunset", "name": "日落 Sunset"},
        {"id": "ocean", "name": "海洋 Ocean"},
        {"id": "forest", "name": "森林 Forest"},
        {"id": "candy", "name": "糖果 Candy"},
        {"id": "royal", "name": "皇家 Royal"},
        {"id": "cyberpunk", "name": "赛博朋克 Cyberpunk"},
        {"id": "autumn", "name": "秋日 Autumn"},
        {"id": "tropical", "name": "热带 Tropical"},
        {"id": "galaxy", "name": "星河 Galaxy"},
        # ===== 第二批 20 套：知名 Markdown 展示样式复刻 =====
        {"id": "typora-newsprint", "name": "Typora Newsprint 报纸"},
        {"id": "typora-pixyll", "name": "Typora Pixyll"},
        {"id": "typora-whitey", "name": "Typora Whitey 素白"},
        {"id": "typora-vue", "name": "Typora Vue 绿"},
        {"id": "typora-gothic", "name": "Typora Gothic 哥特无衬线"},
        {"id": "typora-night", "name": "Typora Night 夜间"},
        {"id": "typora-academic", "name": "Typora Academic 学术"},
        {"id": "lapis", "name": "Lapis 青金石"},
        {"id": "maize", "name": "Maize 玉米黄"},
        {"id": "orange-heart", "name": "橙心 Orange Heart"},
        {"id": "channing-cyan", "name": "全栈蓝 Channing Cyan"},
        {"id": "purple-mdnice", "name": "兰青紫 Purple"},
        {"id": "juejin-default", "name": "掘金 Juejin"},
        {"id": "zhihu-style", "name": "知乎 Zhihu"},
        {"id": "wechat-green", "name": "公众号绿意 WeChat"},
        {"id": "latex-article", "name": "LaTeX Article 论文"},
        {"id": "nord-preview", "name": "Nord 北欧"},
        {"id": "dracula-preview", "name": "Dracula 德古拉"},
        {"id": "rose-pine-preview", "name": "Rosé Pine 玫瑰松"},
        {"id": "mkdocs-material", "name": "MkDocs Material"},
    ],
}

_IDS = {kind: {t["id"] for t in items} for kind, items in THEMES.items()}


def get_theme_options():
    """返回主题选项列表，供设置窗口下拉渲染。"""
    return THEMES


def _load():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data):
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _migrate_if_needed(data):
    """将旧版单套 theme 迁移到 per-window 格式。"""
    old_theme = data.get("theme")
    if not isinstance(old_theme, dict):
        return data
    # 旧格式：{"window": "...", "editor": "...", "preview": "..."}
    if any(k in old_theme for k in ("window", "editor", "preview")):
        migrated = {}
        for wt in WINDOW_TYPES:
            entry = {}
            for kind in ("window", "editor", "preview"):
                v = old_theme.get(kind)
                entry[kind] = v if (v and v in _IDS[kind]) else DEFAULT_PER_WINDOW[wt][kind]
            migrated[wt] = entry
        # 删除旧字段，写入新字段
        del data["theme"]
        for wt in WINDOW_TYPES:
            data["theme_" + wt] = migrated[wt]
        _save(data)
    return data


def _get_per_window(data):
    """从 data 中提取 per-window 主题 dict，缺失则用默认值。"""
    out = {}
    for wt in WINDOW_TYPES:
        entry = data.get("theme_" + wt)
        if not isinstance(entry, dict):
            entry = DEFAULT_PER_WINDOW[wt]
        validated = {}
        for kind in ("window", "editor", "preview"):
            v = entry.get(kind)
            validated[kind] = v if (v and v in _IDS[kind]) else DEFAULT_PER_WINDOW[wt][kind]
        out[wt] = validated
    return out


def get_theme(window_type=None):
    """返回指定窗口的主题 {window, editor, preview}。
    
    如果 window_type 为 None，返回所有窗口的主题 dict。
    """
    data = _load()
    data = _migrate_if_needed(data)
    per_window = _get_per_window(data)
    if window_type is None:
        return per_window
    return per_window.get(window_type, DEFAULT_PER_WINDOW.get(window_type, DEFAULT_PER_WINDOW["flash"]))


def save_theme(window_type, window_theme=None, editor=None, preview=None):
    """保存指定窗口的主题选择，非法值回退默认。返回 (ok, msg, theme_for_window)。"""
    if window_type not in WINDOW_TYPES:
        window_type = "flash"
    data = _load()
    data = _migrate_if_needed(data)
    key = "theme_" + window_type
    entry = data.get(key)
    if not isinstance(entry, dict):
        entry = dict(DEFAULT_PER_WINDOW.get(window_type, DEFAULT_PER_WINDOW["flash"]))
    for kind, val in (("window", window_theme), ("editor", editor), ("preview", preview)):
        if val is None:
            continue
        val = str(val).strip()
        entry[kind] = val if val in _IDS[kind] else DEFAULT_PER_WINDOW[window_type][kind]
    data[key] = entry
    if not _save(data):
        return False, "主题写入失败", get_theme(window_type)
    return True, "主题已保存", get_theme(window_type)