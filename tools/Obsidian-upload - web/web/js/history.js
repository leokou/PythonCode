/* LeoDiary Capture —— 历史记录面板
 * 职责：按时间分组渲染最近编辑文件（今天/昨天/前天/日期）、文件名模糊搜索、点击重新打开。
 * 依赖：外部通过 init() 注入 api（取 pywebview.api）与 onOpen（点击条目回调）。
 * 纯 UI + 调用后端 history 接口，不直接操作编辑器。
 */
"use strict";

window.History = (() => {
  let listEl = null;
  let inputEl = null;
  let apiFn = null;       // () -> pywebview.api
  let onOpen = null;      // (path) -> void
  let items = [];
  let keyword = "";
  let searchTimer = null;

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function parseTs(s) {
    const v = String(s || "").trim();
    if (!v) return null;
    const d = new Date(v.replace(" ", "T"));
    return isNaN(d.getTime()) ? null : d;
  }

  function startOfDay(d) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  }

  /* 分组标题：今天 / 昨天 / 前天 / 具体日期（如 2026年8月22日） */
  function groupLabel(d) {
    const todayStart = startOfDay(new Date());
    const diff = Math.round((todayStart - startOfDay(d)) / 86400000);
    if (diff <= 0) return "今天";
    if (diff === 1) return "昨天";
    if (diff === 2) return "前天";
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
  }

  /* 按最后编辑时间倒序，再按天分组 */
  function groupItems(list) {
    const sorted = list.slice().sort((a, b) =>
      String(b.last_edited || "").localeCompare(String(a.last_edited || "")));
    const groups = [];
    for (const it of sorted) {
      const d = parseTs(it.last_edited);
      const label = d ? groupLabel(d) : "其他";
      const g = groups[groups.length - 1];
      if (!g || g.label !== label) groups.push({ label, items: [] });
      groups[groups.length - 1].items.push(it);
    }
    return groups;
  }

  function itemHtml(it) {
    const type = it.type || "";
    return (
      `<div class="history-item" data-path="${esc(it.path)}" title="${esc(it.path)}">` +
      `<div class="history-name">${esc(it.name)}` +
      (type ? `<span class="history-type">${esc(type)}</span>` : "") +
      `</div>` +
      `</div>`);
  }

  function render() {
    if (!listEl) return;
    if (!items.length) {
      listEl.innerHTML =
        `<div class="history-empty">${keyword ? "没有匹配的历史记录" : "暂无历史记录"}</div>`;
      return;
    }
    let html = "";
    for (const g of groupItems(items)) {
      html += `<div class="history-group">` +
        `<div class="history-group-title">${esc(g.label)}</div>`;
      for (const it of g.items) html += itemHtml(it);
      html += `</div>`;
    }
    listEl.innerHTML = html;
  }

  /* 加载历史：有搜索词走后端模糊搜索，否则取最近记录 */
  async function load() {
    const a = apiFn && apiFn();
    if (!a) return;
    try {
      const res = keyword
        ? await a.search_history(keyword, 100)
        : await a.get_history(100);
      items = (res && res.ok && res.items) || [];
    } catch (e) {
      items = [];
    }
    render();
  }

  function bindEvents() {
    listEl.addEventListener("click", (e) => {
      const item = e.target.closest(".history-item");
      if (!item) return;
      const path = item.dataset.path;
      if (path && onOpen) onOpen(path);
    });
    inputEl.addEventListener("input", () => {
      keyword = inputEl.value.trim();
      clearTimeout(searchTimer);
      searchTimer = setTimeout(load, 200);
    });
  }

  function refresh() {
    load();
  }

  function init(hooks) {
    listEl = document.getElementById("history-list");
    inputEl = document.getElementById("history-search-input");
    if (!listEl || !inputEl) return;
    apiFn = (hooks && hooks.api) || null;
    onOpen = (hooks && hooks.onOpen) || null;
    bindEvents();
    load();
  }

  return { init, refresh };
})();
