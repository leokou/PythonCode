/* LeoDiary Tools —— 工具箱前端逻辑
 * 功能：读取工具列表、卡片网格渲染、点击执行、HTML5 拖动排序并持久化。
 */
"use strict";

const gridEl = document.getElementById("tool-grid");
const statusEl = document.getElementById("status");
const toastEl = document.getElementById("toast");

let tools = [];
let suppressClick = false;

function setStatus(msg) { statusEl.textContent = msg; }

let toastTimer = null;
function toast(msg, kind) {
  toastEl.textContent = msg;
  toastEl.className = "toast show" + (kind ? " " + kind : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.className = "toast hidden"; }, 2800);
}

/* icon 支持 emoji 或图片路径（路径含 / \ 或文件扩展名时按 <img> 渲染） */
function iconHTML(tool) {
  const size = tool.iconSize || 64;
  const icon = tool.icon || "🛠️";
  const isPath = /[\\/]/.test(icon) || /\.(png|jpe?g|gif|svg|webp|ico)$/i.test(icon);
  if (isPath) {
    return `<img class="tool-icon" src="${icon}" style="width:${size}px;height:${size}px" alt="">`;
  }
  return `<span class="tool-icon emoji" style="font-size:${size}px">${icon}</span>`;
}

function renderTools() {
  gridEl.innerHTML = "";
  tools.sort((a, b) => (a.order || 999) - (b.order || 999));
  for (const tool of tools) {
    const card = document.createElement("div");
    card.className = "tool-card";
    card.dataset.id = tool.id;
    card.draggable = true;
    card.title = tool.desc || tool.name;
    card.innerHTML =
      `<label class="tool-pin" title="勾选后显示在保存按钮左侧功能区" onclick="event.stopPropagation()">
        <input type="checkbox" data-pin="${tool.id}" ${tool.pinned ? "checked" : ""}>
      </label>` +
      iconHTML(tool) +
      `<div class="tool-name">${tool.name}</div>` +
      (tool.desc ? `<div class="tool-desc">${tool.desc}</div>` : "");
    gridEl.appendChild(card);
  }
}

/* ---- 勾选：控制是否显示在保存按钮左侧功能区 ---- */
gridEl.addEventListener("change", (e) => {
  const cb = e.target.closest("input[data-pin]");
  if (!cb) return;
  const toolId = cb.dataset.pin;
  if (typeof pywebview === "undefined" || !pywebview.api) return;
  pywebview.api.save_pin(toolId, cb.checked).then((ok) => {
    toast(ok ? (cb.checked ? "已添加到功能区" : "已从功能区移除") : "保存失败", ok ? "ok" : "err");
    if (!ok) cb.checked = !cb.checked;
  });
});

/* ---- HTML5 拖动排序 ---- */
function getDragAfterElement(x) {
  const cards = [...gridEl.querySelectorAll(".tool-card:not(.dragging)")];
  let closest = null;
  let closestOffset = Number.NEGATIVE_INFINITY;
  for (const card of cards) {
    const box = card.getBoundingClientRect();
    const offset = x - box.left - box.width / 2;
    if (offset < 0 && offset > closestOffset) {
      closestOffset = offset;
      closest = card;
    }
  }
  return closest;
}

function syncOrders(ids) {
  ids.forEach((id, i) => {
    const t = tools.find((x) => x.id === id);
    if (t) t.order = i + 1;
  });
}

gridEl.addEventListener("dragstart", (e) => {
  const card = e.target.closest(".tool-card");
  if (!card) return;
  card.classList.add("dragging");
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", card.dataset.id);
});

gridEl.addEventListener("dragover", (e) => {
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  const dragging = gridEl.querySelector(".tool-card.dragging");
  if (!dragging) return;
  const after = getDragAfterElement(e.clientX);
  if (after == null) gridEl.appendChild(dragging);
  else gridEl.insertBefore(dragging, after);
});

gridEl.addEventListener("drop", (e) => {
  e.preventDefault();
  const order = [...gridEl.querySelectorAll(".tool-card")].map((c) => c.dataset.id);
  syncOrders(order);
  if (typeof pywebview !== "undefined" && pywebview.api) {
    pywebview.api.save_order(order).then((ok) => {
      toast(ok ? "已保存排序" : "排序保存失败", ok ? "ok" : "err");
    });
  }
});

gridEl.addEventListener("dragend", (e) => {
  const card = e.target.closest(".tool-card");
  if (card) card.classList.remove("dragging");
  suppressClick = true;
  setTimeout(() => { suppressClick = false; }, 150);
});

/* ---- 点击执行 ---- */
gridEl.addEventListener("click", (e) => {
  if (suppressClick) return;
  const card = e.target.closest(".tool-card");
  if (!card) return;
  if (typeof pywebview === "undefined" || !pywebview.api) {
    toast("非桌面环境，无法执行", "err");
    return;
  }
  pywebview.api.run_tool(card.dataset.id).then((res) => {
    if (res && res.ok) {
      toast(res.msg || "已执行", "ok");
      setStatus("已执行：" + card.querySelector(".tool-name").textContent);
    } else {
      toast((res && res.msg) || "执行失败", "err");
      setStatus("执行失败");
    }
  });
});

/* 等待 pywebview JS 桥接就绪（api 注入晚于页面脚本执行，需轮询等待） */
function waitForApi(timeoutMs) {
  return new Promise((resolve, reject) => {
    if (typeof pywebview !== "undefined" && pywebview.api) { resolve(); return; }
    const t0 = Date.now();
    const limit = timeoutMs || 5000;
    const iv = setInterval(() => {
      if (typeof pywebview !== "undefined" && pywebview.api) {
        clearInterval(iv);
        resolve();
      } else if (Date.now() - t0 > limit) {
        clearInterval(iv);
        reject(new Error("pywebview api 初始化超时"));
      }
    }, 100);
  });
}

/* ---- 初始化 ---- */
(async function init() {
  try {
    await waitForApi();
    tools = (await pywebview.api.get_tools()) || [];
  } catch (err) {
    tools = [];
  }
  if (!tools.length) {
    gridEl.innerHTML = `<div class="tool-empty">暂无工具</div>`;
    setStatus("暂无可用工具");
    return;
  }
  renderTools();
})();
