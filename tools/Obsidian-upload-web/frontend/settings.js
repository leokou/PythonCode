/* settings.js —— 设置窗口前端逻辑
 * 功能：读取当前默认保存路径、修改保存路径、per-window 主题（四窗口四套独立主题），
 *       保存后立即生效。
 */
"use strict";

const pathInput = document.getElementById("set-path");
const saveBtn = document.getElementById("btn-set-save");
const toastEl = document.getElementById("toast");

const themeSelects = {
  window: document.getElementById("set-theme-window"),
  editor: document.getElementById("set-theme-editor"),
  preview: document.getElementById("set-theme-preview"),
};

const msInput = document.getElementById("set-ms-client-id");
const msSaveBtn = document.getElementById("btn-ms-save");

const picgoSwitch = document.getElementById("set-picgo-switch");

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
    }
  } catch (e) { /* ignore */ }
}

/* ---- To Do Microsoft 同步配置 ---- */
async function loadMsConfig() {
  const a = api();
  if (!a || !a.get_microsoft_config) return;
  try {
    const res = await a.get_microsoft_config();
    if (res && res.ok) {
      msInput.value = res.client_id || "";
      msInput.placeholder = res.has_override
        ? "已使用自定义客户端 ID"
        : (res.builtin_client_id ? "内置默认（可留空）" : "未配置，留空则 Microsoft 同步不可用");
    }
  } catch (e) { /* ignore */ }
}

async function saveMsConfig() {
  const a = api();
  if (!a) { toast("非桌面环境，无法保存", "err"); return; }
  const v = msInput.value.trim();
  try {
    const res = await a.save_microsoft_config(v);
    if (res && res.ok) {
      toast(v ? "Microsoft 客户端 ID 已保存（重启程序后生效）" : "已恢复内置默认", "ok");
    } else {
      toast((res && res.msg) || "保存失败", "err");
    }
  } catch (e) {
    toast("保存出错：" + e, "err");
  }
}

msSaveBtn.addEventListener("click", saveMsConfig);
msInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") saveMsConfig();
});

/* ---- 图片上传方式开关：加载 / 保存 ---- */
async function loadPicgoSwitch() {
  const a = api();
  if (!a || !a.get_picgo_upload) return;
  try {
    const res = await a.get_picgo_upload();
    if (res && res.ok) picgoSwitch.checked = !!res.enabled;
  } catch (e) { /* ignore */ }
}

async function savePicgoSwitch() {
  const a = api();
  if (!a || !a.save_picgo_upload) {
    toast("非桌面环境，无法保存", "err");
    return;
  }
  const enabled = picgoSwitch.checked;
  try {
    const res = await a.save_picgo_upload(enabled);
    if (res && res.ok) {
      toast(enabled ? "已开启：粘贴图片上传到 PicGo / Cloudflare" : "已关闭：粘贴图片保存为附件", "ok");
    } else {
      toast((res && res.msg) || "保存失败", "err");
      picgoSwitch.checked = !enabled;
    }
  } catch (e) {
    toast("保存出错：" + e, "err");
    picgoSwitch.checked = !enabled;
  }
}

picgoSwitch.addEventListener("change", savePicgoSwitch);

/* ---- 主题：四个窗口页签切换 ---- */
const tabsContainer = document.getElementById("theme-tabs");
let currentWindowType = "flash";   // 当前激活的页签

/* 所有 per-window 主题数据，格式：{ flash: {window,editor,preview}, inbox: {...}, ... } */
let allThemeData = {};

tabsContainer.addEventListener("click", (e) => {
  const btn = e.target.closest(".set-theme-tab");
  if (!btn) return;
  const wt = btn.dataset.window;
  if (!wt || wt === currentWindowType) return;
  // 保存当前页签的选中值到 allThemeData
  saveCurrentTabValues();
  // 切换激活状态
  document.querySelectorAll(".set-theme-tab").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  currentWindowType = wt;
  // 加载新页签的主题
  applyTabTheme(allThemeData[wt]);
  // 实时预览：设置窗外观切换为该窗口主题（与打开它的窗口一致）
  applyWindowThemeToSelf(wt);
});

function saveCurrentTabValues() {
  if (!allThemeData[currentWindowType]) {
    allThemeData[currentWindowType] = {};
  }
  allThemeData[currentWindowType].window = themeSelects.window.value;
  allThemeData[currentWindowType].editor = themeSelects.editor.value;
  allThemeData[currentWindowType].preview = themeSelects.preview.value;
}

/* 填充三套主题下拉框选项 */
function fillThemeOptions(themes) {
  for (const kind of Object.keys(themeSelects)) {
    const list = (themes && themes[kind]) ? themes[kind] : [];
    themeSelects[kind].innerHTML = "";
    for (const t of list) {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      themeSelects[kind].appendChild(opt);
    }
  }
}

/* 初始化标志：防止 applyCurrentTheme 逐个设置值时触发 change 事件导致错误保存 */
let _initing = false;

/* 根据主题数据设置各下拉框选中值（不触发 change 事件） */
function applyTabTheme(theme) {
  if (!theme) return;
  _initing = true;
  try {
    if (theme.window) themeSelects.window.value = theme.window;
    if (theme.editor) themeSelects.editor.value = theme.editor;
    if (theme.preview) themeSelects.preview.value = theme.preview;
  } finally {
    _initing = false;
  }
}

async function loadThemes() {
  const a = api();
  if (!a || !a.get_themes) return;
  try {
    const res = await a.get_themes();
    if (res && res.ok) {
      fillThemeOptions(res.themes);
      // res.allThemes: { flash: {window,editor,preview}, inbox: {...}, ... }
      allThemeData = res.allThemes || {};
      // 默认显示 FlashNote 页签
      currentWindowType = "flash";
      document.querySelectorAll(".set-theme-tab").forEach((b) => {
        b.classList.toggle("active", b.dataset.window === "flash");
      });
      applyTabTheme(allThemeData.flash);
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
      toast("保存路径已更新", "ok");
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

/* ---- 主题提交按钮：保存当前页签的主题并应用到当前窗口 ---- */
const themeSubmitBtn = document.getElementById("btn-theme-submit");

async function submitTheme() {
  // 保存当前页签的选中值
  saveCurrentTabValues();
  const theme = {
    window: themeSelects.window.value,
    editor: themeSelects.editor.value,
    preview: themeSelects.preview.value,
  };
  const a = api();
  if (!a || !a.save_theme) {
    toast("非桌面环境，无法保存主题", "err");
    return;
  }
  try {
    const res = await a.save_theme(currentWindowType, theme.window, theme.editor, theme.preview);
    if (res && res.ok) {
      toast("主题已应用到 " + currentWindowType, "ok");
      /* 在后端广播之外，本窗口也立即应用 */
      if (window.ThemeManager) {
        try { window.ThemeManager.apply(res.theme); } catch (e) {}
      }
    } else {
      toast((res && res.msg) || "主题保存失败", "err");
    }
  } catch (e) {
    toast("主题提交出错：" + e, "err");
  }
}

themeSubmitBtn.addEventListener("click", submitTheme);

/* 把指定窗口的主题应用到设置窗自身，使弹窗外观与来源窗口一致（实时预览） */
async function applyWindowThemeToSelf(wt) {
  const a = api();
  if (!a || !a.get_theme) return;
  try {
    const theme = await a.get_theme(wt);
    if (theme) {
      if (window.ThemeLoader) { try { await window.ThemeLoader.applyAll(theme); } catch (e) {} }
      if (window.ThemeManager) { try { window.ThemeManager.apply(theme); } catch (e) {} }
    }
  } catch (e) { /* ignore */ }
}

/* ---- 初始化 ---- */
(async function init() {
  try {
    await waitForApi();
  } catch (e) { /* ignore */ }
  await loadSettings();
  await loadMsConfig();
  await loadPicgoSwitch();
  await loadThemes();
  /* 让设置窗默认选中并应用"打开它的来源窗口"的主题（与来源窗口一致） */
  const a = api();
  if (a && a.get_source_window) {
    try {
      const res = await a.get_source_window();
      if (res && res.ok && res.windowType && allThemeData[res.windowType]) {
        const wt = res.windowType;
        saveCurrentTabValues();
        document.querySelectorAll(".set-theme-tab").forEach((b) =>
          b.classList.toggle("active", b.dataset.window === wt));
        currentWindowType = wt;
        applyTabTheme(allThemeData[wt]);
      }
    } catch (e) { /* 失败则沿用默认 FlashNote 页签 */ }
  }
  /* 应用来源窗口主题到设置窗自身（与打开它的窗口保持一致） */
  if (currentWindowType) await applyWindowThemeToSelf(currentWindowType);
})();