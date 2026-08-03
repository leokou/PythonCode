/* LeoDiary Capture —— 收藏夹面板
 * 职责：⭐️ 按钮切换收藏面板；收藏列表渲染（收藏时间排序 + ↑↓ 自定义位置）；
 *      点击收藏项 → 定位资源管理器高亮选中 + 编辑器打开该文件。
 * 纯 UI：通过 init() 注入容器与回调，数据由后端 favorites_* API 提供。
 */
"use strict";

const Favorites = (() => {
  let btn = null;
  let treeEl = null;
  let onOpen = null;       // (path) => void 点击收藏项：定位 + 打开
  let onRefreshTree = null; // () => void 关闭面板时恢复文件树
  let active = false;

  function api() {
    return (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  }

  function fileName(path) {
    const p = String(path || "");
    const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
    return i >= 0 ? p.slice(i + 1) : p;
  }

  /* 单个收藏项：文件名 + 上移/下移/取消收藏按钮 */
  function renderRow(item, idx, total) {
    const row = document.createElement("div");
    row.className = "search-hit fav-row";
    row.title = item.path;

    const head = document.createElement("div");
    head.className = "search-hit-head";
    const nameEl = document.createElement("span");
    nameEl.className = "search-hit-name";
    nameEl.textContent = item.name || fileName(item.path);
    head.appendChild(nameEl);

    const ops = document.createElement("span");
    ops.className = "fav-ops";

    const mkBtn = (text, title, disabled, onClick) => {
      const b = document.createElement("button");
      b.className = "fav-btn";
      b.textContent = text;
      b.title = title;
      b.disabled = !!disabled;
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        onClick();
      });
      return b;
    };

    ops.appendChild(mkBtn("↑", "上移（首项循环到末尾）", false, () => move(item.path, "up")));
    ops.appendChild(mkBtn("↓", "下移（末项循环到开头）", false, () => move(item.path, "down")));
    ops.appendChild(mkBtn("✕", "取消收藏", false, () => remove(item.path)));
    head.appendChild(ops);

    row.appendChild(head);
    row.addEventListener("click", () => {
      if (onOpen) onOpen(item.path);
    });
    return row;
  }

  function render(items) {
    if (!treeEl) return;
    treeEl.innerHTML = "";
    const title = document.createElement("div");
    title.className = "search-hit-title";
    title.textContent = "⭐️ 收藏夹（" + items.length + "）";
    treeEl.appendChild(title);
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "tree-empty";
      empty.textContent = "还没有收藏任何文件\n在资源管理器中右键文件 → 收藏";
      treeEl.appendChild(empty);
      return;
    }
    items.forEach((it, i) => treeEl.appendChild(renderRow(it, i, items.length)));
  }

  async function loadItems() {
    const a = api();
    if (!a || !a.favorites_list) return [];
    try {
      const res = await a.favorites_list();
      return (res && res.ok && res.items) ? res.items : [];
    } catch (e) {
      return [];
    }
  }

  async function refresh() {
    if (!active) return;
    render(await loadItems());
  }

  async function toggle() {
    active = !active;
    if (btn) btn.classList.toggle("active", active);
    if (active) {
      render(await loadItems());
    } else if (onRefreshTree) {
      onRefreshTree();
    }
  }

  /* 关闭收藏面板。skipRefresh=true 时不刷新树（由调用方随后 reveal 定位） */
  function close(skipRefresh) {
    if (!active) return;
    active = false;
    if (btn) btn.classList.remove("active");
    if (!skipRefresh && onRefreshTree) onRefreshTree();
  }

  /* ↑↓ 自定义位置 */
  async function move(path, direction) {
    const a = api();
    if (!a || !a.favorites_move) return;
    try {
      const res = await a.favorites_move(path, direction);
      if (res && res.ok) {
        render(await loadItems());
      } else {
        window.toast((res && res.msg) || "移动失败", "err");
      }
    } catch (e) {
      window.toast("移动出错：" + e, "err");
    }
  }

  /* 取消收藏 */
  async function remove(path) {
    const a = api();
    if (!a || !a.favorites_remove) return;
    try {
      const res = await a.favorites_remove(path);
      if (res && res.ok) {
        window.toast(res.msg || "已取消收藏", "ok");
        render(await loadItems());
      } else {
        window.toast((res && res.msg) || "取消收藏失败", "err");
      }
    } catch (e) {
      window.toast("取消收藏出错：" + e, "err");
    }
  }

  function init(opts) {
    btn = (opts && opts.btn) || document.getElementById("btn-favorites");
    treeEl = (opts && opts.treeEl) || document.getElementById("workspace-tree");
    onOpen = (opts && opts.onOpen) || null;
    onRefreshTree = (opts && opts.onRefreshTree) || null;
    if (btn) btn.addEventListener("click", toggle);
  }

  return { init, toggle, close, refresh, isActive: () => active };
})();

window.Favorites = Favorites;

