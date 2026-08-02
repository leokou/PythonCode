/* LeoDiary Capture —— 三栏布局核心
 * 职责：编辑/预览/第三栏（目录 or 历史）宽度比例、第三栏显隐与模式切换、布局保存。
 * 宽度：以 flex-grow 比例分配（editor:preview:outline），最小/最大由 resize.js 约束。
 */
"use strict";

const Layout = (() => {
  let editorPane = null;
  let previewPane = null;
  let outlinePane = null;
  let workspacePane = null;
  let resizer0 = null;
  let btnOutline = null;
  let btnHistory = null;
  let brandEl = null;
  let paneTitleEl = null;
  let outlineBody = null;
  let historyBody = null;

  let widths = { editor: 60, preview: 30, outline: 10 };
  let visible = true;
  let mode = "outline";   // "outline"（目录）| "history"（历史）
  let workspaceVisible = false;
  let workspaceWidth = 220;
  let explorerSort = "time";   // 资源树排序："time"（最近修改倒序）| "name"（名称）
  let saving = false;

  function norm(v, dflt) {
    const n = parseInt(v, 10);
    return isFinite(n) && n > 0 ? n : dflt;
  }

  function api() {
    return (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  }

  function apply() {
    if (!editorPane) return;
    editorPane.style.flex = `${widths.editor} ${widths.editor} 0`;
    previewPane.style.flex = `${widths.preview} ${widths.preview} 0`;
    outlinePane.style.flex = `${widths.outline} ${widths.outline} 0`;
    outlinePane.style.display = visible ? "flex" : "none";
    const showOutline = visible && mode === "outline";
    const showHistory = visible && mode === "history";
    outlineBody.style.display = showOutline ? "block" : "none";
    historyBody.style.display = showHistory ? "flex" : "none";
    if (paneTitleEl) paneTitleEl.textContent = showHistory ? "历史" : "目录";
    if (btnOutline) btnOutline.classList.toggle("active", showOutline);
    if (btnHistory) btnHistory.classList.toggle("active", showHistory);
    /* 工作区资源管理器：固定像素宽度，显示时占最左侧，其余栏按 flex 比例瓜分剩余 */
    if (workspacePane) {
      workspacePane.style.display = workspaceVisible ? "flex" : "none";
      workspacePane.style.width = workspaceWidth + "px";
    }
    if (resizer0) resizer0.style.display = workspaceVisible ? "block" : "none";
    if (brandEl) brandEl.classList.toggle("active", workspaceVisible);
  }

  /* 初始化：接收后端下发的 layout 配置 */
  function init(cfg) {
    editorPane = document.getElementById("pane-editor");
    previewPane = document.getElementById("pane-preview");
    outlinePane = document.getElementById("pane-outline");
    workspacePane = document.getElementById("pane-workspace");
    resizer0 = document.getElementById("resizer-0");
    btnOutline = document.getElementById("btn-outline");
    btnHistory = document.getElementById("btn-history");
    brandEl = document.getElementById("brand");
    paneTitleEl = document.getElementById("pane-outline-title");
    outlineBody = document.getElementById("outline-body");
    historyBody = document.getElementById("history-body");

    if (cfg && typeof cfg === "object") {
      widths.editor = norm(cfg.editor_width, 60);
      widths.preview = norm(cfg.preview_width, 30);
      widths.outline = norm(cfg.outline_width, 10);
      visible = cfg.outline_visible !== false;
      if (cfg.pane_mode === "history") mode = "history";
      if (cfg.workspace_visible !== undefined) workspaceVisible = !!cfg.workspace_visible;
      const ww = parseInt(cfg.workspace_width, 10);
      if (isFinite(ww) && ww >= 160 && ww <= 400) workspaceWidth = ww;
      if (cfg.explorer_sort === "name" || cfg.explorer_sort === "time") explorerSort = cfg.explorer_sort;
    }

    if (btnOutline) btnOutline.addEventListener("click", toggleOutline);
    if (btnHistory) btnHistory.addEventListener("click", toggleHistory);
    apply();
  }

  /* 目录按钮：切到目录模式并显示；若已在目录且显示中则隐藏 */
  function toggleOutline() {
    if (visible && mode === "outline") {
      visible = false;
    } else {
      visible = true;
      mode = "outline";
    }
    apply();
    save();
  }

  /* 历史按钮：切到历史模式并显示；若已在历史且显示中则隐藏 */
  function toggleHistory() {
    if (visible && mode === "history") {
      visible = false;
    } else {
      visible = true;
      mode = "history";
    }
    apply();
    save();
    if (visible && mode === "history" && window.History && History.refresh) {
      History.refresh();
    }
  }

  function setVisible(v) {
    visible = !!v;
    apply();
  }

  function isVisible() {
    return visible;
  }

  function getMode() {
    return mode;
  }

  /* 工作区资源管理器：显示/隐藏 + 宽度（resize.js 拖拽时调用） */
  function setWorkspaceVisible(v) {
    workspaceVisible = !!v;
    apply();
    save();
    if (workspaceVisible && window.Workspace && Workspace.refreshFolders) {
      Workspace.refreshFolders();
    }
  }

  function isWorkspaceVisible() {
    return workspaceVisible;
  }

  function setWorkspaceWidth(w) {
    const n = parseInt(w, 10);
    if (!isFinite(n)) return;
    workspaceWidth = Math.min(Math.max(n, 160), 400);
    apply();
  }

  function getWorkspaceWidth() {
    return workspaceWidth;
  }

  /* 资源树排序偏好：切换后持久化（config.json layout.explorer_sort） */
  function getExplorerSort() {
    return explorerSort;
  }

  function setExplorerSort(s) {
    if (s !== "time" && s !== "name") return;
    explorerSort = s;
    save();
  }

  /* 拖动时实时应用宽度（resize.js 调用） */
  function setWidths(editorW, previewW, outlineW) {
    widths.editor = editorW;
    widths.preview = previewW;
    widths.outline = outlineW;
    apply();
  }

  function getWidths() {
    return { ...widths };
  }

  /* 保存布局到后端（config.json layout），节流防止连续保存 */
  function save() {
    if (saving) return;
    saving = true;
    const payload = {
      editor_width: Math.round(widths.editor),
      preview_width: Math.round(widths.preview),
      outline_width: Math.round(widths.outline),
      outline_visible: visible,
      pane_mode: mode,
      workspace_visible: workspaceVisible,
      workspace_width: Math.round(workspaceWidth),
      explorer_sort: explorerSort,
    };
    const a = api();
    if (a && a.save_layout) {
      a.save_layout(payload).catch(() => { saving = false; });
    } else {
      saving = false;
    }
  }

  return {
    init, toggleOutline, toggleHistory, setVisible, isVisible, getMode,
    setWidths, getWidths, save,
    setWorkspaceVisible, isWorkspaceVisible, setWorkspaceWidth, getWorkspaceWidth,
    getExplorerSort, setExplorerSort,
  };
})();

window.Layout = Layout;
