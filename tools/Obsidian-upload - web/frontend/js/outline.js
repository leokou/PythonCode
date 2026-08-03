/* LeoDiary Capture —— Markdown 目录
 * 职责：解析当前文档标题（#/##/###）生成树形目录；
 *       点击目录项跳转编辑器+预览；光标移动时高亮当前章节。
 * 依赖：外部通过 bind() 注入 getText / lineFromPos / scrollToLine，保持模块独立。
 */
"use strict";

const Outline = (() => {
  let container = null;
  let getText = () => "";
  let lineFromPos = (pos) => 1;
  let scrollToLine = () => {};

  let items = [];        // [{level, text, line}]
  let activeLine = 0;
  let lastText = null;

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /* 解析标题：# / ## / ###，跳过围栏代码块，行号 1 起 */
  function parse(md) {
    const out = [];
    const lines = String(md || "").split("\n");
    const re = /^(#{1,3})\s+(.+)$/;
    let inFence = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; continue; }
      if (inFence) continue;
      const m = line.match(re);
      if (m) {
        out.push({
          level: m[1].length,
          text: m[2].replace(/#+\s*$/, "").trim(),
          line: i + 1,
        });
      }
    }
    return out;
  }

  function buildTree(list) {
    const root = { level: 0, children: [] };
    const stack = [{ level: 0, node: root }];
    for (const it of list) {
      const node = { level: it.level, text: it.text, line: it.line, children: [] };
      while (stack.length > 1 && stack[stack.length - 1].level >= it.level) stack.pop();
      stack[stack.length - 1].node.children.push(node);
      stack.push({ level: it.level, node });
    }
    return root.children;
  }

  function renderNode(node) {
    const cls = node.line === activeLine ? "outline-item active" : "outline-item";
    let html = `<li class="outline-li" data-level="${node.level}">` +
      `<div class="${cls}" data-line="${node.line}" title="${esc(node.text)}">${esc(node.text)}</div>`;
    if (node.children.length) {
      html += '<ul class="outline-sub">' + node.children.map(renderNode).join("") + "</ul>";
    }
    return html + "</li>";
  }

  function refresh() {
    const md = getText();
    items = parse(md);
    if (!container) return;
    if (md !== lastText) activeLine = 0;
    lastText = md;
    if (!items.length) {
      container.innerHTML = '<div class="outline-empty">暂无标题</div>';
      return;
    }
    const tree = buildTree(items);
    container.innerHTML = '<ul class="outline-tree">' + tree.map(renderNode).join("") + "</ul>";
    scrollActiveIntoView();
  }

  function scrollActiveIntoView() {
    if (!container || !activeLine) return;
    const el = container.querySelector(`.outline-item[data-line="${activeLine}"]`);
    if (!el) return;
    if (el.offsetTop < container.scrollTop ||
        el.offsetTop + el.offsetHeight > container.scrollTop + container.clientHeight) {
      container.scrollTop = el.offsetTop - container.clientHeight * 0.3;
    }
  }

  /* 光标位置变化 → 高亮最近标题章节 */
  function highlightAtPos(pos) {
    const line = lineFromPos(pos);
    let best = null;
    for (const it of items) {
      if (it.line <= line) best = it; else break;
    }
    const nextActive = best ? best.line : 0;
    if (nextActive === activeLine) return;
    activeLine = nextActive;
    if (!container) return;
    const prev = container.querySelector(".outline-item.active");
    if (prev) prev.classList.remove("active");
    if (activeLine) {
      const el = container.querySelector(`.outline-item[data-line="${activeLine}"]`);
      if (el) {
        el.classList.add("active");
        scrollActiveIntoView();
      }
    }
  }

  function bind(hooks) {
    if (hooks) {
      if (typeof hooks.getText === "function") getText = hooks.getText;
      if (typeof hooks.lineFromPos === "function") lineFromPos = hooks.lineFromPos;
      if (typeof hooks.scrollToLine === "function") scrollToLine = hooks.scrollToLine;
    }
  }

  function init(el) {
    container = el;
    if (!container) return;
    container.addEventListener("click", (e) => {
      const item = e.target.closest(".outline-item");
      if (!item) return;
      const line = parseInt(item.getAttribute("data-line"), 10);
      if (isFinite(line)) scrollToLine(line);
    });
  }

  return { init, bind, refresh, highlightAtPos, parse };
})();

window.Outline = Outline;
