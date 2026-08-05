"use strict";

/* ============================================================
 * Markdown 工具栏命令（纯逻辑，不依赖 DOM / UI 结构，可独立测试）
 *
 * 调用入口：ToolbarCommands.execute(commandId, view, ctx)
 *   - commandId: 命令标识（toolbar_config.json 中 buttons[].command）
 *   - view: CodeMirror 6 EditorView（预览区只读命令可传 null）
 *   - ctx: { args, toggleToc, renderPreview, toggleReadingMode,
 *            copyMarkdown, revealFile, toast } 宿主能力，由 toolbar.js 注入
 *
 * 约定：
 *   - 编辑区命令一律走 CodeMirror 的 dispatch API（支持 undo），禁止直接改 textarea。
 *   - 图片命令输出 Obsidian 兼容的 ![[filename]] 嵌入语法（不用 ![](url)）。
 *   - 预览区命令只读，不修改 Markdown 内容。
 * ============================================================ */
const ToolbarCommands = (() => {
  "use strict";

  /* ---------- 选区 / 光标工具 ---------- */

  /* 包裹选区：有选区 → before+text+after；无选区 → 插入 before+after，光标置于中间 */
  function wrap(view, before, after) {
    const sel = view.state.selection.main;
    const from = sel.from, to = sel.to;
    const text = sel.empty ? "" : view.state.sliceDoc(from, to);
    let insert, anchor;
    if (sel.empty) {
      insert = before + after;
      anchor = from + before.length;
    } else {
      insert = before + text + after;
      anchor = from + insert.length;
    }
    view.dispatch({ changes: { from, to, insert }, selection: { anchor } });
  }

  /* 粗体/斜体 toggle：选区已被 before/after 包裹则取消包裹，否则包裹 */
  function wrapToggle(view, before, after) {
    const sel = view.state.selection.main;
    if (sel.empty) {
      wrap(view, before, after);
      return;
    }
    const text = view.state.sliceDoc(sel.from, sel.to);
    if (text.length > before.length + after.length &&
        text.startsWith(before) && text.endsWith(after)) {
      const inner = text.slice(before.length, text.length - after.length);
      view.dispatch({
        changes: { from: sel.from, to: sel.to, insert: inner },
        selection: { anchor: sel.from + inner.length },
      });
    } else {
      wrap(view, before, after);
    }
  }

  /* 行前缀切换：给选区覆盖的所有行添加/移除前缀（空行跳过） */
  function linePrefix(view, prefix) {
    const sel = view.state.selection.main;
    const doc = view.state.doc;
    const fromLine = doc.lineAt(sel.from).number;
    const toLine = doc.lineAt(sel.to).number;
    let allHave = true;
    for (let n = fromLine; n <= toLine; n++) {
      const line = doc.line(n);
      if (line.text.trim() !== "" && !line.text.startsWith(prefix)) {
        allHave = false;
        break;
      }
    }
    const changes = [];
    for (let n = fromLine; n <= toLine; n++) {
      const line = doc.line(n);
      if (line.text.trim() === "") continue;
      if (allHave) {
        changes.push({ from: line.from, to: line.from + prefix.length, insert: "" });
      } else {
        changes.push({ from: line.from, insert: prefix });
      }
    }
    if (changes.length) view.dispatch({ changes });
  }

  /* 内联 HTML 包裹：<span style="...">text</span>，支持再次点击取消包裹 */
  function spanWrap(view, style) {
    wrapToggle(view, '<span style="' + style + '">', "</span>");
  }

  /* ---------- 编辑区命令 ---------- */

  const editorCommands = {
    bold(view) {
      wrapToggle(view, "**", "**");
    },

    italic(view) {
      wrapToggle(view, "*", "*");
    },

    /* 标题：已有标题则切换到目标级别，级别相同则取消标题；普通行添加前缀 */
    heading(view, level) {
      const n = Math.min(6, Math.max(1, parseInt(level, 10) || 1));
      const prefix = "#".repeat(n) + " ";
      const sel = view.state.selection.main;
      const doc = view.state.doc;
      const fromLine = doc.lineAt(sel.from).number;
      const toLine = doc.lineAt(sel.to).number;
      const headRe = /^(#{1,6})\s+/;
      const changes = [];
      for (let i = fromLine; i <= toLine; i++) {
        const line = doc.line(i);
        if (line.text.trim() === "") continue;
        const m = headRe.exec(line.text);
        if (m) {
          if (m[1].length === n) {
            changes.push({ from: line.from, to: line.from + m[0].length, insert: "" });
          } else {
            changes.push({ from: line.from, to: line.from + m[0].length, insert: prefix });
          }
        } else {
          changes.push({ from: line.from, insert: prefix });
        }
      }
      if (changes.length) view.dispatch({ changes });
    },

    list(view) {
      linePrefix(view, "- ");
    },

    /* 有序列表：已有编号行则取消，普通行加 `1. ` 前缀（渲染器自动编号） */
    orderedList(view) {
      const sel = view.state.selection.main;
      const doc = view.state.doc;
      const fromLine = doc.lineAt(sel.from).number;
      const toLine = doc.lineAt(sel.to).number;
      const olRe = /^\d+\.\s+/;
      let allHave = true;
      for (let n = fromLine; n <= toLine; n++) {
        const line = doc.line(n);
        if (line.text.trim() !== "" && !olRe.test(line.text)) {
          allHave = false;
          break;
        }
      }
      const changes = [];
      for (let n = fromLine; n <= toLine; n++) {
        const line = doc.line(n);
        if (line.text.trim() === "") continue;
        const m = olRe.exec(line.text);
        if (allHave && m) {
          changes.push({ from: line.from, to: line.from + m[0].length, insert: "" });
        } else if (!allHave) {
          changes.push({ from: line.from, insert: "1. " });
        }
      }
      if (changes.length) view.dispatch({ changes });
    },

    /* 任务列表：普通列表(- )→任务(- [ ] )→还原为普通列表 */
    taskList(view) {
      const sel = view.state.selection.main;
      const doc = view.state.doc;
      const fromLine = doc.lineAt(sel.from).number;
      const toLine = doc.lineAt(sel.to).number;
      const changes = [];
      for (let i = fromLine; i <= toLine; i++) {
        const line = doc.line(i);
        if (line.text.trim() === "") continue;
        if (line.text.startsWith("- [ ] ")) {
          changes.push({ from: line.from, to: line.from + "- [ ] ".length, insert: "- " });
        } else if (line.text.startsWith("- ")) {
          changes.push({ from: line.from, to: line.from + 2, insert: "- [ ] " });
        } else {
          changes.push({ from: line.from, insert: "- [ ] " });
        }
      }
      if (changes.length) view.dispatch({ changes });
    },

    quote(view) {
      linePrefix(view, "> ");
    },

    codeBlock(view) {
      const sel = view.state.selection.main;
      if (sel.empty) {
        const insert = "```\n\n```";
        const pos = sel.from;
        view.dispatch({ changes: { from: pos, insert }, selection: { anchor: pos + 4 } });
      } else {
        const text = view.state.sliceDoc(sel.from, sel.to);
        const insert = "```\n" + text + "\n```";
        view.dispatch({
          changes: { from: sel.from, to: sel.to, insert },
          selection: { anchor: sel.from + insert.length },
        });
      }
    },

    link(view) {
      const sel = view.state.selection.main;
      const text = sel.empty ? "" : view.state.sliceDoc(sel.from, sel.to);
      const label = text || "文本";
      const insert = "[" + label + "](链接)";
      const from = sel.from, to = sel.to;
      let anchor, head;
      if (sel.empty) {
        anchor = from + label.length + 3;   /* 选中 url 占位便于直接输入 */
        head = anchor + 2;
      } else {
        anchor = from + insert.length;
        head = anchor;
      }
      view.dispatch({ changes: { from, to, insert }, selection: { anchor, head } });
    },

    /* 图片：Obsidian 兼容嵌入 ![[filename]]（不用 ![](url)） */
    image(view) {
      const sel = view.state.selection.main;
      const text = sel.empty ? "" : view.state.sliceDoc(sel.from, sel.to);
      const name = text || "image.png";
      const insert = "![[" + name + "]]";
      const from = sel.from, to = sel.to;
      const anchor = from + 3;              /* 选中文件名便于直接改名 */
      view.dispatch({ changes: { from, to, insert }, selection: { anchor, head: anchor + name.length } });
    },

    wikilink(view) {
      const sel = view.state.selection.main;
      const text = sel.empty ? "" : view.state.sliceDoc(sel.from, sel.to);
      const name = text || "文件名";
      const insert = "[[" + name + "]]";
      const from = sel.from, to = sel.to;
      const anchor = from + 2;
      view.dispatch({ changes: { from, to, insert }, selection: { anchor, head: anchor + name.length } });
    },

    /* 下划线：<u>text</u> */
    underline(view) {
      wrapToggle(view, "<u>", "</u>");
    },

    /* 删除线（中划线）：~~text~~ */
    strikethrough(view) {
      wrapToggle(view, "~~", "~~");
    },

    /* 高亮（荧光笔）：<mark>text</mark> */
    highlight(view) {
      wrapToggle(view, "<mark>", "</mark>");
    },

    /* 文字颜色：<span style="color:...">text</span> */
    color(view, color) {
      spanWrap(view, "color:" + (color || "#e91e63"));
    },

    /* 底色：<span style="background-color:...">text</span> */
    backgroundColor(view, color) {
      spanWrap(view, "background-color:" + (color || "#ffff00"));
    },
  };

  /* ---------- 预览区命令（只读，不改 Markdown） ---------- */

  const previewCommands = {
    toggleToc(_view, ctx) { if (ctx && ctx.toggleToc) ctx.toggleToc(); },
    refresh(_view, ctx) { if (ctx && ctx.renderPreview) ctx.renderPreview(); },
    readingMode(_view, ctx) { if (ctx && ctx.toggleReadingMode) ctx.toggleReadingMode(); },
    copyMarkdown(_view, ctx) { if (ctx && ctx.copyMarkdown) ctx.copyMarkdown(); },
    revealFile(_view, ctx) { if (ctx && ctx.revealFile) ctx.revealFile(); },
    zoom(_view, ctx) { if (ctx && ctx.openZoomDialog) ctx.openZoomDialog(); },
  };

  /* ---------- 统一入口 ---------- */

  function execute(commandId, view, ctx) {
    if (editorCommands[commandId]) {
      if (!view) return;
      editorCommands[commandId](view, ctx && ctx.args);
      view.focus();   /* 执行后焦点回到编辑器 */
      return;
    }
    if (previewCommands[commandId]) {
      previewCommands[commandId](view, ctx);
    }
  }

  /* ---------- 光标所在格式检测（工具栏 active 状态） ---------- */

  /* 光标是否在行内 before..after 包裹内（如 **、<u>、<mark>、<span>） */
  function inInlineWrap(lineText, inLine, open, close) {
    const before = lineText.slice(0, inLine);
    const after = lineText.slice(inLine);
    return before.lastIndexOf(open) >= 0 && after.indexOf(close) >= 0;
  }

  /* 光标前后是否存在「非相邻星号」的单星（*italic*），避开 **bold** 的星号 */
  function findLoneStar(s) {
    for (let i = 0; i < s.length; i++) {
      if (s[i] !== "*") continue;
      if (i > 0 && s[i - 1] === "*") continue;
      if (i + 1 < s.length && s[i + 1] === "*") continue;
      return i;
    }
    return -1;
  }

  /* 检测当前光标位置所在的 Markdown 格式，返回各格式布尔值 + 颜色值 */
  function getActiveState(view) {
    const st = {
      bold: false, italic: false, underline: false, strikethrough: false,
      highlight: false, color: false, backgroundColor: false,
      colorValue: null, bgValue: null,
      heading: 0, list: false, orderedList: false, taskList: false,
      quote: false, codeBlock: false,
    };
    if (!view) return st;
    const doc = view.state.doc;
    const pos = view.state.selection.main.head;
    const line = doc.lineAt(pos);
    const inLine = pos - line.from;
    const lineText = line.text;

    /* 代码块：光标在 ``` 围栏内则仅高亮 code 按钮 */
    st.codeBlock = lineText.trimStart().startsWith("```");
    if (!st.codeBlock) {
      let fenced = false;
      for (let i = 1; i < line.number; i++) {
        if (doc.line(i).text.trimStart().startsWith("```")) fenced = !fenced;
      }
      st.codeBlock = fenced;
    }

    if (!st.codeBlock) {
      /* 行前缀格式 */
      const headM = /^(#{1,6})\s+/.exec(lineText);
      if (headM) {
        st.heading = headM[1].length;
      } else if (/^- \[[ xX]\]\s+/.test(lineText)) {
        st.taskList = true;
      } else if (/^-\s+/.test(lineText)) {
        st.list = true;
      } else if (/^\d+\.\s+/.test(lineText)) {
        st.orderedList = true;
      } else if (/^>\s?/.test(lineText)) {
        st.quote = true;
      }

      /* 行内包裹格式（检测顺序：删除线 → 加粗 → 斜体 → 下划线 → 高亮 → 颜色 → 底色） */
      st.strikethrough = inInlineWrap(lineText, inLine, "~~", "~~");
      st.bold = inInlineWrap(lineText, inLine, "**", "**");
      if (!st.bold) {
        const before = lineText.slice(0, inLine);
        const after = lineText.slice(inLine);
        st.italic = findLoneStar(before) >= 0 && findLoneStar(after) >= 0;
      }
      st.underline = inInlineWrap(lineText, inLine, "<u>", "</u>");
      st.highlight = inInlineWrap(lineText, inLine, "<mark>", "</mark>");
      const before = lineText.slice(0, inLine);
      if (before.lastIndexOf('<span style="color:') >= 0 && lineText.slice(inLine).indexOf("</span>") >= 0) {
        st.color = true;
        const m = /color:\s*(#[0-9a-fA-F]{3,8})/.exec(before.slice(before.lastIndexOf('<span style="color:')));
        if (m) st.colorValue = m[1];
      }
      if (before.lastIndexOf('<span style="background-color:') >= 0 && lineText.slice(inLine).indexOf("</span>") >= 0) {
        st.backgroundColor = true;
        const m = /background-color:\s*(#[0-9a-fA-F]{3,8})/.exec(before.slice(before.lastIndexOf('<span style="background-color:')));
        if (m) st.bgValue = m[1];
      }
    }

    return st;
  }

  return { execute, getActiveState };
})();

window.ToolbarCommands = ToolbarCommands;
