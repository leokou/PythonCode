/* storage.js —— 自动保存（Debounce + 定时保险）+ 页面持久化 API 封装
 *
 * 职责：
 *  - 编辑内容变化 → 等待 2 秒 → 自动保存（覆盖写入 Tab 文件）
 *  - 每 30 秒定时保险保存（强制保存所有页面）
 *  - 封装页面相关 pywebview 调用：创建/自动保存/重命名/恢复/关闭
 *
 * 由 script.js 调用；Tab 状态回调由 tab-manager.js 渲染。
 */
"use strict";

window.Storage = (() => {
  const DEBOUNCE_MS = 2000;   // 输入停止后延迟保存
  const INSURANCE_MS = 30000; // 定时保险保存周期

  let statusCallback = null;   // (pageId, status) -> void
  let getAllTabsFn = null;     // () -> [{pageId, content}]

  const timers = {};           // pageId -> debounce timer

  function setStatusCallback(fn) { statusCallback = fn; }
  function setGetAllTabs(fn) { getAllTabsFn = fn; }

  function report(pageId, status) {
    if (statusCallback) { try { statusCallback(pageId, status); } catch (e) { /* ignore */ } }
  }

  function api() {
    return (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  }

  /* ---- 一次性立即保存（debounce 取消） ---- */
  async function saveNow(pageId, content) {
    const a = api();
    if (!a || !pageId) return;
    clearTimeout(timers[pageId]);
    report(pageId, "saving");
    try {
      const res = await a.autosave_page(pageId, content);
      report(pageId, res && res.ok ? "saved" : "error");
    } catch (e) {
      report(pageId, "error");
    }
  }

  /* ---- Debounce 自动保存 ---- */
  function schedule(pageId, content) {
    const a = api();
    if (!a || !pageId) return;
    report(pageId, "unsaved");
    clearTimeout(timers[pageId]);
    timers[pageId] = setTimeout(() => {
      delete timers[pageId];
      saveNow(pageId, content);
    }, DEBOUNCE_MS);
  }

  /* ---- 外部文件：一次性立即保存（直接覆盖原文件） ---- */
  async function saveNowExternal(extPath, content) {
    const a = api();
    if (!a || !extPath) return;
    clearTimeout(timers[extPath]);
    report(extPath, "saving");
    try {
      const res = await a.save_external_file(extPath, content);
      report(extPath, res && res.ok ? "saved" : "error");
    } catch (e) {
      report(extPath, "error");
    }
  }

  /* ---- 外部文件：Debounce 自动保存 ---- */
  function scheduleExternal(extPath, content) {
    const a = api();
    if (!a || !extPath) return;
    report(extPath, "unsaved");
    clearTimeout(timers[extPath]);
    timers[extPath] = setTimeout(() => {
      delete timers[extPath];
      saveNowExternal(extPath, content);
    }, DEBOUNCE_MS);
  }

  /* ---- 定时保险保存：每 30 秒强制保存所有页面（含外部文件） ---- */
  function insuranceTick() {
    if (!getAllTabsFn) return;
    const items = getAllTabsFn();
    for (const it of items || []) {
      if (it && it.content !== undefined) {
        if (it.extPath) saveNowExternal(it.extPath, it.content);
        else if (it.pageId) saveNow(it.pageId, it.content);
      }
    }
  }

  function startInsurance() {
    insuranceTick();
    setInterval(insuranceTick, INSURANCE_MS);
  }

  /* ---- 创建页面（新增 Tab） ---- */
  function createPage(title) {
    const a = api();
    if (!a) return Promise.resolve({ ok: false, msg: "环境不可用" });
    return a.create_page(title || "");
  }

  /* ---- 恢复页面内容 ---- */
  function restorePage(pageId) {
    const a = api();
    if (!a) return Promise.resolve({ ok: false });
    return a.restore_page(pageId);
  }

  /* ---- 关闭页面（可选删除文件） ---- */
  function closePage(pageId, deleteFile) {
    const a = api();
    if (!a) return Promise.resolve({ ok: false });
    return a.close_page(pageId, !!deleteFile);
  }

  /* ---- 重命名页面（首行标题变化） ---- */
  function renamePage(pageId, newTitle) {
    const a = api();
    if (!a) return Promise.resolve({ ok: false });
    return a.rename_page(pageId, newTitle);
  }

  /* ---- 获取本窗口页面列表 ---- */
  function getPages() {
    const a = api();
    if (!a) return Promise.resolve({ ok: false, pages: [] });
    return a.get_pages();
  }

  return {
    setStatusCallback,
    setGetAllTabs,
    schedule,
    saveNow,
    scheduleExternal,
    saveNowExternal,
    startInsurance,
    createPage,
    restorePage,
    closePage,
    renamePage,
    getPages,
  };
})();
