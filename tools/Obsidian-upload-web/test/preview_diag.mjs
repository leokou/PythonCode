import { createRequire } from 'module';
const require = createRequire('C:/Users/leokou/.workbuddy/binaries/node/workspace/');
const { chromium } = require('playwright');

const PORT = 8767;
const BASE = `http://127.0.0.1:${PORT}`;

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });
  const logs = [];
  page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => logs.push(`[PAGEERROR] ${e.message}\n${e.stack || ''}`));

  await page.addInitScript(() => {
    window.pywebview = {
      api: {
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
        open_tools: () => {}, open_settings: () => {},
        open_canvas: () => Promise.resolve(false), open_todo: () => Promise.resolve(false),
        import_markdown_to_canvas: () => Promise.resolve({ ok: false }),
        save_pinned_order: () => Promise.resolve(), log_debug: () => {},
      },
    };
  });

  await page.goto(`${BASE}/editor.html`, { waitUntil: 'load' });
  await page.waitForTimeout(8000);

  const diag = await page.evaluate(() => {
    const editor = document.getElementById('editor');
    const preview = document.getElementById('preview');
    return {
      hasPywebview: typeof window.pywebview !== 'undefined',
      hasCM: !!document.querySelector('#editor .cm-content'),
      editorHTMLLen: editor ? editor.innerHTML.length : -1,
      previewChildren: preview ? preview.children.length : -1,
      previewHTMLLen: preview ? preview.innerHTML.length : -1,
      outlineChildren: (document.getElementById('outline-body') || {}).children?.length ?? -1,
    };
  });

  console.log('===== 诊断 =====');
  console.log(JSON.stringify(diag, null, 2));
  console.log('\n===== console / pageerror =====');
  for (const l of logs) console.log(l);

  await browser.close();
}
main().catch((e) => { console.error('FATAL', e); process.exit(1); });
