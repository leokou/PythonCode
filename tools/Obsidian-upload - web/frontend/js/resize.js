/* LeoDiary Capture —— 三栏拖拽调整宽度（丝滑版）
 * 职责：编辑|预览、预览|目录、工作区|编辑 三条分割线拖拽。
 * 核心优化：
 *   1. 视口坐标基准：直接用 mousedown 的 e.clientX 作基准，delta = 当前鼠标视口x - 起始视口x
 *      1px 鼠标移动 = 1px 宽度变化，彻底消除坐标系错位导致的漂移
 *   2. Pointer Events + setPointerCapture，保证拖拽过程中事件不丢失
 *   3. rAF 合帧，避免高频 mousemove 导致抖动
 *   4. onUp 强制落盘最后一帧，避免 rAF 竞争导致松手位置丢失
 *   5. 拖动中不 round，只在 save 时 round，避免累积精度丢失
 */
"use strict";

const Resize = (() => {
  let workspace = null;
  let r0 = null;
  let r1 = null;
  let r2 = null;

  const RESIZER_W = 6;        // 每个分割条宽度（与 CSS .resizer flex: 0 0 6px 同步）
  const MIN_EDITOR = 18;
  const MAX_EDITOR = 70;
  const MIN_PREVIEW = 12;
  const MIN_OUTLINE = 8;
  const MIN_WS = 160;
  const MAX_WS = 400;

  let _rafPending = false;
  let _pendingUpdate = null;

  function clamp(v, lo, hi) {
    return v < lo ? lo : (v > hi ? hi : v);
  }

  function requestUpdate(fn) {
    _pendingUpdate = fn;
    if (_rafPending) return;
    _rafPending = true;
    requestAnimationFrame(() => {
      _rafPending = false;
      if (_pendingUpdate) {
        const fn2 = _pendingUpdate;
        _pendingUpdate = null;
        fn2();
      }
    });
  }

  /* 计算三栏可用宽度 = workspace 总宽 - 工作区(含 resizer-0) - 其余两条 resizer */
  function availableThreePaneWidth() {
    const total = workspace.clientWidth;
    const ws = window.Layout;
    let fixed = 0;
    if (ws && ws.isWorkspaceVisible()) {
      fixed += ws.getWorkspaceWidth() + RESIZER_W;  // 工作区面板 + resizer-0
    }
    fixed += RESIZER_W * 2;  // resizer-1 + resizer-2
    return Math.max(100, total - fixed);
  }

  /* ===== 工作区 | 编辑（resizer-0，像素拖拽） ===== */
  function startWorkspaceDrag(e) {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const ws = window.Layout;
    const startW = ws ? ws.getWorkspaceWidth() : 220;
    let lastW = startW;

    document.body.classList.add("resizing");

    const onMove = (ev) => {
      const delta = ev.clientX - startX;
      const newW = clamp(startW + delta, MIN_WS, MAX_WS);
      lastW = newW;
      requestUpdate(() => {
        if (ws && ws.setWorkspaceWidth) ws.setWorkspaceWidth(newW);
      });
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      document.body.classList.remove("resizing");
      if (ws && ws.setWorkspaceWidth) ws.setWorkspaceWidth(lastW);
      requestAnimationFrame(() => {
        if (ws && ws.save) ws.save();
      });
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);

    try { e.setPointerCapture(e.pointerId); } catch (_) {}
  }

  /* ===== 通用：编辑|预览 (idx=0) / 预览|目录 (idx=1) ===== */
  function startDrag(idx) {
    return (e) => {
      e.preventDefault();
      e.stopPropagation();

      const ws = window.Layout;
      if (!ws || !ws.getWidths) return;

      const { editor: ew0, preview: pw0, outline: ow0 } = ws.getWidths();

      /* 基准：直接用 mousedown 的视口坐标，避免坐标系错位
       * delta = 当前鼠标视口x - 起始鼠标视口x，1px = 1px 宽度变化 */
      const startMouseX = e.clientX;
      const threeW = availableThreePaneWidth();
      const previewRatio = (pw0 + ow0) > 0 ? pw0 / (pw0 + ow0) : 0.75;

      /* 记录最后一次计算的宽度，onUp 时强制落盘 */
      let lastEw = ew0, lastPw = pw0, lastOw = ow0;

      document.body.classList.add("resizing");

      const onMove = (ev) => {
        const deltaPx = ev.clientX - startMouseX;
        const deltaPct = (deltaPx / threeW) * 100;

        let newEw, newPw, newOw;

        if (idx === 0) {
          /* 编辑|预览：编辑宽度直接跟随鼠标 delta，剩余按原比例分给 预览/目录 */
          newEw = clamp(ew0 + deltaPct, MIN_EDITOR, MAX_EDITOR);
          const rest = 100 - newEw;
          newPw = rest * previewRatio;
          newOw = rest - newPw;
          /* 最小约束：若预览/目录不足，从另一方拿空间 */
          if (newPw < MIN_PREVIEW) { newPw = MIN_PREVIEW; newOw = rest - newPw; }
          if (newOw < MIN_OUTLINE) { newOw = MIN_OUTLINE; newPw = rest - newOw; }
        } else {
          /* 预览|目录：编辑宽度不变，预览宽度跟随鼠标 delta */
          newEw = ew0;
          const newPwRaw = pw0 + deltaPct;
          newPw = clamp(newPwRaw, MIN_PREVIEW, 100 - ew0 - MIN_OUTLINE);
          newOw = 100 - ew0 - newPw;
        }

        if (newOw < MIN_OUTLINE) {
          /* 兜底：目录最小约束 */
          newOw = MIN_OUTLINE;
          if (idx === 0) {
            const rest = 100 - newEw;
            newPw = clamp(rest - newOw, MIN_PREVIEW, 100);
          } else {
            newPw = 100 - newEw - newOw;
          }
        }

        lastEw = newEw; lastPw = newPw; lastOw = newOw;

        requestUpdate(() => {
          if (ws && ws.setWidths) ws.setWidths(newEw, newPw, newOw);
        });
      };

      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onUp);
        document.body.classList.remove("resizing");
        /* 先强制落盘最后一次宽度，再保存布局（避免 rAF 竞争导致最后一帧丢失） */
        if (ws && ws.setWidths) ws.setWidths(lastEw, lastPw, lastOw);
        requestAnimationFrame(() => {
          if (ws && ws.save) ws.save();
        });
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);

      try { e.setPointerCapture(e.pointerId); } catch (_) {}
    };
  }

  function init() {
    workspace = document.getElementById("workspace");
    r0 = document.getElementById("resizer-0");
    r1 = document.getElementById("resizer-1");
    r2 = document.getElementById("resizer-2");
    if (!workspace) return;
    if (r0) r0.addEventListener("pointerdown", startWorkspaceDrag);
    if (r1) r1.addEventListener("pointerdown", startDrag(0));
    if (r2) r2.addEventListener("pointerdown", startDrag(1));
  }

  return { init };
})();

window.Resize = Resize;
