// 验证：预览区点击 → 目录高亮对应章节（镜像编辑区行为）
import { createRequire } from 'module';
const require = createRequire('C:/Users/leokou/.workbuddy/binaries/node/workspace/');
const { chromium } = require('playwright');

const PORT = 8767;
const BASE = `http://127.0.0.1:${PORT}`;

function longMarkdown() {
  const parts = [];
  parts.push('# 标题一：总览');
  parts.push('这是一段说明文字，用于撑开预览区高度。');
  for (let i = 1; i <= 4; i++) parts.push(`段落 ${i}：背景介绍。`.repeat(3));
  parts.push('## 步骤1：准备工作');
  parts.push('此处列出准备工作的注意事项与前置条件。');
  for (let i = 1; i <= 4; i++) parts.push(`准备项 ${i}：检查环境安装依赖。`.repeat(3));
  parts.push('### 步骤2：新建注册');
  parts.push('这是用于验证目录高亮的目标之一。');
  for (let i = 1; i <= 6; i++) parts.push(`注册流程步骤 ${i}：填写表单提交校验。`.repeat(3));
  parts.push('## 步骤3：配置同步');
  parts.push('配置同步相关的说明。');
  for (let i = 1; i <= 4; i++) parts.push(`同步项 ${i}：选择目录设置间隔。`.repeat(3));
  parts.push('### 步骤4：高级设置');
  parts.push('高级设置说明，这是我们要点击验证的章节。');
  for (let i = 1; i <= 6; i++) parts.push(`高级项 ${i}：自定义模板快捷键映射。`.repeat(3));
  parts.push('# 标题二：附录');
  parts.push('附录内容。');
  for (let i = 1; i <= 6; i++) parts.push(`附录条目 ${i}：参考链接常见问题。`.repeat(3));
  return parts.join('\n\n');
}

function activeOutlineText(page) {
  return page.evaluate(() => {
    const el = document.querySelector('#outline-body .outline-item.active');
    return el ? el.textContent.trim() : '(none)';
  });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`[console.error] ${m.text()}`); });

  await page.addInitScript(() => {
    const api = {
      get_config: () => ({ windowType: 'capture', title: 'Test', saveLabel: '保存', hotkeyHint: '' }),
      get_pinned_tools: () => [], get_pending_files: () => ({ ok: true, files: [] }),
      save: () => Promise.resolve({ ok: true }), save_with_page: () => Promise.resolve({ ok: true }),
      save_external_file: () => Promise.resolve({ ok: true }), upload_image: () => Promise.resolve({ ok: true, url: '' }),
      open_url: () => Promise.resolve(), open_wikilink: () => Promise.resolve({ ok: false }),
      list_md_files: () => Promise.resolve({ ok: true, files: [] }), open_history_file: () => Promise.resolve({ ok: false }),
      save_tab_order: () => Promise.resolve(), open_tools: () => {}, open_settings: () => {},
      open_canvas: () => Promise.resolve(false), open_todo: () => Promise.resolve(false),
      import_markdown_to_canvas: () => Promise.resolve({ ok: false }), save_pinned_order: () => Promise.resolve(),
      log_debug: () => {}, create_page: () => Promise.resolve({ ok: true, page: { id: 1, file: 'D:/test/page1.md' } }),
      autosave_page: () => Promise.resolve({ ok: true }), restore_page: () => Promise.resolve({ ok: true, content: '' }),
      close_page: () => Promise.resolve({ ok: true }), rename_page: () => Promise.resolve({ ok: true }),
      get_pages: () => Promise.resolve({ ok: true, pages: [] }),
    };
    window.pywebview = { api };
  });

  console.log('-> goto editor.html');
  await page.goto(`${BASE}/editor.html`, { waitUntil: 'load' });
  await page.waitForFunction(() => !!document.querySelector('#editor .cm-content'), { timeout: 15000 })
    .catch(() => console.log('WARN: 编辑器未初始化'));

  // 注入文档
  await page.click('#editor .cm-content', { timeout: 10000 }).catch((e) => console.log('click editor err', e.message));
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Delete');
  await page.keyboard.insertText(longMarkdown());
  await page.waitForFunction(() => {
    const el = document.getElementById('preview');
    return el && el.scrollHeight > el.clientHeight + 50 && el.children.length > 5;
  }, { timeout: 8000 }).catch(() => console.log('WARN: 预览区未就绪'));

  await page.waitForTimeout(200);
  const before = await activeOutlineText(page);
  console.log('点击预览前，目录高亮 =', JSON.stringify(before));

  // 测试1：点击预览区 "步骤4：高级设置" 标题块
  console.log('\n[测试1] 点击预览区「步骤4：高级设置」标题');
  const h4 = page.locator('#preview h3', { hasText: '步骤4' });
  await h4.click({ timeout: 5000 }).catch((e) => console.log('  click err', e.message));
  await page.waitForTimeout(150);
  const after4 = await activeOutlineText(page);
  console.log('  目录高亮 =', JSON.stringify(after4), '=>', after4.includes('步骤4') ? 'PASS' : 'FAIL');

  // 测试2：点击预览区 步骤4 下的一个段落（非标题），应仍高亮 步骤4 的最近上层标题
  console.log('\n[测试2] 点击预览区 步骤4 下的段落');
  const pUnder4 = page.locator('#preview p', { hasText: '高级项' }).first();
  if (await pUnder4.count() > 0) {
    await pUnder4.click({ timeout: 5000 }).catch((e) => console.log('  click err', e.message));
    await page.waitForTimeout(150);
    const afterP = await activeOutlineText(page);
    console.log('  目录高亮 =', JSON.stringify(afterP), '=>', afterP.includes('步骤4') ? 'PASS' : 'FAIL');
  } else {
    console.log('  (未找到段落，跳过)');
  }

  // 测试3：点击预览区 "标题二：附录" 标题块，应高亮 标题二
  console.log('\n[测试3] 点击预览区「标题二：附录」标题');
  const hAppend = page.locator('#preview h1', { hasText: '标题二' });
  await hAppend.click({ timeout: 5000 }).catch((e) => console.log('  click err', e.message));
  await page.waitForTimeout(150);
  const afterAppend = await activeOutlineText(page);
  console.log('  目录高亮 =', JSON.stringify(afterAppend), '=>', afterAppend.includes('标题二') ? 'PASS' : 'FAIL');

  console.log('\n===== JS 错误 =====');
  console.log(errors.length ? errors.join('\n') : '(无)');

  await browser.close();
}
main().catch((e) => { console.error('FATAL', e); process.exit(1); });
