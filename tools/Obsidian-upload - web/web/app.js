/* LeoDiary Capture 前端逻辑 */
"use strict";

const {
  EditorView, EditorState, keymap, lineNumbers, highlightActiveLine,
  highlightActiveLineGutter, drawSelection, dropCursor, rectangularSelection,
  crosshairCursor, defaultKeymap, history, historyKeymap, indentWithTab,
  markdown, syntaxHighlighting, defaultHighlightStyle, bracketMatching,
  indentOnInput, foldGutter, foldKeymap, highlightSelectionMatches, searchKeymap,
  autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap, oneDark,
} = window.CodeMirrorBundle;

const editorEl = document.getElementById("editor");
const previewEl = document.getElementById("preview");
const statusEl = document.getElementById("status");
const toastEl = document.getElementById("toast");

function setStatus(msg) { statusEl.textContent = msg; }

let toastTimer = null;
function toast(msg, kind) {
  toastEl.textContent = msg;
  toastEl.className = "toast show" + (kind ? " " + kind : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.className = "toast hidden"; }, 2800);
}

/* ---- Markdown 渲染 ---- */
function renderPreview() {
  previewEl.innerHTML = marked.parse(view.state.doc.toString(),
                                     { breaks: true, gfm: true });
}

/* ---- 图片粘贴上传（保持现有 PicGo/Cloudflare 链路） ---- */
function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = reject;
    fr.readAsDataURL(blob);
  });
}

/* 兼容 WebView2：优先 items，兜底 files */
function findImageItem(cd) {
  if (cd && cd.items) {
    for (const it of cd.items) {
      if (it.type && it.type.startsWith("image/")) return it;
    }
  }
  if (cd && cd.files && cd.files.length) {
    const f = cd.files[0];
    if (f.type && f.type.startsWith("image/")) return f;
  }
  return null;
}

async function uploadAndInsert(imgItem) {
  setStatus("正在上传图片到 PicGo…");
  try {
    const blob = imgItem.getAsFile ? imgItem.getAsFile() : imgItem;
    const dataUrl = await blobToDataURL(blob);
    const res = await pywebview.api.upload_image(dataUrl);
    if (res.ok) {
      view.focus();
      const insert = res.markdown + "\n";
      const pos = view.state.selection.main.head;
      view.dispatch({
        changes: { from: pos, insert },
        selection: { anchor: pos + insert.length },
      });
      renderPreview();
      toast("图片已上传：已插入 " + res.url, "ok");
      setStatus("上传成功：" + res.url);
    } else {
      toast("上传失败：" + res.msg, "err");
      setStatus("上传失败");
    }
  } catch (err) {
    toast("上传出错：" + err, "err");
    setStatus("上传出错");
  }
}

/* 捕获阶段统一拦截：焦点在编辑器内/外都能上传图片，文字粘贴放行给编辑器 */
document.addEventListener("paste", (e) => {
  const imgItem = findImageItem(e.clipboardData);
  if (!imgItem) return; /* 文字：交给编辑器默认处理 */
  e.preventDefault();
  e.stopPropagation();
  uploadAndInsert(imgItem);
}, true);

/* ---- CodeMirror 6 编辑器 ---- */
const view = new EditorView({
  parent: editorEl,
  extensions: [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightActiveLine(),
    history(),
    drawSelection(),
    dropCursor(),
    foldGutter(),
    bracketMatching(),
    closeBrackets(),
    autocompletion(),
    rectangularSelection(),
    crosshairCursor(),
    indentOnInput(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    highlightSelectionMatches(),
    keymap.of([
      ...closeBracketsKeymap,
      ...defaultKeymap,
      ...searchKeymap,
      ...historyKeymap,
      ...foldKeymap,
      ...completionKeymap,
      indentWithTab,
    ]),
    markdown(),
    oneDark,
    EditorView.lineWrapping,
    EditorView.updateListener.of((update) => {
      if (update.docChanged) renderPreview();
    }),
  ],
});

/* ---- 同步滚动：按内容比例双向同步 ---- */
let syncing = false;

function scrollRatio(el) {
  const max = el.scrollHeight - el.clientHeight;
  return max > 0 ? el.scrollTop / max : 0;
}

function setScrollRatio(el, ratio) {
  const max = el.scrollHeight - el.clientHeight;
  if (max > 0) el.scrollTop = ratio * max;
}

view.scrollDOM.addEventListener("scroll", () => {
  if (syncing) return;
  syncing = true;
  setScrollRatio(previewEl, scrollRatio(view.scrollDOM));
  requestAnimationFrame(() => { syncing = false; });
});

previewEl.addEventListener("scroll", () => {
  if (syncing) return;
  syncing = true;
  setScrollRatio(view.scrollDOM, scrollRatio(previewEl));
  requestAnimationFrame(() => { syncing = false; });
});

/* ---- 保存：按钮共用同一个逻辑，参数决定目标 ---- */
async function saveNote(target) {
  const content = view.state.doc.toString();
  if (!content.trim()) {
    toast("没有内容可保存", "err");
    return;
  }
  const res = await pywebview.api.save(content, target);
  if (res.ok) {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length } });
    renderPreview();
    toast(res.msg, "ok");
    setStatus(res.msg);
  } else {
    toast("保存失败：" + res.msg, "err");
    setStatus("保存失败");
  }
}

/* 保存日志：追加到 日志\yyyy-MM-dd 周X.md */
async function saveLog() {
  const content = view.state.doc.toString();
  if (!content.trim()) {
    toast("没有内容可保存", "err");
    return;
  }
  const res = await pywebview.api.save_log(content);
  if (res.ok) {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length } });
    renderPreview();
    toast(res.msg, "ok");
    setStatus(res.msg);
  } else {
    toast("保存失败：" + res.msg, "err");
    setStatus("保存失败");
  }
}

document.getElementById("btn-inbox").addEventListener("click", () => saveNote("inbox"));
document.getElementById("btn-flash").addEventListener("click", () => saveNote("flash"));
document.getElementById("btn-log").addEventListener("click", saveLog);

document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    saveNote("inbox");
  }
});

renderPreview();
setStatus("就绪 · PicGo 图床");
