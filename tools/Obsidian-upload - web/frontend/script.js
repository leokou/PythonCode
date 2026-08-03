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

  /* 处理 [[wikilink]] 链接 */
  _processWikilinks();

  /* 清除上一轮的跨区高亮 */
  _clearCrossHighlight();

  if (window.Outline && Outline.refresh) Outline.refresh();
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

/* 高亮指定行（预览+编辑器） */
function _highlightLine(lineNum) {
  if (lineNum === _lastHighlightedLine) return;
  _clearCrossHighlight();
  _lastHighlightedLine = lineNum;

  /* 高亮预览区对应 data-line 的块 */
  const previewBlock = previewEl.querySelector(`[data-line="${lineNum}"]`);
  if (previewBlock) {
    previewBlock.classList.add("cross-highlight");
  } else {
    /* 找最近的 data-line */
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
    if (bestBlock) bestBlock.classList.add("cross-highlight");
  }

  /* 高亮编辑器对应行 */
  try {
    const cmView = view;
    if (cmView && cmView.dom) {
      const lineEls = cmView.dom.querySelectorAll(".cm-line");
      if (lineEls[lineNum - 1]) {
        lineEls[lineNum - 1].classList.add("cm-crossHighlightLine");
      }
    }
  } catch (e) { /* ignore */ }
}

/* ============ 预览区链接点击 → 默认浏览器打开 / wikilink ============ */
previewEl.addEventListener("click", (e) => {
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

  /* 1. 先尝试在已打开的页签中查找 */
  for (const tab of tabs) {
    if (tab.title && tab.title.toLowerCase() === cleanName.toLowerCase()) {
      setActiveTab(tab.id);
      toast("已切换到: " + cleanName, "ok");
      return;
    }
  }

  /* 2. 尝试在工作区页面中查找 */
  try {
    const res = await Storage.getPages();
    if (res && res.ok && res.pages) {
      const matchPage = res.pages.find(p =>
        (p.title && p.title.toLowerCase() === cleanName.toLowerCase()) ||
        (p.title && p.title.toLowerCase().includes(cleanName.toLowerCase()))
      );
      if (matchPage) {
        /* 创建新 tab 并加载页面内容 */
        const contentRes = await Storage.restorePage(matchPage.id);
        const content = (contentRes && contentRes.ok) ? contentRes.content : "";
        const state = EditorState.create({ doc: content, extensions: editorExtensions });
        const tab = {
          id: ++tabSeq, pageId: matchPage.id, title: matchPage.title || cleanName,
          status: "saved", state, editorScroll: 0, previewScroll: 0,
        };
        tabs.push(tab);
        setActiveTab(tab.id);
        toast("已打开: " + cleanName, "ok");
        syncExplorerWithTab();
        return;
      }
    }
  } catch (e) { /* ignore */ }

  /* 3. 回退：尝试用 search_workspace 搜索文件名 */
  if (typeof pywebview !== "undefined" && pywebview.api) {
    try {
      const searchRes = await pywebview.api.search_workspace(cleanName);
      if (searchRes && searchRes.ok && searchRes.results && searchRes.results.length > 0) {
        const file = searchRes.results[0];
        const tab = addExternalTab({
          content: file.content || "",
          title: file.title || cleanName,
          path: file.path || file.file || cleanName,
        });
        toast("已打开: " + cleanName, "ok");
        return;
      }
    } catch (e) { /* not available, ignore */ }
  }

  toast("未找到文件: " + cleanName, "err");
}

/* ============ 跨区行高亮：光标位置跟踪 ============ */

/* 预览区光标变化 → 高亮编辑器对应行 */
previewEl.addEventListener("mouseup", () => {
  const block = _findCursorBlock();
  if (!block) return;
  const lineNum = parseInt(block.getAttribute("data-line"), 10);
  _highlightLine(lineNum);
});

previewEl.addEventListener("keyup", (e) => {
  if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "Home" || e.key === "End") {
    const block = _findCursorBlock();
    if (!block) return;
    const lineNum = parseInt(block.getAttribute("data-line"), 10);
    _highlightLine(lineNum);
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
      return node;
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

/* ============ 预览区键盘拦截：Enter / Ctrl+Z / Ctrl+Y ============ */

/* 构建 markdown 行中「纯文本位置 → markdown 位置」的映射
 * 用于将预览区光标位置正确映射到 markdown 源码位置 */
function _buildTextPosMap(markdownLine) {
  const map = []; /* [mdPos] = plainTextPos | -1 (语法字符) */
  let plainIdx = 0;
  let i = 0;
  while (i < markdownLine.length) {
    const ch = markdownLine[i];
    const next2 = markdownLine.substring(i, i + 2);

    if (next2 === "**" || next2 === "__" || next2 === "~~") {
      map.push(-1); map.push(-1); i += 2; continue;
    }
    if (ch === '`' || ch === '*' || ch === '_' || ch === '~') {
      map.push(-1); i++; continue;
    }
    if (ch === '#') { map.push(-1); i++; continue; }

    /* 行首列表标记 */
    if (ch === '-' || ch === '*' || ch === '+') {
      const lineStart = markdownLine.lastIndexOf('\n', i - 1) + 1;
      if (i === lineStart || (markdownLine.substring(lineStart, i).match(/^\s+$/) && markdownLine[i - 1] !== ' ')) {
        /* 简单处理：如果前面只有空格，可能是列表标记 */
      }
      /* 更精确：只在行首时视为语法 */
      const prefix = markdownLine.substring(lineStart, i);
      if (prefix.trimStart() === '' || /^\d+\.\s*$/.test(prefix)) {
        map.push(-1); i++; continue;
      }
    }
    if (ch === '>') {
      const lineStart = markdownLine.lastIndexOf('\n', i - 1) + 1;
      if (i === lineStart || markdownLine.substring(lineStart, i).trimStart() === '') {
        map.push(-1); i++; continue;
      }
    }

    /* 链接 [text](url) */
    if (ch === '[') {
      map.push(-1); i++;
      while (i < markdownLine.length && markdownLine[i] !== ']') {
        map.push(plainIdx++); i++;
      }
      if (i < markdownLine.length) { map.push(-1); i++; }
      if (i < markdownLine.length && markdownLine[i] === '(') {
        map.push(-1); i++;
        while (i < markdownLine.length && markdownLine[i] !== ')') { map.push(-1); i++; }
        if (i < markdownLine.length) { map.push(-1); i++; }
      }
      continue;
    }

    /* 图片 ![alt](url) */
    if (ch === '!') {
      map.push(-1); i++;
      if (i < markdownLine.length && markdownLine[i] === '[') {
        map.push(-1); i++;
        while (i < markdownLine.length && markdownLine[i] !== ']') { map.push(-1); i++; }
        if (i < markdownLine.length) { map.push(-1); i++; }
        if (i < markdownLine.length && markdownLine[i] === '(') {
          map.push(-1); i++;
          while (i < markdownLine.length && markdownLine[i] !== ')') { map.push(-1); i++; }
          if (i < markdownLine.length) { map.push(-1); i++; }
        }
      }
      continue;
    }

    /* 普通字符 */
    map.push(plainIdx++);
    i++;
  }
  return map;
}

/* 从纯文本位置找到对应的 markdown 位置 */
function _findMdPosFromPlainPos(mdLine, plainPos) {
  const map = _buildTextPosMap(mdLine);
  /* 找到第一个 >= plainPos 的纯文本位置 */
  for (let i = 0; i < map.length; i++) {
    if (map[i] >= plainPos) return i;
  }
  /* 如果没找到，返回行末 */
  return map.length;
}

/* 从纯文本位置找到对应的 markdown 位置范围 [start, end]
 * 返回插入位置（在该位置插入字符后，纯文本会在 plainPos 处出现） */
function _findInsertMdPosFromPlainPos(mdLine, plainPos) {
  const map = _buildTextPosMap(mdLine);
  /* 策略：在 plainPos 对应的 markdown 位置插入，
   * 但如果该位置是语法字符，我们需要找到最近的安全位置 */
  let targetMdPos = map.length;

  /* 找到纯文本位置 == plainPos 的 markdown 位置 */
  for (let i = 0; i < map.length; i++) {
    if (map[i] === plainPos) {
      targetMdPos = i;
      break;
    }
    if (map[i] > plainPos) {
      targetMdPos = i;
      break;
    }
  }

  /* 如果 targetMdPos 是语法字符，找到最近的纯文本边界 */
  if (map[targetMdPos] === -1 && targetMdPos < map.length) {
    /* 向前找最后一个纯文本位置 */
    for (let j = targetMdPos - 1; j >= 0; j--) {
      if (map[j] !== -1) {
        targetMdPos = j + 1;
        break;
      }
    }
    /* 如果前面没找到，向后找第一个纯文本位置 */
    if (map[targetMdPos] === -1) {
      for (let j = targetMdPos + 1; j < map.length; j++) {
        if (map[j] !== -1) {
          targetMdPos = j;
          break;
        }
      }
    }
  }

  return targetMdPos;
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

/* 在每次预览区编辑前保存快照 */
function _savePreviewHistory() {
  const tab = currentTab();
  if (!tab) return;
  _previewHistory.push(tab.state.doc.toString());
  if (_previewHistory.length > MAX_HISTORY) _previewHistory.shift();
  _previewRedoStack = [];
}

/* 执行预览区撤销/重做 */
function _doPreviewUndoRedo(type) {
  const tab = currentTab();
  if (!tab) return;

  _previewEditing = true;
  _skipPreviewRerender = true;

  let newDoc;
  if (type === "undo") {
    newDoc = _previewHistory.pop();
    if (!newDoc) {
      _previewEditing = false;
      _skipPreviewRerender = false;
      return;
    }
    /* 保存当前状态到重做栈 */
    _previewRedoStack.push(tab.state.doc.toString());
  } else {
    newDoc = _previewRedoStack.pop();
    if (!newDoc) {
      _previewEditing = false;
      _skipPreviewRerender = false;
      return;
    }
    /* 保存当前状态到撤销栈 */
    _previewHistory.push(tab.state.doc.toString());
  }

  /* 替换整篇文档 */
  view.dispatch({
    changes: { from: 0, to: tab.state.doc.length, insert: newDoc }
  });
  tab.state = view.state;

  /* 保存并恢复滚动位置 */
  const savedScrollTop = previewEl.scrollTop;

  requestAnimationFrame(() => {
    renderPreview();

    syncing = true;
    previewEl.scrollTop = savedScrollTop;

    _previewEditing = false;
    _skipPreviewRerender = false;

    /* 光标回到文档末尾 */
    _placeCursorAtDocEnd();

    requestAnimationFrame(() => { syncing = false; });

    if (tab.pageId) {
      Storage.schedule(tab.pageId, tab.state.doc.toString());
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
}

/* ============ 执行预览区 Enter 键 ============ */
function _doPreviewEnter(isSoftEnter) {
  const tab = currentTab();
  if (!tab) return;

  _savePreviewHistory();

  _previewEditing = true;
  _skipPreviewRerender = true;

  const block = _findCursorBlock();
  if (!block) {
    _previewEditing = false;
    _skipPreviewRerender = false;
    return;
  }

  const blockLine = parseInt(block.getAttribute("data-line"), 10);
  const doc = tab.state.doc;
  if (blockLine > doc.lines) {
    _previewEditing = false;
    _skipPreviewRerender = false;
    return;
  }

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
  const mdInsertOffset = _findInsertMdPosFromPlainPos(mdBlockText, plainOffset);
  const absInsertPos = fromPos + mdInsertOffset;

  /* 构建插入文本 */
  const insertText = isSoftEnter ? "  \n" : "\n";

  /* 只插入换行符，不替换任何内容 → 保留所有 markdown 语法 */
  view.dispatch({
    changes: { from: absInsertPos, to: absInsertPos, insert: insertText },
    selection: { anchor: absInsertPos + insertText.length },
  });
  tab.state = view.state;

  const savedScrollTop = previewEl.scrollTop;

  requestAnimationFrame(() => {
    renderPreview();
    syncing = true;
    previewEl.scrollTop = savedScrollTop;
    _previewEditing = false;
    _skipPreviewRerender = false;

    /* 光标放到新行开头 */
    const newLineNum = blockLine + 1;
    _placeCursorAtLineStart(newLineNum);

    requestAnimationFrame(() => { syncing = false; });

    if (tab.pageId) {
      Storage.schedule(tab.pageId, tab.state.doc.toString());
    } else if (tab.extPath) {
      Storage.scheduleExternal(tab.extPath, tab.state.doc.toString());
    }
  });
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

/* 从 markdown 位置反查纯文本位置 */
function _findPlainOffsetFromMdPos(mdLine, mdOffset) {
  const map = _buildTextPosMap(mdLine);
  if (mdOffset >= map.length) {
    /* 超过范围，返回最后一个纯文本位置 */
    let lastPlain = 0;
    for (let i = 0; i < map.length; i++) {
      if (map[i] !== -1) lastPlain = map[i] + 1;
    }
    return lastPlain;
  }
  return map[mdOffset] !== -1 ? map[mdOffset] : 0;
}

/* ============ 预览区普通输入同步（保留 Markdown 语法） ============ */
previewEl.addEventListener("input", () => {
  if (_previewEditing || _pendingAction) return;

  /* 首次输入：保存历史快照用于撤销 */
  if (!_previewInputActive) {
    _savePreviewHistory();
    _previewInputActive = true;
  }

  /* 保存编辑前的状态：用于 diff 计算和光标恢复 */
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
        _oldBlockPlainText = block.innerText;
        _oldBlockLine = blockLine;
      }
    }
  }

  clearTimeout(_previewSyncTimer);
  _previewSyncTimer = setTimeout(_syncPreviewToEditor, 200);
});

let _lastEditedBlock = null;

/* 核心同步：用文本 diff 保留 Markdown 语法 */
function _syncPreviewToEditor() {
  if (_previewEditing || _pendingAction) return;
  const tab = currentTab();
  if (!tab) return;

  const cursorBlock = _findCursorBlock();
  if (!cursorBlock) return;

  const blockLine = parseInt(cursorBlock.getAttribute("data-line"), 10);
  const newPlainText = cursorBlock.innerText;
  const doc = tab.state.doc;

  if (blockLine > doc.lines) return;

  /* 如果没有保存的旧状态，用旧方法（全文本替换） */
  if (_oldBlockMarkdown === null || _oldBlockLine !== blockLine) {
    _oldBlockLine = blockLine;
    _oldBlockMarkdown = doc.line(blockLine).slice();
    _oldBlockPlainText = newPlainText;
    return;
  }

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

    previewEl.focus();

    requestAnimationFrame(() => {
      _skipPreviewRerender = false;
      _previewEditing = false;
      _restorePreviewCursor(blockLine, newPlainText, diff);
    });

    if (tab.pageId) {
      Storage.schedule(tab.pageId, tab.state.doc.toString());
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

  previewEl.focus();

  requestAnimationFrame(() => {
    _skipPreviewRerender = false;
    _previewEditing = false;
    _restorePreviewCursor(null, _previewCursorInfo);
  });

  if (tab.pageId) {
    Storage.schedule(tab.pageId, newText);
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
  targetBlock.scrollIntoView({ block: "nearest", behavior: "auto" });
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

/* 初始化编辑器光标跟踪（跨区行高亮） */
(function initCursorTracking() {
  view.dom.addEventListener("keyup", (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "Home" || e.key === "End") {
      const head = view.state.selection.main.head;
      const doc = view.state.doc;
      const lineNum = doc.lineAt(head).number;
      _highlightLine(lineNum);
    }
  });
  view.dom.addEventListener("mouseup", () => {
    const head = view.state.selection.main.head;
    const doc = view.state.doc;
    const lineNum = doc.lineAt(head).number;
    _highlightLine(lineNum);
  });
  view.dom.addEventListener("focus", () => {
    const head = view.state.selection.main.head;
    const doc = view.state.doc;
    const lineNum = doc.lineAt(head).number;
    _highlightLine(lineNum);
  });
  let _cursorTrackTimer = null;
  view.dom.addEventListener("click", () => {
    clearTimeout(_cursorTrackTimer);
    _cursorTrackTimer = setTimeout(() => {
      const head = view.state.selection.main.head;
      const doc = view.state.doc;
      const lineNum = doc.lineAt(head).number;
      _highlightLine(lineNum);
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
