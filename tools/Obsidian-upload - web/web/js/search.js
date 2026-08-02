/* LeoDiary Capture —— 工作区全局搜索
 * 职责：资源管理器顶部搜索框 → 后端 search_workspace 全量搜索 → 结果渲染。
 * 搜索条件设置（⚙️ 按钮）：匹配大小写 / 正则 / 整词 / 折叠搜索结果，localStorage 持久化。
 * 点击结果：打开文件并定位到命中行（line_no=0 表示文件名命中）。
 * 空关键字 / Esc：恢复文件树。
 */
"use strict";

const Search = (() => {
  const STORE_KEY = "leodiary.search.options";
  let input = null;
  let treeEl = null;
  let debounceTimer = null;
  const opts = { matchCase: false, regex: false, wholeWord: false, collapse: true };

  function api() {
    return (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  }

  function debounce(fn, ms) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, ms);
  }

  function loadOptions() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (saved && typeof saved === "object") Object.assign(opts, saved);
      }
    } catch (e) { /* 忽略存储异常 */ }
  }

  function saveOptions() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(opts));
    } catch (e) { /* 忽略存储异常 */ }
  }

  function bindOption(el, key) {
    el.checked = !!opts[key];
    el.addEventListener("change", () => {
      opts[key] = el.checked;
      saveOptions();
      if (input && input.value.trim()) run(input.value);
    });
  }

  /* ---- 折叠渲染：同一文件多条命中合并为一个条目 ---- */
  function buildFileGroup(fileHits) {
    const first = fileHits[0];
    const container = document.createElement("div");
    container.className = "search-hit collapsed-file";

    const top = document.createElement("div");
    top.className = "search-hit-head";
    const toggle = document.createElement("span");
    toggle.className = "collapse-toggle";
    toggle.textContent = "▶";
    const nameEl = document.createElement("span");
    nameEl.className = "search-hit-name";
    nameEl.textContent = first.name;
    const badge = document.createElement("span");
    badge.className = "search-hit-badge";
    badge.textContent = fileHits.length + " 处";
    top.appendChild(toggle);
    top.appendChild(nameEl);
    top.appendChild(badge);
    container.appendChild(top);

    const sub = document.createElement("div");
    sub.className = "search-hit-sub";
    sub.style.display = "none";
    for (const it of fileHits) {
      const row = document.createElement("div");
      row.className = "search-hit";
      const innerTop = document.createElement("div");
      innerTop.className = "search-hit-head";
      const n = document.createElement("span");
      n.className = "search-hit-name";
      n.textContent = it.kind === "filename" ? "(文件名命中)" : "第 " + it.line_no + " 行";
      innerTop.appendChild(n);
      row.appendChild(innerTop);
      if (it.kind === "content" && it.line) {
        const lineEl = document.createElement("div");
        lineEl.className = "search-hit-line";
        lineEl.textContent = it.line.trim() || "(空行)";
        row.appendChild(lineEl);
      }
      row.addEventListener("click", () => {
        if (window.openWorkspaceFile) window.openWorkspaceFile(it.path, it.line_no);
      });
      sub.appendChild(row);
    }
    container.appendChild(sub);

    container.addEventListener("click", () => {
      const open = sub.style.display !== "none";
      sub.style.display = open ? "none" : "block";
      toggle.textContent = open ? "▶" : "▼";
    });
    return container;
  }

  function renderResult(item) {
    const row = document.createElement("div");
    row.className = "search-hit";
    row.title = item.path;

    const top = document.createElement("div");
    top.className = "search-hit-head";
    const nameEl = document.createElement("span");
    nameEl.className = "search-hit-name";
    nameEl.textContent = item.name;
    top.appendChild(nameEl);
    const badge = document.createElement("span");
    badge.className = "search-hit-badge";
    if (item.kind === "filename") {
      badge.textContent = "文件名";
    } else {
      badge.textContent = "第 " + item.line_no + " 行";
    }
    top.appendChild(badge);
    row.appendChild(top);

    if (item.kind === "content" && item.line) {
      const lineEl = document.createElement("div");
      lineEl.className = "search-hit-line";
      lineEl.textContent = item.line.trim() || "(空行)";
      row.appendChild(lineEl);
    }

    row.addEventListener("click", () => {
      if (window.openWorkspaceFile) window.openWorkspaceFile(item.path, item.line_no);
    });
    return row;
  }

  function renderEmpty(msg) {
    treeEl.innerHTML = "";
    const el = document.createElement("div");
    el.className = "tree-empty";
    el.textContent = msg;
    treeEl.appendChild(el);
  }

  function extOf(path) {
    const m = /\.([^.\\/]+)$/.exec(String(path || ""));
    return m ? m[1].toLowerCase() : "?";
  }

  /* 按扩展名分组渲染：防止 .md 命中太多把其他类型淹没 */
  function renderGrouped(hits) {
    const groups = new Map();
    for (const it of hits) {
      const ext = extOf(it.path);
      if (!groups.has(ext)) groups.set(ext, []);
      groups.get(ext).push(it);
    }
    const extOrder = [...groups.keys()].sort((a, b) => groups.get(b).length - groups.get(a).length);
    const frag = document.createDocumentFragment();
    const title = document.createElement("div");
    title.className = "search-hit-title";
    title.textContent = "「" + (input ? input.value : "") + "」共 " + hits.length + " 处";
    frag.appendChild(title);
    for (const ext of extOrder) {
      const list = groups.get(ext);
      const hdr = document.createElement("div");
      hdr.className = "search-hit-group";
      hdr.textContent = "." + ext + "（" + list.length + " 处）";
      frag.appendChild(hdr);
      if (opts.collapse) {
        /* 折叠模式：按文件合并 */
        const byFile = new Map();
        for (const it of list) {
          if (!byFile.has(it.path)) byFile.set(it.path, []);
          byFile.get(it.path).push(it);
        }
        for (const fileHits of byFile.values()) frag.appendChild(buildFileGroup(fileHits));
      } else {
        for (const it of list) frag.appendChild(renderResult(it));
      }
    }
    return frag;
  }

  async function run(keyword) {
    const a = api();
    const kw = (keyword || "").trim();
    if (!kw) {
      if (window.Workspace && Workspace.clearSearch) Workspace.clearSearch();
      return;
    }
    if (!a || !a.search_workspace) return;
    try {
      const res = await a.search_workspace(kw, 500, opts.matchCase, opts.regex, opts.wholeWord);
      if (!res || !res.ok) {
        renderEmpty((res && res.msg) || "搜索失败");
        return;
      }
      const hits = res.results || [];
      if (!hits.length) {
        renderEmpty("未找到匹配「" + kw + "」");
        return;
      }
      treeEl.innerHTML = "";
      treeEl.appendChild(renderGrouped(hits));
    } catch (e) {
      renderEmpty("搜索出错：" + e);
    }
  }

  function initOptionsPanel() {
    const btn = document.getElementById("btn-search-options");
    const panel = document.getElementById("search-options-panel");
    if (!btn || !panel) return;
    loadOptions();
    bindOption(document.getElementById("opt-match-case"), "matchCase");
    bindOption(document.getElementById("opt-regex"), "regex");
    bindOption(document.getElementById("opt-whole-word"), "wholeWord");
    bindOption(document.getElementById("opt-collapse"), "collapse");
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = panel.classList.toggle("open");
      btn.classList.toggle("active", open);
    });
    document.addEventListener("mousedown", (e) => {
      if (!panel.classList.contains("open")) return;
      if (panel.contains(e.target) || btn.contains(e.target)) return;
      panel.classList.remove("open");
      btn.classList.remove("active");
    });
  }

  function init() {
    input = document.getElementById("workspace-search-input");
    treeEl = document.getElementById("workspace-tree");
    if (!input || !treeEl) return;
    initOptionsPanel();

    input.addEventListener("input", () => {
      debounce(() => run(input.value), 300);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        clearTimeout(debounceTimer);
        run(input.value);
      } else if (e.key === "Escape") {
        e.preventDefault();
        input.value = "";
        run("");
      }
    });
  }

  return { init, run };
})();

window.Search = Search;
