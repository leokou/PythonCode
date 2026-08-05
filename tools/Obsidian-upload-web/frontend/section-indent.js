/* 章节缩进（Section Indent）—— 独立插件，逻辑不进入 script.js
 * 规则：
 *   - 标题行（ATX #~######，且不在 frontmatter / 围栏代码块内）：加 cm-heading cm-headingN，顶格（不缩进）
 *   - 其余行（正文、列表、引用、表格、分隔线等）：加 cm-section-indent，统一固定缩进
 *   - frontmatter（文档开头 --- … ---）、围栏代码块（``` … ``` / ~~~ … ~~~）及其定界行：不参与
 * 纯视觉装饰，不修改 Markdown 内容；缩进量由 --cm-section-indent 控制（默认 16px），
 * 所有层级统一使用同一值，禁止随标题级别递增缩进。
 */
const { ViewPlugin: _SIViewPlugin, Decoration: _SIDecoration } = window.CodeMirrorBundle;

const _SI_RE_HEADING = /^(#{1,6})(\s|$)/;
const _SI_RE_FENCE = /^\s*(```|~~~)/;

function _buildSectionDecorations(view) {
  const decos = [];
  const doc = view.state.doc;
  let inFence = false;
  let inFrontmatter = false;

  if (doc.lines >= 1 && /^---\s*$/.test(doc.line(1).text)) inFrontmatter = true;

  for (let i = 1; i <= doc.lines; i++) {
    const line = doc.line(i);
    const text = line.text;

    // frontmatter：跳过缩进与标题判定
    if (inFrontmatter) {
      if (i > 1 && /^---\s*$/.test(text)) inFrontmatter = false;
      continue;
    }

    // 围栏代码块：定界行与内部行均不参与（内部 # 不得误判为标题，代码块保留自身内边距）
    if (_SI_RE_FENCE.test(text)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;

    // 标题：顶格 + heading 类
    const h = text.match(_SI_RE_HEADING);
    if (h) {
      const level = h[1].length;
      decos.push(_SIDecoration.line({ class: "cm-heading cm-heading" + level }).range(line.from));
      continue;
    }

    // 其余行：统一固定缩进
    decos.push(_SIDecoration.line({ class: "cm-section-indent" }).range(line.from));
  }
  return _SIDecoration.set(decos, true);
}

const sectionIndentPlugin = _SIViewPlugin.fromClass(
  class {
    constructor(view) { this.decorations = _buildSectionDecorations(view); }
    update(u) {
      if (u.docChanged || u.viewportChanged) this.decorations = _buildSectionDecorations(u.view);
    }
  },
  { decorations: (v) => v.decorations }
);
