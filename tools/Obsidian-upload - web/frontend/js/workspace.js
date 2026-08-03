/* LeoDiary Capture —— 工作区资源管理器
 * 职责：资源管理器栏的显隐控制、工作区文件夹增删、文件树加载（懒加载）。
 * 布局状态：workspace_visible / workspace_width 由 Layout 管理（存 layout.json）。
 * 目录树渲染由 Explorer 负责（web/explorer.js），排序偏好存 config.json layout.explorer_sort。
 */
"use strict";

const Workspace = (() => {
  let pane = null;
  let brandEl = null;
  let treeEl = null;
  let searchInput = null;

  function api() {
    return (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  }

  /* 拉取工作区文件夹列表并渲染文件树 */
  async function refreshFolders() {
    const a = api();
    if (!a || !a.get_workspace) return;
    try {
      const res = await a.get_workspace();
      if (res && res.ok && window.Explorer) Explorer.renderFolders(res.folders || []);
    } catch (e) { /* ignore */ }
  }

  async function loadChildren(path, sort) {
    const a = api();
    if (!a || !a.get_file_tree) return [];
    try {
      const res = await a.get_file_tree(path, sort || "time");
      return (res && res.ok && res.items) ? res.items : [];
    } catch (e) {
      return [];
    }
  }

  function onOpenFile(path) {
    if (window.openWorkspaceFile) window.openWorkspaceFile(path, 0);
  }

  /* ---- 文件右键菜单 ----
   * 复制文件名称 / 复制完整路径 / 在资源管理器中显示 / 用 VSCode 打开 / 重命名 / 删除
   */
  function fileName(path) {
    const p = String(path || "");
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.slice(i + 1) : p;
  }

  function fileBase(path) {
    const n = fileName(path);
    const i = n.lastIndexOf(".");
    return i > 0 ? n.slice(0, i) : n;
  }

  function dirOf(path) {
    const p = String(path || "");
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.slice(0, i) : p;
  }

  async function copyText(text, okMsg) {
    const a = api();
    if (!a || !a.explorer_copy_text) { toast("复制失败：接口不可用", "err"); return; }
    try {
      const res = await a.explorer_copy_text(text);
      toast(res && res.ok ? okMsg : ((res && res.msg) || "复制失败"), res && res.ok ? "ok" : "err");
    } catch (e) {
      toast("复制出错：" + e, "err");
    }
  }

  async function revealInExplorer(path) {
    const a = api();
    if (!a || !a.explorer_reveal) { toast("操作失败：接口不可用", "err"); return; }
    try {
      const res = await a.explorer_reveal(path);
      toast(res && res.ok ? "已在资源管理器中定位" : (res && res.msg || "定位失败"), res && res.ok ? "ok" : "err");
    } catch (e) {
      toast("定位出错：" + e, "err");
    }
  }

  async function openWithVSCode(path) {
    const a = api();
    if (!a || !a.explorer_open_vscode) { toast("操作失败：接口不可用", "err"); return; }
    try {
      const res = await a.explorer_open_vscode(path);
      toast(res && res.ok ? res.msg : ((res && res.msg) || "打开失败"), res && res.ok ? "ok" : "err");
    } catch (e) {
      toast("打开出错：" + e, "err");
    }
  }

  /* 重命名：弹输入框 → 后端重命名 → 成功刷新树 + 历史面板 */
  async function renameFile(path, isDir) {
    if (!window.ContextMenu) return;
    ContextMenu.renameDialog(isDir ? fileName(path) : fileBase(path), async (newBase) => {
      const a = api();
      if (!a || !a.explorer_rename) { toast("重命名失败：接口不可用", "err"); return; }
      try {
        const res = await a.explorer_rename(path, newBase);
        if (res && res.ok) {
          toast(res.msg || "已重命名", "ok");
          if (window.Explorer && Explorer.refreshDir) Explorer.refreshDir(dirOf(path));
          if (window.History && History.refresh) History.refresh();
        } else {
          toast((res && res.msg) || "重命名失败", "err");
        }
      } catch (e) {
        toast("重命名出错：" + e, "err");
      }
    });
  }

  /* 删除：确认框 → 后端删除到回收站 → 成功刷新树 + 历史面板 */
  async function deleteFile(path, isDir) {
    if (!window.ContextMenu) return;
    ContextMenu.confirmDialog(isDir ? "删除文件夹" : "删除笔记", "将删除「" + fileName(path) + "」到回收站（可恢复）。", "删除", async () => {
      const a = api();
      if (!a || !a.explorer_delete) { toast("删除失败：接口不可用", "err"); return; }
      try {
        const res = await a.explorer_delete(path);
        if (res && res.ok) {
          toast(res.msg || "已删除", "ok");
          if (window.Explorer && Explorer.refreshDir) Explorer.refreshDir(dirOf(path));
          if (window.History && History.refresh) History.refresh();
        } else {
          toast((res && res.msg) || "删除失败", "err");
        }
      } catch (e) {
        toast("删除出错：" + e, "err");
      }
    });
  }

  /* 复制副本：当前目录生成 xxx-副本.md */
  async function duplicateFile(path) {
    const a = api();
    if (!a || !a.explorer_duplicate) { toast("复制副本失败：接口不可用", "err"); return; }
    try {
      const res = await a.explorer_duplicate(path);
      if (res && res.ok) {
        toast(res.msg || "已复制副本", "ok");
        if (window.Explorer && Explorer.refreshDir) Explorer.refreshDir(dirOf(path));
      } else {
        toast((res && res.msg) || "复制失败", "err");
      }
    } catch (e) {
      toast("复制出错：" + e, "err");
    }
  }

  /* 移动：弹窗选目标目录 → 后端移动 → 刷新源父目录与目标目录 */
  async function moveFile(path) {
    const a = api();
    if (!a || !a.explorer_dirs) { toast("移动失败：接口不可用", "err"); return; }
    let dirs = [];
    try {
      const res = await a.explorer_dirs();
      if (res && res.ok) dirs = res.dirs || [];
      else { toast((res && res.msg) || "获取目录失败", "err"); return; }
    } catch (e) {
      toast("获取目录出错：" + e, "err");
      return;
    }
    if (!window.ContextMenu || !ContextMenu.moveDialog) return;
    ContextMenu.moveDialog(dirs, path, async (dest) => {
      if (!a.explorer_move) { toast("移动失败：接口不可用", "err"); return; }
      try {
        const res = await a.explorer_move(path, dest);
        if (res && res.ok) {
          toast(res.msg || "已移动", "ok");
          if (window.Explorer && Explorer.refreshDir) {
            Explorer.refreshDir(dirOf(path));
            Explorer.refreshDir(dest);
          }
          if (window.History && History.refresh) History.refresh();
        } else {
          toast((res && res.msg) || "移动失败", "err");
        }
      } catch (e) {
        toast("移动出错：" + e, "err");
      }
    });
  }

  /* 新建文件夹：当前目录内创建，成功刷新该目录 */
  async function newFolder(parent) {
    const a = api();
    if (!a || !a.explorer_new_folder) { toast("新建失败：接口不可用", "err"); return; }
    try {
      const res = await a.explorer_new_folder(parent);
      if (res && res.ok) {
        toast(res.msg || "已新建文件夹", "ok");
        if (window.Explorer && Explorer.refreshDir) Explorer.refreshDir(parent);
      } else {
        toast((res && res.msg) || "新建失败", "err");
      }
    } catch (e) {
      toast("新建出错：" + e, "err");
    }
  }

  /* 新建文件：当前目录内创建 md 文件，成功刷新该目录 */
  async function newFile(parent) {
    const a = api();
    if (!a || !a.explorer_new_file) { toast("新建失败：接口不可用", "err"); return; }
    try {
      const res = await a.explorer_new_file(parent);
      if (res && res.ok) {
        toast(res.msg || "已新建文件", "ok");
        if (window.Explorer && Explorer.refreshDir) Explorer.refreshDir(parent);
      } else {
        toast((res && res.msg) || "新建失败", "err");
      }
    } catch (e) {
      toast("新建出错：" + e, "err");
    }
  }

  /* 收藏当前文件 */
  async function favoriteFile(path) {
    const a = api();
    if (!a || !a.favorites_add) { toast("收藏失败：接口不可用", "err"); return; }
    try {
      const res = await a.favorites_add(path);
      if (res && res.ok) {
        toast(res.msg || "已收藏", "ok");
        if (window.Favorites && Favorites.isActive()) Favorites.refresh();
      } else {
        toast((res && res.msg) || "收藏失败", "err");
      }
    } catch (e) {
      toast("收藏出错：" + e, "err");
    }
  }

  /* 文件右键入口：弹出右键菜单 */
  function showFileContextMenu(path, x, y) {
    if (!window.ContextMenu) return;
    ContextMenu.open(x, y, [
      { icon: "⭐️", label: "收藏", action: "favorite" },
      { icon: "📋", label: "复制文件名称", action: "copy_name" },
      { icon: "🔗", label: "复制文件完整路径", action: "copy_path" },
      { icon: "📂", label: "在资源管理器中显示", action: "reveal" },
      { icon: "💻", label: "用 VSCode 打开", action: "vscode" },
      { icon: "📄", label: "复制副本", action: "duplicate" },
      { icon: "📁", label: "移动文件", action: "move" },
      { icon: "✏️", label: "重命名笔记", action: "rename" },
      { icon: "🗑️", label: "删除笔记", action: "delete", danger: true },
    ], (item) => {
      const act = item && item.action;
      if (act === "favorite") favoriteFile(path);
      else if (act === "copy_name") copyText(fileName(path), "已复制文件名称：" + fileName(path));
      else if (act === "copy_path") copyText(path, "已复制完整路径：" + path);
      else if (act === "reveal") revealInExplorer(path);
      else if (act === "vscode") openWithVSCode(path);
      else if (act === "duplicate") duplicateFile(path);
      else if (act === "move") moveFile(path);
      else if (act === "rename") renameFile(path);
      else if (act === "delete") deleteFile(path);
    });
  }

  /* 目录右键入口：弹出右键菜单（复制/显示/复制副本/移动/重命名/删除，无 VSCode） */
  function showDirContextMenu(path, x, y) {
    if (!window.ContextMenu) return;
    ContextMenu.open(x, y, [
      { icon: "📋", label: "复制目录名称", action: "copy_name" },
      { icon: "🔗", label: "复制目录完整路径", action: "copy_path" },
      { icon: "📂", label: "在资源管理器中显示", action: "reveal" },
      { icon: "📄", label: "复制副本", action: "duplicate" },
      { icon: "📁", label: "移动文件夹", action: "move" },
      { icon: "✏️", label: "重命名文件夹", action: "rename" },
      { icon: "📁", label: "新建文件夹", action: "new_folder" },
      { icon: "📝", label: "新建文件", action: "new_file" },
      { icon: "🗑️", label: "删除文件夹", action: "delete", danger: true },
    ], (item) => {
      const act = item && item.action;
      if (act === "copy_name") copyText(fileName(path), "已复制目录名称：" + fileName(path));
      else if (act === "copy_path") copyText(path, "已复制完整路径：" + path);
      else if (act === "reveal") revealInExplorer(path);
      else if (act === "duplicate") duplicateFile(path);
      else if (act === "move") moveFile(path);
      else if (act === "rename") renameFile(path, true);
      else if (act === "new_folder") newFolder(path);
      else if (act === "new_file") newFile(path);
      else if (act === "delete") deleteFile(path, true);
    });
  }

  /* 排序按钮图标/提示同步当前排序状态 */
  function updateSortButton(btn) {
    if (!btn || !window.Explorer) return;
    if (Explorer.getSort() === "time") {
      btn.textContent = "🕒";
      btn.title = "按最近修改排序（点击切换名称排序）";
    } else {
      btn.textContent = "🔤";
      btn.title = "按名称排序（点击切换时间排序）";
    }
  }

  /* 时间排序 ⇄ 名称排序切换（持久化到 config.json layout.explorer_sort） */
  function toggleSort(btn) {
    if (!window.Explorer) return;
    const next = Explorer.getSort() === "time" ? "name" : "time";
    Explorer.setSort(next);
    if (window.Layout && Layout.setExplorerSort) Layout.setExplorerSort(next);
    updateSortButton(btn);
    toast("已切换为" + (next === "time" ? "时间排序" : "名称排序"), "ok");
  }

  /* 显示/隐藏资源管理器栏（同步 Layout 状态并持久化） */
  function setVisible(v) {
    if (window.Layout && Layout.setWorkspaceVisible) Layout.setWorkspaceVisible(v);
  }

  function toggle() {
    const cur = window.Layout && Layout.isWorkspaceVisible ? Layout.isWorkspaceVisible() : false;
    setVisible(!cur);
  }

  /* 添加工作区文件夹：系统目录选择 → 后端登记 → 刷新 */
  async function addFolder() {
    const a = api();
    if (!a || !a.pick_workspace_folder) return;
    try {
      const picked = await a.pick_workspace_folder();
      if (!picked || !picked.ok || !picked.path) return;
      const res = await a.add_workspace_folder(picked.path);
      if (res && res.ok) {
        toast("已添加工作区：" + picked.path, "ok");
        refreshFolders();
      } else {
        toast((res && res.msg) || "添加失败", "err");
      }
    } catch (e) {
      toast("添加文件夹出错：" + e, "err");
    }
  }

  /* 移除工作区文件夹（带确认） */
  async function removeFolder(path) {
    if (!confirm("确认从工作区移除该文件夹？\n" + path)) return;
    const a = api();
    if (!a || !a.remove_workspace_folder) return;
    try {
      const res = await a.remove_workspace_folder(path);
      if (res && res.ok) {
        toast("已移除文件夹", "ok");
        refreshFolders();
      } else {
        toast((res && res.msg) || "移除失败", "err");
      }
    } catch (e) {
      toast("移除文件夹出错：" + e, "err");
    }
  }

  /* 上移/下移工作区文件夹（direction: "up" | "down"） */
  async function moveFolder(path, direction) {
    const a = api();
    if (!a || !a.move_workspace_folder) { toast("移动失败：接口不可用", "err"); return; }
    try {
      const res = await a.move_workspace_folder(path, direction);
      if (res && res.ok) {
        refreshFolders();
      } else {
        toast((res && res.msg) || "移动失败", "err");
      }
    } catch (e) {
      toast("移动出错：" + e, "err");
    }
  }

  /* Ctrl+H：显示资源管理器并聚焦搜索框 */
  function showSearch() {
    setVisible(true);
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
  }

  /* 清理搜索结果，恢复文件树（保持展开状态全量刷新） */
  function clearSearch() {
    if (window.Favorites && Favorites.isActive()) Favorites.close();
    if (window.Explorer && Explorer.refreshAll) {
      Explorer.refreshAll();
    } else {
      refreshFolders();
    }
  }

  function init() {
    pane = document.getElementById("pane-workspace");
    brandEl = document.getElementById("brand");
    treeEl = document.getElementById("workspace-tree");
    searchInput = document.getElementById("workspace-search-input");
    if (brandEl) brandEl.addEventListener("click", toggle);
    const addBtn = document.getElementById("btn-explorer-add");
    if (addBtn) addBtn.addEventListener("click", addFolder);
    const refreshBtn = document.getElementById("btn-workspace-refresh");
    if (refreshBtn) refreshBtn.addEventListener("click", () => { clearSearch(); });
    const expandBtn = document.getElementById("btn-explorer-expand");
    if (expandBtn) expandBtn.addEventListener("click", async () => {
      if (window.Explorer && Explorer.expandAll) await Explorer.expandAll();
    });
    const collapseBtn = document.getElementById("btn-explorer-collapse");
    if (collapseBtn) collapseBtn.addEventListener("click", () => {
      if (window.Explorer && Explorer.collapseAll) Explorer.collapseAll();
    });
    const sortBtn = document.getElementById("btn-explorer-sort");
    if (sortBtn) sortBtn.addEventListener("click", () => toggleSort(sortBtn));

    if (window.Explorer) {
      Explorer.init({
        container: treeEl,
        loadChildren,
        onOpenFile,
        onAddFolder: () => { addFolder(); },
        onRemoveFolder: (p) => { removeFolder(p); },
        onMoveFolder: (p, d) => { moveFolder(p, d); },
        onFileContext: (path, x, y) => { showFileContextMenu(path, x, y); },
        onDirContext: (path, x, y) => { showDirContextMenu(path, x, y); },
      });
      if (window.Layout && Layout.getExplorerSort) {
        Explorer.setSort(Layout.getExplorerSort());
      }
      updateSortButton(document.getElementById("btn-explorer-sort"));
    }

    if (window.Favorites) {
      Favorites.init({
        btn: document.getElementById("btn-favorites"),
        treeEl,
        onOpen: (path) => {
          Favorites.close(true);
          Explorer.reveal(path).then(() => onOpenFile(path));
        },
        onRefreshTree: () => {
          if (window.Explorer && Explorer.refreshAll) Explorer.refreshAll();
        },
      });
    }
  }

  /* 启动时由 script.js 在 Layout 应用后调用。
   * 无论面板是否可见都先构建资源树：保证打开文件时能自动定位高亮。 */
  async function start() {
    await refreshFolders();
    updateSortButton(document.getElementById("btn-explorer-sort"));
  }

  return { init, start, toggle, addFolder, removeFolder, showSearch, clearSearch, refreshFolders };
})();

window.Workspace = Workspace;
