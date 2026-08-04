/* tab-manager.js —— Tab 创建/关闭/状态显示 + 关闭确认/删除确认/恢复提示弹窗
 *
 * 职责：
 *  - Tab DOM 渲染（含保存状态徽标：已保存 / 保存中… / 未保存 *）
 *  - 关闭确认弹窗（删除=红 / 保存=绿）
 *  - 删除二次确认弹窗
 *  - 启动恢复提示弹窗
 *
 * 纯 UI 层，不直接操作编辑器数据；由 script.js 注入回调。
 */
"use strict";

window.TabManager = (() => {
  let _alwaysGray = false;

  const STATUS_TEXT = {
    saved: "已保存",
    saving: "保存中…",
    unsaved: "未保存",
    error: "保存失败",
  };

  /* ---- 通用弹窗 ---- */
  function openModal(innerHTML) {
    closeModal();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.id = "modal-overlay";
    overlay.innerHTML =
      `<div class="modal-card">${innerHTML}</div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) closeModal();
    });
    return overlay;
  }

  function closeModal() {
    const m = document.getElementById("modal-overlay");
    if (m) m.remove();
  }

  /* ---- Tab DOM ---- */
  function tabHTML(tab, activeId) {
    const title = tab.title || "未命名";
    const status = tab.status || "saved";
    const statusText = STATUS_TEXT[status] || status;
    const pinIcon = tab.pinned ? `<span class="tab-pin" title="已锁定">🔒</span>` : "";
    return (
      `${pinIcon}` +
      `<span class="tab-name">${escapeHTML(title)}</span>` +
      `<span class="tab-status ${status}" title="${statusText}" aria-label="${statusText}"></span>` +
      `<button class="tab-close" title="${tab.pinned ? '已锁定，无法直接关闭' : '关闭页签'}">×</button>`
    );
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function setTabStatus(el, status) {
    const badge = el.querySelector(".tab-status");
    if (!badge) return;
    const effectiveStatus = _alwaysGray ? "unsaved" : status;
    const text = STATUS_TEXT[effectiveStatus] || effectiveStatus;
    badge.className = "tab-status " + effectiveStatus;
    badge.title = text;
    badge.setAttribute("aria-label", text);
  }

  function updateTabName(el, title) {
    const name = el.querySelector(".tab-name");
    if (name) name.textContent = title || "未命名";
    el.title = title || "未命名";
  }

  function setTabPinned(el, pinned) {
    el.classList.toggle("pinned", !!pinned);
    const pinIcon = el.querySelector(".tab-pin");
    if (pinned) {
      if (!pinIcon) {
        const span = document.createElement("span");
        span.className = "tab-pin";
        span.title = "已锁定";
        span.textContent = "🔒";
        el.insertBefore(span, el.firstChild);
      }
    } else {
      if (pinIcon) pinIcon.remove();
    }
    const closeBtn = el.querySelector(".tab-close");
    if (closeBtn) {
      closeBtn.title = pinned ? "已锁定，无法直接关闭" : "关闭页签";
      closeBtn.style.cursor = pinned ? "not-allowed" : "";
    }
  }

  /* ---- 渲染页签列表：只重建 .tab，保留末尾的「＋ 新增」按钮 ---- */
  function renderTabs(listEl, addBtnEl, tabs, activeId, onClick, onContextMenu) {
    listEl.querySelectorAll(".tab").forEach((el) => el.remove());
    for (const tab of tabs) {
      const el = document.createElement("div");
      el.className = "tab" + (tab.id === activeId ? " active" : "") + (tab.pinned ? " pinned" : "");
      el.dataset.id = String(tab.id);
      el.draggable = true;
      el.title = tab.title || "未命名";
      el.innerHTML = tabHTML(tab, activeId);
      el.addEventListener("click", (e) => {
        if (e.target.closest(".tab-close")) {
          e.stopPropagation();
          if (tab.pinned) return; /* 锁定页签不可直接关闭 */
          onClick && onClick("close", tab.id);
          return;
        }
        onClick && onClick("activate", tab.id);
      });
      el.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        e.stopPropagation();
        onContextMenu && onContextMenu(e, tab);
      });
      listEl.insertBefore(el, addBtnEl);
    }
  }

  /* ---- 关闭确认弹窗（左删除红 / 右保存绿） ---- */
  function confirmClose(tabName, onDelete, onSave, options) {
    const isBatch = options && options.batch;
    const title = isBatch ? (options.title || "是否保存这些页签？") : "是否保存当前内容？";
    const msg = isBatch
      ? (options.message || `「${escapeHTML(tabName || "未命名")}」即将关闭。`)
      : `页签「${escapeHTML(tabName || "未命名")}」即将关闭。`;
    openModal(
      `<div class="modal-title">${escapeHTML(title)}</div>` +
      `<div class="modal-msg">${msg}</div>` +
      `<div class="modal-btns">` +
        `<button class="btn-modal danger" data-act="delete">删除</button>` +
        `<button class="btn-modal success" data-act="save">保存</button>` +
      `</div>`
    );
    const overlay = document.getElementById("modal-overlay");
    overlay.querySelector('[data-act="delete"]').addEventListener("click", () => {
      closeModal();
      onDelete && onDelete();
    });
    overlay.querySelector('[data-act="save"]').addEventListener("click", () => {
      closeModal();
      onSave && onSave();
    });
  }

  /* ---- 删除二次确认弹窗 ---- */
  function confirmDelete(onConfirm) {
    openModal(
      `<div class="modal-title">确认删除？</div>` +
      `<div class="modal-msg danger-text">将删除当前页面对应的 Markdown 文件，删除后不可恢复。</div>` +
      `<div class="modal-btns">` +
        `<button class="btn-modal neutral" data-act="cancel">取消</button>` +
        `<button class="btn-modal danger" data-act="confirm">确认删除</button>` +
      `</div>`
    );
    const overlay = document.getElementById("modal-overlay");
    overlay.querySelector('[data-act="cancel"]').addEventListener("click", closeModal);
    overlay.querySelector('[data-act="confirm"]').addEventListener("click", () => {
      closeModal();
      onConfirm && onConfirm();
    });
  }

  return {
    renderTabs,
    setTabStatus,
    setTabPinned,
    updateTabName,
    confirmClose,
    confirmDelete,
    closeModal,
    escapeHTML,
    setAlwaysGray(v) { _alwaysGray = !!v; },
  };
})();
