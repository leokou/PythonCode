/* settings.js —— 设置窗口前端逻辑
 * 功能：读取当前默认保存路径、修改保存路径、保存后显示当前保存路径。
 */
"use strict";

const pathInput = document.getElementById("set-path");
const currentValueEl = document.getElementById("set-current-value");
const saveBtn = document.getElementById("btn-set-save");
const toastEl = document.getElementById("toast");

let toastTimer = null;
function toast(msg, kind) {
  toastEl.textContent = msg;
  toastEl.className = "toast show" + (kind ? " " + kind : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.className = "toast hidden"; }, 2800);
}

function api() {
  return (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
}

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

async function loadSettings() {
  const a = api();
  if (!a) return;
  try {
    const res = await a.get_settings();
    if (res && res.ok && res.default_save_path) {
      pathInput.value = res.default_save_path;
      currentValueEl.textContent = res.default_save_path;
    }
  } catch (e) { /* ignore */ }
}

async function saveSettings() {
  const a = api();
  if (!a) { toast("非桌面环境，无法保存", "err"); return; }
  const p = pathInput.value.trim();
  if (!p) { toast("请填写保存路径", "err"); return; }
  try {
    const res = await a.save_settings(p);
    if (res && res.ok) {
      currentValueEl.textContent = res.path;
      toast("设置已保存，立即生效", "ok");
    } else {
      toast((res && res.msg) || "保存失败", "err");
    }
  } catch (e) {
    toast("保存出错：" + e, "err");
  }
}

saveBtn.addEventListener("click", saveSettings);
pathInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") saveSettings();
});

/* ---- 初始化 ---- */
(async function init() {
  try {
    await waitForApi();
  } catch (e) { /* ignore */ }
  await loadSettings();
})();
