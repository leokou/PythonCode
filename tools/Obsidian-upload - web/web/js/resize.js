/* LeoDiary Capture —— 三栏拖拽调整宽度
 * 职责：编辑|预览、预览|目录、工作区|编辑 三条分割线拖拽。
 * 宽度计算：编辑/预览/目录基于鼠标相对 workspace 的百分比；工作区为固定像素宽度。
 */
"use strict";

const Resize = (() => {
  let workspace = null;
  let r0 = null;
  let r1 = null;
  let r2 = null;

  const MIN_EDITOR = 18;
  const MAX_EDITOR = 70;
  const MIN_PREVIEW = 12;
  const MIN_OUTLINE = 8;
  const MIN_WS = 160;
  const MAX_WS = 400;

  function clamp(v, lo, hi) {
    return Math.min(Math.max(v, lo), hi);
  }

  function applyWidths(ew, pw, ow) {
    if (window.Layout && Layout.setWidths) Layout.setWidths(ew, pw, ow);
  }

  function startWorkspaceDrag(e) {
    e.preventDefault();
    const rect = workspace.getBoundingClientRect();
    document.body.classList.add("resizing");

    const onMove = (ev) => {
      const w = clamp(ev.clientX - rect.left, MIN_WS, MAX_WS);
      if (window.Layout && Layout.setWorkspaceWidth) Layout.setWorkspaceWidth(w);
    };

    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.classList.remove("resizing");
      if (window.Layout && Layout.save) Layout.save();
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function startDrag(idx) {
    return (e) => {
      e.preventDefault();
      const rect = workspace.getBoundingClientRect();
      const w = rect.width;
      const { editor: ew, preview: pw, outline: ow } =
        (window.Layout && Layout.getWidths ? Layout.getWidths() : { editor: 60, preview: 30, outline: 10 });
      const previewRatio = pw / (pw + ow);

      document.body.classList.add("resizing");

      const onMove = (ev) => {
        const pct = ((ev.clientX - rect.left) / w) * 100;
        let newEw, newPw, newOw;
        if (idx === 0) {
          /* 编辑|预览：分割线跟随鼠标（绝对定位），剩余按原比例分给 预览/目录 */
          newEw = clamp(pct, MIN_EDITOR, MAX_EDITOR);
          const rest = 100 - newEw;
          newPw = rest * previewRatio;
          newOw = rest - newPw;
          if (newPw < MIN_PREVIEW) { newPw = MIN_PREVIEW; newOw = rest - newPw; }
          if (newOw < MIN_OUTLINE) { newOw = MIN_OUTLINE; newPw = rest - newOw; }
        } else {
          /* 预览|目录：编辑宽度不变，改 预览/目录 分配 */
          newEw = ew;
          newPw = clamp(pct - ew, MIN_PREVIEW, 100 - ew - MIN_OUTLINE);
          newOw = 100 - ew - newPw;
        }
        applyWidths(Math.round(newEw), Math.round(newPw), Math.round(newOw));
      };

      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        document.body.classList.remove("resizing");
        if (window.Layout && Layout.save) Layout.save();
      };

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    };
  }

  function init() {
    workspace = document.getElementById("workspace");
    r0 = document.getElementById("resizer-0");
    r1 = document.getElementById("resizer-1");
    r2 = document.getElementById("resizer-2");
    if (!workspace) return;
    if (r0) r0.addEventListener("mousedown", startWorkspaceDrag);
    if (r1) r1.addEventListener("mousedown", startDrag(0));
    if (r2) r2.addEventListener("mousedown", startDrag(1));
  }

  return { init };
})();

window.Resize = Resize;
