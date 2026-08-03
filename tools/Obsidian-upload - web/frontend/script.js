/* LeoDiary Capture —— 多标签页 Markdown 编辑器前端逻辑
 * 功能：多标签页管理、实时预览（带行号锚点）、行级双向同步滚动、
 *       图片粘贴上传（PicGo→Cloudflare R2）、按窗口类型保存。
 */
"use strict";

const {
  EditorView, EditorState, keymap, lineNumbers, highlightActiveLine,
  highlightActiveLineGutter, drawSelection, dropCursor, rectangularSelection,
  crosshairCursor, defaultKeymap, history, historyKeymap, indentWithTab,
  markdown, syntaxHighlighting, defaultHighlightStyle, bracketMatching,
  indentOnInput, foldGutter, foldKeymap, highlightSelectionMatches, searchKeymap,
  autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap,
} = window.CodeMirrorBundle;

const editorEl = document.getElementById("editor");
const previewEl = document.getElementById("preview");
const statusEl = document.getElementById("status");
const toastEl = document.getElementById("toast");
const tabsEl = document.getElementById("tabs");
const listEl = document.getElementById("tabs-list");
const addBtnEl = document.getElementById("btn-add-tab");
const dropdownWrapEl = document.getElementById("tab-dropdown");
const dropdownBtnEl = document.getElementById("btn-tab-dropdown");
const dropdownMenuEl = document.getElementById("tab-dropdown-menu");

/* ---- 窗口配置（由后端 js_api.get_config() 注入） ---- */
let CFG = { windowType: "inbox", title: "LeoDiary Capture", saveLabel: "保存", hotkeyHint: "" };

/* ---- 多标签页数据 ---- */
let tabs = [];         // [{id, pageId, title, status, state, editorScroll, previewScroll}]
let activeTabId = null;
let tabSeq = 0;
let _lastFocusArea = "editor";

function currentTab() {
  return tabs.find((t) => t.id === activeTabId) || null;
}

function firstLineTitle(state) {
  return state.doc.line(1).text.trim();
}

function tabTitle(tab) {
  return firstLineTitle(tab.state) || "未命名";
}

/* 当前打开文件 → 资源树自动展开父目录并高亮（编辑/预览/资源树三态一致） */
function syncExplorerWithTab() {
  const tab = currentTab();
  const p = (tab && (tab.extPath || tab.file)) || null;
  if (p && window.Explorer && Explorer.reveal) Explorer.reveal(p);
}

/* ---- Toast / 状态 ---- */
function setStatus(msg) { statusEl.textContent = msg; }

let toastTimer = null;
function toast(msg, kind) {
  toastEl.textContent = msg;
  toastEl.className = "toast show" + (kind ? " " + kind : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.className = "toast hidden"; }, 2800);
}

/* 右下角通知：从右往左推进展示，3 秒后自动滑出 */
const syncToastEl = document.getElementById("sync-toast");
let syncToastTimer = null;
function syncToast(msg, kind) {
  syncToastEl.textContent = msg;
  syncToastEl.className = "sync-toast show" + (kind ? " " + kind : "");
  clearTimeout(syncToastTimer);
  syncToastTimer = setTimeout(() => { syncToastEl.classList.remove("show"); }, 3000);
}

/* ============ Markdown 渲染（带 data-line 行号锚点） ============ */
let _renderDoc = "";
let _renderPos = 0;

/* 根据 token.raw 在原文中的位置推算起始行号（1 起） */
function _lineOf(raw) {
  const idx = _renderDoc.indexOf(raw, _renderPos);
  if (idx >= 0) {
    _renderPos = idx + raw.length;
    return _renderDoc.slice(0, idx).split("\n").length;
  }
  return _renderDoc.slice(0, _renderPos).split("\n").length;
}

marked.use({
  renderer: {
    heading({ tokens, depth, raw }) {
      return `<h${depth} data-line="${_lineOf(raw)}">${this.parser.parseInline(tokens)}</h${depth}>`;
    },
    paragraph({ tokens, raw }) {
      return `<p data-line="${_lineOf(raw)}">${this.parser.parseInline(tokens)}</p>`;
    },
    blockquote({ tokens, raw }) {
      return `<blockquote data-line="${_lineOf(raw)}">${this.parser.parse(tokens)}</blockquote>`;
    },
    code({ text, lang, raw }) {
      const cls = lang ? ` class="language-${lang}"` : "";
      const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
      return `<pre data-line="${_lineOf(raw)}"><code${cls}>${esc}</code></pre>`;
    },
    hr({ raw }) {
      return `<hr data-line="${_lineOf(raw)}">`;
    },
    list({ ordered, start, items, raw }) {
      const tag = ordered ? "ol" : "ul";
      const startAttr = ordered && start !== 1 ? ` start="${start}"` : "";
      let body = "";
      for (const item of items) {
        body += `<li>${this.parser.parse(item.tokens)}</li>`;
      }
      return `<${tag}${startAttr} data-line="${_lineOf(raw)}">${body}</${tag}>`;
    },
    table({ header, rows, raw }) {
      let html = `<table data-line="${_lineOf(raw)}"><thead><tr>`;
      for (const cell of header) html += `<th>${this.parser.parseInline(cell.tokens)}</th>`;
      html += "</tr></thead><tbody>";
      for (const row of rows) {
        html += "<tr>";
        for (const cell of row) html += `<td>${this.parser.parseInline(cell.tokens)}</td>`;
        html += "</tr>";
      }
      html += "</tbody></table>";
      return html;
    },
  },
});

function renderPreview() {
  const tab = currentTab();
  if (!tab) { previewEl.innerHTML = ""; return; }
  _renderDoc = tab.state.doc.toString();
  _renderPos = 0;
  previewEl.innerHTML = marked.parse(_renderDoc, { breaks: true, gfm: true });
  if (window.Outline && Outline.refresh) Outline.refresh();
}

/* ============ 预览区编辑同步：contenteditable → 编辑器 ============ */
let _previewEditing = false;
let _skipPreviewRerender = false;
let _previewSyncTimer = null;

/* 预览区输入事件 → 同步回编辑器（全量文本替换方案） */
previewEl.addEventListener("input", () => {
  if (_previewEditing) return;
  clearTimeout(_previewSyncTimer);
  _previewSyncTimer = setTimeout(_syncPreviewToEditor, 120);
});

/* 核心：用预览区全文本替换编辑器文档 */
function _syncPreviewToEditor() {
  if (_previewEditing) return;
  const tab = currentTab();
  if (!tab) return;

  /* 读取预览区纯文本，统一换行符 */
  const newText = previewEl.innerText.replace(/\r\n/g, "\n");
  const oldText = tab.state.doc.toString();

  if (newText === oldText) return;

  _previewEditing = true;
  _skipPreviewRerender = true;

  /* 全量替换编辑器文档 */
  view.dispatch({
    changes: { from: 0, to: tab.state.doc.length, insert: newText }
  });
  tab.state = view.state;

  /* 恢复焦点 */
  previewEl.focus();

  requestAnimationFrame(() => {
    _skipPreviewRerender = false;
    _previewEditing = false;
  });

  /* 自动保存 */
  if (tab.pageId) {
    Storage.schedule(tab.pageId, newText);
  } else if (tab.extPath) {
    Storage.scheduleExternal(tab.extPath, newText);
  }
}

/* ============ 预览区右键菜单：复制/剪切/粘贴/全选 ============ */
previewEl.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  e.stopPropagation();
  if (!window.ContextMenu) return;
  const sel = window.getSelection();
  const hasSel = sel && !sel.isCollapsed && sel.toString().length > 0;
  const items = [
    { icon: "📋", label: "复制", shortcut: "Ctrl+C", action: "copy", disabled: !hasSel },
    { icon: "✂️", label: "剪切", shortcut: "Ctrl+X", action: "cut", disabled: !hasSel },
    { icon: "📥", label: "粘贴", shortcut: "Ctrl+V", action: "paste" },
    { icon: "✅", label: "全选", shortcut: "Ctrl+A", action: "select_all" },
  ];
  ContextMenu.open(e.clientX, e.clientY, items, (item) => {
    const act = item.action;
    if (act === "copy") previewCopy();
    else if (act === "cut") previewCut();
    else if (act === "paste") previewPaste();
    else if (act === "select_all") previewSelectAll();
  });
});

async function previewCopy() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed) return;
  const text = sel.toString();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    toast("已复制 " + text.length + " 字符", "ok");
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e2) { /* ignore */ }
    ta.remove();
    toast("已复制 " + text.length + " 字符", "ok");
  }
}

async function previewCut() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed) return;
  const text = sel.toString();
  if (!text) return;
  await previewCopy();
  /* 剪切：删除选中文本 */
  const range = sel.getRangeAt(0);
  range.deleteContents();
  _syncPreviewToEditor();
}

async function previewPaste() {
  const sel = window.getSelection();
  if (!sel) return;
  try {
    const text = await navigator.clipboard.readText();
    if (!text) return;
    const range = sel.rangeCount > 0 ? sel.getRangeAt(0) : document.createRange();
    range.deleteContents();
    const textNode = document.createTextNode(text);
    range.insertNode(textNode);
    /* 移动光标到插入文本末尾 */
    range.setStartAfter(textNode);
    range.setEndAfter(textNode);
    sel.removeAllRanges();
    sel.addRange(range);
    _syncPreviewToEditor();
  } catch (e) {
    toast("粘贴失败，请使用 Ctrl+V", "err");
  }
}

function previewSelectAll() {
  const range = document.createRange();
  range.selectNodeContents(previewEl);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}

/* 预览区原生快捷键支持：Ctrl+C/V/X/A */
previewEl.addEventListener("keydown", async (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
  const key = e.key.toLowerCase();
  if (key === "c") {
    /* 原生浏览器复制已可工作，这里做兼容 */
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) {
      try { await navigator.clipboard.writeText(sel.toString()); } catch (e2) { /* ignore */ }
    }
  } else if (key === "x") {
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) {
      e.preventDefault();
      await previewCut();
    }
  } else if (key === "v") {
    e.preventDefault();
    await previewPaste();
  } else if (key === "a") {
    e.preventDefault();
    previewSelectAll();
  }
});

/* ============ CodeMirror 6 编辑器（单 view，多 tab 共享） ============ */
let view;

const editorExtensions = [
  lineNumbers(),
  highlightActiveLineGutter(),
  highlightActiveLine(),
  history(),
  drawSelection(),
  dropCursor(),
  foldGutter(),
  bracketMatching(),
  closeBrackets(),
  autocompletion(),
  rectangularSelection(),
  crosshairCursor(),
  indentOnInput(),
  syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
  highlightSelectionMatches(),
  keymap.of([
    ...closeBracketsKeymap,
    ...defaultKeymap,
    ...searchKeymap,
    ...historyKeymap,
    ...foldKeymap,
    ...completionKeymap,
    indentWithTab,
  ]),
  markdown(),
  EditorView.lineWrapping,
  EditorView.theme({
    "&": {
      backgroundColor: "var(--cm-bg)",
      color: "var(--cm-fg)",
    },
    ".cm-gutters": {
      backgroundColor: "var(--cm-gutter-bg)",
      color: "var(--cm-gutter-fg)",
      borderRight: "1px solid var(--cm-gutter-border)",
    },
    ".cm-activeLine": { backgroundColor: "var(--cm-active-line)" },
    ".cm-activeLineGutter": { backgroundColor: "var(--cm-active-line-gutter)" },
    ".cm-cursor": { borderLeftColor: "var(--cm-cursor)" },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground": {
      backgroundColor: "var(--cm-selection)",
    },
    ".cm-searchMatch": { backgroundColor: "var(--cm-search-match)" },
    ".cm-foldPlaceholder": {
      backgroundColor: "var(--cm-fold-bg)",
      borderColor: "var(--cm-fold-border)",
      color: "var(--cm-fold-fg)",
    },
    ".cm-content": { fontFamily: "var(--cm-font, inherit)" },
  }),
  EditorView.updateListener.of((update) => {
    const tab = currentTab();
    if (tab) {
      tab.state = update.state;
      if (update.docChanged) {
        updateTabName(tab);
        /* 从预览区同步过来的变更，跳过预览重新渲染（避免覆盖用户光标） */
        if (!_skipPreviewRerender) {
          renderPreview();
        }
        /* 自动保存：编辑内容变化 → 5 秒 debounce 后保存到 Tab 文件 */
        if (tab.pageId) {
          Storage.schedule(tab.pageId, update.state.doc.toString());
        } else if (tab.external && tab.extPath) {
          /* 外部文件：直接覆盖原文件 */
          Storage.scheduleExternal(tab.extPath, update.state.doc.toString());
        }
      }
      /* 光标/内容变化 → 目录高亮当前章节 */
      if (update.selectionSet || update.docChanged) {
        if (window.Outline && Outline.highlightAtPos) {
          Outline.highlightAtPos(update.state.selection.main.head);
        }
      }
    }
  }),
];

view = new EditorView({ parent: editorEl, extensions: editorExtensions });

/* ============ 编辑器右键菜单：复制 / 剪切 / 粘贴 / 全选 ============ */
function editorSelText() {
  const sel = view.state.selection.main;
  return sel.empty ? "" : view.state.sliceDoc(sel.from, sel.to);
}

async function editorCopy() {
  const text = editorSelText();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e2) { /* ignore */ }
    ta.remove();
  }
  view.focus();
}

async function editorCut() {
  const sel = view.state.selection.main;
  if (sel.empty) return;
  const text = view.state.sliceDoc(sel.from, sel.to);
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) { /* 剪贴板写入失败也继续剪切 */ }
  view.dispatch({ changes: { from: sel.from, to: sel.to, insert: "" } });
  view.focus();
}

async function editorPaste() {
  const a = (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  if (!a || !a.clipboard_get_text) { toast("粘贴失败：接口不可用", "err"); return; }
  try {
    const res = await a.clipboard_get_text();
    if (res && res.ok) {
      const sel = view.state.selection.main;
      view.dispatch({ changes: { from: sel.from, to: sel.to, insert: res.text } });
      view.focus();
    } else {
      toast((res && res.msg) || "剪贴板没有文本", "err");
    }
  } catch (e) {
    toast("粘贴出错：" + e, "err");
  }
}

function editorSelectAll() {
  view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
  view.focus();
}

/* 光标同步保存：编辑器获焦时，若上次焦点在预览区则立即保存 */
view.dom.addEventListener("focusin", () => {
  if (CFG.windowType !== "capture") return;
  if (_lastFocusArea === "preview") {
    const tab = currentTab();
    if (tab && tab.state.doc.toString().trim()) {
      if (tab.pageId) Storage.saveNow(tab.pageId, tab.state.doc.toString());
      else if (tab.extPath) Storage.saveNowExternal(tab.extPath, tab.state.doc.toString());
    }
  }
  _lastFocusArea = "editor";
});
/* 光标同步保存：单击预览区时，若上次焦点在编辑器则立即保存 */
previewEl.addEventListener("mousedown", () => {
  if (CFG.windowType !== "capture") return;
  if (_lastFocusArea === "editor") {
    const tab = currentTab();
    if (tab && tab.state.doc.toString().trim()) {
      if (tab.pageId) Storage.saveNow(tab.pageId, tab.state.doc.toString());
      else if (tab.extPath) Storage.saveNowExternal(tab.extPath, tab.state.doc.toString());
    }
  }
  _lastFocusArea = "preview";
});
view.dom.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  e.stopPropagation();
  if (!window.ContextMenu) return;
  const hasSel = !view.state.selection.main.empty;
  ContextMenu.open(e.clientX, e.clientY, [
    { icon: "📋", label: "复制", shortcut: "Ctrl+C", action: "copy", disabled: !hasSel },
    { icon: "✂️", label: "剪切", shortcut: "Ctrl+X", action: "cut", disabled: !hasSel },
    { icon: "📥", label: "粘贴", shortcut: "Ctrl+V", action: "paste" },
    { icon: "✅", label: "全选", shortcut: "Ctrl+A", action: "select_all" },
  ], (item) => {
    const act = item.action;
    if (act === "copy") editorCopy();
    else if (act === "cut") editorCut();
    else if (act === "paste") editorPaste();
    else if (act === "select_all") editorSelectAll();
  });
});

/* ============ 搜索面板：帮助按钮 + 选项教程弹窗 ============ */
const SEARCH_HELP_HTML = `
  <div class="search-help-card">
    <div class="search-help-head">搜索选项说明</div>
    <div class="search-help-body">
      <div class="help-item">
        <b>匹配大小写</b>
        <div>搜索时区分字母大小写。</div>
        <div class="help-ex">搜 <code>Apple</code>，勾选后只匹配 <code>Apple</code>，不匹配 <code>apple</code>。</div>
      </div>
      <div class="help-item">
        <b>正则</b>
        <div>使用正则表达式匹配更灵活的模式。</div>
        <div class="help-ex">搜 <code>\\d{4}-\\d{2}-\\d{2}</code> 可匹配 <code>2026-08-02</code> 这类日期。</div>
      </div>
      <div class="help-item">
        <b>整词</b>
        <div>只匹配完整单词，忽略包含该词的更长单词。</div>
        <div class="help-ex">搜 <code>cat</code>，勾选后匹配 <code>a cat</code> 中的 <code>cat</code>，不匹配 <code>category</code> 中的 <code>cat</code>。</div>
      </div>
    </div>
    <button type="button" class="search-help-close" id="search-help-close">知道了</button>
  </div>`;

function showSearchHelp() {
  if (document.getElementById("search-help-overlay")) return;
  const overlay = document.createElement("div");
  overlay.id = "search-help-overlay";
  overlay.className = "search-help-overlay";
  overlay.innerHTML = SEARCH_HELP_HTML;
  document.body.appendChild(overlay);
  overlay.addEventListener("mousedown", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  overlay.querySelector("#search-help-close").addEventListener("click", () => overlay.remove());
}

function injectSearchHelpButton() {
  if (!view || !view.dom) return;
  const panel = view.dom.querySelector(".cm-search");
  if (!panel || panel.querySelector(".cm-search-help")) return;
  const replaceAllBtn = panel.querySelector('button[name="replaceAll"]');
  if (!replaceAllBtn) return;
  const helpBtn = document.createElement("button");
  helpBtn.type = "button";
  helpBtn.className = "cm-button cm-search-help";
  helpBtn.textContent = "?";
  helpBtn.title = "搜索选项说明";
  helpBtn.addEventListener("click", showSearchHelp);
  replaceAllBtn.insertAdjacentElement("afterend", helpBtn);
}

if (view && view.dom) {
  const searchObserver = new MutationObserver(() => injectSearchHelpButton());
  searchObserver.observe(view.dom, { childList: true, subtree: true });
}

/* ============ 行级双向同步滚动 ============ */
let syncing = false;

function findPreviewBlockForLine(line) {
  const blocks = previewEl.querySelectorAll("[data-line]");
  let best = null;
  for (const b of blocks) {
    const l = parseInt(b.getAttribute("data-line"), 10);
    if (l <= line) best = b; else break;
  }
  return best;
}

function scrollPreviewToLine(line) {
  const b = findPreviewBlockForLine(line);
  if (b) {
    previewEl.scrollTop = Math.max(0, b.offsetTop - previewEl.clientHeight * 0.2);
  }
}

function scrollEditorToLine(line) {
  const doc = view.state.doc;
  if (line < 1 || line > doc.lines) return;
  const block = view.lineBlockAt(doc.line(line).from);
  view.scrollDOM.scrollTop = Math.max(0, block.top - 4);
}

view.scrollDOM.addEventListener("scroll", () => {
  if (syncing) return;
  syncing = true;
  const pos = view.lineBlockAtHeight(view.scrollDOM.scrollTop).from;
  const line = view.state.doc.lineAt(pos).number;
  scrollPreviewToLine(line);
  requestAnimationFrame(() => { syncing = false; });
});

previewEl.addEventListener("scroll", () => {
  if (syncing) return;
  syncing = true;
  const blocks = previewEl.querySelectorAll("[data-line]");
  const viewTop = previewEl.scrollTop + 10;
  let target = null;
  for (const b of blocks) {
    if (b.offsetTop >= viewTop) { target = b; break; }
  }
  if (!target && blocks.length) target = blocks[0];
  if (target) {
    const line = parseInt(target.getAttribute("data-line"), 10);
    scrollEditorToLine(line);
  }
  requestAnimationFrame(() => { syncing = false; });
});

/* ============ 图片粘贴上传（PicGo/Cloudflare 链路） ============ */
function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = reject;
    fr.readAsDataURL(blob);
  });
}

function findImageItem(cd) {
  if (cd && cd.items) {
    for (const it of cd.items) {
      if (it.type && it.type.startsWith("image/")) return it;
    }
  }
  if (cd && cd.files && cd.files.length) {
    const f = cd.files[0];
    if (f.type && f.type.startsWith("image/")) return f;
  }
  return null;
}

async function uploadAndInsert(imgItem) {
  setStatus("正在上传图片到 PicGo…");
  try {
    const blob = imgItem.getAsFile ? imgItem.getAsFile() : imgItem;
    const dataUrl = await blobToDataURL(blob);
    const res = await pywebview.api.upload_image(dataUrl);
    if (res.ok) {
      view.focus();
      const insert = res.markdown + "\n";
      const pos = view.state.selection.main.head;
      view.dispatch({
        changes: { from: pos, insert },
        selection: { anchor: pos + insert.length },
      });
      toast("图片已上传：已插入 " + res.url, "ok");
      setStatus("上传成功：" + res.url);
    } else {
      toast("上传失败：" + res.msg, "err");
      setStatus("上传失败");
    }
  } catch (err) {
    toast("上传出错：" + err, "err");
    setStatus("上传出错");
  }
}

/* 捕获阶段统一拦截：焦点在编辑器内/外都能上传图片，文字粘贴放行 */
document.addEventListener("paste", (e) => {
  const imgItem = findImageItem(e.clipboardData);
  if (!imgItem) return;
  e.preventDefault();
  e.stopPropagation();
  uploadAndInsert(imgItem);
}, true);

/* ============ 标签页管理 ============ */
function updateTabName(tab) {
  const el = listEl.querySelector(`.tab[data-id="${tab.id}"]`);
  if (el) TabManager.updateTabName(el, tabTitle(tab));
  scheduleRename(tab);
  requestAnimationFrame(manageOverflow);
}

/* 首行标题变化 → 自动重命名文件（防抖，避免每敲一个字就重命名一次） */
let renameTimers = {};
function scheduleRename(tab) {
  const title = firstLineTitle(tab.state);
  if (!title || !tab.pageId) return;
  if (tab.title === title) return;
  clearTimeout(renameTimers[tab.id]);
  renameTimers[tab.id] = setTimeout(async () => {
    delete renameTimers[tab.id];
    try {
      const res = await Storage.renamePage(tab.pageId, title);
      if (res && res.ok && res.page) {
        tab.title = title;
        tab.file = res.page.file;
        logDebug("页面重命名: " + title);
      }
    } catch (e) { /* ignore */ }
  }, 1200);
}

/* ---- 标签页右键菜单 ---- */
function showTabContextMenu(e, tab) {
  if (!window.ContextMenu) return;
  const idx = tabs.findIndex((t) => t.id === tab.id);
  const isPinned = !!tab.pinned;
  const items = [
    { icon: "✕", label: "关闭", shortcut: "Ctrl+W", action: "close", disabled: isPinned },
    { icon: "🔒", label: isPinned ? "取消锁定" : "锁定", action: "toggle_pin" },
    { icon: "➡️", label: "关闭右侧标签页", action: "close_right", disabled: idx >= tabs.length - 1 },
    { icon: "🔀", label: "关闭其他标签页", action: "close_others", disabled: tabs.length <= 1 },
    { icon: "🗑️", label: "全部关闭", action: "close_all", disabled: tabs.length <= 1, danger: true },
  ];
  ContextMenu.open(e.clientX, e.clientY, items, (item) => {
    const act = item.action;
    if (act === "close") {
      closeTab(tab.id);
    } else if (act === "toggle_pin") {
      togglePinTab(tab.id);
    } else if (act === "close_right") {
      closeTabsRight(tab.id);
    } else if (act === "close_others") {
      closeOtherTabs(tab.id);
    } else if (act === "close_all") {
      closeAllTabs();
    }
  });
}

/* 锁定/解锁标签页 */
function togglePinTab(id) {
  const tab = tabs.find((t) => t.id === id);
  if (!tab) return;
  tab.pinned = !tab.pinned;
  /* 重新排序：锁定页签移到最左侧 */
  sortTabsByPinned();
  if (tab.pinned) {
    toast("已锁定：" + (tab.title || "未命名"), "ok");
  } else {
    toast("已解除锁定", "ok");
  }
  renderTabs();
}

/* 按锁定状态排序：锁定在前，非锁定在后，保持原顺序 */
function sortTabsByPinned() {
  const pinned = tabs.filter((t) => t.pinned);
  const unpinned = tabs.filter((t) => !t.pinned);
  tabs.length = 0;
  tabs.push(...pinned, ...unpinned);
}

/* 关闭右侧所有标签页（关闭即保存，不弹窗） */
function closeTabsRight(id) {
  const idx = tabs.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const toClose = tabs.slice(idx + 1).filter((t) => !t.pinned);
  if (!toClose.length) {
    toast("右侧没有可关闭的标签页", "ok");
    return;
  }
  for (const t of [...toClose]) doCloseTab(t, false);
}

/* 关闭其他标签页（保留当前，关闭即保存） */
function closeOtherTabs(id) {
  const toClose = tabs.filter((t) => t.id !== id && !t.pinned);
  if (!toClose.length) {
    toast("没有可关闭的其他标签页", "ok");
    return;
  }
  for (const t of [...toClose]) doCloseTab(t, false);
}

/* 全部关闭（保留至少一个非锁定页签，关闭即保存） */
function closeAllTabs() {
  const unpinned = tabs.filter((t) => !t.pinned);
  if (unpinned.length <= 1) {
    toast("至少保留一个页签", "err");
    return;
  }
  const toClose = unpinned.slice(0, -1); /* 保留最后一个 */
  for (const t of toClose) doCloseTab(t, false);
}

function renderTabs() {
  TabManager.renderTabs(listEl, addBtnEl, tabs, activeTabId, (action, id) => {
    if (action === "close") {
      closeTab(id);
    } else {
      setActiveTab(id);
    }
  }, showTabContextMenu);
  manageOverflow();
}

/* 新建 Tab：先建内存 tab，再异步创建对应 Markdown 文件 */
function addTab() {
  const state = EditorState.create({ doc: "", extensions: editorExtensions });
  const tab = {
    id: ++tabSeq, pageId: null, title: "", status: "saved",
    state, editorScroll: 0, previewScroll: 0,
  };
  tabs.push(tab);
  setActiveTab(tab.id);
  Storage.createPage("").then((res) => {
    if (res && res.ok && res.page) {
      tab.pageId = res.page.id;
      tab.file = res.page.file;
      syncExplorerWithTab();
      /* 创建期间可能已输入内容：走 debounce 保存，保持灰色直到 5 秒后落盘 */
      const content = tab.state.doc.toString();
      if (content.trim()) {
        Storage.schedule(tab.pageId, content);
        scheduleRename(tab);
      }
    }
  }).catch(() => { /* ignore */ });
}

/* 打开外部文件（Windows 文件关联 / 带参数启动）为一个独立 Tab */
function addExternalTab(file) {
  const state = EditorState.create({ doc: file.content || "", extensions: editorExtensions });
  const tab = {
    id: ++tabSeq, pageId: null, title: file.title || "未命名",
    status: "saved", external: true, extPath: file.path,
    state, editorScroll: 0, previewScroll: 0,
  };
  tabs.push(tab);
  setActiveTab(tab.id);
  logDebug("打开外部文件: " + file.path);
  toast("已打开 " + (file.title || file.path), "ok");
  setStatus("已打开 " + file.path);
  return tab;
}

/* 工作区/搜索打开文件：读取内容 → 新建外部 Tab → 可选定位到指定行 */
async function openWorkspaceFile(path, line) {
  try {
    const res = await pywebview.api.open_history_file(path);
    if (!res || !res.ok) {
      toast("打开失败：" + ((res && res.msg) || "未知错误"), "err");
      return;
    }
    const tab = addExternalTab({ content: res.content, title: res.title, path: res.path });
    if (line && line >= 1) {
      requestAnimationFrame(() => {
        const doc = tab.state.doc;
        const ln = Math.min(line, doc.lines);
        if (ln >= 1) {
          const pos = doc.line(ln).from;
          view.dispatch({ selection: { anchor: pos }, scrollIntoView: true });
          scrollEditorToLine(ln);
          scrollPreviewToLine(ln);
        }
        view.focus();
      });
    }
  } catch (err) {
    toast("打开出错：" + err, "err");
  }
}

/* 从页面元数据恢复一个 Tab（启动恢复用） */
async function restoreTab(page) {
  const content = await Storage.restorePage(page.id)
    .then((r) => (r && r.ok ? r.content : ""))
    .catch(() => "");
  const state = EditorState.create({ doc: content, extensions: editorExtensions });
  return {
    id: ++tabSeq, pageId: page.id, title: page.title || "",
    status: "unsaved", state, editorScroll: 0, previewScroll: 0,
  };
}

function scrollActiveTabIntoView() {
  /* 保证活动页签（及其后的 + 按钮）在横向滚动列表中可见 */
  const el = listEl.querySelector(`.tab[data-id="${activeTabId}"]`);
  if (!el) return;
  const tabRect = el.getBoundingClientRect();
  const listRect = listEl.getBoundingClientRect();
  if (tabRect.left < listRect.left) {
    listEl.scrollLeft += tabRect.left - listRect.left - 4;
  } else if (tabRect.right > listRect.right) {
    listEl.scrollLeft += tabRect.right - listRect.right + 4;
  }
}

function setActiveTab(id) {
  const prev = currentTab();
  if (prev) {
    prev.editorScroll = view.scrollDOM.scrollTop;
    prev.previewScroll = previewEl.scrollTop;
  }
  activeTabId = id;
  const tab = currentTab();
  view.setState(tab.state);
  renderTabs();
  renderPreview();
  _lastFocusArea = "editor"; /* 切换标签不算编辑↔预览切换，跳过光标同步保存 */
  view.focus();
  requestAnimationFrame(() => {
    if (tab.editorScroll) view.scrollDOM.scrollTop = tab.editorScroll;
    if (tab.previewScroll) previewEl.scrollTop = tab.previewScroll;
    scrollActiveTabIntoView();
    syncExplorerWithTab();
  });
}

/* 关闭 Tab：弹确认框（删除=红 / 保存=绿）；锁定页签不允许直接关闭 */
function closeTab(id) {
  const idx = tabs.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const tab = tabs[idx];
  if (tab.pinned) {
    toast("该页签已锁定，请先解锁后再关闭", "err");
    return;
  }
  /* 关闭即保存：直接保存并关闭，不弹窗 */
  doCloseTab(tab, false);
}

async function doCloseTab(tab, deleteFile) {
  /* 关闭即保存：确保内容落盘 */
  if (tab.external && tab.extPath) {
    const content = tab.state.doc.toString();
    await Storage.saveNowExternal(tab.extPath, content).catch(() => {});
    /* 外部文件：不调用 closePage */
  } else if (tab.pageId) {
    const content = tab.state.doc.toString();
    await Storage.saveNow(tab.pageId, content).catch(() => {});
    await Storage.closePage(tab.pageId, false).catch(() => {});
  }
  clearTimeout(renameTimers[tab.id]);
  delete renameTimers[tab.id];
  const idx = tabs.findIndex((t) => t.id === tab.id);
  if (idx < 0) return;
  tabs.splice(idx, 1);
  if (tabs.length === 0) {
    addTab(); /* 至少保留一个页签 */
    return;
  }
  if (activeTabId === tab.id) {
    const next = tabs[Math.min(idx, tabs.length - 1)];
    setActiveTab(next.id);
  } else {
    renderTabs();
  }
}

/* ---- 页签溢出折叠 + 下拉清单 ----
 * 页签过多时：从后往前折叠页签（优先保留当前激活页签），
 * 最后一个页签后显示 ▼ 下拉按钮，点击在按钮下方弹出清单，
 * 清单按页签顺序展示全部被折叠页签，点击任意一项快速切换。
 */
let overflowedIds = [];

function manageOverflow() {
  const gap = 6;
  const addW = addBtnEl.offsetWidth + gap;
  /* 先全部展开再测量（display:none 的 offsetWidth 为 0） */
  listEl.querySelectorAll(".tab").forEach((el) => el.classList.remove("overflowed"));
  const tabsArr = Array.from(listEl.querySelectorAll(".tab"));
  const avail = listEl.clientWidth;

  const calcWidth = (list) =>
    list.reduce((s, el) => s + el.offsetWidth, 0) + gap * list.length + addW;

  if (calcWidth(tabsArr) <= avail) {
    overflowedIds = [];
    setDropdownState(false);
    return;
  }

  let keep = tabsArr.slice();
  const hiddenSet = new Set();
  const rev = tabsArr.slice().reverse();
  const activeId = String(activeTabId);
  /* 从后往前折叠非激活页签，优先保留当前激活页签 */
  for (const el of rev) {
    if (String(el.dataset.id) === activeId) continue;
    if (keep.length <= 1 || calcWidth(keep) <= avail) break;
    keep = keep.filter((x) => x !== el);
    hiddenSet.add(el);
  }
  /* 空间仍不足时再折叠激活页签 */
  for (const el of rev) {
    if (keep.length <= 1 || calcWidth(keep) <= avail) break;
    if (keep.includes(el)) {
      keep = keep.filter((x) => x !== el);
      hiddenSet.add(el);
    }
  }

  listEl.querySelectorAll(".tab").forEach((el) => {
    el.classList.toggle("overflowed", hiddenSet.has(el));
  });
  overflowedIds = tabs
    .filter((t) => hiddenSet.has(listEl.querySelector(`.tab[data-id="${t.id}"]`)))
    .map((t) => t.id);
  setDropdownState(overflowedIds.length > 0);
  if (dropdownMenuEl.classList.contains("open")) renderDropdownMenu();
}

function setDropdownState(show) {
  dropdownWrapEl.classList.toggle("show", show);
  if (!show) closeDropdown();
}

function renderDropdownMenu() {
  dropdownMenuEl.innerHTML = overflowedIds.map((id) => {
    const tab = tabs.find((t) => t.id === id);
    return `<div class="dropdown-item" data-id="${id}">${
      TabManager.escapeHTML(tab ? tab.title : "未命名")}</div>`;
  }).join("");
}

function toggleDropdown() {
  if (dropdownMenuEl.classList.contains("open")) { closeDropdown(); return; }
  renderDropdownMenu();
  dropdownMenuEl.classList.add("open");
}

function closeDropdown() {
  dropdownMenuEl.classList.remove("open");
}

/* 页签点击由 TabManager.renderTabs 内部处理（activate / close） */

/* 鼠标滚轮在页签栏滚动 = 切换上一个/下一个页签（越界时交给横向滚动） */
listEl.addEventListener("wheel", (e) => {
  const idx = tabs.findIndex((t) => t.id === activeTabId);
  if (idx < 0) return;
  const next = e.deltaY > 0 ? idx + 1 : idx - 1;
  if (next >= 0 && next < tabs.length) {
    e.preventDefault();
    setActiveTab(tabs[next].id);
  }
}, { passive: false });

/* "+" 新增页签按钮 */
document.getElementById("btn-add-tab").addEventListener("click", addTab);

dropdownBtnEl.addEventListener("click", (e) => {
  e.stopPropagation();
  if (dropdownMenuEl.classList.contains("open")) { closeDropdown(); return; }
  toggleDropdown();
});

dropdownMenuEl.addEventListener("click", (e) => {
  const item = e.target.closest(".dropdown-item");
  if (!item) return;
  setActiveTab(Number(item.dataset.id));
  closeDropdown();
});

document.addEventListener("click", () => closeDropdown());

/* 窗口尺寸变化时重新折叠 */
if (typeof ResizeObserver !== "undefined") {
  new ResizeObserver(() => manageOverflow()).observe(tabsEl);
}

/* ============ 保存（Tab 文件 + 聚合追加并存） ============ */
const btnSaveEl = document.getElementById("btn-save");
const btnSyncEl = document.getElementById("btn-sync");
function setSyncSpinning(on) { btnSyncEl.classList.toggle("spinning", on); }

/* 历史面板刷新（节流 2 秒，仅历史模式可见时生效） */
let _histRefreshTimer = null;
function refreshHistoryIfVisible() {
  if (!(window.History && window.Layout)) return;
  if (!(Layout.isVisible() && Layout.getMode() === "history")) return;
  if (_histRefreshTimer) return;
  _histRefreshTimer = setTimeout(() => { _histRefreshTimer = null; }, 2000);
  try { History.refresh(); } catch (e) { _histRefreshTimer = null; }
}

async function saveCurrent(hideWindow) {
  const tab = currentTab();
  if (!tab) return;
  const content = tab.state.doc.toString();
  if (!content.trim()) {
    toast("没有内容可保存", "err");
    return;
  }
  setSyncSpinning(!hideWindow);
  setStatus("正在保存…");
  try {
    const res = tab.external && tab.extPath
      ? await pywebview.api.save_external_file(tab.extPath, content)
      : (tab.pageId
          ? await pywebview.api.save_with_page(tab.pageId, content, hideWindow)
          : await pywebview.api.save(content, hideWindow));
    if (res.ok) {
      if (tab.external && tab.extPath) {
        tab.status = "saved";
        const el = listEl.querySelector(`.tab[data-id="${tab.id}"]`);
        if (el) TabManager.setTabStatus(el, "saved");
      } else if (tab.pageId) {
        tab.status = "saved";
        const el = listEl.querySelector(`.tab[data-id="${tab.id}"]`);
        if (el) TabManager.setTabStatus(el, "saved");
      }
      setStatus(res.msg);
      syncToast("同步成功：" + res.msg, "ok");
      refreshHistoryIfVisible();
      /* 普通窗口（非 Capture）保存/同步后关闭标签，保留 pages.json 记录以便下次恢复 */
      if (CFG.windowType !== "capture" && !tab.external && tab.pageId) {
        clearTimeout(renameTimers[tab.id]);
        delete renameTimers[tab.id];
        const idx = tabs.findIndex((t) => t.id === tab.id);
        if (idx >= 0) {
          tabs.splice(idx, 1);
          if (tabs.length === 0) {
            addTab();
          } else {
            const next = tabs[Math.min(idx, tabs.length - 1)];
            setActiveTab(next.id);
          }
        }
        return;
      }
    } else {
      toast("保存失败：" + res.msg, "err");
      setStatus("保存失败");
    }
  } catch (err) {
    toast("保存出错：" + err, "err");
    setStatus("保存出错");
  } finally {
    setSyncSpinning(false);
  }
}

document.getElementById("btn-save").addEventListener("click", () => saveCurrent(true));
document.getElementById("btn-sync").addEventListener("click", () => saveCurrent(false));

document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    saveCurrent(true);
  }
  /* Ctrl+W：关闭当前页签 */
  if (e.key === "w" && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
    /* 检查焦点是否在输入框内（搜索框等），避免误关 */
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || e.target && e.target.isContentEditable) {
      /* 允许在输入框内正常输入 Ctrl+W（删除前一个单词） */
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      /* contenteditable 在预览区外也要关闭 */
    }
    e.preventDefault();
    closeTab(activeTabId);
  }
});

/* Ctrl+H：工作区全量搜索（捕获阶段，避免被编辑器键位吞掉） */
document.addEventListener("keydown", (e) => {
  if (e.key === "h" && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
    e.preventDefault();
    e.stopPropagation();
    if (window.Workspace && Workspace.showSearch) Workspace.showSearch();
  }
}, true);

/* ============ 工具箱：打开窗口 + 工具执行入口 ============ */
document.getElementById("btn-tools").addEventListener("click", () => {
  if (typeof pywebview !== "undefined" && pywebview.api) {
    pywebview.api.open_tools();
  }
});

/* ============ 设置窗口 ============ */
document.getElementById("btn-settings").addEventListener("click", () => {
  if (typeof pywebview !== "undefined" && pywebview.api) {
    pywebview.api.open_settings();
  }
});

/* 删除空行工具：删除所有空行（含空白行），尽量保持光标 */
function cleanEmptyLines() {
  const tab = currentTab();
  if (!tab) return;
  const doc = tab.state.doc.toString();
  const cleaned = doc.split(/\r?\n/).filter((l) => l.trim() !== "").join("\n");
  if (cleaned === doc) {
    toast("没有空行可清理", "ok");
    return;
  }
  const head = view.state.selection.main.head;
  const before = doc.slice(0, head);
  const newHead = before.split(/\r?\n/).filter((l) => l.trim() !== "").join("\n").length;
  view.dispatch({
    changes: { from: 0, to: doc.length, insert: cleaned },
    selection: { anchor: Math.min(newHead, cleaned.length) },
  });
  toast("已删除全部空行", "ok");
}

/* Python 端（ToolApi.run_tool）通过 evaluate_js 调用的统一入口 */
window.__runTool = function (toolId) {
  if (toolId === "clean_empty_lines") {
    view.focus();
    cleanEmptyLines();
  } else if (toolId === "editor_find") {
    view.focus();
    const findCmd = (searchKeymap || []).find((k) => k.key === "Mod-f");
    if (findCmd && typeof findCmd.run === "function") {
      findCmd.run(view);
    } else {
      toast("查找面板不可用", "err");
    }
  } else if (toolId === "editor_scroll_top") {
    view.focus();
    view.scrollDOM.scrollTop = 0;
  } else if (toolId === "editor_scroll_bottom") {
    view.focus();
    view.scrollDOM.scrollTop = view.scrollDOM.scrollHeight;
  } else if (toolId === "canvas") {
    if (typeof pywebview !== "undefined" && pywebview.api) {
      pywebview.api.open_canvas().catch(() => {});
    }
  }
};

/* ============ 自定义功能区：保存按钮左侧的快捷小工具 ============ */
(function pinToolbar() {
  let inner = null;
  let tools = [];
  let suppressClick = false;

  function iconHTML(tool) {
    const icon = tool.icon || "🛠️";
    const isPath = /[\\/]/.test(icon) || /\.(png|jpe?g|gif|svg|webp|ico)$/i.test(icon);
    if (isPath) return `<img src="${icon}" alt="">`;
    return icon;
  }

  function render() {
    if (!inner) inner = document.getElementById("pin-toolbar-inner");
    if (!inner) return;
    inner.innerHTML = "";
    if (!tools.length) {
      const el = document.createElement("span");
      el.className = "pin-tool-empty";
      el.textContent = "工具箱勾选工具后显示于此";
      inner.appendChild(el);
      return;
    }
    for (const t of tools) {
      const btn = document.createElement("button");
      btn.className = "pin-tool";
      btn.dataset.id = t.id;
      btn.draggable = true;
      btn.title = (t.name || t.id) + (t.desc ? "：" + t.desc : "");
      btn.innerHTML = iconHTML(t);
      btn.addEventListener("click", () => {
        if (suppressClick) return;
        window.__runTool && window.__runTool(t.id);
      });
      inner.appendChild(btn);
    }
  }

  async function load() {
    try {
      if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.get_pinned_tools) return;
      tools = (await pywebview.api.get_pinned_tools()) || [];
    } catch (e) {
      tools = [];
    }
    render();
  }
  function getDragAfterElement(x, y) {
    const items = [...inner.querySelectorAll(".pin-tool:not(.dragging)")];
    let closest = null;
    let closestOffset = Number.NEGATIVE_INFINITY;
    for (const item of items) {
      const box = item.getBoundingClientRect();
      const cx = box.left + box.width / 2;
      const cy = box.top + box.height / 2;
      const offset = Math.abs(x - cx) + Math.abs(y - cy) * 2;
      if (offset < closestOffset || closest === null) {
        closestOffset = offset;
        closest = item;
      }
    }
    return closest;
  }

  function initDrag() {
    if (!inner) inner = document.getElementById("pin-toolbar-inner");
    if (!inner) return;
    inner.addEventListener("dragstart", (e) => {
      const el = e.target.closest(".pin-tool");
      if (!el) return;
      el.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", el.dataset.id);
    });
    inner.addEventListener("dragover", (e) => {
      e.preventDefault();
      const dragging = inner.querySelector(".pin-tool.dragging");
      if (!dragging) return;
      const target = getDragAfterElement(e.clientX, e.clientY);
      if (target) inner.insertBefore(dragging, target);
    });
    inner.addEventListener("drop", (e) => {
      e.preventDefault();
    });
    inner.addEventListener("dragend", (e) => {
      const el = e.target.closest(".pin-tool");
      if (el) el.classList.remove("dragging");
      suppressClick = true;
      setTimeout(() => { suppressClick = false; }, 150);
      const order = [...inner.querySelectorAll(".pin-tool")].map((el) => el.dataset.id);
      if (order.length && typeof pywebview !== "undefined" && pywebview.api && pywebview.api.save_pinned_order) {
        pywebview.api.save_pinned_order(order).catch(() => {});
      }
    });
  }

  /* 工具箱勾选变化后由后端调用刷新 */
  window.__reloadPinToolbar = load;

  initDrag();

  /* 等待 pywebview 就绪后再加载（脚本在页面加载时解析，api 可能尚未注入） */
  function start() {
    if (typeof pywebview !== "undefined" && pywebview.api && pywebview.api.get_pinned_tools) {
      load();
    } else if (window.addEventListener) {
      window.addEventListener("pywebviewready", start, { once: true });
      setTimeout(start, 800);
    }
  }
  start();
})();

/* 从历史列表重新打开文件：读取内容 → 新建外部 Tab（恢复编辑状态 + 预览同步） */
async function openHistoryFile(path) {
  try {
    const res = await pywebview.api.open_history_file(path);
    if (res && res.ok) {
      addExternalTab({ content: res.content, title: res.title, path: res.path });
    } else {
      toast("打开失败：" + ((res && res.msg) || "未知错误"), "err");
    }
  } catch (err) {
    toast("打开出错：" + err, "err");
  }
}

/* 退出前强制保存所有 Tab 内容（Python 端退出时调用） */
window.__flushAll = function () {
  const items = [];
  for (const t of tabs) {
    if (t.external && t.extPath) {
      items.push({ ext_path: t.extPath, content: t.state.doc.toString() });
    } else if (t.pageId) {
      items.push({ page_id: t.pageId, content: t.state.doc.toString() });
    }
  }
  return JSON.stringify(items);
};

/* 等待 pywebview JS 桥接就绪（api 注入晚于页面脚本执行，需轮询等待） */
function waitForApi(timeoutMs) {
  return new Promise((resolve, reject) => {
    if (typeof pywebview !== "undefined" && pywebview.api) { resolve(); return; }
    const t0 = Date.now();
    const limit = timeoutMs || 5000;
    const iv = setInterval(() => {
      if (typeof pywebview !== "undefined" && pywebview.api) {
        clearInterval(iv);
        resolve();
      } else if (Date.now() - t0 > limit) {
        clearInterval(iv);
        reject(new Error("pywebview api 初始化超时"));
      }
    }, 100);
  });
}

function logDebug(msg) {
  try {
    if (typeof pywebview !== "undefined" && pywebview.api) {
      pywebview.api.log_debug && pywebview.api.log_debug(msg);
    }
  } catch (e) { /* ignore */ }
}

/* ---- 启动加载：直接读取已保存页面（不弹窗），无页面则新建 ---- */
async function handleStartupRestore() {
  let pages = [];
  try {
    const res = await Storage.getPages();
    if (res && res.ok) pages = res.pages || [];
  } catch (e) { /* ignore */ }

  if (!pages.length) {
    addTab();
    return;
  }
  /* 直接恢复全部已保存页面 */
  for (const p of pages) {
    const tab = await restoreTab(p);
    tabs.push(tab);
  }
  if (tabs.length) setActiveTab(tabs[0].id);
}

/* ============ 初始化 ============ */
(async function init() {
  try {
    await waitForApi();
    CFG = await pywebview.api.get_config();
  } catch (err) {
    /* 非 WebView2 环境（如浏览器直开）时使用默认配置 */
  }
  /* FlashNote / Inbox / 日志 页签状态统一灰色 */
  if (CFG.windowType === "flash" || CFG.windowType === "inbox" || CFG.windowType === "log") {
    TabManager.setAlwaysGray(true);
  }
  /* Capture 窗口：隐藏保存/同步按钮 */
  if (CFG.windowType === "capture") {
    const saveActions = document.querySelector(".save-actions");
    if (saveActions) saveActions.style.display = "none";
  }
  document.getElementById("win-title").textContent = CFG.title;
  document.getElementById("brand-name").textContent = CFG.title;
  setStatus("就绪 · PicGo 图床");

  /* 三栏布局：应用记忆的宽度比例与目录可见性 */
  if (window.Layout && Layout.init) Layout.init(CFG.layout);

  /* 目录：解析当前文档标题，点击跳转编辑器+预览，光标移动高亮当前章节 */
  if (window.Outline && Outline.init) {
    Outline.bind({
      getText: () => { const t = currentTab(); return t ? t.state.doc.toString() : ""; },
      lineFromPos: (pos) => view.state.doc.lineAt(pos).number,
      scrollToLine: (line) => { scrollEditorToLine(line); scrollPreviewToLine(line); },
    });
    Outline.init(document.getElementById("outline-body"));
  }

  /* 历史记录面板：列表渲染 / 搜索 / 点击重新打开 */
  if (window.History && History.init) {
    History.init({
      api: () => pywebview.api,
      onOpen: (path) => openHistoryFile(path),
    });
  }

  /* 拖拽调整三栏宽度 */
  if (window.Resize && Resize.init) Resize.init();

  /* 工作区资源管理器：文件夹树 + Ctrl+H 全局搜索 */
  if (window.Workspace && Workspace.init) Workspace.init();
  if (window.Search && Search.init) Search.init();
  if (window.Workspace && Workspace.start) await Workspace.start();

  /* 自动保存状态回调：更新 Tab 状态徽标（key = pageId 或外部文件路径） */
  Storage.setStatusCallback((key, status) => {
    const tab = tabs.find((t) => t.pageId === key || t.extPath === key);
    if (!tab) return;
    tab.status = status;
    const el = listEl.querySelector(`.tab[data-id="${tab.id}"]`);
    if (el) TabManager.setTabStatus(el, status);
    if (status === "saved") refreshHistoryIfVisible();
  });
  Storage.setGetAllTabs(() =>
    tabs.map((t) => t.external && t.extPath
      ? { extPath: t.extPath, content: t.state.doc.toString() }
      : { pageId: t.pageId, content: t.state.doc.toString() })
  );

  await handleStartupRestore();
  Storage.startInsurance();

  /* 文件关联：前端轮询拉取 pending 文件并打开为 Tab。
   * 后端 _pending_file_watcher 只负责检测到文件时显示 capture 窗口，
   * 前端定时调用 get_pending_files 消费队列（take 清空），避免 evaluate_js
   * 后台线程不返回值导致的注入失败。窗口隐藏时浏览器节流定时器，窗口显示后立即恢复。
   */
  async function pollPendingFiles() {
    try {
      const res = await pywebview.api.get_pending_files();
      if (res && res.ok && res.files && res.files.length) {
        for (const f of res.files) addExternalTab(f);
      }
    } catch (e) { /* ignore */ }
  }
  window.pollPendingFilesNow = pollPendingFiles; /* 暴露给后端 shown 事件触发即时轮询 */
  pollPendingFiles();                  /* 启动时立即检查一次（覆盖启动参数带来的文件） */
  setInterval(pollPendingFiles, 2000); /* 每 2 秒轮询一次 */

  /* 窗口从隐藏变为可见时立即触发一次轮询（解决浏览器节流定时器导致文件延迟打开） */
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) pollPendingFiles();
  });
})();
