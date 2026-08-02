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
  EditorView.updateListener.of((update) => {
    const tab = currentTab();
    if (tab) {
      tab.state = update.state;
      if (update.docChanged) {
        updateTabName(tab);
        renderPreview();
        /* 自动保存：编辑内容变化 → 2 秒 debounce 后保存到 Tab 文件 */
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

function renderTabs() {
  TabManager.renderTabs(listEl, addBtnEl, tabs, activeTabId, (action, id) => {
    if (action === "close") {
      closeTab(id);
    } else {
      setActiveTab(id);
    }
  });
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
      /* 创建期间可能已输入内容：立即补存一次 */
      const content = tab.state.doc.toString();
      if (content.trim()) {
        Storage.saveNow(tab.pageId, content).catch(() => {});
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
    status: "saved", state, editorScroll: 0, previewScroll: 0,
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
  view.focus();
  requestAnimationFrame(() => {
    if (tab.editorScroll) view.scrollDOM.scrollTop = tab.editorScroll;
    if (tab.previewScroll) previewEl.scrollTop = tab.previewScroll;
    scrollActiveTabIntoView();
    syncExplorerWithTab();
  });
}

/* 关闭 Tab：弹确认框（删除=红 / 保存=绿） */
function closeTab(id) {
  const idx = tabs.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const tab = tabs[idx];
  if (tab.external && tab.extPath) {
    /* 外部文件：不弹删除确认（避免误删原文件），先保存再直接关闭 */
    doCloseTab(tab, false);
    return;
  }
  TabManager.confirmClose(tabTitle(tab), () => {
    /* 删除：删除当前 Tab 对应文件（二次确认），再关闭 */
    TabManager.confirmDelete(() => doCloseTab(tab, true));
  }, () => {
    /* 保存：先保存文件，再关闭 Tab */
    doCloseTab(tab, false);
  });
}

async function doCloseTab(tab, deleteFile) {
  if (tab.external && tab.extPath) {
    /* 外部文件：关闭前确保内容已覆盖原文件 */
    const content = tab.state.doc.toString();
    await Storage.saveNowExternal(tab.extPath, content).catch(() => {});
  } else if (tab.pageId) {
    if (!deleteFile) {
      /* 保存模式：确保内容已落盘 */
      const content = tab.state.doc.toString();
      await Storage.saveNow(tab.pageId, content).catch(() => {});
    }
    await Storage.closePage(tab.pageId, deleteFile).catch(() => {});
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
  }
};

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
  });
  Storage.setGetAllTabs(() =>
    tabs.map((t) => t.external && t.extPath
      ? { extPath: t.extPath, content: t.state.doc.toString() }
      : { pageId: t.pageId, content: t.state.doc.toString() })
  );

  await handleStartupRestore();
  Storage.startInsurance();

  /* 文件关联：轮询待打开外部文件（新进程带文件参数启动时传递进来）。
   * 仅 FlashNote 主窗口消费（get_pending_files 后端已限定）。 */
  const pollExternalFiles = async () => {
    try {
      const res = await pywebview.api.get_pending_files();
      if (res && res.ok && res.files && res.files.length) {
        for (const f of res.files) addExternalTab(f);
      }
    } catch (e) { /* ignore */ }
  };
  pollExternalFiles();
  setInterval(pollExternalFiles, 2000);
})();
