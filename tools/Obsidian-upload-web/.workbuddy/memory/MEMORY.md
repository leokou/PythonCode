# 项目长期约定（Obsidian-upload-web）

## 2026-08-05 用户明确红线
- **不往旧大文件堆代码**：新功能必须独立成文件，禁止追加进 `script.js` / `*.html` / `*.py` 等大文件。前端新功能写 `frontend/xxx.js` 并在 `editor.html` 按序引入（全局函数需先于 `script.js` 定义）；后端在 `lib/modules/` 或 `lib/backend/` 新建独立 `.py`。（已写入 CLAUDE.md 一、红线 + 十一、3）
- **不随意修改预览区代码**：预览区（contenteditable `#preview`）与编辑器↔预览区双向同步代码高度纠缠（双真相源 + markdown→HTML 有损非双射映射），历史 13+ 轮修复易回归。**无用户明确需求禁止改动**。既有机制见 CLAUDE.md「十三、编辑区与预览区联动机制」，仅供理解不构成改动许可。
- 2026-08-05 已完成 script.js 拆分（页签 UI→tab-ui.js / 预览渲染→preview-render.js / 粘贴上传→paste-upload.js），核心同步保留在 script.js（约 3134 行）。diff 纯函数块因与核心同步状态紧耦合保留未抽离。
