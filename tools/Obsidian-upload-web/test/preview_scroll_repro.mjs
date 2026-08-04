// 预览区删除跳转 bug 复现脚本
// 通过 HTTP 服务加载 editor.html + mock pywebview 后端，注入长文档，
// 在预览区删除并捕获 scrollTop 变化 / toast / console，定位真正滚动来源。
import { createRequire } from 'module';
const require = createRequire('C:/Users/leokou/.workbuddy/binaries/node/workspace/');
const { chromium } = require('playwright');

const PORT = 8767;
const BASE = `http://127.0.0.1:${PORT}`;

// 足够长、含多级标题的 markdown，确保预览区溢出视口产生滚动条
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
  page.on('console', (msg) => {
    logs.push(`[console.${msg.type()}] ${msg.text()}`);
  });
  page.on('pageerror', (err) => {
    logs.push(`[pageerror] ${err.message}`);
  });

  // 注入 mock 后端，让 waitForApi 立即 resolve，且提供初始化所需 api
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

    // 捕获 #preview scrollTop 的 JS 赋值（含调用栈）
    window.__scrollAssign = [];
    window.__scrollEvents = [];
    window.__toasts = [];
    const installHooks = () => {
      const el = document.getElementById('preview');
      if (!el || el.__hooked) return;
      el.__hooked = true;
      const orig = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollTop');
      Object.defineProperty(el, 'scrollTop', {
        get() { return orig.get.call(this); },
        set(v) {
          try {
            const stack = new Error().stack || '';
            const caller = (stack.split('\n')[2] || '').trim();
            window.__scrollAssign.push({ v, caller, stack });
          } catch (e) {}
          return orig.set.call(this, v);
        },
        configurable: true,
      });
      el.addEventListener('scroll', () => {
        window.__scrollEvents.push({ top: el.scrollTop, t: Date.now() });
      });
      const toastEl = document.getElementById('toast');
      if (toastEl) {
        const mo = new MutationObserver(() => {
          const txt = toastEl.textContent;
          if (txt && txt.trim()) window.__toasts.push({ txt: txt.trim(), t: Date.now() });
        });
        mo.observe(toastEl, { childList: true, characterData: true, subtree: true });
      }
    };
    window.__installHooks = installHooks;
    // 轮询安装 hook（DOM 就绪后）
    const iv = setInterval(() => {
      const el = document.getElementById('preview');
      if (el) { installHooks(); clearInterval(iv); }
    }, 100);
  });

  console.log('-> goto editor.html');
  await page.goto(`${BASE}/editor.html`, { waitUntil: 'load' });

  // 等待预览区渲染出内容
  await page.waitForFunction(() => !!document.querySelector('#editor .cm-content'), { timeout: 15000 }).catch(() => console.log('WARN: 编辑器未初始化'));

  await page.evaluate(() => window.__installHooks && window.__installHooks());

  // 注入长文档：聚焦 CM6 content，全选删除后一次性插入
  console.log('-> 注入长文档');
  await page.click('#editor .cm-content', { timeout: 10000 }).catch((e) => console.log('click editor err', e.message));
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Delete');
  await page.keyboard.insertText(longMarkdown());

  // 等待预览区重新渲染并出现滚动条
  await page.waitForFunction(() => {
    const el = document.getElementById('preview');
    return el && el.scrollHeight > el.clientHeight + 50;
  }, { timeout: 8000 }).catch(() => console.log('WARN: 预览区未溢出（可能无滚动条）'));

  const before = await page.evaluate(() => {
    const el = document.getElementById('preview');
    const cm = document.querySelector('#editor .cm-content');
    return {
      scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
      children: el.children.length, previewLen: el.innerHTML.length,
      editorLen: cm ? cm.innerText.length : -1,
    };
  });
  console.log('注入后预览区状态:', JSON.stringify(before));

  // 构造用户真实场景：编辑器 head 停在顶部"步骤2"标题，
  // 预览滚动到底部（附录），在预览底部删除 → 同步变更在底部，
  // CM6 映射选区后 head 仍停留顶部步骤2 → focus 监听把预览滚回步骤2（跳转 bug）
  console.log('-> 点击目录"步骤2"使编辑器 head 停在顶部');
  const step2 = page.locator('#outline-body .outline-item', { hasText: '步骤2' });
  await step2.click({ timeout: 5000 }).catch((e) => console.log('click step2 err', e.message));
  await page.waitForTimeout(150);

  const bottom = await page.evaluate(() => {
    const el = document.getElementById('preview');
    el.scrollTop = el.scrollHeight - el.clientHeight;
    return el.scrollTop;
  });
  console.log('预览滚到底部 scrollTop=', bottom);
  await page.waitForTimeout(150);

  const box = await page.evaluate(() => {
    const el = document.getElementById('preview');
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  const clickX = box.x + box.w * 0.4;
  const clickY = box.y + box.h - 12; // 预览底部
  await page.mouse.click(clickX, clickY);
  await page.waitForTimeout(50);

  console.log('-> 预览底部删除（Backspace x6）');
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press('Backspace');
    await page.waitForTimeout(350); // 等待 debounce + rAF
    const st = await page.evaluate(() => {
      const el = document.getElementById('preview');
      const sel = window.getSelection();
      const anchor = sel && sel.anchorNode ? (sel.anchorNode.textContent || '').slice(0, 20) : '';
      return {
        scrollTop: el.scrollTop,
        active: document.activeElement ? document.activeElement.id || document.activeElement.className : '',
        anchor,
      };
    });
    console.log(`  [${i + 1}] scrollTop=${st.scrollTop} active=${st.active} anchor="${st.anchor}"`);
  }

  // 输出诊断
  const diag = await page.evaluate(() => ({
    scrollAssign: window.__scrollAssign.slice(-15),
    scrollEvents: window.__scrollEvents.slice(-15),
    toasts: window.__toasts.slice(-15),
  }));

  console.log('\n===== 诊断结果 =====');
  console.log('JS scrollTop 赋值（最后15条）:');
  for (const a of diag.scrollAssign) {
    console.log(`  -> v=${a.v} caller=${a.caller}`);
  }
  console.log('scroll 事件（最后15条）:');
  for (const e of diag.scrollEvents) console.log(`  -> top=${e.top}`);
  console.log('toast（最后15条）:');
  for (const t of diag.toasts) console.log(`  -> "${t.txt}"`);
  console.log('\n===== console 日志（相关）=====');
  for (const l of logs) {
    if (/scroll|cursor|preview|header|jump|delete/i.test(l)) console.log('  ' + l);
  }

  await browser.close();
}

main().catch((e) => { console.error('FATAL', e); process.exit(1); });
