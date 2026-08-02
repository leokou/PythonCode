/* 删除空行工具 —— 纯函数实现
 * 规则：删除所有空行（含仅含空白字符的行），全部行首尾相连。
 * web/script.js 的 cleanEmptyLines() 使用同一逻辑；本文件作为模块化参考。
 */
function cleanEmptyLines(doc) {
  return doc.split(/\r?\n/).filter(function (l) { return l.trim() !== ""; }).join("\n");
}
