/* LeoDiary Capture —— 文件树渲染
 * 职责：渲染工作区文件夹树（目录懒加载），维护展开状态，文件点击回调。
 * 纯 UI：数据由 Workspace 注入（loadChildren 异步回调），可单独替换。
 */
"use strict";

const FileTree = (() => {
  let container = null;
  let loadChildren = null;   // async (path) => [{name,path,type,ext}, ...]
  let onOpenFile = null;     // (path) => void

  function init(opts) {
    container = (opts && opts.container) || null;
    loadChildren = (opts && opts.loadChildren) || null;
    onOpenFile = (opts && opts.onOpenFile) || null;
  }

  function fileIcon(ext) {
    if (ext === "md") return "📝";
    if (ext === "py") return "🐍";
    if (ext === "js") return "🟨";
    if (ext === "json") return "🧾";
    if (ext === "yaml" || ext === "yml") return "⚙️";
    if (ext === "txt") return "📄";
    return "🗒️";
  }

  function makeRow(cls, icon, name, title) {
    const row = document.createElement("div");
    row.className = "tree-row " + cls;
    row.title = title || "";
    const iconEl = document.createElement("span");
    iconEl.className = "tree-icon";
    iconEl.textContent = icon;
    const nameEl = document.createElement("span");
    nameEl.className = "tree-name";
    nameEl.textContent = name;
    row.appendChild(iconEl);
    row.appendChild(nameEl);
    return { row, nameEl };
  }

  function buildChildrenBox() {
    const box = document.createElement("div");
    box.className = "tree-children";
    return box;
  }

  function buildFileRow(item) {
    const { row } = makeRow("tree-file", fileIcon(item.ext), item.name, item.path);
    row.dataset.path = item.path;
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      if (onOpenFile) onOpenFile(item.path);
    });
    return row;
  }

  function buildDirRow(item) {
    const { row } = makeRow("tree-dir", "📁", item.name, item.path);
    row.dataset.path = item.path;
    const arrow = document.createElement("span");
    arrow.className = "tree-arrow";
    arrow.textContent = "▸";
    row.insertBefore(arrow, row.firstChild);

    const childrenBox = buildChildrenBox();
    row.appendChild(childrenBox);
    row.classList.add("tree-dir-collapsed");

    row.addEventListener("click", async (e) => {
      if (e.target.closest(".tree-del")) return;
      await toggleDir(row, item.path);
    });
    return row;
  }

  async function toggleDir(row, path) {
    if (row.classList.contains("tree-dir-collapsed")) {
      await expandDir(row, path);
    } else {
      collapseDir(row);
    }
  }

  async function expandDir(row, path) {
    row.classList.add("tree-loading");
    const childrenBox = row.querySelector(".tree-children");
    let items = [];
    try {
      if (loadChildren) items = (await loadChildren(path)) || [];
    } catch (e) { /* 扫描失败按空处理 */ }
    row.classList.remove("tree-loading");
    childrenBox.innerHTML = "";
    for (const it of items) {
      const child = it.type === "dir" ? buildDirRow(it) : buildFileRow(it);
      childrenBox.appendChild(child);
    }
    row.classList.remove("tree-dir-collapsed");
    row.classList.add("tree-dir-expanded");
    row.querySelector(".tree-arrow").textContent = "▾";
  }

  function collapseDir(row) {
    row.classList.add("tree-dir-collapsed");
    row.classList.remove("tree-dir-expanded");
    row.querySelector(".tree-arrow").textContent = "▸";
  }

  /* 渲染文件夹层（顶级），空状态带添加入口 */
  function renderFolders(folders) {
    if (!container) return;
    container.innerHTML = "";
    if (!folders || !folders.length) {
      const empty = document.createElement("div");
      empty.className = "tree-empty";
      empty.innerHTML = "尚未添加工作区文件夹";
      const btn = document.createElement("button");
      btn.className = "tree-add-btn";
      btn.textContent = "＋ 添加文件夹";
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.Workspace && Workspace.addFolder) Workspace.addFolder();
      });
      empty.appendChild(btn);
      container.appendChild(empty);
      return;
    }
    for (const f of folders) {
      const { row } = makeRow("tree-folder", "🗂️", f.name, f.path);
      row.dataset.path = f.path;
      const del = document.createElement("button");
      del.className = "tree-del";
      del.title = "移除该文件夹";
      del.textContent = "✕";
      del.addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.Workspace && Workspace.removeFolder) Workspace.removeFolder(f.path);
      });
      row.appendChild(del);
      row.appendChild(buildChildrenBox());
      row.classList.add("tree-dir-collapsed");
      row.addEventListener("click", (e) => {
        if (e.target.closest(".tree-del")) return;
        toggleDir(row, f.path);
      });
      container.appendChild(row);
    }
  }

  return { init, renderFolders };
})();

window.FileTree = FileTree;
