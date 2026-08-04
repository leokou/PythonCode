/* LeoDiary Capture —— 页签 UI 逻辑（从 script.js 抽离，全局函数，零逻辑改动）
 * 功能：页签渲染/拖拽排序/下拉菜单/固定/关闭/切换 + 跨页签激活。
 * 依赖全局：tabs, activeTabId, TabManager, Storage, CFG, view, listEl 等（由 script.js 提供）。
 */
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
