// 预览区删除 → 编辑区跳页首 + 目录高亮 H1 的复现脚本
// 通过 HTTP 服务加载 editor.html + mock pywebview 后端，注入长文档，
// 在预览区删除并捕获 编辑器 scroller / 预览区 scrollTop 变化 的调用栈，
// 以及 Outline.highlightAtPos 被调用时的 (pos, head, stack)，定位真实来源。
import { createRequire } from 'module';
const require = createRequire('C:/Users/leokou/.workbuddy/binaries/node/workspace/');
const { chromium } = require('playwright');

const PORT = 8799;
const BASE = `http://127.0.0.1:${PORT}`;

function longMarkdown() {
  const parts = [];
  parts.push('# 标题一：总览');
  parts.push('这是一段说明文字，用于撑开预览区高度，确保删除时页面有滚动空间。');
  for (let i = 1; i <= 4; i++) {
    parts.push(`段落 ${i}：关于本系统的背景介绍，描述其设计目标与核心能力。`.repeat(3));
  }
  parts.push('## 步骤1：准备工作');
  parts.push('此处列出准备工作的注意事项与前置条件。');
  for (let i = 1; i <= 4; i++) {
    parts.push(`准备项 ${i}：检查环境、安装依赖、配置参数、验证连通性。`.repeat(3));
  }
  parts.push('### 步骤2：新建注册');
  parts.push('这是目录中常亮选中的标题之一，用于验证删除时预览是否跳到此处。');
  for (let i = 1; i <= 6; i++) {
    parts.push(`注册流程步骤 ${i}：填写表单、提交校验、等待审核、激活账号、设置密码、完成引导。`.repeat(3));
  }
  parts.push('## 步骤3：配置同步');
  parts.push('配置同步相关的说明与排错建议。');
  for (let i = 1; i <= 4; i++) {
    parts.push(`同步项 ${i}：选择目录、设置间隔、启用自动、监控状态。`.repeat(3));
  }
  parts.push('### 步骤4：高级设置');
  parts.push('高级设置说明。');
  for (let i = 1; i <= 6; i++) {
    parts.push(`高级项 ${i}：自定义模板、快捷键映射、插件管理、日志级别、缓存策略、导出格式。`.repeat(3));
  }
  parts.push('# 标题二：附录');
  parts.push('附录内容。');
  for (let i = 1; i <= 6; i++) {
    parts.push(`附录条目 ${i}：参考链接、常见问题、变更记录、联系方式、许可证、致谢。`.repeat(3));
  }
  return parts.join('\n\n');
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });

  const logs = [];
  page.on('console', (msg) => logs.push(`[console.${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => logs.push(`[pageerror] ${err.message}`));

  await page.addInitScript(() => {
    const api = {
      get_config: () => ({ windowType: 'capture', title: 'Test', saveLabel: '保存', hotkeyHint: '' }),
      get_pinned_tools: () => [],
      get_pending_files: () => ({ ok: true, files: [] }),
      save: () => Promise.resolve({ ok: true }),
      save_with_page: () => Promise.resolve({ ok: true }),
      save_external_file: () => Promise.resolve({ ok: true }),
      upload_image: () => Promise.resolve({ ok: true, url: '' }),
      open_url: () => Promise.resolve(),
      open_wikilink: () => Promise.resolve({ ok: false }),
      list_md_files: () => Promise.resolve({ ok: true, files: [] }),
      open_history_file: () => Promise.resolve({ ok: false }),
      save_tab_order: () => Promise.resolve(),
      open_tools: () => {},
      open_settings: () => {},
      open_canvas: () => Promise.resolve(false),
      open_todo: () => Promise.resolve(false),
      import_markdown_to_canvas: () => Promise.resolve({ ok: false }),
      save_pinned_order: () => Promise.resolve(),
      log_debug: () => {},
      create_page: () => Promise.resolve({ ok: true, page: { id: 1, file: 'D:/test/page1.md' } }),
      autosave_page: () => Promise.resolve({ ok: true }),
      restore_page: () => Promise.resolve({ ok: true, content: '' }),
      close_page: () => Promise.resolve({ ok: true }),
      rename_page: () => Promise.resolve({ ok: true }),
      get_pages: () => Promise.resolve({ ok: true, pages: [] }),
    };
    window.pywebview = { api };

    // 捕获 scrollTop 赋值（含调用栈）
    window.__scrollAssign = [];
    function hookScroll(id) {
      const el = document.getElementById(id);
      if (!el || el.__hooked) return false;
      el.__hooked = true;
      const orig = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollTop');
      Object.defineProperty(el, 'scrollTop', {
        get() { return orig.get.call(this); },
        set(v) {
          const stack = (new Error().stack || '').split('\n').slice(1, 4).join(' | ');
          window.__scrollAssign.push({ id, v, stack, t: Date.now() });
          return orig.set.call(this, v);
        },
        configurable: true,
      });
      el.addEventListener('scroll', () => {
        // 仅记录由原生滚动带来的 scrollTop（非 JS 赋值）
      });
      return true;
    }
    window.__hookScroll = hookScroll;

    // 捕获 Outline.highlightAtPos 调用
    window.__highlightCalls = [];
    const iv2 = setInterval(() => {
      if (window.Outline && typeof window.Outline.highlightAtPos === 'function') {
        const orig = window.Outline.highlightAtPos;
        if (!orig.__wrapped) {
          orig.__wrapped = true;
          window.Outline.highlightAtPos = function (pos) {
            const stack = (new Error().stack || '').split('\n').slice(1, 5).join(' | ');
            let head = -1, inSync = false;
            try { head = window.view ? window.view.state.selection.main.head : -1; } catch (e) {}
            try { inSync = (typeof window._inPreviewSync === 'function') ? window._inPreviewSync() : false; } catch (e) {}
            window.__highlightCalls.push({ pos, head, inSync, stack, t: Date.now() });
            return orig.apply(this, arguments);
          };
        }
        clearInterval(iv2);
      }
    }, 50);
  });

  console.log('-> goto editor.html');
  await page.goto(`${BASE}/editor.html`, { waitUntil: 'load' });
  await page.waitForFunction(() => !!document.querySelector('#editor .cm-content'), { timeout: 15000 }).catch(() => console.log('WARN: 编辑器未初始化'));
  await page.waitForFunction(() => !!document.getElementById('preview'), { timeout: 5000 });
  await page.evaluate(() => {
    window.__hookScroll('preview');
    window.__hookScroll('editor'); // 注意：CM6 scroller 是 .cm-scroller，下面单独 hook
    const sc = document.querySelector('#editor .cm-scroller');
    if (sc && !sc.__hooked) {
      sc.__hooked = true;
      const orig = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollTop');
      Object.defineProperty(sc, 'scrollTop', {
        get() { return orig.get.call(this); },
        set(v) {
          const stack = (new Error().stack || '').split('\n').slice(1, 4).join(' | ');
          window.__scrollAssign.push({ id: 'cm-scroller', v, stack, t: Date.now() });
          return orig.set.call(this, v);
        },
        configurable: true,
      });
    }
  });

  // 注入长文档
  console.log('-> 注入长文档');
  await page.click('#editor .cm-content', { timeout: 10000 }).catch((e) => console.log('click editor err', e.message));
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Delete');
  await page.keyboard.insertText(longMarkdown());
  await page.waitForFunction(() => {
    const el = document.getElementById('preview');
    return el && el.scrollHeight > el.clientHeight + 50;
  }, { timeout: 8000 }).catch(() => console.log('WARN: 预览区未溢出'));

  // === 复现场景：让编辑器选区停在顶部(head=0)，再把编辑器滚到下方 ===
  console.log('-> Ctrl+Home 使编辑器选区停在文档顶部(位置0)');
  await page.click('#editor .cm-content', { timeout: 10000 }).catch((e) => console.log('click editor err', e.message));
  await page.keyboard.press('Control+Home');
  await page.waitForTimeout(100);
  const headInfo = await page.evaluate(() => {
    // 通过 CM6 公开 API 读取：view 是模块作用域，这里改从 DOM 选区近似判断
    const cm = document.querySelector('#editor .cm-content');
    const sel = window.getSelection();
    return { anchorOffset: sel ? sel.anchorOffset : -1, focusNodeLen: cm ? cm.innerText.length : -1 };
  });
  console.log('编辑器选区信息 =', JSON.stringify(headInfo));

  // 把编辑器滚到下方
  const editorScrollBefore = await page.evaluate(() => {
    const sc = document.querySelector('#editor .cm-scroller');
    sc.scrollTop = Math.floor(sc.scrollHeight * 0.6);
    return sc.scrollTop;
  });
  console.log('编辑器滚到 scrollTop =', editorScrollBefore);
  await page.waitForTimeout(150);

  // 预览也滚到下方某段
  await page.evaluate(() => {
    const el = document.getElementById('preview');
    el.scrollTop = Math.floor(el.scrollHeight * 0.6);
  });
  await page.waitForTimeout(150);

  const before = await page.evaluate(() => {
    const sc = document.querySelector('#editor .cm-scroller');
    const el = document.getElementById('preview');
    const active = document.querySelector('#outline-body .outline-item.active');
    return {
      editorScroll: sc.scrollTop,
      previewScroll: el.scrollTop,
      tocActive: active ? active.textContent : '(none)',
    };
  });
  console.log('删除前状态:', JSON.stringify(before));

  // 聚焦预览区，点击进入"附录"附近块，删除一个字符
  console.log('-> 点击预览区下部块（附录）并删除');
  const pbox = await page.evaluate(() => {
    const el = document.getElementById('preview');
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  await page.mouse.click(pbox.x + pbox.w * 0.4, pbox.y + pbox.h * 0.8);
  await page.waitForTimeout(80);

  // 记录删除前编辑器/预览 scroll
  const justBefore = await page.evaluate(() => ({
    editorScroll: document.querySelector('#editor .cm-scroller').scrollTop,
    previewScroll: document.getElementById('preview').scrollTop,
  }));
  console.log('即将删除前:', JSON.stringify(justBefore));

  const t0 = await page.evaluate(() => { window.__deleteT = Date.now(); return window.__deleteT; });
  await page.keyboard.press('Backspace');
  await page.waitForTimeout(900); // 等待 debounce(200) + dispatch + rAF + 复原

  const after = await page.evaluate(() => {
    const sc = document.querySelector('#editor .cm-scroller');
    const el = document.getElementById('preview');
    const active = document.querySelector('#outline-body .outline-item.active');
    return {
      editorScroll: sc.scrollTop,
      previewScroll: el.scrollTop,
      tocActive: active ? active.textContent : '(none)',
      activeLine: active ? active.getAttribute('data-line') : '',
    };
  });
  console.log('删除后状态:', JSON.stringify(after));

  const diag = await page.evaluate((t0) => ({
    scrollAssign: (window.__scrollAssign || []).filter(a => a.t >= t0 - 50),
    highlightCalls: (window.__highlightCalls || []).filter(h => h.t >= t0 - 50),
  }), t0);

  console.log('\n===== 删除后 scrollTop 赋值（含调用栈）=====');
  for (const a of diag.scrollAssign) {
    console.log(`  [${a.id}] v=${a.v} stack=${a.stack}`);
  }
  console.log('\n===== Outline.highlightAtPos 调用（最后10条）=====');
  for (const h of diag.highlightCalls) {
    console.log(`  pos=${h.pos} head=${h.head} inSync=${h.inSync} stack=${h.stack}`);
  }

  await browser.close();

  // 判定
  const editorJumped = after.editorScroll < editorScrollBefore * 0.3;
  const tocIsH1 = /标题一/.test(after.tocActive || '');
  console.log('\n===== 判定 =====');
  console.log('编辑器是否跳到顶部(<30%):', editorJumped, `(before=${editorScrollBefore}, after=${after.editorScroll})`);
  console.log('目录是否高亮一级标题(标题一):', tocIsH1, `(active="${after.tocActive}")`);
}

main().catch((e) => { console.error('FATAL', e); process.exit(1); });
