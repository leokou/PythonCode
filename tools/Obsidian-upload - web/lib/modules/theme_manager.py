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