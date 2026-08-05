"use strict";

/* ============================================================
 * Markdown 工具栏（编辑区 + 预览区）
 *
 * - 按钮定义：toolbar/toolbar_config.json（fetch 加载，失败回退内置默认）
 * - 命令实现：toolbar/commands.js（ToolbarCommands.execute）
 * - 宿主能力：Toolbar.init(ctx) 由 script.js 注入（getView / copyMarkdown /
 *   revealFile / toast / capturePreviewRange / applyPreviewRangeToEditor），本模块不直接依赖全局函数
 *
 * 扩展方式：新增按钮只需在 toolbar_config.json 加一项（id/icon/title/command），
 * 命令逻辑在 commands.js 注册即可，无需改本文件。
 * ============================================================ */
const Toolbar = (() => {
  "use strict";

  const CONFIG_URL = "toolbar/toolbar_config.json";

  /* fetch 失败（如 file:// 直开）时的兜底配置，与 toolbar_config.json 保持一致 */
  const FALLBACK_CONFIG = {
    editor: {
      buttons: [
        { id: "bold", icon: "B", title: "加粗 (Ctrl+B)", command: "bold", "class": "md-tb-bold" },
        { id: "italic", icon: "I", title: "斜体 (Ctrl+I)", command: "italic", "class": "md-tb-italic" },
        { id: "underline", icon: "U", title: "下划线 (Ctrl+U)", command: "underline", "class": "md-tb-underline" },
        { id: "strikethrough", icon: "S", title: "删除线（中划线）", command: "strikethrough", "class": "md-tb-strike" },
        { type: "separator" },
        { id: "h1", icon: "H1", title: "一级标题", command: "heading", args: 1 },
        { id: "h2", icon: "H2", title: "二级标题", command: "heading", args: 2 },
        { id: "h3", icon: "H3", title: "三级标题", command: "heading", args: 3 },
        { id: "h4", icon: "H4", title: "四级标题", command: "heading", args: 4 },
        { type: "separator" },
        { id: "ol", icon: "1.", title: "有序列表", command: "orderedList", "class": "md-tb-ol" },
        { id: "list", icon: "•", title: "无序列表", command: "list" },
        { id: "task", icon: "☑", title: "任务列表", command: "taskList" },
        { id: "quote", icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M14,17H17L19,13V7H13V13H16M6,17H9L11,13V7H5V13H8L6,17Z"/></svg>', title: "引用", command: "quote", "class": "md-tb-svg" },
        { id: "code", icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M16,6L18,6L22,12L18,18L16,18L20,12L16,6ZM8,6L6,6L2,12L6,18L8,18L4,12L8,6Z"/></svg>', title: "代码块", command: "codeBlock", "class": "md-tb-svg" },
        { id: "highlight", icon: "🖍️", title: "高亮（荧光笔）", command: "highlight" },
        { id: "color", icon: "A", title: "文字颜色", command: "color", input: "color", defaultColor: "#e91e63" },
        { id: "bg", icon: "A", title: "底色（文字背景）", command: "backgroundColor", input: "color", defaultColor: "#ffff00" },
      ],
    },
    preview: {
      buttons: [
        { id: "reading", icon: "📖", title: "阅读模式（隐藏编辑区）", command: "readingMode" },
        { id: "copy", icon: "📋", title: "复制 Markdown", command: "copyMarkdown" },
        { id: "reveal", icon: "📂", title: "在资源管理器中定位当前文件", command: "revealFile" },
        { type: "separator" },
        { id: "link", icon: "🔗", title: "链接", command: "link" },
        { id: "image", icon: "🖼️", title: "图片", command: "image" },
        { id: "wikilink", icon: "⛓️", title: "双链", command: "wikilink" },
        { id: "zoom", icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><rect x="8" y="8" width="13" height="13" rx="2" fill="currentColor" fill-opacity="0.18"/></svg>', title: "显示缩放（编辑区 / 预览区）", command: "zoom" },
      ],
    },
  };

  /* 编辑区命令（会修改 Markdown 内容）。注意：link/image/wikilink 虽在预览工具栏，
   * 仍是修改 Markdown 的编辑命令，必须保留在集合中，才能把预览区选区映射到编辑器后执行。 */
  const EDIT_COMMANDS = new Set([
    "bold", "italic", "heading", "orderedList", "list", "taskList", "quote", "codeBlock",
    "link", "image", "wikilink", "underline", "strikethrough", "highlight",
    "color", "backgroundColor",
  ]);

  let ctx = {};            /* 宿主能力（script.js 注入） */
  let _readingMode = false;
  const _buttons = {};     /* button id -> DOM 元素 */
  let _pendingPreviewRange = null;  /* pointerdown 时捕获的预览区选区，点击时映射到编辑器 */
  let _previewOrder = null;   /* 预览区工具栏顺序（id 列表，来自设置，重启保持） */
  let _previewBar = null;     /* 预览区工具栏 DOM 引用 */
  let _dragEl = null;         /* 当前拖拽中的按钮元素 */

  /* ---------- 阅读模式状态管理 ---------- */

  function setReadingMode(on) {
    _readingMode = !!on;
    document.body.classList.toggle("reading-mode", _readingMode);
    const btn = _buttons.reading;
    if (btn) btn.classList.toggle("active", _readingMode);
  }

  function toggleReadingMode() {
    setReadingMode(!_readingMode);
  }

  /* ---------- 渲染 ---------- */

  /* 颜色/底色按钮：label 内叠放透明 input[type=color]，点击弹出系统取色器 */
  function createColorButton(b) {
    const label = document.createElement("label");
    label.className = "md-toolbar-btn md-toolbar-color";
    label.title = b.title || b.id || "";
    label.setAttribute("data-command", b.command || "");
    label.setAttribute("data-id", b.id || "");

    const icon = document.createElement("span");
    icon.className = "md-tb-color-icon";
    icon.textContent = "A";
    const swatch = document.createElement("span");
    swatch.className = "md-tb-color-bar";
    swatch.style.background = b.defaultColor || "#e91e63";
    icon.appendChild(swatch);

    const input = document.createElement("input");
    input.type = "color";
    input.value = b.defaultColor || "#e91e63";
    input.addEventListener("change", () => {
      swatch.style.background = input.value;
      executeCommand(b.command, input.value);
    });

    label.appendChild(icon);
    label.appendChild(input);
    if (b.id) _buttons[b.id] = label;
    return label;
  }

  function buildToolbar(containerId, buttons, toolbarClass) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const bar = document.createElement("div");
    bar.className = "md-toolbar " + toolbarClass;
    const isPreview = toolbarClass === "md-toolbar-preview";
    let sepCounter = 0;

    for (const b of buttons || []) {
      if (b.type === "separator") {
        const sep = document.createElement("span");
        sep.className = "md-toolbar-sep";
        sep.setAttribute("data-id", "__sep__" + (sepCounter++));
        bar.appendChild(sep);
        continue;
      }
      let btn;
      if (b.input === "color") {
        btn = createColorButton(b);
      } else {
        btn = document.createElement("button");
        btn.type = "button";
        btn.className = "md-toolbar-btn" + (b["class"] ? " " + b["class"] : "");
        btn.title = b.title || b.id || "";
        btn.setAttribute("data-command", b.command || "");
        btn.setAttribute("data-args", b.args !== undefined ? b.args : "");
        btn.setAttribute("data-id", b.id || "");
        if (typeof b.icon === "string" && b.icon.trim().startsWith("<svg")) {
          btn.innerHTML = b.icon;
        } else {
          btn.textContent = b.icon || "";
        }
        btn.addEventListener("click", onClick);
        /* 仅预览区工具栏按钮支持拖拽自定义顺序 */
        if (isPreview && b.id) {
          btn.draggable = true;
          btn.classList.add("md-toolbar-draggable");
        }
      }
      bar.appendChild(btn);
      if (b.id && b.input !== "color") _buttons[b.id] = btn;
    }

    /* pointerdown 先于 click 触发：提前捕获预览区选中范围（点击按钮可能清空选区） */
    bar.addEventListener("pointerdown", () => {
      _pendingPreviewRange = (typeof ctx.capturePreviewRange === "function")
        ? ctx.capturePreviewRange()
        : null;
    });

    /* 仅预览区工具栏支持拖拽排序 */
    if (isPreview) {
      _previewBar = bar;
      bindPreviewDrag(bar);
      /* 应用上次保存的顺序（Toolbar.setPreviewOrder 可能在工具栏构建前已调用） */
      if (Array.isArray(_previewOrder) && _previewOrder.length) {
        reorderBarByOrder(bar, _previewOrder);
      }
    }

    /* 插到 pane-title 之后、内容区之前 */
    const title = container.querySelector(".pane-title");
    const anchor = title ? title.nextElementSibling : null;
    if (anchor) {
      container.insertBefore(bar, anchor);
    } else {
      container.appendChild(bar);
    }
  }

  /* ---------- 预览区工具栏拖拽排序 ---------- */

  /* 按保存的 id 顺序重排子节点；保存列表中没有的现有子节点追加到末尾 */
  function reorderBarByOrder(bar, order) {
    const nodes = Array.from(bar.children);
    const byId = {};
    for (const n of nodes) {
      const id = n.getAttribute("data-id");
      if (id) byId[id] = n;
    }
    const frag = document.createDocumentFragment();
    const seen = new Set();
    for (const id of order) {
      const el = byId[id];
      if (el) { frag.appendChild(el); seen.add(id); }
    }
    for (const n of nodes) {
      const id = n.getAttribute("data-id");
      if (id && !seen.has(id)) frag.appendChild(n);
    }
    bar.appendChild(frag);
  }

  /* 读取当前 DOM 顺序（data-id 列表），用于保存 */
  function getOrderArray(bar) {
    return Array.from(bar.children)
      .map((n) => n.getAttribute("data-id"))
      .filter(Boolean);
  }

  /* 计算拖拽插入点：返回应插入其前的元素（无则放回末尾） */
  function getDragAfterElement(container, x) {
    const els = Array.from(container.children).filter(
      (c) => c !== _dragEl);
    let closest = { offset: -Infinity, el: null };
    for (const child of els) {
      const box = child.getBoundingClientRect();
      const offset = x - box.left - box.width / 2;
      if (offset < 0 && offset > closest.offset) {
        closest = { offset, el: child };
      }
    }
    return closest.el;
  }

  function bindPreviewDrag(bar) {
    bar.addEventListener("dragstart", (e) => {
      const btn = e.target.closest(".md-toolbar-btn");
      if (!btn || !btn.draggable) return;
      _dragEl = btn;
      btn.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", btn.getAttribute("data-id") || ""); } catch (_) {}
    });
    bar.addEventListener("dragover", (e) => {
      if (!_dragEl) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const after = getDragAfterElement(bar, e.clientX);
      if (after == null) bar.appendChild(_dragEl);
      else bar.insertBefore(_dragEl, after);
    });
    bar.addEventListener("dragend", () => {
      if (_dragEl) _dragEl.classList.remove("dragging");
      _dragEl = null;
      const order = getOrderArray(bar);
      _previewOrder = order;
      if (typeof ctx.savePreviewToolbarOrder === "function") {
        try { ctx.savePreviewToolbarOrder(order); } catch (_) {}
      }
    });
  }

  function render(cfg) {
    const editor = (cfg && cfg.editor) || FALLBACK_CONFIG.editor;
    const preview = (cfg && cfg.preview) || FALLBACK_CONFIG.preview;
    if (document.getElementById("pane-editor")) {
      buildToolbar("pane-editor", editor.buttons, "md-toolbar-editor");
    }
    if (document.getElementById("pane-preview")) {
      buildToolbar("pane-preview", preview.buttons, "md-toolbar-preview");
    }
  }

  function loadConfig() {
    fetch(CONFIG_URL, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
      .then((cfg) => render(cfg))
      .catch(() => render(FALLBACK_CONFIG));
  }

  /* ---------- 点击处理 ---------- */

  /* 统一执行入口：编辑命令先映射预览区选区到编辑器，再执行 */
  function executeCommand(command, args) {
    const view = (typeof ctx.getView === "function") ? ctx.getView() : null;
    if (EDIT_COMMANDS.has(command) && _pendingPreviewRange &&
        typeof ctx.applyPreviewRangeToEditor === "function") {
      ctx.applyPreviewRangeToEditor(_pendingPreviewRange);
    }
    ToolbarCommands.execute(command, view, Object.assign({}, ctx, { args }));
    _pendingPreviewRange = null;
  }

  function onClick(e) {
    const btn = e.target.closest(".md-toolbar-btn");
    if (!btn) return;
    /* 颜色/底色按钮由 input[type=color] 的 change 事件驱动，跳过普通点击 */
    if (btn.classList.contains("md-toolbar-color")) return;
    const command = btn.getAttribute("data-command");
    if (!command) return;
    executeCommand(command, btn.getAttribute("data-args"));
  }

  /* ---------- 光标格式 → 按钮 active 状态 ---------- */

  /* 由 script.js 在编辑器光标/内容变化时调用（updateListener） */
  function updateActiveState(view) {
    if (!view) return;
    const st = ToolbarCommands.getActiveState(view);
    const map = {
      bold: st.bold, italic: st.italic, underline: st.underline,
      strikethrough: st.strikethrough, highlight: st.highlight,
      color: st.color, bg: st.backgroundColor,
      list: st.list, ol: st.orderedList, task: st.taskList,
      quote: st.quote, code: st.codeBlock,
      h1: st.heading === 1, h2: st.heading === 2,
      h3: st.heading === 3, h4: st.heading === 4,
    };
    for (const [id, on] of Object.entries(map)) {
      const el = _buttons[id];
      if (el) el.classList.toggle("active", !!on);
    }
    /* 光标在颜色/底色内：色条与取色器同步为实际颜色 */
    if (st.colorValue) setColorValue("color", st.colorValue);
    if (st.bgValue) setColorValue("bg", st.bgValue);
  }

  function setColorValue(id, value) {
    const el = _buttons[id];
    if (!el) return;
    const input = el.querySelector("input[type=color]");
    const swatch = el.querySelector(".md-tb-color-bar");
    if (input) input.value = value;
    if (swatch) swatch.style.background = value;
  }

  /* ---------- 生命周期 ---------- */

  function start() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
      return;
    }
    loadConfig();
  }

  start();

  return {
    /* script.js 注入宿主能力：
     * { getView, copyMarkdown, revealFile, toast,
     *   capturePreviewRange, applyPreviewRangeToEditor, savePreviewToolbarOrder } */
    init(c) {
      ctx = Object.assign({ toggleReadingMode: toggleReadingMode }, c || {});
    },
    /* script.js 读取设置后注入预览区工具栏顺序（可能在工具栏异步构建前调用） */
    setPreviewOrder(order) {
      _previewOrder = Array.isArray(order) ? order : null;
      if (_previewBar && _previewOrder && _previewOrder.length) {
        reorderBarByOrder(_previewBar, _previewOrder);
      }
    },
    /* script.js 在编辑器光标/内容变化时调用，刷新格式按钮 active 状态 */
    updateActiveState,
  };
})();

window.Toolbar = Toolbar;
