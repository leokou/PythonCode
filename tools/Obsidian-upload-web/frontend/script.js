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
  ViewPlugin, Decoration, HighlightStyle, tags,
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

/* 按窗口类型调度保存：Capture 窗口立即保存，其他窗口 debounce 后保存 */
function scheduleOrSave(pageId, content) {
  if (CFG.windowType === "capture") {
    Storage.saveNow(pageId, content);
  } else {
    Storage.schedule(pageId, content);
  }
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
  /* 嵌套块（如 li 内的 p / blockquote / code）的 raw 在 _renderPos 之后不可见，
   * 返回 0 表示无法定位行号，由调用方跳过 data-line 属性 */
  return 0;
}

/* 从列表原始文本中提取每个 <li> 的起始行号（1 起），返回长度 = count 的数组。
 * 扫描 raw 逐行识别列表标记（- / * / + / 数字.），按出现顺序分配行号。 */
function _findListItemLines(raw, count) {
  const lines = raw.split("\n");
  const result = [];
  const baseLine = _renderDoc.slice(0, _renderDoc.indexOf(raw, _renderPos) >= 0
    ? _renderDoc.indexOf(raw, _renderPos) : _renderPos).split("\n").length;
  for (let i = 0; i < lines.length && result.length < count; i++) {
    const t = lines[i].trimStart();
    if (/^[-*+]\s/.test(t) || /^\d+\.\s/.test(t)) {
      result.push(baseLine + i);
    }
  }
  /* 补齐：若 raw 解析出的标记行不足 items 数量（如多行 item），用最后一个行号兜底 */
  while (result.length < count) result.push(result.length ? result[result.length - 1] + 1 : baseLine);
  return result;
}

marked.use({
  renderer: {
    heading({ tokens, depth, raw }) {
      return `<h${depth} data-line="${_lineOf(raw)}">${this.parser.parseInline(tokens)}</h${depth}>`;
    },
    paragraph({ tokens, raw }) {
      const line = _lineOf(raw);
      return line > 0
        ? `<p data-line="${line}">${this.parser.parseInline(tokens)}</p>`
        : `<p>${this.parser.parseInline(tokens)}</p>`;
    },
    blockquote({ tokens, raw }) {
      const line = _lineOf(raw);
      return line > 0
        ? `<blockquote data-line="${line}">${this.parser.parse(tokens)}</blockquote>`
        : `<blockquote>${this.parser.parse(tokens)}</blockquote>`;
    },
    code({ text, lang, raw }) {
      const line = _lineOf(raw);
      const cls = lang ? ` class="language-${lang}"` : "";
      const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
      return line > 0
        ? `<pre data-line="${line}"><code${cls}>${esc}</code></pre>`
        : `<pre><code${cls}>${esc}</code></pre>`;
    },
    hr({ raw }) {
      return `<hr data-line="${_lineOf(raw)}">`;
    },
    list({ ordered, start, items, raw }) {
      const tag = ordered ? "ol" : "ul";
      const startAttr = ordered && start !== 1 ? ` start="${start}"` : "";
      /* 计算每个 <li> 的行号：扫描 raw 文本，识别列表标记行（- / * / + / 数字.） */
      const itemLines = _findListItemLines(raw, items.length);
      let body = "";
      for (let i = 0; i < items.length; i++) {
        const line = itemLines[i] || 0;
        body += `<li data-line="${line}">${this.parser.parse(items[i].tokens)}</li>`;
      }
      return `<${tag}${startAttr} data-line="${_lineOf(raw)}">${body}</${tag}>`;
    },
    table({ header, rows, raw }) {
      const line = _lineOf(raw);
      const lineAttr = line > 0 ? ` data-line="${line}"` : "";
      let html = `<table${lineAttr}><thead><tr>`;
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

  /* 保存并恢复滚动位置：设置 innerHTML 会重置 scrollTop=0，
   * 编辑器 Ctrl+Z（CM6 undo）经 updateListener 触发 renderPreview 时尤其明显。 */
  const savedScrollTop = previewEl.scrollTop;
  previewEl.innerHTML = marked.parse(_renderDoc, { breaks: true, gfm: true });
  previewEl.scrollTop = savedScrollTop;

  /* 处理 ![[image.png]] Obsidian 图片嵌入（必须在 wikilink 之前，避免 ![[x]] 被 [[x]] 误匹配） */
  _processImageEmbeds();

  /* 处理 [[wikilink]] 链接 */
  _processWikilinks();

  /* 为预览区图片挂载放大镜按钮（本地附件 / PicGo 通用） */
  _setupImageZoom();

  /* 重建跨区高亮：innerHTML 已抹掉 .cross-highlight，此处按 _lastHighlightedLine 复原。
   * 原实现是 _clearCrossHighlight()，导致「编辑区删一个词 → 预览区高亮丢失」。 */
  _reapplyCrossHighlight();

  if (window.Outline && Outline.refresh) Outline.refresh();
}

/* ============ 预览区 ![[image]] Obsidian 图片嵌入处理 ============ */
const _IMG_EXT_RE = /\.(png|jpe?g|gif|webp|svg|bmp|avif)$/i;
/* data URL 缓存：{filename: dataUrl}，避免重复请求后端 */
const _embedImgCache = {};

function _processImageEmbeds() {
  const walker = document.createTreeWalker(previewEl, NodeFilter.SHOW_TEXT, null);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) {
    if (node.nodeValue && /!\[\[/.test(node.nodeValue)) {
      textNodes.push(node);
    }
  }

  const pending = [];  /* 待异步解析的图片：[{img, name}] */

  for (const textNode of textNodes) {
    const text = textNode.nodeValue;
    if (!/!\[\[/.test(text)) continue;
    /* 匹配 ![[filename]] 或 ![[filename|alt]] */
    const regex = /!\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]/g;
    let lastIndex = 0;
    const parent = textNode.parentNode;
    const fragment = document.createDocumentFragment();
    let hasMatch = false;
    let match;
    while ((match = regex.exec(text)) !== null) {
      hasMatch = true;
      if (match.index > lastIndex) {
        fragment.appendChild(document.createTextNode(text.substring(lastIndex, match.index)));
      }
      const filename = match[1].trim();
      const alt = (match[2] || filename).trim();
      if (_IMG_EXT_RE.test(filename)) {
        const img = document.createElement("img");
        img.className = "embed-image";
        img.alt = alt;
        img.setAttribute("data-embed-name", filename);
        img.setAttribute("loading", "lazy");
        /* 命中缓存直接设置 src，否则占位等待异步解析 */
        if (_embedImgCache[filename]) {
          img.src = _embedImgCache[filename];
        } else {
          img.style.opacity = "0.3";
          pending.push({ img, name: filename });
        }
        fragment.appendChild(img);
      } else {
        /* 非图片，当作 wikilink 文本处理 */
        const wl = document.createElement("span");
        wl.className = "wikilink";
        wl.setAttribute("data-wikilink", filename);
        wl.textContent = alt;
        fragment.appendChild(wl);
      }
      lastIndex = match.index + match[0].length;
    }
    if (hasMatch) {
      if (lastIndex < text.length) {
        fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
      }
      parent.replaceChild(fragment, textNode);
    }
  }

  /* 异步解析未命中的图片 data URL */
  if (pending.length) _resolveEmbedImages(pending);
}

/* 异步从后端加载附件 data URL 并填充到 <img>（带缓存） */
async function _resolveEmbedImages(pending) {
  const a = (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  if (!a || !a.get_attachment_data_url) return;
  for (const { img, name } of pending) {
    /* 再次检查缓存（可能并发已加载） */
    if (_embedImgCache[name]) {
      img.src = _embedImgCache[name];
      img.style.opacity = "";
      continue;
    }
    try {
      const res = await a.get_attachment_data_url(name);
      if (res && res.ok && res.dataUrl) {
        _embedImgCache[name] = res.dataUrl;
        img.src = res.dataUrl;
        img.style.opacity = "";
      }
    } catch (e) { /* ignore single image failure */ }
  }
}

/* ============ 预览区图片放大镜：悬浮按钮 + 点击放大预览 ============ */
/* 覆盖两种图片：本地附件嵌入 ![[image.png]]（data URL）与 PicGo 远程图 ![alt](url) */
function _setupImageZoom() {
  const imgs = previewEl.querySelectorAll("img");
  for (const img of imgs) {
    if (img.closest(".img-zoom-wrap")) continue; /* 已包装（重复渲染防抖） */
    const wrap = document.createElement("span");
    wrap.className = "img-zoom-wrap";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "img-zoom-btn";
    btn.title = "放大预览";
    btn.tabIndex = -1;
    btn.setAttribute("aria-label", "放大预览");
    /* 内联 SVG 放大镜：无文本节点，不影响预览区 innerText diff 同步 */
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
    /* 阻止 mousedown 在 contenteditable 中移动光标 / 抢焦点 */
    btn.addEventListener("mousedown", (e) => e.preventDefault());
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      _openImageLightbox(img);
    });
    wrap.appendChild(btn);
    img.parentNode.insertBefore(wrap, img);
    wrap.appendChild(img);
  }
}

/* 放大预览（lightbox）：支持本地附件 data URL 与 PicGo 远程 URL */
let _imgLightboxEl = null;

function _openImageLightbox(img) {
  if (!img || !img.src) return;
  _closeImageLightbox();

  const overlay = document.createElement("div");
  overlay.className = "img-lightbox";

  const big = document.createElement("img");
  big.src = img.src;
  big.alt = img.alt || "";

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "img-lightbox-close";
  closeBtn.title = "关闭（Esc）";
  closeBtn.setAttribute("aria-label", "关闭");
  closeBtn.textContent = "✕";

  overlay.appendChild(big);
  overlay.appendChild(closeBtn);
  document.body.appendChild(overlay);
  _imgLightboxEl = overlay;

  /* 点击背景 / ✕ / Esc 关闭；点击图片本身不关闭（便于查看细节） */
  overlay.addEventListener("click", (e) => {
    e.stopPropagation();
    _closeImageLightbox();
  });
  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    _closeImageLightbox();
  });
  big.addEventListener("click", (e) => e.stopPropagation());
  document.addEventListener("keydown", _imgLightboxKeydown);
}

function _imgLightboxKeydown(e) {
  if (e.key === "Escape") _closeImageLightbox();
}

function _closeImageLightbox() {
  if (!_imgLightboxEl) return;
  _imgLightboxEl.remove();
  _imgLightboxEl = null;
  document.removeEventListener("keydown", _imgLightboxKeydown);
}

/* ============ 预览区 [[wikilink]] 处理 ============ */
function _processWikilinks() {
  const walker = document.createTreeWalker(previewEl, NodeFilter.SHOW_TEXT, null);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) {
    if (node.nodeValue && /\[\[/.test(node.nodeValue)) {
      textNodes.push(node);
    }
  }

  for (const textNode of textNodes) {
    const text = textNode.nodeValue;
    if (!/\[\[/.test(text)) continue;

    /* 用正则匹配 [[filename]] 或 [[filename|display]] */
    const regex = /\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]/g;
    let lastIndex = 0;
    const parent = textNode.parentNode;
    const fragment = document.createDocumentFragment();
    let match;
    let hasMatch = false;

    while ((match = regex.exec(text)) !== null) {
      hasMatch = true;
      if (match.index > lastIndex) {
        fragment.appendChild(document.createTextNode(text.substring(lastIndex, match.index)));
      }

      const filename = match[1].trim();
      const display = match[2] || filename;
      const wikilinkEl = document.createElement("span");
      wikilinkEl.className = "wikilink";
      wikilinkEl.setAttribute("data-wikilink", filename);
      wikilinkEl.textContent = display;
      fragment.appendChild(wikilinkEl);
      lastIndex = match.index + match[0].length;
    }

    if (hasMatch) {
      if (lastIndex < text.length) {
        fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
      }
      parent.replaceChild(fragment, textNode);
    }
  }
}

/* ============ 跨区行高亮 ============ */
let _lastHighlightedLine = -1;
/* 光标驱动的滚动同步标志：防止 scroll 事件反向触发造成循环 */
let _cursorSyncActive = false;
/* 抑制 cursorFollowPlugin 的编辑器滚动。预览区撤销/重做走全文替换 dispatch，
 * 会让 cursorFollowPlugin 把编辑区滚到光标处 → 编辑区乱飘。置位期间保持编辑区视图不动。 */
let _suppressCursorFollow = false;

function _clearCrossHighlight() {
  /* 清除预览区高亮 */
  previewEl.querySelectorAll("[data-line].cross-highlight").forEach(el => {
    el.classList.remove("cross-highlight");
  });
  /* 清除编辑器高亮 */
  try {
    const cmView = view;
    if (cmView && cmView.dom) {
      cmView.dom.querySelectorAll(".cm-crossHighlightLine").forEach(el => {
        el.classList.remove("cm-crossHighlightLine");
      });
    }
  } catch (e) { /* ignore */ }
  _lastHighlightedLine = -1;
}

/* 通过 CodeMirror 的 domAtPos 定位指定行的 .cm-line 元素
 * CodeMirror 6 虚拟化渲染，视口外的行不在 DOM 中，所以不能用 querySelectorAll(".cm-line")[n] */
function _findEditorLineEl(lineNum) {
  try {
    const doc = view.state.doc;
    if (lineNum < 1 || lineNum > doc.lines) return null;
    const pos = doc.line(lineNum).from;
    const info = view.domAtPos(pos);
    let el = info.node;
    if (el && el.nodeType === Node.TEXT_NODE) el = el.parentElement;
    while (el && el !== view.dom) {
      if (el.classList && el.classList.contains("cm-line")) return el;
      el = el.parentElement;
    }
  } catch (e) { /* ignore */ }
  return null;
}

/* 给编辑器指定行加高亮（先清除旧的） */
function _highlightEditorLine(lineNum) {
  try {
    if (view && view.dom) {
      view.dom.querySelectorAll(".cm-crossHighlightLine").forEach(el => {
        el.classList.remove("cm-crossHighlightLine");
      });
    }
  } catch (e) { /* ignore */ }
  const lineEl = _findEditorLineEl(lineNum);
  if (lineEl) lineEl.classList.add("cm-crossHighlightLine");
}

/* 查找预览区中对应行号的块元素
 * 可能有多个元素共享 data-line（如 <ul> 与 <li>），取 DOM 序最后一个（最深嵌套），
 * 避免高亮到容器元素导致多行全亮。找不到精确匹配时回退到不超过该行号的最近块。 */
function _findPreviewBlockByLine(lineNum) {
  const exact = previewEl.querySelectorAll(`[data-line="${lineNum}"]`);
  if (exact.length) return exact[exact.length - 1];
  let bestBlock = null;
  let bestLine = 0;
  for (const b of previewEl.querySelectorAll("[data-line]")) {
    const bl = parseInt(b.getAttribute("data-line"), 10);
    if (bl <= lineNum && bl > bestLine) { bestLine = bl; bestBlock = b; }
  }
  return bestBlock;
}

/* 重建跨区高亮（不改动 _lastHighlightedLine，也不滚动）
 * 两侧高亮都是纯 DOM class，会被下列操作抹掉，抹掉后必须重建：
 *   - 预览区：renderPreview() 重设 innerHTML → .cross-highlight 丢失
 *   - 编辑区：CM6 文档变更后重建 .cm-line 元素 → .cm-crossHighlightLine 丢失
 * 这就是「删掉一个词后高亮消失、要再点一下才亮」的原因。 */
function _reapplyCrossHighlight() {
  const ln = _lastHighlightedLine;
  if (ln <= 0) return;
  const block = _findPreviewBlockByLine(ln);
  if (block) block.classList.add("cross-highlight");
  _highlightEditorLine(ln);
}

/* 获取编辑器光标行在视口中的相对位置（0=顶部, 1=底部） */
function _getEditorCursorRatio() {
  try {
    const head = view.state.selection.main.head;
    const block = view.lineBlockAt(head);
    const clientH = view.scrollDOM.clientHeight;
    if (clientH <= 0) return 0.2;
    const y = block.top - view.scrollDOM.scrollTop;
    return Math.max(0, Math.min(1, y / clientH));
  } catch (e) { return 0.2; }
}

/* 获取预览区某块在视口中的相对位置（0=顶部, 1=底部） */
function _getPreviewBlockRatio(block) {
  if (!block) return 0.2;
  const clientH = previewEl.clientHeight;
  if (clientH <= 0) return 0.2;
  const y = block.offsetTop - previewEl.scrollTop;
  return Math.max(0, Math.min(1, y / clientH));
}

/* 高亮指定行（预览+编辑器）
 * scrollTarget: 'preview' | 'editor' | undefined
 *   'preview' → 编辑器光标移动：高亮两侧 + 把预览区滚到同一水平线
 *   'editor'  → 预览区光标移动：高亮两侧 + 把编辑器滚到同一水平线
 *   undefined → 只高亮，不滚动 */
function _highlightLine(lineNum, scrollTarget) {
  /* 防御：无效行号（如嵌套块产生的 data-line="0"）不处理 */
  if (lineNum <= 0) return;
  _clearCrossHighlight();
  _lastHighlightedLine = lineNum;

  /* 高亮预览区对应 data-line 的块（预览区不虚拟化，总是可以高亮） */
  const previewBlock = _findPreviewBlockByLine(lineNum);
  if (previewBlock) previewBlock.classList.add("cross-highlight");

  if (scrollTarget === "editor") {
    /* 预览区 → 编辑器：先获取预览区光标的相对位置，滚动编辑器到相同位置
     * CodeMirror 虚拟化，目标行可能不在视口内，需先滚动再等待渲染后高亮 */
    const ratio = _getPreviewBlockRatio(previewBlock);
    _cursorSyncActive = true;
    if (typeof scrollEditorToLine === "function") {
      scrollEditorToLine(lineNum, ratio);
    }
    /* 等待 CodeMirror 渲染目标行后再添加高亮 */
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        _highlightEditorLine(lineNum);
        setTimeout(() => { _cursorSyncActive = false; }, 200);
      });
    });
  } else if (scrollTarget === "preview") {
    /* 编辑器 → 预览区：编辑器行已在视口内（光标在那里），直接高亮
     * 用编辑器光标的相对位置滚动预览区，使两侧对应行在同一水平线 */
    const ratio = _getEditorCursorRatio();
    _highlightEditorLine(lineNum);
    _cursorSyncActive = true;
    if (typeof scrollPreviewToLine === "function") {
      scrollPreviewToLine(lineNum, ratio);
    }
    setTimeout(() => { _cursorSyncActive = false; }, 200);
  } else {
    /* 只高亮，不滚动：编辑器行如果在视口内则高亮 */
    _highlightEditorLine(lineNum);
  }
}

/* ============ 预览区链接点击 → 默认浏览器打开 / wikilink ============ */
previewEl.addEventListener("click", (e) => {
  /* 图片放大镜按钮点击（放大逻辑已由按钮自身处理，这里拦截防止光标/链接干扰） */
  if (e.target.closest(".img-zoom-btn")) {
    e.preventDefault();
    e.stopPropagation();
    return;
  }

  /* wikilink 点击 */
  const wikilink = e.target.closest(".wikilink");
  if (wikilink) {
    e.preventDefault();
    e.stopPropagation();
    const filename = wikilink.getAttribute("data-wikilink");
    if (filename) {
      _openWikilinkTab(filename);
    }
    return;
  }

  /* 普通链接点击 */
  const a = e.target.closest("a");
  if (!a || !a.href) return;
  /* Ctrl/Cmd + 点击 → 允许编辑（放置光标），不拦截 */
  if (e.ctrlKey || e.metaKey) return;
  e.preventDefault();
  e.stopPropagation();
  if (typeof pywebview !== "undefined" && pywebview.api && pywebview.api.open_url) {
    pywebview.api.open_url(a.href).catch(() => {
      window.open(a.href, "_blank", "noopener,noreferrer");
    });
  } else {
    window.open(a.href, "_blank", "noopener,noreferrer");
  }
});

/* 打开 [[wikilink]] 对应的文件到新页签 */
async function _openWikilinkTab(filename) {
  const cleanName = filename.trim();
  if (!cleanName) return;

  /* 1. 先尝试在已打开的页签中查找（标题精确匹配，忽略 .md 后缀） */
  for (const tab of tabs) {
    if (tab.title) {
      const t = tab.title.replace(/\.md$/i, "").toLowerCase();
      if (t === cleanName.toLowerCase()) {
        setActiveTab(tab.id);
        toast("已切换到: " + cleanName, "ok");
        return;
      }
    }
  }

  /* 2. 调用后端 open_wikilink：精确查找文件名，找不到则在 Capture 新建 */
  if (typeof pywebview !== "undefined" && pywebview.api && pywebview.api.open_wikilink) {
    try {
      const res = await pywebview.api.open_wikilink(cleanName);
      if (res && res.ok) {
        addExternalTab({
          content: res.content || "",
          title: res.title || cleanName,
          path: res.path,
        });
        if (res.created) {
          toast("未找到文件，已在 Capture 新建: " + cleanName, "ok");
        }
        return;
      } else {
        toast("打开失败: " + ((res && res.msg) || "未知错误"), "err");
        return;
      }
    } catch (e) {
      toast("打开链接异常: " + e, "err");
      return;
    }
  }

  toast("无法打开链接（后端未就绪）", "err");
}

/* ============ 跨区行高亮：光标位置跟踪 ============ */

/* 预览区光标变化 → 高亮编辑器对应行 + 滚动编辑器到同一水平线 */
previewEl.addEventListener("mouseup", () => {
  const block = _findCursorBlock();
  if (!block) return;
  const lineNum = parseInt(block.getAttribute("data-line"), 10);
  _highlightLine(lineNum, "editor");
});

previewEl.addEventListener("keyup", (e) => {
  if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "Home" || e.key === "End") {
    const block = _findCursorBlock();
    if (!block) return;
    const lineNum = parseInt(block.getAttribute("data-line"), 10);
    _highlightLine(lineNum, "editor");
  }
});

/* 编辑器光标变化 → 高亮预览区对应行（在 view 初始化后绑定，见 initCursorTracking） */

/* 保存编辑前的块纯文本（用于 diff 计算） */
let _oldBlockPlainText = null;
let _oldBlockMarkdown = null;
let _oldBlockLine = -1;

/* 计算两个字符串的简单 diff：返回 { start, oldLen, newLen, newText }
 * 只处理单个连续插入/删除（typing 和退格的常见场景） */
function _computeSimpleDiff(oldText, newText) {
  if (oldText === newText) return null;
  const minLen = Math.min(oldText.length, newText.length);
  let start = 0;
  while (start < minLen && oldText[start] === newText[start]) start++;
  let oldEnd = oldText.length;
  let newEnd = newText.length;
  while (oldEnd > start && newEnd > start && oldText[oldEnd - 1] === newText[newEnd - 1]) {
    oldEnd--;
    newEnd--;
  }
  return {
    start: start,
    oldLen: oldEnd - start,
    newLen: newEnd - start,
    removed: oldText.substring(start, oldEnd),
    added: newText.substring(start, newEnd),
  };
}

/* ============ 预览区编辑同步：contenteditable → 编辑器（保留 Markdown 语法） ============ */
let _previewEditing = false;
let _skipPreviewRerender = false;
let _previewSyncTimer = null;
let _previewCursorInfo = null;
let _previewInputActive = false;  /* 当前是否处于输入会话中 */
let _skipNextInputFlag = false;  /* 一次性：跳过由 <br> 插入引发的下一个杂散 input 事件 */

/* 预览区失焦时重置输入会话标记 */
previewEl.addEventListener("blur", () => {
  _previewInputActive = false;
  _lastEditedBlock = null;
});

/* 标记下一次 input 事件的处理模式 */
let _pendingAction = null;

/* 找到光标所在的带 data-line 属性的块级祖先元素 */
function _findCursorBlock() {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  let node = sel.anchorNode;
  if (!node) return null;
  if (node.nodeType === Node.TEXT_NODE) node = node.parentNode;
  while (node && node !== previewEl) {
    if (node.nodeType === Node.ELEMENT_NODE && node.hasAttribute && node.hasAttribute("data-line")) {
      /* 跳过 data-line="0" 的嵌套假锚点（子块内部被 marked.js 包裹的 paragraph/code/blockquote 等），
       * 继续向上遍历到真正的块级父元素（li / h1-h6 / 顶层 p 等） */
      if (parseInt(node.getAttribute("data-line"), 10) > 0) return node;
    }
    node = node.parentNode;
  }
  return null;
}

/* 计算光标在块内文本中的偏移位置 */
function _getCursorOffsetInBlock(block) {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !block) return 0;
  const range = sel.getRangeAt(0);
  const pre = range.cloneRange();
  pre.selectNodeContents(block);
  pre.setEnd(range.startContainer, range.startOffset);
  return pre.toString().length;
}

/* 将光标在预览区中的位置映射到编辑器 markdown 中的字符位置 */
function _mapPreviewCursorToEditor() {
  const block = _findCursorBlock();
  if (!block) return null;
  const blockLine = parseInt(block.getAttribute("data-line"), 10);
  const offsetInBlock = _getCursorOffsetInBlock(block);
  const tab = currentTab();
  if (!tab) return null;
  const doc = tab.state.doc;
  if (blockLine > doc.lines) return null;
  const lineStart = doc.line(blockLine).from;
  return lineStart + offsetInBlock;
}

/* ============ Markdown 工具栏宿主能力（供 toolbar.js 经 Toolbar.init 注入） ============ */

/* 将预览区一个 DOM 点（container+offset）映射到编辑器 markdown 字符位置 */
function _mapPreviewPointToEditor(container, offset) {
  if (!container) return null;
  let node = (container.nodeType === Node.TEXT_NODE) ? container.parentNode : container;
  let block = null;
  while (node && node !== previewEl) {
    if (node.nodeType === Node.ELEMENT_NODE && node.hasAttribute && node.hasAttribute("data-line")
        && parseInt(node.getAttribute("data-line"), 10) > 0) {
      block = node;
      break;
    }
    node = node.parentNode;
  }
  if (!block) return null;
  const blockLine = parseInt(block.getAttribute("data-line"), 10);
  const range = document.createRange();
  range.selectNodeContents(block);
  range.setEnd(container, offset);
  const plainOffset = range.toString().length;
  const tab = currentTab();
  if (!tab) return null;
  const doc = tab.state.doc;
  if (blockLine > doc.lines) return null;
  const mdOffset = _mapPlainToMd(doc.line(blockLine).text, plainOffset);
  return doc.line(blockLine).from + mdOffset;
}

/* 捕获预览区当前选区，映射为编辑器 {from,to}（供编辑命令在预览选区上操作） */
function _toolbarCapturePreviewRange() {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  if (!currentTab()) return null;
  const a = _mapPreviewPointToEditor(sel.anchorNode, sel.anchorOffset);
  const b = _mapPreviewPointToEditor(sel.focusNode, sel.focusOffset);
  if (a == null || b == null) return null;
  return { from: Math.min(a, b), to: Math.max(a, b) };
}

/* 将捕获的预览选区应用到编辑器并聚焦 */
function _toolbarApplyPreviewRange(range) {
  if (!range) return;
  const len = view.state.doc.length;
  const to = Math.min(range.to, len);
  const from = Math.min(range.from, to);
  view.dispatch({ selection: { anchor: from, head: to } });
  view.focus();
}

/* 复制当前页签全文 Markdown */
function _toolbarCopyMarkdown() {
  if (!currentTab()) return;
  const text = view.state.doc.toString();
  if (!text) { toast("内容为空", "warn"); return; }
  navigator.clipboard.writeText(text).then(
    () => toast("已复制全文 " + text.length + " 字符", "ok"),
    () => toast("复制失败", "err")
  );
}

/* ============ 预览区键盘拦截：Enter / Ctrl+Z / Ctrl+Y ============ */

/* 将预览区纯文本偏移映射为 markdown 源码位置
 * 逐字符扫描 markdown，跳过语法标记，累计可见字符数 */
function _mapPlainToMd(mdText, plainOffset) {
  let plainCount = 0;
  let i = 0;

  while (i < mdText.length) {
    if (plainCount >= plainOffset) return i;

    const ch = mdText[i];
    const next2 = mdText.substring(i, i + 2);

    /* ** 或 __ 或 ~~ （双字符语法标记） */
    if (next2 === "**" || next2 === "__" || next2 === "~~") {
      i += 2;
      continue;
    }

    /* 单字符语法标记：` * _ ~ */
    if (ch === "`" || ch === "*" || ch === "_" || ch === "~") {
      i++;
      continue;
    }

    /* 行首语法：# ## ### - * + > 1. 等 */
    const atLineStart = (i === 0 || mdText[i - 1] === "\n");
    if (atLineStart) {
      /* 标题标记 # ## ### 等 + 空格 */
      if (ch === "#") {
        let j = i;
        while (j < mdText.length && mdText[j] === "#") j++;
        if (j < mdText.length && mdText[j] === " ") {
          i = j + 1;
          continue;
        }
      }
      /* 列表标记 - * + 后跟空格 */
      if ((ch === "-" || ch === "*" || ch === "+") && mdText[i + 1] === " ") {
        i += 2;
        continue;
      }
      /* 引用 > 后跟空格 */
      if (ch === ">" && mdText[i + 1] === " ") {
        i += 2;
        continue;
      }
      /* 有序列表 1. 2. 等 */
      const m = mdText.substring(i).match(/^(\d+\.)\s/);
      if (m) {
        i += m[0].length;
        continue;
      }
    }

    /* 链接 [text](url) — text 部分可见，其余跳过 */
    if (ch === "[") {
      let j = i + 1;
      while (j < mdText.length && mdText[j] !== "]") j++;
      if (j < mdText.length) {
        const linkText = mdText.substring(i + 1, j);
        if (plainCount + linkText.length >= plainOffset) {
          return i + 1 + (plainOffset - plainCount);
        }
        plainCount += linkText.length;
        i = j + 1;
        if (i < mdText.length && mdText[i] === "(") {
          while (i < mdText.length && mdText[i] !== ")") i++;
          if (i < mdText.length) i++;
        }
        continue;
      }
    }

    /* 图片 ![alt](url) — 整体跳过 */
    if (ch === "!" && mdText[i + 1] === "[") {
      let j = i + 2;
      while (j < mdText.length && mdText[j] !== "]") j++;
      if (j < mdText.length) j++;
      if (j < mdText.length && mdText[j] === "(") {
        while (j < mdText.length && mdText[j] !== ")") j++;
        if (j < mdText.length) j++;
      }
      i = j;
      continue;
    }

    /* 普通可见字符 */
    plainCount++;
    i++;
  }

  return mdText.length;
}

/* 预览区 keydown 拦截：Enter / Ctrl+Z / Ctrl+Y */
previewEl.addEventListener("keydown", (e) => {
  /* ============ Ctrl+Z / Ctrl+Y → 转发到编辑器的 undo/redo ============ */
  if ((e.ctrlKey || e.metaKey) && !e.altKey) {
    const key = e.key.toLowerCase();
    if (key === "z" && !e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      _doPreviewUndoRedo("undo");
      return;
    }
    if (key === "y" || (key === "z" && e.shiftKey)) {
      e.preventDefault();
      e.stopPropagation();
      _doPreviewUndoRedo("redo");
      return;
    }
  }

  /* ============ Enter 键 → 在 markdown 中插入换行 ============ */
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    e.stopPropagation();
    _doPreviewEnter(false);
    return;
  }

  /* ============ Shift+Enter → 软换行 ============ */
  if (e.key === "Enter" && e.shiftKey) {
    e.preventDefault();
    e.stopPropagation();
    _doPreviewEnter(true);
    return;
  }
});

/* ============ 预览区自定义历史栈（替代 CM6 内部 undo/redo） ============ */
let _previewHistory = [];    /* 撤销栈：保存 markdown 文本快照 */
let _previewRedoStack = [];   /* 重做栈 */
const MAX_HISTORY = 200;

/* 在每次预览区编辑前保存快照。
 * 去重策略即输入分组：input 事件触发时 _syncPreviewToEditor 尚未执行（200ms debounce），
 * tab.state.doc 仍是本次编辑之前的状态——正是要存的快照。连续快速输入期间 doc 不变，
 * 读到的快照与栈顶相同 → 跳过 → 自动合并为一个撤销组；停顿超过 debounce 周期后 doc 更新
 * → 下次输入读到新内容 → 开启新的撤销组。无需额外计时器。 */
function _savePreviewHistory() {
  const tab = currentTab();
  if (!tab) return;
  const snapshot = tab.state.doc.toString();
  if (_previewHistory.length && _previewHistory[_previewHistory.length - 1] === snapshot) return;
  _previewHistory.push(snapshot);
  if (_previewHistory.length > MAX_HISTORY) _previewHistory.shift();
  _previewRedoStack = [];
}

/* 清空预览区历史栈（切换 Tab 时必须调用：历史栈是全局的，
 * 不清会把上一个 Tab 的整篇内容通过 Ctrl+Z 写进当前 Tab） */
function _clearPreviewHistory() {
  _previewHistory = [];
  _previewRedoStack = [];
}

/* 新旧文档的公共前缀长度 = 撤销/重做实际生效的位置 */
function _commonPrefixLen(a, b) {
  const n = Math.min(a.length, b.length);
  let i = 0;
  while (i < n && a.charCodeAt(i) === b.charCodeAt(i)) i++;
  return i;
}

/* 执行预览区撤销/重做 */
function _doPreviewUndoRedo(type) {
  /* 关键：先 flush 挂起的 200ms debounce 同步。
   * 否则「输入后 200ms 内按 Ctrl+Z」会出现两个故障：
   *   1. tab.state.doc 尚未包含最新输入 → pop 出的快照与当前 doc 相同 → 撤销看起来无效果
   *   2. 200ms 到点后 pending sync 仍会执行 → 把 DOM 内容写回 markdown → 覆盖掉撤销结果 */
  if (_previewSyncTimer) {
    clearTimeout(_previewSyncTimer);
    _previewSyncTimer = null;
    _syncPreviewToEditor();
  }

  const tab = currentTab();
  if (!tab) return;

  _previewEditing = true;
  _skipPreviewRerender = true;

  let newDoc;
  if (type === "undo") {
    newDoc = _previewHistory.pop();
    /* 必须用 === undefined 判空：空文档快照是 ""，!"" 为 true 会被误判成栈空，
     * 导致「撤销回到空文档」这一步永远做不到 */
    if (newDoc === undefined) {
      _previewEditing = false;
      _skipPreviewRerender = false;
      return;
    }
    /* 保存当前状态到重做栈 */
    _previewRedoStack.push(tab.state.doc.toString());
  } else {
    newDoc = _previewRedoStack.pop();
    if (newDoc === undefined) {
      _previewEditing = false;
      _skipPreviewRerender = false;
      return;
    }
    /* 保存当前状态到撤销栈 */
    _previewHistory.push(tab.state.doc.toString());
  }

  /* 替换整篇文档。光标落在「实际变更点」（新旧文档公共前缀末尾）而非文档末尾——
   * 落末尾会让 cursorFollowPlugin 把编辑区一路滚到文末，即「编辑区乱飘」。 */
  const oldDoc = tab.state.doc.toString();
  const anchor = Math.min(_commonPrefixLen(oldDoc, newDoc), newDoc.length);

  const savedEditorScroll = view.scrollDOM.scrollTop;
  syncing = true;               /* 抑制 editor↔preview 的 scroll 事件互相触发 */
  _suppressCursorFollow = true; /* 抑制 cursorFollowPlugin 主动滚动编辑区 */

  view.dispatch({
    changes: { from: 0, to: oldDoc.length, insert: newDoc },
    selection: { anchor },
  });
  tab.state = view.state;
  view.scrollDOM.scrollTop = savedEditorScroll; /* dispatch 后 CM6 重排，立即回位 */
  /* 兜底：rAF 链若因异常中断，防止抑制标志永久置位导致光标跟随彻底失效 */
  setTimeout(() => { _suppressCursorFollow = false; }, 300);

  /* dispatch 已完成，立即恢复标志（避免 rAF 窗口内编辑区 docChanged 跳过预览渲染） */
  _previewEditing = false;
  _skipPreviewRerender = false;

  /* 保存并恢复滚动位置 */
  const savedScrollTop = previewEl.scrollTop;

  /* 变更点所在行号：撤销/重做要把两侧视图定位到这里，否则用户看不出改了哪 */
  let changeLine = 0;
  try {
    changeLine = view.state.doc.lineAt(Math.min(anchor, view.state.doc.length)).number;
  } catch (e) { changeLine = 0; }

  requestAnimationFrame(() => {
    renderPreview();

    syncing = true;
    /* 先回位，避免 renderPreview / CM6 重排造成的中间态闪动 */
    previewEl.scrollTop = savedScrollTop;
    view.scrollDOM.scrollTop = savedEditorScroll;

    /* 再定位到变更行：仅在该行不在视口内时滚动（nearest 语义，避免无谓跳动）。
     * 上一轮为止住「编辑区乱飘」把视图完全冻结，副作用是撤销后定位不到那一行。 */
    if (changeLine > 0) {
      try {
        const eBlock = view.lineBlockAt(view.state.doc.line(changeLine).from);
        const eTop = eBlock.top - view.scrollDOM.scrollTop;
        if (eTop < 0 || eTop + eBlock.height > view.scrollDOM.clientHeight) {
          scrollEditorToLine(changeLine, 0.3);
        }
      } catch (e) { /* ignore */ }

      const pBlock = _findPreviewBlockByLine(changeLine);
      if (pBlock) {
        const pTop = pBlock.offsetTop - previewEl.scrollTop;
        if (pTop < 0 || pTop + pBlock.offsetHeight > previewEl.clientHeight) {
          scrollPreviewToLine(changeLine, 0.3);
        }
      }
    }

    requestAnimationFrame(() => {
      /* 高亮放在滚动之后：CM6 虚拟化，目标行滚入视口后才有 DOM 元素可加 class */
      if (changeLine > 0) _highlightLine(changeLine);
      syncing = false;
      _suppressCursorFollow = false;
    });

    if (tab.pageId) {
      scheduleOrSave(tab.pageId, tab.state.doc.toString());
    } else if (tab.extPath) {
      Storage.scheduleExternal(tab.extPath, tab.state.doc.toString());
    }
  });
}

/* 将光标放到文档末尾（预览区） */
function _placeCursorAtDocEnd() {
  const blocks = previewEl.querySelectorAll("[data-line]");
  if (!blocks.length) return;
  const lastBlock = blocks[blocks.length - 1];
  _placeCursorAtBlockEnd(lastBlock);
  _scrollPreviewCursorIntoView();
}

/* 预览区：确保光标所在块在视口内（nearest 语义，光标已在视口内则不滚动）
 * 用 getBoundingClientRect 差值计算（offsetTop 依赖定位祖先，preview 无 position 时坐标系不对） */
function _isCaretAtDocEnd() {
  /* 光标是否在【最后一个 data-line 块】的【末尾】
   * （末尾回车产生 trailing <br>，块不增高，getBoundingClientRect 无法感知，需单独处理） */
  const block = _findCursorBlock();
  if (!block) return false;
  const blocks = previewEl.querySelectorAll("[data-line]");
  if (!blocks.length) return false;
  if (block !== blocks[blocks.length - 1]) return false;
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return false;
  const range = sel.getRangeAt(0);
  if (!range.collapsed) return false;
  const tail = range.cloneRange();
  tail.selectNodeContents(block);
  tail.setStart(range.endContainer, range.endOffset);
  return tail.toString().trim().length === 0;
}

function _scrollPreviewCursorIntoView() {
  const block = _findCursorBlock();
  if (!block) return;
  const sh = previewEl.clientHeight;
  if (sh === 0) return;

  let target = null; /* 目标 scrollTop；null 表示无需滚动 */
  let needGuard = false; /* 仅末尾回车场景需要抑制 editor→preview 同步覆盖 */

  if (_isCaretAtDocEnd()) {
    /* 末尾空行特殊处理：trailing <br> 不增加块高度，getBoundingClientRect 测不到，
     * 直接滚到预览区底部，配合 .preview-body 的 padding-bottom 保证光标行不贴边可见 */
    const maxScroll = Math.max(0, previewEl.scrollHeight - sh);
    if (previewEl.scrollTop < maxScroll) {
      target = maxScroll;
      needGuard = true; /* cursorFollowPlugin 的编辑器滚动会把预览区拉离底部，需抑制 */
    }
  } else {
    const pr = previewEl.getBoundingClientRect();
    const br = block.getBoundingClientRect();
    const relTop = br.top - pr.top;       /* 块顶相对预览区视口（含已滚动偏移） */
    const relBottom = br.bottom - pr.top; /* 块底相对预览区视口 */
    let delta = 0;
    if (relTop < 10) {
      delta = relTop - 10;                /* 块在视口上方：向上滚 */
    } else if (relBottom > sh - 24) {
      delta = relBottom - (sh - 24);      /* 块在视口下方：向下滚 */
    }
    if (delta !== 0) {
      const maxScroll = Math.max(0, previewEl.scrollHeight - sh);
      target = Math.max(0, Math.min(previewEl.scrollTop + delta, maxScroll));
    }
    /* 非末尾场景不设 guard：保留原有 editor↔preview 滚动同步，避免中段编辑时两侧错位/跳动 */
  }

  if (target === null) return;

  previewEl.scrollTop = target;
  if (needGuard) {
    /* 仅末尾回车：抑制 200ms 内 cursorFollowPlugin 编辑器滚动触发的 editor→preview 同步，
     * 防止预览区被拉离底部 */
    _cursorSyncActive = true;
    setTimeout(() => { _cursorSyncActive = false; }, 200);
  }
}

/* ============ 执行预览区 Enter 键 ============ */
function _doPreviewEnter(isSoftEnter) {
  /* 先 flush 挂起的 debounce 同步：否则 tab.state.doc 还是旧文档，
   * 下面按 data-line 算出的行范围与实际 markdown 错位 → 换行插到错误位置 */
  if (_previewSyncTimer) {
    clearTimeout(_previewSyncTimer);
    _previewSyncTimer = null;
    _syncPreviewToEditor();
  }

  const tab = currentTab();
  if (!tab) return;

  _savePreviewHistory();

  const block = _findCursorBlock();
  if (!block) return;

  const blockLine = parseInt(block.getAttribute("data-line"), 10);
  const doc = tab.state.doc;
  if (blockLine > doc.lines) return;

  /* 获取当前块对应的 markdown 行范围 */
  const allBlocks = previewEl.querySelectorAll("[data-line]");
  let endLine = doc.lines;
  for (const b of allBlocks) {
    const bl = parseInt(b.getAttribute("data-line"), 10);
    if (bl > blockLine) { endLine = bl - 1; break; }
  }
  const fromPos = doc.line(blockLine).from;
  const toPos = (endLine <= doc.lines) ? doc.line(endLine).to : doc.length;
  const mdBlockText = doc.sliceString(fromPos, toPos);

  /* 获取光标在块内的纯文本偏移 */
  const plainOffset = _getCursorOffsetInBlock(block);

  /* 计算插入位置：将纯文本偏移映射为 markdown 偏移 */
  const mdInsertOffset = _mapPlainToMd(mdBlockText, plainOffset);
  const absInsertPos = fromPos + mdInsertOffset;

  /* 构建插入文本：硬换行用 \n，软换行用 "  \n" */
  const insertText = isSoftEnter ? "  \n" : "\n";

  /* 硬换行时，删除光标前的尾部空格（与 marked breaks 行为一致，
   * 确保 markdown 与 innerText 字符位置对应，避免后续 diff 同步错位） */
  let deleteFrom = absInsertPos;
  if (!isSoftEnter) {
    let checkPos = absInsertPos - 1;
    while (checkPos >= fromPos && doc.sliceString(checkPos, checkPos + 1) === " ") {
      checkPos--;
    }
    deleteFrom = checkPos + 1;
  }

  _previewEditing = true;
  _skipPreviewRerender = true;

  /* 在 markdown 中插入换行符（删除尾部空格） */
  view.dispatch({
    changes: { from: deleteFrom, to: absInsertPos, insert: insertText },
    selection: { anchor: deleteFrom + insertText.length },
  });
  tab.state = view.state;

  /* 直接在 DOM 中插入 <br>，不重新渲染整个预览区
   * （marked 会把单个 \n 渲染成 <br>，仍是同一个段落，data-line 不变。
   *  重新渲染会导致 _placeCursorAtLineStart 找不到下一个块，光标跑到段落开头） */
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) {
    _previewEditing = false;
    _skipPreviewRerender = false;
    return;
  }

  const range = sel.getRangeAt(0);
  range.deleteContents();

  /* 硬换行时，同步删除 DOM 中光标前的尾部空格（与 markdown 操作一致） */
  if (!isSoftEnter && deleteFrom < absInsertPos) {
    const node = range.startContainer;
    if (node.nodeType === Node.TEXT_NODE) {
      const offset = range.startOffset;
      const text = node.nodeValue;
      let delEnd = offset;
      let delStart = delEnd;
      while (delStart > 0 && text[delStart - 1] === " ") delStart--;
      if (delStart < delEnd) {
        node.deleteData(delStart, delEnd - delStart);
        range.setStart(node, delStart);
        range.collapse(true);
      }
    }
  }

  const br = document.createElement("br");
  range.insertNode(br);

  /* 光标移动到 <br> 之后 */
  const newRange = document.createRange();
  newRange.setStartAfter(br);
  newRange.collapse(true);
  sel.removeAllRanges();
  sel.addRange(newRange);

  /* 更新 _oldBlock 状态，避免下次 input 事件错误同步 */
  _oldBlockLine = blockLine;
  const newDoc = tab.state.doc;
  let newEndLine = newDoc.lines;
  for (const b of allBlocks) {
    const bl = parseInt(b.getAttribute("data-line"), 10);
    if (bl > blockLine) { newEndLine = bl - 1; break; }
  }
  const newFromPos = newDoc.line(blockLine).from;
  const newToPos = (newEndLine <= newDoc.lines) ? newDoc.line(newEndLine).to : newDoc.length;
  _oldBlockMarkdown = newDoc.sliceString(newFromPos, newToPos);
  _oldBlockPlainText = block.innerText;
  /* 插入 <br> 会异步派发 input 事件 → 该 input 若被 _syncPreviewToEditor 处理将追加多余 \n。
   * 用一次性标志 _skipNextInputFlag 精准跳过该杂散 input；_previewEditing /
   * _skipPreviewRerender 立即恢复，确保后续真实输入（退格/键入）的 beforeinput 不受影响。 */
  _previewEditing = false;
  _skipPreviewRerender = false;
  _skipNextInputFlag = true;

  /* 回车后光标已移到新行，滚动预览区确保新行可见（长文档末尾回车不丢光标） */
  _scrollPreviewCursorIntoView();

  /* 触发保存 */
  if (tab.pageId) {
    scheduleOrSave(tab.pageId, tab.state.doc.toString());
  } else if (tab.extPath) {
    Storage.scheduleExternal(tab.extPath, tab.state.doc.toString());
  }
}

/* 在指定行的起始位置放置光标（不滚动） */
function _placeCursorAtLineStart(lineNum) {
  const targetBlock = previewEl.querySelector(`[data-line="${lineNum}"]`);
  if (!targetBlock) {
    /* 找最近的块 */
    const allBlocks = previewEl.querySelectorAll("[data-line]");
    let bestBlock = null;
    let bestLine = 0;
    for (const b of allBlocks) {
      const bl = parseInt(b.getAttribute("data-line"), 10);
      if (bl <= lineNum && bl > bestLine) {
        bestLine = bl;
        bestBlock = b;
      }
    }
    if (bestBlock) _placeCursorAtBlockStart(bestBlock);
    return;
  }
  _placeCursorAtBlockStart(targetBlock);
}

/* 在指定块起始位置放置光标（不滚动） */
function _placeCursorAtBlockStart(block) {
  if (!block) return;
  const sel = window.getSelection();
  if (!sel) return;
  const range = document.createRange();
  range.selectNodeContents(block);
  range.collapse(true);
  sel.removeAllRanges();
  sel.addRange(range);
  /* 注意：不调用 scrollIntoView 避免跳动 */
}

/* 在指定块末尾放置光标 */
function _placeCursorAtBlockEnd(block) {
  if (!block) return;
  const sel = window.getSelection();
  if (!sel) return;
  const range = document.createRange();
  range.selectNodeContents(block);
  range.collapse(false);
  sel.removeAllRanges();
  sel.addRange(range);
}

/* 编辑器变更后，静默将光标位置映射回预览区（不触发滚动） */
function _restoreCursorFromEditorSilently() {
  const tab = currentTab();
  if (!tab) return;

  const head = view.state.selection.main.head;
  const doc = tab.state.doc;
  if (head > doc.length) return;

  const lineNum = doc.lineAt(head).number;
  const targetBlock = previewEl.querySelector(`[data-line="${lineNum}"]`);
  if (!targetBlock) {
    const allBlocks = previewEl.querySelectorAll("[data-line]");
    let bestBlock = null;
    let bestLine = 0;
    for (const b of allBlocks) {
      const bl = parseInt(b.getAttribute("data-line"), 10);
      if (bl <= lineNum && bl > bestLine) {
        bestLine = bl;
        bestBlock = b;
      }
    }
    if (bestBlock) _placeCursorAtBlockEnd(bestBlock);
    return;
  }

  const lineStart = doc.line(lineNum).from;
  const offsetInLine = head - lineStart;

  /* 使用纯文本映射来定位光标 */
  const mdLine = doc.sliceString(lineStart, doc.line(lineNum).to);
  const plainOffset = _findPlainOffsetFromMdPos(mdLine, offsetInLine);

  const sel = window.getSelection();
  if (!sel) return;

  const range = document.createRange();
  const walker = document.createTreeWalker(targetBlock, NodeFilter.SHOW_TEXT, null);
  let remaining = plainOffset;
  let node;
  let found = false;

  while ((node = walker.nextNode())) {
    const len = node.nodeValue.length;
    if (remaining <= len) {
      range.setStart(node, Math.max(0, Math.min(remaining, len - 1)));
      range.collapse(true);
      found = true;
      break;
    }
    remaining -= len;
  }

  if (!found) {
    range.selectNodeContents(targetBlock);
    range.collapse(false);
  }

  sel.removeAllRanges();
  sel.addRange(range);
  /* 注意：不调用 scrollIntoView 避免跳动 */
}

/* 从 markdown 位置反查纯文本位置（反向映射） */
function _findPlainOffsetFromMdPos(mdText, mdOffset) {
  let plainCount = 0;
  let i = 0;
  while (i < mdOffset && i < mdText.length) {
    const ch = mdText[i];
    const next2 = mdText.substring(i, i + 2);

    if (next2 === "**" || next2 === "__" || next2 === "~~") { i += 2; continue; }
    if (ch === "`" || ch === "*" || ch === "_" || ch === "~") { i++; continue; }

    const atLineStart = (i === 0 || mdText[i - 1] === "\n");
    if (atLineStart) {
      if (ch === "#") {
        let j = i;
        while (j < mdText.length && mdText[j] === "#") j++;
        if (j < mdText.length && mdText[j] === " ") { i = j + 1; continue; }
      }
      if ((ch === "-" || ch === "*" || ch === "+") && mdText[i + 1] === " ") { i += 2; continue; }
      if (ch === ">" && mdText[i + 1] === " ") { i += 2; continue; }
      const m = mdText.substring(i).match(/^(\d+\.)\s/);
      if (m) { i += m[0].length; continue; }
    }

    if (ch === "[") {
      let j = i + 1;
      while (j < mdText.length && mdText[j] !== "]") j++;
      if (j < mdText.length) {
        if (i + 1 + (j - i - 1) > mdOffset) {
          return plainCount + (mdOffset - i - 1);
        }
        plainCount += (j - i - 1);
        i = j + 1;
        if (i < mdText.length && mdText[i] === "(") {
          while (i < mdText.length && mdText[i] !== ")") i++;
          if (i < mdText.length) i++;
        }
        continue;
      }
    }

    if (ch === "!" && mdText[i + 1] === "[") {
      let j = i + 2;
      while (j < mdText.length && mdText[j] !== "]") j++;
      if (j < mdText.length) j++;
      if (j < mdText.length && mdText[j] === "(") {
        while (j < mdText.length && mdText[j] !== ")") j++;
        if (j < mdText.length) j++;
      }
      i = j;
      continue;
    }

    plainCount++;
    i++;
  }
  return plainCount;
}

/* ============ 预览区普通输入同步（保留 Markdown 语法） ============ */
/* beforeinput：DOM 变更前捕获编辑前基准（innerText 此时还是编辑前文本）。
 * 若在 input 事件里保存基准，innerText 已是编辑后文本 → 首次编辑 diff 基准
 * 与 newPlainText 相同 → diff null 不同步；后续删除/输入位置错位。 */
previewEl.addEventListener("beforeinput", () => {
  if (_previewEditing || _pendingAction) return;
  const block = _findCursorBlock();
  if (block && block !== _lastEditedBlock) {
    _lastEditedBlock = block;
    const blockLine = parseInt(block.getAttribute("data-line"), 10);
    const tab = currentTab();
    if (tab) {
      const doc = tab.state.doc;
      if (blockLine <= doc.lines) {
        const lineStart = doc.line(blockLine).from;
        const allBlocks = previewEl.querySelectorAll("[data-line]");
        let endLine = doc.lines;
        for (const b of allBlocks) {
          const bl = parseInt(b.getAttribute("data-line"), 10);
          if (bl > blockLine) { endLine = bl - 1; break; }
        }
        const lineEnd = (endLine <= doc.lines) ? doc.line(endLine).to : doc.length;
        _oldBlockMarkdown = doc.sliceString(lineStart, lineEnd);
        _oldBlockPlainText = block.innerText; /* 编辑前文本 */
        _oldBlockLine = blockLine;
      }
    }
  }
});

previewEl.addEventListener("input", () => {
  if (_previewEditing || _pendingAction) return;

  /* 阻截 _doPreviewEnter 中 range.insertNode(br) 产生的杂散 input：
   * 该 input 会触发 _syncPreviewToEditor → 错误 diff 追加多余 \n → 两侧内容分歧。
   * 用一次性标志跳过，不影响后续真实用户输入。 */
  if (_skipNextInputFlag) { _skipNextInputFlag = false; return; }

  /* 每次输入都尝试入栈；_savePreviewHistory 内部按内容去重自动合并同一输入会话。
   * 旧实现用 _previewInputActive 门控「仅首次输入存快照」→ 一次 focus 期间撤销栈里
   * 永远只有 1 个快照 → 第一次 Ctrl+Z 直接跳回进入预览区时的状态、第二次栈空无反应。 */
  _savePreviewHistory();
  _previewInputActive = true;

  clearTimeout(_previewSyncTimer);
  _previewSyncTimer = setTimeout(_syncPreviewToEditor, 200);
});

let _lastEditedBlock = null;

/* 核心同步：用文本 diff 保留 Markdown 语法 */
function _syncPreviewToEditor() {
  /* 进入即清 timer 句柄：debounce 触发后变量仍保留旧 id（truthy），
   * 会让外部「是否有挂起同步」的判断误判并重复 flush */
  _previewSyncTimer = null;
  if (_previewEditing || _pendingAction) return;
  const tab = currentTab();
  if (!tab) return;

  const cursorBlock = _findCursorBlock();
  if (!cursorBlock) return;

  const blockLine = parseInt(cursorBlock.getAttribute("data-line"), 10);
  const newPlainText = cursorBlock.innerText;
  const doc = tab.state.doc;

  if (blockLine > doc.lines) return;

  /* 计算 markdown 行的范围 */
  const allBlocks = previewEl.querySelectorAll("[data-line]");
  let endLine = doc.lines;
  for (const b of allBlocks) {
    const bl = parseInt(b.getAttribute("data-line"), 10);
    if (bl > blockLine) { endLine = bl - 1; break; }
  }
  const fromPos = doc.line(blockLine).from;
  const toPos = (endLine <= doc.lines) ? doc.line(endLine).to : doc.length;
  const currentMarkdown = doc.sliceString(fromPos, toPos);

  /* 如果没有保存的旧状态，初始化整个块的基准（而非仅当前行） */
  if (_oldBlockMarkdown === null || _oldBlockLine !== blockLine) {
    _oldBlockLine = blockLine;
    _oldBlockMarkdown = currentMarkdown;
    _oldBlockPlainText = newPlainText;
    return;
  }

  /* 如果 markdown 没变，说明是其他块的编辑，跳过 */
  if (currentMarkdown === _oldBlockMarkdown) {
    /* 用 diff 比较纯文本 */
    const diff = _computeSimpleDiff(_oldBlockPlainText, newPlainText);
    if (!diff) return; /* 真的没变化 */

    /* 应用 diff 到 markdown：在纯文本位置插入/删除字符 */
    const newMarkdown = _applyDiffToMarkdown(currentMarkdown, _oldBlockPlainText, newPlainText, diff);
    _previewEditing = true;
    _skipPreviewRerender = true;

    view.dispatch({
      changes: { from: fromPos, to: toPos, insert: newMarkdown }
    });
    tab.state = view.state;

    /* 更新保存的状态 */
    _oldBlockMarkdown = newMarkdown;
    _oldBlockPlainText = newPlainText;

    /* dispatch 已完成，立即恢复标志（避免 rAF 窗口内编辑区 docChanged 跳过预览渲染） */
    _previewEditing = false;
    _skipPreviewRerender = false;

    previewEl.focus();

    requestAnimationFrame(() => {
      _restorePreviewCursor(blockLine, newPlainText, diff);
    });

    if (tab.pageId) {
      scheduleOrSave(tab.pageId, tab.state.doc.toString());
    } else if (tab.extPath) {
      Storage.scheduleExternal(tab.extPath, tab.state.doc.toString());
    }
  } else {
    /* markdown 已被修改（可能是预览重新渲染），重置基准 */
    _oldBlockMarkdown = currentMarkdown;
    _oldBlockPlainText = newPlainText;
  }
}

/* 将纯文本 diff 应用到 markdown 源码中
 * 核心思路：markdown 源码 = 语法标记 + 纯文本内容
 * 我们通过扫描 markdown 源码，找到纯文本位置，然后在该位置应用 diff */
function _applyDiffToMarkdown(markdown, oldPlain, newPlain, diff) {
  if (!diff) return markdown;

  /* 构建 markdown 字符 → 纯文本位置 的映射
   * 对于行内 markdown（**bold**、*italic*、`code`、[link](url)等），
   * 我们识别语法字符并跳过它们来定位纯文本 */
  const textPositions = []; /* 每个 markdown 字符对应的纯文本位置（-1 表示语法字符） */
  let plainIdx = 0;
  let i = 0;

  while (i < markdown.length) {
    const ch = markdown[i];
    const next2 = markdown.substring(i, i + 2);

    /* 跳过 markdown 语法标记 */
    if (next2 === "**" || next2 === "__") {
      textPositions.push(-1);
      textPositions.push(-1);
      i += 2;
      continue;
    }
    if (next2 === "* " || next2 === "- ") {
      textPositions.push(-1);
      textPositions.push(-1);
      i += 2;
      continue;
    }
    if (ch === '`' || ch === '*' || ch === '_' || ch === '~') {
      textPositions.push(-1);
      i++;
      continue;
    }
    if (ch === '#') {
      textPositions.push(-1);
      i++;
      continue;
    }
    /* 链接 [text](url) 格式：跳过 [ 和 ](url) */
    if (ch === '[') {
      textPositions.push(-1);
      i++;
      /* 找 ] */
      while (i < markdown.length && markdown[i] !== ']') {
        const c = markdown[i];
        /* 链接文本中的字符是纯文本 */
        textPositions.push(plainIdx++);
        i++;
      }
      if (i < markdown.length) { textPositions.push(-1); i++; } /* ] */
      /* 找 (url) */
      if (i < markdown.length && markdown[i] === '(') {
        textPositions.push(-1); i++;
        while (i < markdown.length && markdown[i] !== ')') {
          textPositions.push(-1); i++;
        }
        if (i < markdown.length) { textPositions.push(-1); i++; } /* ) */
      }
      continue;
    }
    /* 图片 ![alt](url) 格式 */
    if (ch === '!') {
      textPositions.push(-1);
      i++;
      if (i < markdown.length && markdown[i] === '[') {
        textPositions.push(-1); i++;
        while (i < markdown.length && markdown[i] !== ']') { textPositions.push(-1); i++; }
        if (i < markdown.length) { textPositions.push(-1); i++; }
        if (i < markdown.length && markdown[i] === '(') {
          textPositions.push(-1); i++;
          while (i < markdown.length && markdown[i] !== ')') { textPositions.push(-1); i++; }
          if (i < markdown.length) { textPositions.push(-1); i++; }
        }
      }
      continue;
    }
    /* 行首标记：#、##、###、-、*、>、1. 等 */
    if (ch === '#' && i <= 3) {
      textPositions.push(-1);
      i++;
      continue;
    }
    if (ch === '>' || ch === '-' || ch === '*') {
      /* 检查是否为行首标记 */
      const before = markdown.substring(0, i);
      const lineStart = before.lastIndexOf('\n') + 1;
      const prefix = markdown.substring(lineStart, i).trimStart();
      if (prefix.length === 0 || /^\d+\.\s*$/.test(prefix)) {
        textPositions.push(-1);
        i++;
        continue;
      }
    }

    /* 普通字符 → 纯文本位置 */
    textPositions.push(plainIdx++);
    i++;
  }

  /* 现在用 diff 的 start（纯文本位置）映射回 markdown 位置 */
  const { start, oldLen, newLen, added } = diff;

  /* 找到 markdown 中对应纯文本位置 start 的位置 */
  let mdStart = -1;
  for (let j = 0; j < textPositions.length; j++) {
    if (textPositions[j] === start) {
      mdStart = j;
      break;
    }
    /* 也接受紧邻的语法字符位置 */
    if (textPositions[j] > start) break;
  }

  if (mdStart === -1) {
    /* 回退：简单替换 */
    return _fallbackReplace(markdown, newPlain);
  }

  /* 找到需要删除的 oldLen 个纯文本字符在 markdown 中的范围 */
  let mdEnd = mdStart;
  if (oldLen > 0) {
    let plainCount = 0;
    for (let j = mdStart; j < textPositions.length; j++) {
      if (textPositions[j] >= start + oldLen) {
        mdEnd = j;
        break;
      }
      if (textPositions[j] >= start) {
        plainCount++;
      }
      if (plainCount >= oldLen) {
        mdEnd = j + 1;
        break;
      }
    }
    if (mdEnd === mdStart) mdEnd = mdStart + oldLen;
  }

  /* 应用 diff：删除旧内容，插入新内容 */
  let result = markdown.substring(0, mdStart);
  result += added;
  result += markdown.substring(mdEnd);

  /* 验证：如果 diff 后纯文本和预期不符，用回退方案 */
  const verifyPlain = _extractPlainText(result);
  if (verifyPlain !== newPlain) {
    return _fallbackReplace(markdown, newPlain);
  }

  return result;
}

/* 从 markdown 提取纯文本（用于验证） */
function _extractPlainText(md) {
  return md
    .replace(/!\[.*?\]\(.*?\)/g, '')     /* 移除图片 */
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') /* 链接 → 文本 */
    .replace(/[*_]{1,3}/g, '')            /* 移除加粗/斜体标记 */
    .replace(/`([^`]*)`/g, '$1')          /* 行内代码 */
    .replace(/~~([^~]*)~~/g, '$1')        /* 删除线 */
    .replace(/^#{1,6}\s+/gm, '')          /* 标题标记 */
    .replace(/^[-*]\s+/gm, '')            /* 列表标记 */
    .replace(/^\d+\.\s+/gm, '')           /* 有序列表 */
    .replace(/^>\s+/gm, '')               /* 引用标记 */
    .replace(/\n{2,}/g, '\n')             /* 合并空行 */
    .trim();
}

/* 回退方案：当 diff 失败时，用旧方法替换 */
function _fallbackReplace(markdown, newPlain) {
  /* 尝试在保留行首标记的前提下替换纯文本 */
  const lines = markdown.split('\n');
  const plainLines = newPlain.split('\n');
  const result = [];

  for (let i = 0; i < lines.length; i++) {
    if (i < plainLines.length) {
      const line = lines[i];
      /* 提取行首标记 */
      const prefixMatch = line.match(/^((?:#{1,6}\s+)|(?:[-*+]\s+)|(?:>\s+)|(?:\d+\.\s+)|(?:\s*))/);
      const prefix = prefixMatch ? prefixMatch[1] : '';
      result.push(prefix + plainLines[i]);
    } else {
      result.push(lines[i]);
    }
  }
  return result.join('\n');
}

/* 回退方案：全文本替换 */
function _doFullReplace(newText, tab) {
  _previewEditing = true;
  _skipPreviewRerender = true;

  view.dispatch({
    changes: { from: 0, to: tab.state.doc.length, insert: newText }
  });
  tab.state = view.state;

  /* dispatch 已完成，立即恢复标志（避免 rAF 窗口内编辑区 docChanged 跳过预览渲染） */
  _previewEditing = false;
  _skipPreviewRerender = false;

  previewEl.focus();

  requestAnimationFrame(() => {
    _restorePreviewCursor(null, _previewCursorInfo);
  });

  if (tab.pageId) {
    scheduleOrSave(tab.pageId, newText);
  } else if (tab.extPath) {
    Storage.scheduleExternal(tab.extPath, newText);
  }
}

/* 同步后恢复预览区光标位置 */
function _restorePreviewCursor(targetLine, newPlainText, diff) {
  if (!targetLine) return;
  let targetBlock = previewEl.querySelector(`[data-line="${targetLine}"]`);
  if (!targetBlock) return;

  const sel = window.getSelection();
  if (!sel) return;

  let cursorOffset = 0;
  if (diff && diff.newLen > 0) {
    cursorOffset = diff.start + diff.newLen;
  } else if (diff) {
    cursorOffset = diff.start;
  } else {
    cursorOffset = newPlainText ? newPlainText.length : 0;
  }

  const range = document.createRange();
  range.selectNodeContents(targetBlock);
  let remaining = cursorOffset;

  const walker = document.createTreeWalker(targetBlock, NodeFilter.SHOW_TEXT, null);
  let node;
  let found = false;
  while ((node = walker.nextNode())) {
    const len = node.nodeValue.length;
    if (remaining <= len) {
      /* 注意：不能 clamp 到 len-1——光标位于文本末尾（remaining === len）时
       * 会被挪到倒数第二个字符后，下次 Backspace 删错字 */
      range.setStart(node, Math.max(0, Math.min(remaining, len)));
      range.collapse(true);
      found = true;
      break;
    }
    remaining -= len;
  }

  if (!found) {
    range.selectNodeContents(targetBlock);
    range.collapse(false);
  }

  sel.removeAllRanges();
  sel.addRange(range);
  /* 用 _scrollPreviewCursorIntoView 代替 scrollIntoView：
   * scrollIntoView 会遍历所有可滚动祖先（可能滚动外层容器 → 跳首页/乱飘），
   * 且 block:nearest 在未重新渲染时（diff 同步场景）完全多余。
   * _scrollPreviewCursorIntoView 用 getBoundingClientRect + delta 仅在需要时滚动，体验平滑。 */
  _scrollPreviewCursorIntoView();
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

/* 向预览区光标位置插入纯文本（避免 HTML 格式污染 contenteditable） */
function _insertPlainTextToPreview(text) {
  if (!text) return;
  const sel = window.getSelection();
  if (!sel) return;
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
}

/* 右键菜单粘贴：从 paste 事件无法获取，尝试 navigator.clipboard 回退 */
async function previewPaste() {
  const sel = window.getSelection();
  if (!sel) return;
  try {
    const text = await navigator.clipboard.readText();
    if (!text) return;
    _insertPlainTextToPreview(text);
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

/* 预览区原生快捷键支持：Ctrl+C/X/A
 * 注意：Ctrl+V 不在此处理，让 paste 事件正常触发，
 * 由 document 的 paste 捕获处理器统一处理图片上传和文本粘贴 */
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
  } else if (key === "a") {
    e.preventDefault();
    previewSelectAll();
  }
});

/* ============ CodeMirror 6 编辑器（单 view，多 tab 共享） ============ */
let view;

/* ============ 编辑器 [[wikilink]] 装饰 + 自动补全 ============ */

/* 装饰：给编辑器中的 [[filename]] / [[filename|display]] 加上 cm-wikilink 样式 */
const _wlDeco = Decoration.mark({ class: "cm-wikilink" });
/* 装饰：未闭合的 [[filename 也加上 cm-wikilink-unfinished 样式（输入中） */
const _wlDecoUnfinished = Decoration.mark({ class: "cm-wikilink cm-wikilink-unfinished" });

const wikilinkPlugin = ViewPlugin.fromClass(class {
  constructor(v) { this.decorations = this._build(v); }
  update(u) {
    if (u.docChanged || u.viewportChanged || u.selectionSet) {
      this.decorations = this._build(u.view);
    }
  }
  _build(v) {
    const decos = [];
    const completeRe = /\[\[([^\[\]\n|]+)(?:\|([^\[\]\n]+))?\]\]/g;
    const openRe = /\[\[([^\[\]\n|]+)$/gm;
    for (const { from, to } of v.visibleRanges) {
      const text = v.state.doc.sliceString(from, to);
      let m;
      completeRe.lastIndex = 0;
      while ((m = completeRe.exec(text)) !== null) {
        decos.push(_wlDeco.range(from + m.index, from + m.index + m[0].length));
      }
      /* 未闭合的 [[filename（光标可能在其中） */
      openRe.lastIndex = 0;
      while ((m = openRe.exec(text)) !== null) {
        const start = from + m.index;
        const end = from + m.index + m[0].length;
        /* 跳过被完整匹配覆盖的范围 */
        let overlap = false;
        for (const d of decos) {
          if (d.from <= start && d.to >= end) { overlap = true; break; }
        }
        if (!overlap) {
          decos.push(_wlDecoUnfinished.range(start, end));
        }
      }
    }
    return Decoration.set(decos, true);
  }
}, { decorations: v => v.decorations });

/* 自动补全：输入 [[ 后弹出候选 .md 文件列表 */
async function wikilinkCompletionSource(ctx) {
  const before = ctx.matchBefore(/\[\[[^\]\[|]*$/);
  if (!before) return null;
  const prefix = before.text.slice(2);
  let options = [];
  try {
    if (typeof pywebview !== "undefined" && pywebview.api && pywebview.api.list_md_files) {
      const res = await pywebview.api.list_md_files(prefix, 30);
      if (res && res.ok && res.items) {
        options = res.items.map(it => ({
          label: it.name,
          type: "file",
          apply: (v, completion, from, to) => {
            /* closeBrackets 可能已在光标后自动插入 ]]，需检测避免重复 */
            const after = v.state.doc.sliceString(to, to + 2);
            const insert = (after === "]]") ? it.name : (it.name + "]]");
            v.dispatch({
              changes: { from, to, insert },
              selection: { anchor: from + insert.length },
            });
          },
          detail: "Wiki Link",
        }));
      }
    }
  } catch (e) { /* ignore */ }
  if (options.length === 0) return null;
  return {
    from: before.from + 2,
    to: ctx.pos,
    options: options,
    validFor: /^\[\[[^\]\[|]*$/,
  };
}

/* ============ 光标跟随滚动（编辑区） ============ */
/* CM6 内置光标滚动仅在编辑器持焦点时生效，且 scrollIntoView 在新增行
 * 尚未布局时可能按过期的 scrollHeight clamp，滚动距离不足。
 * 本插件不依赖焦点：事务后 rAF（DOM 已布局）直接设置 scrollTop，最可靠。 */
const _CURSOR_MARGIN_TOP = 10;
const _CURSOR_MARGIN_BOTTOM = 40; /* 底部留白，光标不贴边 */

function _ensureEditorCursorVisible() {
  if (_suppressCursorFollow) return; /* 预览区撤销/重做期间：编辑区视图保持不动 */
  const v = view;
  if (!v) return;
  const main = v.state.selection.main;
  if (!main.empty) return; /* 拖拽/多选交给 CM6 内置行为 */
  const scroller = v.scrollDOM;
  const sh = scroller.clientHeight;
  if (sh === 0) return; /* 编辑区隐藏/未布局时跳过 */
  const block = v.lineBlockAt(main.head);
  const st = scroller.scrollTop;
  let target = null;
  if (block.top < st + _CURSOR_MARGIN_TOP) {
    target = Math.max(0, block.top - _CURSOR_MARGIN_TOP);
  } else if (block.bottom > st + sh - _CURSOR_MARGIN_BOTTOM) {
    target = Math.max(0, block.bottom + _CURSOR_MARGIN_BOTTOM - sh);
  }
  if (target === null) return; /* 光标行已在视口内 */
  /* 直接设置 scrollTop（不做手动 clamp）：浏览器会自动限制到实际最大滚动位置。
   * 不用 scrollHeight / documentHeight 手动 clamp——rAF 阶段浏览器 scrollHeight
   * 可能仍是旧布局值（新增行未计入），clamp 后滚动距离不足导致光标行被裁。 */
  if (Math.abs(scroller.scrollTop - target) > 1) {
    scroller.scrollTop = target;
    /* 下一帧复测：此时布局已完成（scrollHeight 已更新），若光标行仍越界则补滚 */
    requestAnimationFrame(() => {
      const b2 = v.lineBlockAt(v.state.selection.main.head);
      const st2 = scroller.scrollTop;
      const sh2 = scroller.clientHeight;
      if (b2.bottom > st2 + sh2 - _CURSOR_MARGIN_BOTTOM) {
        scroller.scrollTop = Math.min(
          b2.bottom + _CURSOR_MARGIN_BOTTOM - sh2,
          Math.max(0, scroller.scrollHeight - sh2)
        );
      }
    });
  }
}

const cursorFollowPlugin = ViewPlugin.fromClass(class {
  update(update) {
    if (!(update.docChanged || update.selectionSet)) return;
    /* rAF 阶段执行：CM6 内置同步滚动已尝试，此处为可靠兜底 */
    requestAnimationFrame(_ensureEditorCursorVisible);
  }
});

/* 主题化语法高亮：CM6 defaultHighlightStyle 内置的标记色(#404740 等)是浅色主题配色，
 * 在深色主题下不可见。这里用 HighlightStyle.define 将各语法元素映射到 --cm-* 主题变量，
 * 与 themes/editor/*.css 联动（同 tag 冲突时靠后定义的规则优先，后注册 style 整体接管同 tag）。
 * 注意：CM6 markdown 把格式化标记（# - * 1. > ` 等）标为 meta tag；
 *       而 tags.list 会命中段落等普通正文，因此不做 list 染色，避免正文被误染。 */
const themeHighlightStyle = HighlightStyle.define([
  { tag: tags.strong, color: "var(--cm-strong-color)", fontWeight: "bold" },
  { tag: tags.emphasis, color: "var(--cm-emphasis-color)", fontStyle: "italic" },
  { tag: tags.strikethrough, color: "var(--cm-strikethrough-color)", textDecoration: "line-through" },
  { tag: tags.link, color: "var(--cm-link-color)", textDecoration: "underline" },
  { tag: tags.url, color: "var(--cm-url-color)" },
  { tag: tags.monospace, color: "var(--cm-inline-code-color)" },
  { tag: tags.quote, color: "var(--cm-blockquote-color)" },
  { tag: tags.meta, color: "var(--cm-formatting-color)" },
  { tag: tags.heading, color: "var(--cm-heading1-color)", fontWeight: "bold" },
  { tag: tags.heading6, color: "var(--cm-heading6-color)" },
  { tag: tags.heading5, color: "var(--cm-heading5-color)" },
  { tag: tags.heading4, color: "var(--cm-heading4-color)" },
  { tag: tags.heading3, color: "var(--cm-heading3-color)" },
  { tag: tags.heading2, color: "var(--cm-heading2-color)" },
  { tag: tags.heading1, color: "var(--cm-heading1-color)" },
]);

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
  autocompletion({ override: [wikilinkCompletionSource] }),
  rectangularSelection(),
  crosshairCursor(),
  indentOnInput(),
  syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
  syntaxHighlighting(themeHighlightStyle),
  highlightSelectionMatches(),
  wikilinkPlugin,
  cursorFollowPlugin,
  /* 内置滚动（编辑器聚焦时）预留边距，与光标跟随滚动体验一致 */
  EditorView.scrollMargins.of(() => ({ top: _CURSOR_MARGIN_TOP, bottom: _CURSOR_MARGIN_BOTTOM })),
  keymap.of([
    ...completionKeymap,
    ...closeBracketsKeymap,
    ...defaultKeymap,
    ...searchKeymap,
    ...historyKeymap,
    ...foldKeymap,
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

        /* 跨区高亮跟随光标行更新。高亮只由 mouseup / 方向键 / focus 触发，打字和删除都不触发，
         * 而两侧高亮又是会被重排抹掉的纯 DOM class —— 这就是「删掉一个词后高亮消失、
         * 要再点一下才亮」的成因。光标即编辑位置；预览区来源的变更经 CM6 change mapping
         * 后光标同样落在编辑点。必须在 renderPreview 之前更新行号，否则那一帧会闪旧高亮。
         * 仅在此前已有高亮时重建，不凭空产生高亮。 */
        const needRehighlight = _lastHighlightedLine > 0;
        if (needRehighlight) {
          try {
            _lastHighlightedLine = update.state.doc.lineAt(update.state.selection.main.head).number;
          } catch (e) { /* 保留原值 */ }
        }

        /* 从预览区同步过来的变更，跳过预览重新渲染（避免覆盖用户光标） */
        if (!_skipPreviewRerender) {
          renderPreview(); /* 内部已按 _lastHighlightedLine 重建预览区侧高亮 */
        }
        /* 编辑区侧：CM6 重建 .cm-line 会抹掉 class，等重排完成后再加 */
        if (needRehighlight) {
          requestAnimationFrame(() => _reapplyCrossHighlight());
        }
        /* 自动保存：Capture 立即保存，其他窗口 3 秒 debounce 后保存到 Tab 文件 */
        if (tab.pageId) {
          scheduleOrSave(tab.pageId, update.state.doc.toString());
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
        if (window.Toolbar && Toolbar.updateActiveState) {
          Toolbar.updateActiveState(update.view);
        }
      }
    }
  }),
];

view = new EditorView({ parent: editorEl, extensions: editorExtensions });

/* 初始化编辑器光标跟踪（跨区行高亮 + 滚动同步预览区到同一水平线） */
(function initCursorTracking() {
  view.dom.addEventListener("keyup", (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "Home" || e.key === "End") {
      const head = view.state.selection.main.head;
      const doc = view.state.doc;
      const lineNum = doc.lineAt(head).number;
      _highlightLine(lineNum, "preview");
    }
  });
  view.dom.addEventListener("mouseup", () => {
    const head = view.state.selection.main.head;
    const doc = view.state.doc;
    const lineNum = doc.lineAt(head).number;
    _highlightLine(lineNum, "preview");
  });
  view.dom.addEventListener("focus", () => {
    const head = view.state.selection.main.head;
    const doc = view.state.doc;
    const lineNum = doc.lineAt(head).number;
    _highlightLine(lineNum, "preview");
  });
  let _cursorTrackTimer = null;
  view.dom.addEventListener("click", () => {
    clearTimeout(_cursorTrackTimer);
    _cursorTrackTimer = setTimeout(() => {
      const head = view.state.selection.main.head;
      const doc = view.state.doc;
      const lineNum = doc.lineAt(head).number;
      _highlightLine(lineNum, "preview");
    }, 50);
  });
})();

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
  const sel = view.state.selection.main;
  if (!sel.empty) {
    view.dispatch({ changes: { from: sel.from, to: sel.to, insert: "" } });
  }
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      const pos = view.state.selection.main.head;
      view.dispatch({
        changes: { from: pos, insert: text },
        selection: { anchor: pos + text.length },
      });
      view.focus();
    }
  } catch (e) {
    /* 浏览器剪贴板不可用时回退到后端 API */
    const a = (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
    if (!a || !a.clipboard_get_text) {
      toast("粘贴失败：接口不可用", "err");
      return;
    }
    try {
      const res = await a.clipboard_get_text();
      if (res && res.ok) {
        const pos = view.state.selection.main.head;
        view.dispatch({
          changes: { from: pos, insert: res.text },
          selection: { anchor: pos + res.text.length },
        });
        view.focus();
      } else {
        toast((res && res.msg) || "剪贴板没有文本", "err");
      }
    } catch (e2) {
      toast("粘贴出错：" + e2, "err");
    }
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

function scrollPreviewToLine(line, ratio) {
  const b = findPreviewBlockForLine(line);
  if (b) {
    /* ratio: 目标行在视口中的目标相对位置（0=顶部, 1=底部），默认 0.2 */
    const r = (typeof ratio === "number") ? Math.max(0, Math.min(1, ratio)) : 0.2;
    previewEl.scrollTop = Math.max(0, b.offsetTop - previewEl.clientHeight * r);
  }
}

function scrollEditorToLine(line, ratio) {
  const doc = view.state.doc;
  if (line < 1 || line > doc.lines) return;
  const block = view.lineBlockAt(doc.line(line).from);
  /* ratio: 目标行在视口中的目标相对位置，与本侧光标位置一致以实现平行 */
  const r = (typeof ratio === "number") ? Math.max(0, Math.min(1, ratio)) : 0.2;
  const offset = view.scrollDOM.clientHeight * r;
  view.scrollDOM.scrollTop = Math.max(0, block.top - offset);
}

view.scrollDOM.addEventListener("scroll", () => {
  if (syncing || _cursorSyncActive) return;
  syncing = true;
  const pos = view.lineBlockAtHeight(view.scrollDOM.scrollTop).from;
  const line = view.state.doc.lineAt(pos).number;
  scrollPreviewToLine(line);
  requestAnimationFrame(() => { syncing = false; });
});

previewEl.addEventListener("scroll", () => {
  if (syncing || _cursorSyncActive) return;
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

/* 判断当前焦点/选区是否在预览区内 */
function _isFocusInPreview() {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return false;
  let node = sel.anchorNode;
  if (!node) return false;
  if (node === previewEl) return true;
  while (node && node !== document.body) {
    if (node === previewEl) return true;
    node = node.parentNode;
  }
  return false;
}

/* 插入上传成功结果：焦点在预览区 → 插入到预览区光标所在块末尾；否则编辑器光标处 */
function insertUploadResult(res) {
  if (_isFocusInPreview()) {
    _insertImageToPreview(res);
  } else {
    view.focus();
    const insert = res.markdown + "\n";
    const pos = view.state.selection.main.head;
    view.dispatch({
      changes: { from: pos, insert },
      selection: { anchor: pos + insert.length },
    });
  }
  toast("图片已上传：已插入 " + res.url, "ok");
  setStatus("上传成功：" + res.url);
}

async function uploadAndInsert(imgItem) {
  setStatus("正在上传图片到 PicGo…");
  try {
    const blob = (imgItem && imgItem.getAsFile) ? imgItem.getAsFile() : imgItem;
    if (!blob) throw new Error("无法读取图片数据");
    const dataUrl = await blobToDataURL(blob);
    const res = await pywebview.api.upload_image(dataUrl);
    if (res.ok) {
      insertUploadResult(res);
    } else {
      toast("上传失败：" + res.msg, "err");
      setStatus("上传失败");
    }
  } catch (err) {
    toast("上传出错：" + err, "err");
    setStatus("上传出错");
  }
}

/* 预览区插入图片：在光标所在块末尾插入图片 markdown，重新渲染预览区 */
function _insertImageToPreview(res) {
  const tab = currentTab();
  if (!tab) {
    /* 回退：插入到编辑器 */
    view.focus();
    const insert = res.markdown + "\n";
    const pos = view.state.selection.main.head;
    view.dispatch({
      changes: { from: pos, insert },
      selection: { anchor: pos + insert.length },
    });
    return;
  }

  const block = _findCursorBlock();
  const doc = tab.state.doc;

  /* 找不到块或空文档 → 插入到文档末尾 */
  let insertPos;
  if (!block) {
    insertPos = doc.length;
  } else {
    const blockLine = parseInt(block.getAttribute("data-line"), 10);
    if (blockLine > doc.lines) {
      insertPos = doc.length;
    } else {
      /* 计算块末尾在 markdown 中的位置 */
      const allBlocks = previewEl.querySelectorAll("[data-line]");
      let endLine = doc.lines;
      for (const b of allBlocks) {
        const bl = parseInt(b.getAttribute("data-line"), 10);
        if (bl > blockLine) { endLine = bl - 1; break; }
      }
      insertPos = (endLine <= doc.lines) ? doc.line(endLine).to : doc.length;
    }
  }

  /* 块末尾插入：空行 + 图片 + 空行（保证 marked 渲染为独立段落） */
  const insertText = "\n\n" + res.markdown + "\n";

  _previewEditing = true;
  _skipPreviewRerender = true;

  view.dispatch({
    changes: { from: insertPos, to: insertPos, insert: insertText },
    selection: { anchor: insertPos + insertText.length },
  });
  tab.state = view.state;

  /* dispatch 已完成，立即恢复标志（避免 rAF 窗口内编辑区 docChanged 跳过预览渲染） */
  _previewEditing = false;
  _skipPreviewRerender = false;

  /* 重新渲染预览区（图片是块级元素，重新渲染保证 data-line 正确） */
  const savedScrollTop = previewEl.scrollTop;

  requestAnimationFrame(() => {
    renderPreview();
    previewEl.scrollTop = savedScrollTop;

    /* 重置 _oldBlock 状态（下次输入会重新初始化） */
    _oldBlockMarkdown = null;
    _oldBlockLine = -1;

    /* 光标放到图片所在块之后 */
    const imgEl = previewEl.querySelector(`img[src="${res.url}"]`);
    if (imgEl) {
      const imgBlock = imgEl.closest("[data-line]");
      if (imgBlock) {
        _placeCursorAtBlockEnd(imgBlock);
      }
    }

    if (tab.pageId) {
      scheduleOrSave(tab.pageId, tab.state.doc.toString());
    } else if (tab.extPath) {
      Storage.scheduleExternal(tab.extPath, tab.state.doc.toString());
    }
  });
}

/* 捕获阶段统一拦截：
 * - 优先处理 text/html 富文本（网页复制）→ 解析图片保存附件 + 生成 Obsidian Markdown
 * - 图片粘贴（截图）→ 保存为附件 + 生成 ![[...]] 引用
 * - 预览区文本粘贴 → 插入纯文本（避免 HTML 格式污染 contenteditable）
 * - 编辑器文本粘贴 → 放行给 CodeMirror 原生处理 */
document.addEventListener("paste", (e) => {
  const cd = e.clipboardData;
  /* 1. 优先处理 HTML 富文本（网页复制场景） */
  if (cd && cd.types && Array.from(cd.types).indexOf("text/html") >= 0) {
    const html = cd.getData("text/html");
    if (html && html.trim()) {
      e.preventDefault();
      e.stopPropagation();
      pasteHtmlContent(html, cd);
      return;
    }
  }
  /* 2. 图片（截图 / 图片文件复制） */
  const imgItem = findImageItem(cd);
  if (imgItem) {
    e.preventDefault();
    e.stopPropagation();
    pasteClipboardImage(imgItem);
    return;
  }
  /* 3. 预览区文本粘贴：插入纯文本，阻止浏览器插入 HTML 格式 */
  if (_isFocusInPreview()) {
    const text = cd ? cd.getData("text/plain") : "";
    if (text) {
      e.preventDefault();
      _insertPlainTextToPreview(text);
    }
  }
}, true);

/* HTML 富文本粘贴：发送给后端 paste_html → 保存图片 → 返回 Obsidian Markdown */
async function pasteHtmlContent(html, cd) {
  setStatus("正在解析粘贴内容…");
  const a = (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  if (!a || !a.paste_html) {
    /* 回退：剥离 HTML 标签，粘贴纯文本 */
    const text = cd ? cd.getData("text/plain") : html.replace(/<[^>]+>/g, "");
    if (text) _insertPasteText(text);
    setStatus("已粘贴纯文本");
    return;
  }
  try {
    const res = await a.paste_html(html);
    if (res && res.ok && res.markdown) {
      _insertPasteText(res.markdown);
      const ic = res.imageCount || 0;
      setStatus(ic > 0 ? "已粘贴：" + ic + " 张图片 + 文本" : "已粘贴文本");
      if (ic > 0) toast("已保存 " + ic + " 张图片到附件", "ok");
    } else {
      /* 后端解析失败 → 回退到纯文本（图片失败不影响文字粘贴） */
      const text = cd ? cd.getData("text/plain") : html.replace(/<[^>]+>/g, "");
      if (text) _insertPasteText(text);
      setStatus((res && res.msg) || "HTML 粘贴失败，已粘贴纯文本");
    }
  } catch (err) {
    const text = cd ? cd.getData("text/plain") : "";
    if (text) _insertPasteText(text);
    toast("HTML 粘贴出错：" + err, "err");
    setStatus("粘贴出错");
  }
}

/* 图片粘贴（截图 / 图片文件）：
 * 开关开启（设置 → 图片上传到 PicGo）→ 直接走 PicGo 上传（→ Cloudflare），插入远程链接；
 * 开关关闭（默认）→ 保存为本地附件，失败回退 PicGo 上传。 */
async function pasteClipboardImage(imgItem) {
  setStatus("正在保存图片…");
  const a = (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  /* 实时读取图片上传开关（设置窗口修改后立即生效） */
  let usePicgo = false;
  if (a && a.get_picgo_upload) {
    try {
      const r = await a.get_picgo_upload();
      usePicgo = !!(r && r.ok && r.enabled);
    } catch (e) { /* 读取失败按关闭处理 */ }
  }
  if (usePicgo) {
    /* 能拿到图片文件数据（复制图片文件）→ 前端直接上传 */
    const blob = (imgItem && imgItem.getAsFile) ? imgItem.getAsFile() : imgItem;
    if (blob) {
      uploadAndInsert(imgItem);
      return;
    }
    /* 剪贴板位图（截图）：getAsFile 返回 null，由后端读剪贴板位图上传；
     * 上传失败时降级保存本地附件，保证截图不丢失。 */
    if (a && a.upload_clipboard_image) {
      try {
        const res = await a.upload_clipboard_image();
        if (res && res.ok && res.markdown) {
          insertUploadResult(res);
        } else {
          toast("上传失败：" + (res && res.msg), "err");
          setStatus("上传失败，回退本地附件");
          const fb = await a.paste_clipboard_image();
          if (fb && fb.ok && fb.markdown) {
            _insertPasteText(fb.markdown);
            toast("已回退保存到本地附件", "ok");
          }
        }
        return;
      } catch (err) {
        toast("上传出错：" + err, "err");
        setStatus("上传出错，回退本地附件");
        try {
          const fb = await a.paste_clipboard_image();
          if (fb && fb.ok && fb.markdown) {
            _insertPasteText(fb.markdown);
            toast("已回退保存到本地附件", "ok");
          }
        } catch (e2) { /* 忽略 */ }
        return;
      }
    }
  }
  if (a && a.paste_clipboard_image) {
    try {
      const res = await a.paste_clipboard_image();
      if (res && res.ok && res.markdown) {
        _insertPasteText(res.markdown);
        toast("图片已保存到附件", "ok");
        setStatus("图片已保存");
        return;
      }
      /* 剪贴板无位图（可能是图片文件项），尝试 PicGo 上传 */
    } catch (err) {
      /* 回退到 PicGo */
    }
  }
  /* 回退：PicGo 上传（保留原有行为） */
  uploadAndInsert(imgItem);
}

/* 统一文本插入：编辑器光标处 / 预览区光标处 */
function _insertPasteText(text) {
  if (!text) return;
  if (_isFocusInPreview()) {
    _insertPlainTextToPreview(text);
  } else {
    view.focus();
    const sel = view.state.selection.main;
    view.dispatch({
      changes: { from: sel.from, to: sel.to, insert: text },
      selection: { anchor: sel.from + text.length },
    });
  }
}

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

/* ============ 页签拖拽排序（拖动自定义顺序 + 重启保持） ============ */
function initTabDrag() {
  if (!listEl) return;

  function getDragAfterElement(x) {
    const els = [...listEl.querySelectorAll(".tab:not(.dragging)")];
    let closest = null;
    let closestOffset = Number.NEGATIVE_INFINITY;
    for (const el of els) {
      const box = el.getBoundingClientRect();
      const offset = x - box.left - box.width / 2;
      if (offset < 0 && offset > closestOffset) {
        closestOffset = offset;
        closest = el;
      }
    }
    return closest;
  }

  listEl.addEventListener("dragstart", (e) => {
    const el = e.target.closest(".tab");
    if (!el) return;
    el.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", el.dataset.id);
  });

  listEl.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const dragging = listEl.querySelector(".tab.dragging");
    if (!dragging) return;
    const after = getDragAfterElement(e.clientX);
    if (after == null) listEl.insertBefore(dragging, addBtnEl);
    else listEl.insertBefore(dragging, after);
  });

  listEl.addEventListener("drop", (e) => { e.preventDefault(); });

  listEl.addEventListener("dragend", (e) => {
    const el = e.target.closest(".tab");
    if (el) el.classList.remove("dragging");

    const order = [...listEl.querySelectorAll(".tab")].map((t) => Number(t.dataset.id));
    if (!order.length) return;

    /* 同步内存 tabs 数组到拖拽后的 DOM 顺序（保持 active / 滚动等状态） */
    const map = {};
    for (const t of tabs) map[t.id] = t;
    const newTabs = order.map((id) => map[id]).filter(Boolean);
    if (newTabs.length) {
      tabs.length = 0;
      tabs.push(...newTabs);
    }

    /* 仅持久化本窗口的页面页签（外部打开文件不持久化，无需保存顺序） */
    const pageIds = newTabs.filter((t) => t.pageId).map((t) => t.pageId);
    if (pageIds.length && typeof pywebview !== "undefined" && pywebview.api && pywebview.api.save_tab_order) {
      pywebview.api.save_tab_order(pageIds).catch(() => {});
    }
  });
}

/* 新建 Tab：先建内存 tab，再异步创建对应 Markdown 文件 */
const NEW_PAGE_DEFAULT = "# \n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n";
function addTab() {
  const state = EditorState.create({ doc: NEW_PAGE_DEFAULT, extensions: editorExtensions });
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
      /* 刷新父目录使新文件出现在资源管理器中，再高亮定位 */
      if (window.Explorer && Explorer.refreshDir) {
        const dir = tab.file.substring(0, tab.file.lastIndexOf("\\"));
        Explorer.refreshDir(dir).then(() => syncExplorerWithTab());
      } else {
        syncExplorerWithTab();
      }
      /* 创建期间可能已输入内容：Capture 立即保存，其他窗口 3 秒 debounce 后落盘 */
      const content = tab.state.doc.toString();
      if (content.trim()) {
        scheduleOrSave(tab.pageId, content);
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
  /* 如果该文件已在某个页签中打开，直接切换到该页签 */
  const existing = tabs.find((t) => {
    const tp = t.extPath || t.file || "";
    return tp.toLowerCase() === path.toLowerCase();
  });
  if (existing) {
    setActiveTab(existing.id);
    if (line && line >= 1) {
      requestAnimationFrame(() => {
        const doc = existing.state.doc;
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
    return;
  }
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
  _clearPreviewHistory(); /* 历史栈是全局的，不清会把上个 Tab 的内容 Ctrl+Z 写进当前 Tab */
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

/* 关闭 Tab：Inbox/FlashNote/日志弹窗确认（保存/删除），Capture 保持原有关闭即保存 */
function closeTab(id) {
  const idx = tabs.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const tab = tabs[idx];
  if (tab.pinned) {
    toast("该页签已锁定，请先解锁后再关闭", "err");
    return;
  }
  /* Capture 窗口：保持原有关闭即保存逻辑 */
  if (CFG.windowType === "capture") {
    doCloseTab(tab, false, false);
    return;
  }
  /* Inbox / FlashNote / 日志：弹窗确认 */
  TabManager.confirmClose(tab.title || "未命名", () => {
    /* 删除：不保存，直接从页签栏消失 */
    doCloseTab(tab, false, true);
  }, () => {
    /* 保存：保存内容后再关闭 */
    doCloseTab(tab, false, false);
  });
}

async function doCloseTab(tab, deleteFile, skipSave) {
  /* 不保存模式：跳过保存，直接从页签栏消失 */
  if (!skipSave) {
    /* 关闭即保存：确保内容落盘 */
    if (tab.external && tab.extPath) {
      const content = tab.state.doc.toString();
      await Storage.saveNowExternal(tab.extPath, content).catch(() => {});
      /* 外部文件：不调用 closePage */
    } else if (tab.pageId) {
      const content = tab.state.doc.toString();
      if (content.trim()) {
        /* 保存到聚合文件（如 📦 inbox.md），触发完整保存流程 */
        await pywebview.api.save_with_page(tab.pageId, content, false).catch(() => {});
      }
    }
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
  /* Ctrl+E / Cmd+E：手动保存（原 Ctrl+S，已互换） */
  if (e.key === "e" && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
    e.preventDefault();
    saveCurrent(true);
  }
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

/* 定位行数：主题弹窗输入行号，光标快速定位到指定行 */
function goToLineDialog() {
  view.focus();
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.id = "modal-overlay";
  overlay.innerHTML =
    `<div class="modal-card">` +
      `<div class="modal-title">📍 定位行数</div>` +
      `<div class="modal-msg">请输入要跳转的行号（1 ~ ${view.state.doc.lines}）：</div>` +
      `<input class="modal-input" id="goto-line-input" value="" placeholder="行号" spellcheck="false" type="number" min="1" max="${view.state.doc.lines}">` +
      `<div class="modal-btns">` +
        `<button class="btn-modal neutral" data-act="cancel">取消</button>` +
        `<button class="btn-modal success" data-act="ok">定位</button>` +
      `</div>` +
    `</div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener("mousedown", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  const input = overlay.querySelector("#goto-line-input");
  const submit = () => {
    const lineStr = input.value.trim();
    overlay.remove();
    if (!lineStr) return;
    const lineNum = parseInt(lineStr, 10);
    if (isNaN(lineNum) || lineNum < 1) {
      toast("请输入有效的行号（正整数）", "err");
      return;
    }
    const doc = view.state.doc;
    if (lineNum > doc.lines) {
      toast("文档只有 " + doc.lines + " 行，无法定位到第 " + lineNum + " 行", "err");
      return;
    }
    const line = doc.line(lineNum);
    view.dispatch({
      selection: { anchor: line.from },
      scrollIntoView: true,
    });
    toast("已定位到第 " + lineNum + " 行", "ok");
  };
  overlay.querySelector('[data-act="cancel"]').addEventListener("click", () => overlay.remove());
  overlay.querySelector('[data-act="ok"]').addEventListener("click", submit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
    if (e.key === "Escape") overlay.remove();
  });
  setTimeout(() => { input.focus(); input.select(); }, 50);
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
    /* 两侧同时回顶：syncing 抑制 scroll 事件互相触发，rAF 后释放 */
    view.focus();
    syncing = true;
    view.scrollDOM.scrollTop = 0;
    previewEl.scrollTop = 0;
    requestAnimationFrame(() => { syncing = false; });
  } else if (toolId === "editor_scroll_bottom") {
    view.focus();
    syncing = true;
    view.scrollDOM.scrollTop = view.scrollDOM.scrollHeight;
    previewEl.scrollTop = previewEl.scrollHeight;
    requestAnimationFrame(() => { syncing = false; });
  } else if (toolId === "canvas") {
    if (typeof pywebview !== "undefined" && pywebview.api) {
      pywebview.api.open_canvas().catch(() => {});
    }
  } else if (toolId === "todo") {
    if (typeof pywebview !== "undefined" && pywebview.api) {
      pywebview.api.open_todo().then((ok) => {
        if (ok === false) toast("To Do 不可用（可能为旧版 EXE，请重新构建）", "err");
      }).catch((err) => {
        toast("打开 To Do 出错：" + err, "err");
      });
    }
  } else if (toolId === "canvas_import") {
    /* Drawnix 画布：导入当前页签内容（思维导图） */
    const tab = currentTab();
    if (!tab) { toast("没有打开的页签", "err"); return; }
    const content = tab.state.doc.toString();
    if (!content.trim()) { toast("页签内容为空，无法导入", "err"); return; }
    if (typeof pywebview !== "undefined" && pywebview.api) {
      pywebview.api.import_markdown_to_canvas(content).then((res) => {
        if (res && res.ok) syncToast(res.msg, "ok");
        else toast((res && res.msg) || "导入失败", "err");
      }).catch((err) => {
        toast("导入出错：" + err, "err");
      });
    }
  } else if (toolId === "go_to_line") {
    /* 定位行数：弹窗输入行号，光标快速定位到指定行 */
    goToLineDialog();
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
  /* Capture 窗口：隐藏保存/同步按钮（保留画布导入按钮） */
  if (CFG.windowType === "capture") {
    const bs = document.getElementById("btn-save");
    const by = document.getElementById("btn-sync");
    if (bs) bs.style.display = "none";
    if (by) by.style.display = "none";
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

  /* Markdown 工具栏：注入宿主能力（getView / 复制 / 定位 / 预览选区映射 / 重新渲染） */
  if (window.Toolbar && Toolbar.init) {
    Toolbar.init({
      getView: () => view,
      copyMarkdown: _toolbarCopyMarkdown,
      revealFile: syncExplorerWithTab,
      renderPreview: renderPreview,
      capturePreviewRange: _toolbarCapturePreviewRange,
      applyPreviewRangeToEditor: _toolbarApplyPreviewRange,
    });
  }

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

  /* 页签拖拽排序（拖动自定义顺序 + 重启保持） */
  initTabDrag();

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
