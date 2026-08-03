/* LeoDiary Capture —— 通用右键菜单（Context Menu）
 * 职责：在指定坐标弹出菜单、点击外部关闭、菜单项点击回调。
 * 同时提供「重命名输入框」与「确认删除」两个弹层（复用 modal 样式）。
 * 纯 UI：通过 open(x, y, items, onPick) 调用，items=[{label, icon, danger, action}]。
 */
"use strict";

window.ContextMenu = (() => {
  let menuEl = null;

  function close() {
    if (menuEl) {
      menuEl.remove();
      menuEl = null;
    }
    document.removeEventListener("mousedown", onOutside, true);
  }

  function onOutside(e) {
    if (menuEl && !menuEl.contains(e.target)) close();
  }

  /* 弹出右键菜单（自动校正越界位置） */
  function open(x, y, items, onPick) {
    close();
    if (!items || !items.length) return;
    menuEl = document.createElement("div");
    menuEl.className = "ctx-menu";
    menuEl.innerHTML = items.map((it, i) =>
      `<div class="ctx-item${it.danger ? " danger" : ""}${it.disabled ? " disabled" : ""}" data-i="${i}" title="${it.label}">` +
        `<span class="ctx-icon">${it.icon || ""}</span>` +
        `<span class="ctx-label">${escapeHTML(it.label)}</span>` +
        (it.shortcut ? `<span class="ctx-kbd">${escapeHTML(it.shortcut)}</span>` : "") +
      `</div>`).join("");
    document.body.appendChild(menuEl);
    menuEl.addEventListener("click", (e) => {
      const item = e.target.closest(".ctx-item");
      if (!item) return;
      const i = Number(item.dataset.i);
      const it = items[i];
      if (!it || it.disabled) return;
      close();
      if (onPick) onPick(it);
    });
    /* 边界校正：不超出窗口 */
    const rect = menuEl.getBoundingClientRect();
    let px = x;
    let py = y;
    if (px + rect.width > window.innerWidth - 4) px = window.innerWidth - rect.width - 4;
    if (py + rect.height > window.innerHeight - 4) py = window.innerHeight - rect.height - 4;
    menuEl.style.left = Math.max(4, px) + "px";
    menuEl.style.top = Math.max(4, py) + "px";
    document.addEventListener("mousedown", onOutside, true);
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  /* 关闭所有菜单/弹层 */
  function closeModal() {
    close();
    const m = document.getElementById("modal-overlay");
    if (m) m.remove();
  }

  /* ---- 重命名输入框弹层：onConfirm(newName) ---- */
  function renameDialog(initial, onConfirm) {
    closeModal();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.id = "modal-overlay";
    overlay.innerHTML =
      `<div class="modal-card">` +
        `<div class="modal-title">重命名</div>` +
        `<div class="modal-msg">输入新名称（不含扩展名，自动保留原扩展名）：</div>` +
        `<input class="modal-input" id="ctx-rename-input" value="${escapeHTML(initial)}" spellcheck="false">` +
        `<div class="modal-btns">` +
          `<button class="btn-modal neutral" data-act="cancel">取消</button>` +
          `<button class="btn-modal success" data-act="ok">确定</button>` +
        `</div>` +
      `</div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) closeModal();
    });
    const input = overlay.querySelector("#ctx-rename-input");
    const submit = () => {
      const val = input.value.trim();
      closeModal();
      if (val && onConfirm) onConfirm(val);
    };
    overlay.querySelector('[data-act="cancel"]').addEventListener("click", closeModal);
    overlay.querySelector('[data-act="ok"]').addEventListener("click", submit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submit();
      if (e.key === "Escape") closeModal();
    });
    setTimeout(() => { input.focus(); input.select(); }, 50);
  }

  /* ---- 确认删除弹层：onConfirm() ---- */
  function confirmDialog(title, msg, confirmText, onConfirm) {
    closeModal();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.id = "modal-overlay";
    overlay.innerHTML =
      `<div class="modal-card">` +
        `<div class="modal-title">${escapeHTML(title)}</div>` +
        `<div class="modal-msg danger-text">${escapeHTML(msg)}</div>` +
        `<div class="modal-btns">` +
          `<button class="btn-modal neutral" data-act="cancel">取消</button>` +
          `<button class="btn-modal danger" data-act="ok">${escapeHTML(confirmText || "确定")}</button>` +
        `</div>` +
      `</div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) closeModal();
    });
    overlay.querySelector('[data-act="cancel"]').addEventListener("click", closeModal);
    overlay.querySelector('[data-act="ok"]').addEventListener("click", () => {
      closeModal();
      if (onConfirm) onConfirm();
    });
  }

  /* ---- 移动弹层：可展开/收缩的目录树 + 检索，点击目录行直接移动 ----
   * dirs = [{path, level, name, rel}]（level=相对工作区根的层级）。
   * currentPath：被移动项路径，其自身与子目录不可作为目标。
   * 默认只展开工作区根（显示一二级文件夹），点击箭头展开/收缩；
   * 检索后仅显示匹配目录及其祖先，点任意匹配行即移动。
   */
  function moveDialog(dirs, currentPath, onPick) {
    closeModal();
    const dirList = dirs || [];
    const cur = String(currentPath || "");
    const curNorm = cur.toLowerCase();
    const invalid = new Set();
    for (const d of dirList) {
      const p = String(d.path || "").toLowerCase();
      if (p === curNorm || p.indexOf(curNorm + "\\") === 0 || p.indexOf(curNorm + "/") === 0) {
        invalid.add(p);
      }
    }

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.id = "modal-overlay";
    const card = document.createElement("div");
    card.className = "modal-card move-card";
    card.innerHTML =
      `<div class="modal-title">移动到</div>` +
      `<input class="modal-input" id="ctx-move-search" placeholder="检索目录名称…" spellcheck="false">` +
      `<div class="move-list" id="ctx-move-list"></div>` +
      `<div class="modal-btns">` +
        `<button class="btn-modal neutral" data-act="cancel">取消</button>` +
      `</div>`;
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    const listEl = card.querySelector("#ctx-move-list");
    const searchEl = card.querySelector("#ctx-move-search");
    let searchTimer = null;
    let kw = "";

    /* 构建目录树：过滤无效目标（自身/子目录），按路径排序保证父在前 */
    const nodes = new Map();
    const roots = [];
    for (const d of dirList) {
      if (invalid.has(String(d.path).toLowerCase())) continue;
      nodes.set(String(d.path).toLowerCase(), {
        item: d, children: [], parent: null,
        expanded: false, match: false, subMatch: false,
      });
    }
    const sorted = [...nodes.values()].sort((a, b) =>
      String(a.item.path).toLowerCase() < String(b.item.path).toLowerCase() ? -1 : 1);
    for (const node of sorted) {
      const p = String(node.item.path).toLowerCase();
      let parent = null;
      for (const [pk, n] of nodes) {
        if (pk !== p && p.indexOf(pk + "\\") === 0 && n.item.level === node.item.level - 1) parent = n;
      }
      if (parent) { parent.children.push(node); node.parent = parent; }
      else roots.push(node);
    }
    for (const r of roots) r.expanded = true;   /* 默认展开根：显示到一二级文件夹 */

    function matchNode(node, k) {
      return String(node.item.name || "").toLowerCase().indexOf(k) >= 0 ||
             String(node.item.rel || "").toLowerCase().indexOf(k) >= 0;
    }

    function computeSearch() {
      const calc = (node) => {
        node.match = matchNode(node, kw);
        node.subMatch = node.match;
        for (const c of node.children) { calc(c); node.subMatch = node.subMatch || c.subMatch; }
        return node.subMatch;
      };
      for (const r of roots) calc(r);
      const expandAncestors = (node) => {
        let p = node.parent;
        while (p) { p.expanded = true; p = p.parent; }
      };
      const apply = (node) => {
        if (node.match) expandAncestors(node);
        for (const c of node.children) apply(c);
      };
      for (const r of roots) apply(r);
    }

    function render() {
      if (kw) {
        computeSearch();
      } else {
        const clearMatch = (n) => {
          n.match = false; n.subMatch = false;
          for (const c of n.children) clearMatch(c);
        };
        for (const r of roots) clearMatch(r);
      }
      listEl.innerHTML = "";
      let shown = 0;
      const emit = (node) => {
        if (kw && !node.subMatch) return;
        const d = node.item;
        const hasChildren = node.children.length > 0;
        const row = document.createElement("div");
        row.className = "move-row" + (node.match ? " match" : "");
        row.title = d.path + "（点击移动）";
        row.style.paddingLeft = (12 + d.level * 16) + "px";
        row.innerHTML =
          `<span class="exp-arrow">${hasChildren ? (node.expanded ? "▾" : "▸") : ""}</span>` +
          `<span class="ctx-icon">${d.level === 0 ? "🗂️" : "📁"}</span>` +
          `<span class="ctx-label">${escapeHTML(d.name || d.path)}</span>` +
          (kw && d.rel !== "." ? `<span class="move-rel">${escapeHTML(d.rel)}</span>` : "");
        row.addEventListener("click", (e) => {
          e.stopPropagation();
          if (e.target.closest(".exp-arrow")) {
            node.expanded = !node.expanded;
            render();
            return;
          }
          closeModal();
          if (onPick) onPick(d.path);
        });
        listEl.appendChild(row);
        shown++;
        if (node.expanded) for (const c of node.children) emit(c);
      };
      for (const r of roots) emit(r);
      if (!shown) {
        listEl.innerHTML = `<div class="move-empty">${kw ? "没有匹配的目录" : "没有可移动的目录"}</div>`;
      }
    }

    searchEl.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => { kw = searchEl.value; render(); }, 200);
    });
    searchEl.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
    card.querySelector('[data-act="cancel"]').addEventListener("click", closeModal);
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) closeModal();
    });
    render();
    setTimeout(() => { searchEl.focus(); }, 50);
  }

  return { open, close, closeModal, renameDialog, confirmDialog, moveDialog };
})();
