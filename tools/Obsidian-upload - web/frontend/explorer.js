/* LeoDiary Capture —— 资源管理器（File Explorer）
 * 职责：目录树渲染（懒加载）、展开收起、文件点击、高亮/自动定位、排序。
 * 纯 UI：数据由 Workspace 注入（loadChildren 异步回调），可单独替换。
 * 排序偏好由调用方通过 setSort 传入（对应 config.json layout.explorer_sort）。
 */
"use strict";

const Explorer = (() => {
  let container = null;
  let loadChildren = null;   // async (path, sort) => [{name,path,type,ext,mtime}, ...]
  let onOpenFile = null;     // (path) => void
  let onAddFolder = null;    // () => void（空状态添加按钮）
  let onRemoveFolder = null; // (path) => void（移除工作区文件夹）
  let onMoveFolder = null;   // (path, direction) => void（上移/下移工作区文件夹）
  let onFileContext = null;  // (path, x, y) => void（文件右键菜单）
  let onDirContext = null;   // (path, x, y) => void（目录右键菜单）
  let sort = "time";         // "time"（最近修改倒序）| "name"（名称 A-Z）
  let lastFolders = null;    // 最近一次 renderFolders 的文件夹列表
  let activePath = null;     // 当前高亮文件路径（规范化小写）
  let revealToken = 0;       // 防止并发 reveal 竞态

  const MAX_DEPTH = 12;

  function norm(p) {
    return String(p || "").replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
  }

  function init(opts) {
    container = (opts && opts.container) || null;
    loadChildren = (opts && opts.loadChildren) || null;
    onOpenFile = (opts && opts.onOpenFile) || null;
    onAddFolder = (opts && opts.onAddFolder) || null;
    onRemoveFolder = (opts && opts.onRemoveFolder) || null;
    onMoveFolder = (opts && opts.onMoveFolder) || null;
    onFileContext = (opts && opts.onFileContext) || null;
    onDirContext = (opts && opts.onDirContext) || null;
  }

  function setSort(s) {
    sort = s === "name" ? "name" : "time";
    if (lastFolders) renderFolders(lastFolders); /* 排序变化：整树重建（默认收起） */
  }

  function getSort() { return sort; }

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
    row.className = "exp-row " + cls;
    row.title = title || "";
    row.dataset.name = name;
    const arrow = document.createElement("span");
    arrow.className = "exp-arrow";
    arrow.textContent = cls.indexOf("exp-file") >= 0 ? "" : "▸";
    const iconEl = document.createElement("span");
    iconEl.className = "exp-icon";
    iconEl.textContent = icon;
    const nameEl = document.createElement("span");
    nameEl.className = "exp-name";
    nameEl.textContent = name;
    row.appendChild(arrow);
    row.appendChild(iconEl);
    row.appendChild(nameEl);
    return row;
  }

  function buildChildrenBox() {
    const box = document.createElement("div");
    box.className = "exp-children";
    return box;
  }

  function buildFileRow(item) {
    const row = makeRow("exp-file", fileIcon(item.ext), item.name, item.path);
    row.dataset.path = item.path;
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      setActive(item.path);
      if (onOpenFile) onOpenFile(item.path);
    });
    /* 文件右键菜单：禁止默认菜单，交由 workspace.js 处理 */
    row.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      e.stopPropagation();
      setActive(item.path);
      if (onFileContext) onFileContext(item.path, e.clientX, e.clientY);
    });
    return row;
  }

  function buildDirRow(item) {
    const row = makeRow("exp-dir", "📁", item.name, item.path);
    row.dataset.path = item.path;
    const box = buildChildrenBox();
    row.appendChild(box);
    row.classList.add("exp-collapsed");
    row.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (e.target.closest(".exp-del")) return;
      await toggleDir(row, item.path);
    });
    /* 目录右键菜单：禁止默认菜单，交由 workspace.js 处理 */
    row.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (onDirContext) onDirContext(item.path, e.clientX, e.clientY);
    });
    return row;
  }

  async function expandDir(row, path) {
    row.classList.add("exp-loading");
    let items = [];
    try {
      if (loadChildren) items = (await loadChildren(path, sort)) || [];
    } catch (e) { /* 扫描失败按空处理 */ }
    row.classList.remove("exp-loading");
    const box = row.querySelector(".exp-children");
    box.innerHTML = "";
    for (const it of items) {
      const child = it.type === "dir" ? buildDirRow(it) : buildFileRow(it);
      box.appendChild(child);
    }
  }

  async function toggleDir(row, path) {
    if (row.classList.contains("exp-collapsed")) {
      await expandDir(row, path);
      row.classList.remove("exp-collapsed");
      row.classList.add("exp-expanded");
      row.querySelector(".exp-arrow").textContent = "▾";
    } else {
      collapseDir(row);
    }
  }

  function collapseDir(row) {
    row.classList.add("exp-collapsed");
    row.classList.remove("exp-expanded");
    row.querySelector(".exp-arrow").textContent = "▸";
  }

  /* 渲染工作区文件夹层（顶级），空状态带添加入口 */
  function renderFolders(folders) {
    lastFolders = folders || [];
    activePath = null;
    if (!container) return;
    container.innerHTML = "";
    if (!lastFolders.length) {
      const empty = document.createElement("div");
      empty.className = "exp-empty";
      empty.innerHTML = "尚未添加工作区文件夹";
      const btn = document.createElement("button");
      btn.className = "exp-add-btn";
      btn.textContent = "＋ 添加文件夹";
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (onAddFolder) onAddFolder();
      });
      empty.appendChild(btn);
      container.appendChild(empty);
      return;
    }
    for (const f of lastFolders) {
      const row = makeRow("exp-folder exp-dir", "🗂️", f.name, f.path);
      row.dataset.path = f.path;
      const mvUp = document.createElement("button");
      mvUp.className = "exp-mv";
      mvUp.title = "上移文件夹";
      mvUp.textContent = "↑";
      mvUp.addEventListener("click", (e) => {
        e.stopPropagation();
        if (onMoveFolder) onMoveFolder(f.path, "up");
      });
      row.appendChild(mvUp);
      const mvDown = document.createElement("button");
      mvDown.className = "exp-mv";
      mvDown.title = "下移文件夹";
      mvDown.textContent = "↓";
      mvDown.addEventListener("click", (e) => {
        e.stopPropagation();
        if (onMoveFolder) onMoveFolder(f.path, "down");
      });
      row.appendChild(mvDown);
      const del = document.createElement("button");
      del.className = "exp-del";
      del.title = "移除该文件夹";
      del.textContent = "✕";
      del.addEventListener("click", (e) => {
        e.stopPropagation();
        if (onRemoveFolder) onRemoveFolder(f.path);
      });
      row.appendChild(del);
      row.appendChild(buildChildrenBox());
      row.classList.add("exp-collapsed");
      row.addEventListener("click", async (e) => {
        if (e.target.closest(".exp-del")) return;
        await toggleDir(row, f.path);
      });
      container.appendChild(row);
    }
  }

  /* 高亮当前文件（编辑/预览/资源树三态一致），并滚动到可见位置 */
  function setActive(path) {
    const n = norm(path);
    activePath = n;
    if (!container) return;
    container.querySelectorAll(".exp-row.exp-active").forEach((el) => el.classList.remove("exp-active"));
    if (!n) return;
    for (const r of container.querySelectorAll(".exp-row[data-path]")) {
      if (norm(r.dataset.path) === n) {
        r.classList.add("exp-active");
        try { r.scrollIntoView({ block: "nearest" }); } catch (e) { /* ignore */ }
        break;
      }
    }
  }

  function highlight(path) { setActive(path); }

  function relativeSegments(from, to) {
    const f = norm(from);
    const t = norm(to);
    if (t === f) return [];
    if (!t.startsWith(f)) return null;
    const rest = t.slice(f.length).replace(/^\//, "");
    if (!rest) return [];
    return rest.split("/").filter(Boolean);
  }

  function findDirChild(row, name) {
    const n = String(name || "").toLowerCase();
    const box = row.querySelector(".exp-children");
    if (!box) return null;
    for (const child of box.children) {
      if (child.classList.contains("exp-dir") && norm(child.dataset.name) === n) return child;
    }
    return null;
  }

  async function expandTo(row, dirPath, segments) {
    if (row.classList.contains("exp-collapsed")) {
      await toggleDir(row, dirPath);
    }
    if (!segments || !segments.length) return;
    const next = findDirChild(row, segments[0]);
    if (next && next.dataset.path) {
      await expandTo(next, next.dataset.path, segments.slice(1));
    }
  }

  /* 打开/切换文件时自动展开父目录并高亮目标文件（懒加载逐层展开） */
  async function reveal(path) {
    if (!container || !path) return;
    const token = ++revealToken;
    const t = norm(path);
    if (!lastFolders || !lastFolders.length) return;
    if (!container.querySelector(".exp-folder")) renderFolders(lastFolders);
    const root = lastFolders.find((f) => t === norm(f.path) || t.startsWith(norm(f.path) + "/"));
    if (!root) return;
    const rootRow = [...container.querySelectorAll(".exp-folder")].find(
      (r) => norm(r.dataset.path) === norm(root.path));
    if (!rootRow) return;
    const segs = relativeSegments(root.path, path);
    await expandTo(rootRow, root.path, segs || []);
    if (token !== revealToken) return; /* 期间又有新的 reveal，放弃本次 */
    setActive(path);
  }

  /* 收集当前所有已展开的目录路径（含顶级，深度优先） */
  function collectExpanded() {
    const out = [];
    const walk = (rows) => {
      for (const r of rows) {
        if (r.classList.contains("exp-dir") && !r.classList.contains("exp-collapsed")) {
          out.push(r.dataset.path);
          const box = r.querySelector(".exp-children");
          if (box) walk(box.children);
        }
      }
    };
    if (container) walk(container.querySelectorAll(":scope > .exp-folder"));
    return out;
  }

  /* 局部刷新指定目录：重载其子项并保持该目录展开状态。
   * 折叠目录跳过（下次展开时 expandDir 总会重新加载，天然最新）。 */
  async function refreshDir(dirPath) {
    if (!container || !dirPath) return;
    const n = norm(dirPath);
    for (const row of container.querySelectorAll(".exp-dir[data-path]")) {
      if (norm(row.dataset.path) === n) {
        if (!row.classList.contains("exp-collapsed")) {
          await expandDir(row, row.dataset.path);
        }
        break;
      }
    }
    if (activePath) setActive(activePath);
  }

  /* 全量刷新：重建顶级层后逐层恢复展开并重载，保持原有展开结构 */
  async function refreshAll() {
    if (!container) return;
    const wasActive = activePath;
    const expanded = collectExpanded();
    renderFolders(lastFolders);
    for (const p of expanded) {
      const row = [...container.querySelectorAll(".exp-dir[data-path]")].find(
        (r) => norm(r.dataset.path) === norm(p));
      if (row && row.classList.contains("exp-collapsed")) {
        await toggleDir(row, row.dataset.path);
      }
    }
    if (wasActive) setActive(wasActive);
  }

  /* 一键全部展开（懒加载逐层展开，带深度上限防失控） */
  async function expandAll() {
    const roots = [...container.querySelectorAll(":scope > .exp-folder")];
    for (const r of roots) await expandRec(r, 0);
  }

  async function expandRec(row, depth) {
    if (depth > MAX_DEPTH) return;
    if (row.classList.contains("exp-collapsed")) {
      await toggleDir(row, row.dataset.path);
    }
    if (depth >= MAX_DEPTH) return;
    const box = row.querySelector(".exp-children");
    if (!box) return;
    for (const child of [...box.children]) {
      if (child.classList.contains("exp-dir")) {
        await expandRec(child, depth + 1);
      }
    }
  }

  /* 一键全部收起（回到仅工作区文件夹层） */
  function collapseAll() {
    const rows = [...container.querySelectorAll(".exp-dir.exp-expanded")];
    for (const r of rows) collapseDir(r);
  }

  return {
    init, setSort, getSort, renderFolders,
    reveal, highlight, expandAll, collapseAll,
    refreshDir, refreshAll,
  };
})();

window.Explorer = Explorer;
