/* LeoDiary Capture —— 主题管理器（窗口 / 编辑区 / Markdown 预览三套独立主题）
 *
 * 设计：主题 CSS 懒加载（由 ThemeLoader 按需注入），每套 CSS 以
 *   body[data-*-theme="id"] 选择器作用域。切换主题时先加载对应 CSS 再设置 data 属性。
 *
 * 同步方案：save_theme 只保存到文件 + 本地应用，不调用 evaluate_js 广播。
 * 各窗口通过 2 秒轮询 get_theme() 检测变化并同步应用，彻底避免
 * pywebview evaluate_js 与 JS→Python 调用链并发导致的 _jsApiCallback 冲突。
 */
"use strict";

const ThemeManager = (() => {
  let current = { window: "", editor: "", preview: "" };
  let pollTimer = null;

  function api() {
    return (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  }

  function waitForApi(timeoutMs) {
    return new Promise((resolve, reject) => {
      if (api()) { resolve(); return; }
      const t0 = Date.now();
      const limit = timeoutMs || 5000;
      const iv = setInterval(() => {
        if (api()) {
          clearInterval(iv);
          resolve();
        } else if (Date.now() - t0 > limit) {
          clearInterval(iv);
          reject(new Error("pywebview api 初始化超时"));
        }
      }, 100);
    });
  }

  /* 应用主题：同步设置 body data 属性，CSS 已通过 <link> 预加载自动生效。
   * 主题未变化时跳过 DOM 写入，避免轮询产生不必要的重绘。 */
  function apply(theme) {
    if (!theme) return;
    const next = {
      window: theme.window || current.window,
      editor: theme.editor || current.editor,
      preview: theme.preview || current.preview
    };
    if (next.window === current.window
        && next.editor === current.editor
        && next.preview === current.preview) {
      return;
    }
    current = next;
    document.body.setAttribute("data-window-theme", current.window);
    document.body.setAttribute("data-editor-theme", current.editor);
    document.body.setAttribute("data-preview-theme", current.preview);
  }

  /* 从后端读取最新主题并应用（轮询调用）。
   * 先通过 ThemeLoader 加载对应 CSS，再设置 data 属性使主题生效。 */
  async function load() {
    const a = api();
    if (!a || !a.get_theme) return;
    try {
      const t = await a.get_theme();
      if (t) {
        if (window.ThemeLoader) await ThemeLoader.applyAll(t);
        apply(t);
      }
    } catch (e) { /* 读取失败沿用当前 */ }
  }

  function startPolling(intervalMs) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(load, intervalMs || 2000);
  }

  function get() { return { ...current }; }

  function init() {
    waitForApi().then(() => {
      load();
      startPolling(2000);
    }).catch(() => {});
  }

  window.ThemeManager = { apply, load, get, init };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
