/* LeoDiary Capture —— 剪贴板粘贴与图片上传（从 script.js 抽离，全局函数，零逻辑改动）
 * 功能：HTML 富文本粘贴、剪贴板图片上传(PicGo→R2)、预览区图片插入、纯文本粘贴。
 * 依赖全局：pywebview.api, previewEl, view, CFG, toast, _embedImgCache,
 *         _isFocusInPreview, _insertPlainTextToPreview, Storage（由 script.js / preview-render.js 提供）。
 */
function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = reject;
    fr.readAsDataURL(blob);
  });
}

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

/* 判断当前焦点/选区是否在预览区内 */
function _isFocusInPreview() {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return false;
  let node = sel.anchorNode;
  if (!node) return false;
  if (node === previewEl) return true;
  while (node && node !== document.body) {
    if (node === previewEl) return true;
    node = node.parentNode;
  }
  return false;
}

/* 插入上传成功结果：焦点在预览区 → 插入到预览区光标所在块末尾；否则编辑器光标处 */
function insertUploadResult(res) {
  if (_isFocusInPreview()) {
    _insertImageToPreview(res);
  } else {
    view.focus();
    const insert = res.markdown + "\n";
    const pos = view.state.selection.main.head;
    view.dispatch({
      changes: { from: pos, insert },
      selection: { anchor: pos + insert.length },
    });
  }
  toast("图片已上传：已插入 " + res.url, "ok");
  setStatus("上传成功：" + res.url);
}

async function uploadAndInsert(imgItem) {
  setStatus("正在上传图片到 PicGo…");
  try {
    const blob = (imgItem && imgItem.getAsFile) ? imgItem.getAsFile() : imgItem;
    if (!blob) throw new Error("无法读取图片数据");
    const dataUrl = await blobToDataURL(blob);
    const res = await pywebview.api.upload_image(dataUrl);
    if (res.ok) {
      insertUploadResult(res);
    } else {
      toast("上传失败：" + res.msg, "err");
      setStatus("上传失败");
    }
  } catch (err) {
    toast("上传出错：" + err, "err");
    setStatus("上传出错");
  }
}

/* 预览区插入图片：在光标所在块末尾插入图片 markdown，重新渲染预览区 */
function _insertImageToPreview(res) {
  const tab = currentTab();
  if (!tab) {
    /* 回退：插入到编辑器 */
    view.focus();
    const insert = res.markdown + "\n";
    const pos = view.state.selection.main.head;
    view.dispatch({
      changes: { from: pos, insert },
      selection: { anchor: pos + insert.length },
    });
    return;
  }

  const block = _findCursorBlock();
  const doc = tab.state.doc;

  /* 找不到块或空文档 → 插入到文档末尾 */
  let insertPos;
  if (!block) {
    insertPos = doc.length;
  } else {
    const blockLine = parseInt(block.getAttribute("data-line"), 10);
    if (blockLine > doc.lines) {
      insertPos = doc.length;
    } else {
      /* 计算块末尾在 markdown 中的位置 */
      const allBlocks = previewEl.querySelectorAll("[data-line]");
      let endLine = doc.lines;
      for (const b of allBlocks) {
        const bl = parseInt(b.getAttribute("data-line"), 10);
        if (bl > blockLine) { endLine = bl - 1; break; }
      }
      insertPos = (endLine <= doc.lines) ? doc.line(endLine).to : doc.length;
    }
  }

  /* 块末尾插入：空行 + 图片 + 空行（保证 marked 渲染为独立段落） */
  const insertText = "\n\n" + res.markdown + "\n";

  _previewEditing = true;
  _skipPreviewRerender = true;

  view.dispatch({
    changes: { from: insertPos, to: insertPos, insert: insertText },
    selection: { anchor: insertPos + insertText.length },
  });
  tab.state = view.state;

  /* dispatch 已完成，立即恢复标志（避免 rAF 窗口内编辑区 docChanged 跳过预览渲染） */
  _previewEditing = false;
  _skipPreviewRerender = false;

  /* 重新渲染预览区（图片是块级元素，重新渲染保证 data-line 正确） */
  const savedScrollTop = previewEl.scrollTop;

  requestAnimationFrame(() => {
    renderPreview();
    previewEl.scrollTop = savedScrollTop;

    /* 重置 _oldBlock 状态（下次输入会重新初始化） */
    _oldBlockMarkdown = null;
    _oldBlockLine = -1;

    /* 光标放到图片所在块之后 */
    const imgEl = previewEl.querySelector(`img[src="${res.url}"]`);
    if (imgEl) {
      const imgBlock = imgEl.closest("[data-line]");
      if (imgBlock) {
        _placeCursorAtBlockEnd(imgBlock);
      }
    }

    if (tab.pageId) {
      scheduleOrSave(tab.pageId, tab.state.doc.toString());
    } else if (tab.extPath) {
      Storage.scheduleExternal(tab.extPath, tab.state.doc.toString());
    }
  });
}

/* 捕获阶段统一拦截：
 * - 优先处理 text/html 富文本（网页复制）→ 解析图片保存附件 + 生成 Obsidian Markdown
 * - 图片粘贴（截图）→ 保存为附件 + 生成 ![[...]] 引用
 * - 预览区文本粘贴 → 插入纯文本（避免 HTML 格式污染 contenteditable）
 * - 编辑器文本粘贴 → 放行给 CodeMirror 原生处理 */
document.addEventListener("paste", (e) => {
  const cd = e.clipboardData;
  /* 1. 优先处理 HTML 富文本（网页复制场景） */
  if (cd && cd.types && Array.from(cd.types).indexOf("text/html") >= 0) {
    const html = cd.getData("text/html");
    if (html && html.trim()) {
      e.preventDefault();
      e.stopPropagation();
      pasteHtmlContent(html, cd);
      return;
    }
  }
  /* 2. 图片（截图 / 图片文件复制） */
  const imgItem = findImageItem(cd);
  if (imgItem) {
    e.preventDefault();
    e.stopPropagation();
    pasteClipboardImage(imgItem);
    return;
  }
  /* 3. 预览区文本粘贴：插入纯文本，阻止浏览器插入 HTML 格式 */
  if (_isFocusInPreview()) {
    const text = cd ? cd.getData("text/plain") : "";
    if (text) {
      e.preventDefault();
      _insertPlainTextToPreview(text);
    }
  }
}, true);

/* HTML 富文本粘贴：发送给后端 paste_html → 保存图片 → 返回 Obsidian Markdown */
async function pasteHtmlContent(html, cd) {
  setStatus("正在解析粘贴内容…");
  const a = (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  if (!a || !a.paste_html) {
    /* 回退：剥离 HTML 标签，粘贴纯文本 */
    const text = cd ? cd.getData("text/plain") : html.replace(/<[^>]+>/g, "");
    if (text) _insertPasteText(text);
    setStatus("已粘贴纯文本");
    return;
  }
  try {
    const res = await a.paste_html(html);
    if (res && res.ok && res.markdown) {
      _insertPasteText(res.markdown);
      const ic = res.imageCount || 0;
      setStatus(ic > 0 ? "已粘贴：" + ic + " 张图片 + 文本" : "已粘贴文本");
      if (ic > 0) toast("已保存 " + ic + " 张图片到附件", "ok");
    } else {
      /* 后端解析失败 → 回退到纯文本（图片失败不影响文字粘贴） */
      const text = cd ? cd.getData("text/plain") : html.replace(/<[^>]+>/g, "");
      if (text) _insertPasteText(text);
      setStatus((res && res.msg) || "HTML 粘贴失败，已粘贴纯文本");
    }
  } catch (err) {
    const text = cd ? cd.getData("text/plain") : "";
    if (text) _insertPasteText(text);
    toast("HTML 粘贴出错：" + err, "err");
    setStatus("粘贴出错");
  }
}

/* 图片粘贴（截图 / 图片文件）：
 * 开关开启（设置 → 图片上传到 PicGo）→ 直接走 PicGo 上传（→ Cloudflare），插入远程链接；
 * 开关关闭（默认）→ 保存为本地附件，失败回退 PicGo 上传。 */
async function pasteClipboardImage(imgItem) {
  setStatus("正在保存图片…");
  const a = (typeof pywebview !== "undefined" && pywebview.api) ? pywebview.api : null;
  /* 实时读取图片上传开关（设置窗口修改后立即生效） */
  let usePicgo = false;
  if (a && a.get_picgo_upload) {
    try {
      const r = await a.get_picgo_upload();
      usePicgo = !!(r && r.ok && r.enabled);
    } catch (e) { /* 读取失败按关闭处理 */ }
  }
  if (usePicgo) {
    /* 能拿到图片文件数据（复制图片文件）→ 前端直接上传 */
    const blob = (imgItem && imgItem.getAsFile) ? imgItem.getAsFile() : imgItem;
    if (blob) {
      uploadAndInsert(imgItem);
      return;
    }
    /* 剪贴板位图（截图）：getAsFile 返回 null，由后端读剪贴板位图上传；
     * 上传失败时降级保存本地附件，保证截图不丢失。 */
    if (a && a.upload_clipboard_image) {
      try {
        const res = await a.upload_clipboard_image();
        if (res && res.ok && res.markdown) {
          insertUploadResult(res);
        } else {
          toast("上传失败：" + (res && res.msg), "err");
          setStatus("上传失败，回退本地附件");
          const fb = await a.paste_clipboard_image();
          if (fb && fb.ok && fb.markdown) {
            _insertPasteText(fb.markdown);
            toast("已回退保存到本地附件", "ok");
          }
        }
        return;
      } catch (err) {
        toast("上传出错：" + err, "err");
        setStatus("上传出错，回退本地附件");
        try {
          const fb = await a.paste_clipboard_image();
          if (fb && fb.ok && fb.markdown) {
            _insertPasteText(fb.markdown);
            toast("已回退保存到本地附件", "ok");
          }
        } catch (e2) { /* 忽略 */ }
        return;
      }
    }
  }
  if (a && a.paste_clipboard_image) {
    try {
      const res = await a.paste_clipboard_image();
      if (res && res.ok && res.markdown) {
        _insertPasteText(res.markdown);
        toast("图片已保存到附件", "ok");
        setStatus("图片已保存");
        return;
      }
      /* 剪贴板无位图（可能是图片文件项），尝试 PicGo 上传 */
    } catch (err) {
      /* 回退到 PicGo */
    }
  }
  /* 回退：PicGo 上传（保留原有行为） */
  uploadAndInsert(imgItem);
}

/* 统一文本插入：编辑器光标处 / 预览区光标处 */
function _insertPasteText(text) {
  if (!text) return;
  if (_isFocusInPreview()) {
    _insertPlainTextToPreview(text);
  } else {
    view.focus();
    const sel = view.state.selection.main;
    view.dispatch({
      changes: { from: sel.from, to: sel.to, insert: text },
      selection: { anchor: sel.from + text.length },
    });
  }
}

