/* LeoDiary Capture —— 主题 CSS 懒加载
 *
 * 替代 editor.html 中预加载全部主题 CSS 的做法，仅按需加载当前激活的主题。
 * 主题 id 与 CSS 文件名一一对应：themes/<kind>/<id>.css
 *   window  -> themes/window/<id>.css
 *   editor  -> themes/editor/<id>.css
 *   preview -> themes/preview/<id>.css
 *
 * 用法：await ThemeLoader.applyAll(theme);  // theme = {window, editor, preview}
 *       已加载相同主题时跳过，切换时移除旧 <link> 再加载新 <link>。
 */
"use strict";

window.ThemeLoader = (() => {
  const BASE = {
    window: "themes/window/",
    editor: "themes/editor/",
    preview: "themes/preview/",
  };

  // 当前已加载的 link 元素：kind -> {id, linkEl}
  const loaded = { window: null, editor: null, preview: null };

  function cssUrl(kind, id) {
    return BASE[kind] + id + ".css";
  }

  /* 加载单个主题 CSS，返回 link 元素（加载失败返回 null，不抛异常） */
  function loadLink(href) {
    return new Promise((resolve) => {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      link.onload = () => resolve(link);
      link.onerror = () => resolve(null); // 加载失败静默处理，不影响其它主题
      document.head.appendChild(link);
    });
  }

  /* 确保指定类型的主体的指定主题已加载，切换时移除旧 CSS */
  async function ensure(kind, id) {
    if (!id || !BASE[kind]) return;
    // 已加载相同主题，跳过
    if (loaded[kind] && loaded[kind].id === id) return;
    // 加载新 CSS（先加载再移除旧的，避免切换瞬间无样式）
    const linkEl = await loadLink(cssUrl(kind, id));
    // 移除旧的 CSS link
    if (loaded[kind] && loaded[kind].linkEl) {
      loaded[kind].linkEl.remove();
    }
    loaded[kind] = { id, linkEl };
  }

  /* 批量加载三套主题，返回 Promise（全部完成后 resolve） */
  async function applyAll(theme) {
    if (!theme) return;
    await Promise.all([
      ensure("window", theme.window),
      ensure("editor", theme.editor),
      ensure("preview", theme.preview),
    ]);
  }

  return { ensure, applyAll };
})();
