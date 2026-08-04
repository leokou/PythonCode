/* LeoDiary Capture —— 预览区 Markdown 渲染（从 script.js 抽离，全局函数，零逻辑改动）
 * 功能：marked 渲染 + data-line 行号锚点 + ![[image]] 嵌入 + 图片缩放/灯箱 + [[wikilink]] 处理。
 * 依赖全局：marked, previewEl, CFG, pywebview.api, currentTab, _reapplyCrossHighlight, Outline（由 script.js 提供）。
 */
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
