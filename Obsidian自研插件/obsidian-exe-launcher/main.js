var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/main.ts
var main_exports = {};
__export(main_exports, {
  default: () => ExeLauncherPlugin
});
module.exports = __toCommonJS(main_exports);
var import_obsidian = require("obsidian");
var import_child_process = require("child_process");
var path = __toESM(require("path"));
var EXE_CONFIGS = [
  {
    name: "\u7D22\u5F15\u66F4\u65B0\u5DE5\u5177",
    description: "\u66F4\u65B0\u6240\u6709\u76EE\u5F55\u7D22\u5F15",
    exeName: "\u7D22\u5F15\u66F4\u65B0\u5DE5\u5177.exe",
    icon: "\u{1F4CB}"
  },
  {
    name: "Home\u4FEE\u6539\u540C\u6B65\u76EE\u5F55",
    description: "\u4FEE\u6539\u4E86home\u6587\u4EF6\u540E\u8FD0\u884C",
    exeName: "Home\u4FEE\u6539\u540C\u6B65\u76EE\u5F55.exe",
    icon: "\u{1F504}"
  },
  {
    name: "\u76EE\u5F55\u4FEE\u6539\u540C\u6B65home",
    description: "\u4FEE\u6539\u4E86\u{1F9E9}\u76EE\u5F55\u6587\u4EF6\u540E\u8FD0\u884C",
    exeName: "\u76EE\u5F55\u4FEE\u6539\u540C\u6B65home.exe",
    icon: "\u{1F501}"
  },
  {
    name: "\u6587\u4EF6\u540D\u6807\u9898\u68C0\u67E5",
    description: "\u68C0\u67E5\u6240\u6709.md\u6587\u4EF6\u6807\u9898",
    exeName: "\u6587\u4EF6\u540D\u6807\u9898\u68C0\u67E5.exe",
    icon: "\u270F\uFE0F"
  },
  {
    name: "\u5907\u4EFD\u7B14\u8BB0",
    description: "\u5907\u4EFDObsidian\u7B14\u8BB0",
    exeName: "Obsidian -\u5907\u4EFD\u7B14\u8BB0.exe",
    icon: "\u{1F4E6}"
  },
  {
    name: "\u540C\u6B65GitHub",
    description: "\u540C\u6B65\u5230GitHub\u4ED3\u5E93",
    exeName: "Obsidian -\u540C\u6B65GitHub.exe",
    icon: "\u{1F680}"
  }
];
var ExeLauncherModal = class extends import_obsidian.Modal {
  constructor(app) {
    super(app);
  }
  onOpen() {
    const { contentEl } = this;
    const header = contentEl.createDiv("exe-launcher-header");
    header.createEl("span", { text: "\u26A1", cls: "exe-launcher-logo" });
    const headerText = header.createDiv("exe-launcher-header-text");
    headerText.createEl("h2", { text: "\u5FEB\u901F\u542F\u52A8\u5DE5\u5177" });
    headerText.createEl("p", { text: "\u9009\u62E9\u9700\u8981\u8FD0\u884C\u7684\u5DE5\u5177", cls: "exe-launcher-subtitle" });
    const buttonContainer = contentEl.createDiv("exe-launcher-buttons");
    EXE_CONFIGS.forEach((config) => {
      const btn = buttonContainer.createEl("button", {
        cls: "exe-launcher-btn"
      });
      btn.createEl("span", { text: config.icon, cls: "exe-launcher-btn-icon" });
      btn.createEl("div", { text: config.name, cls: "exe-launcher-btn-title" });
      btn.createEl("span", { text: "\u203A", cls: "exe-launcher-btn-arrow" });
      btn.setAttribute("title", config.description);
      btn.onClickEvent(() => {
        this.launchExe(config.exeName, config.name);
      });
    });
  }
  launchExe(exeName, displayName) {
    const exePath = path.join("D:", "Python", "dist", exeName);
    (0, import_child_process.exec)(`"${exePath}"`, (error) => {
      if (error) {
        console.error(`\u542F\u52A8\u5931\u8D25: ${error.message}`);
        new Notice(`\u542F\u52A8\u5931\u8D25: ${displayName}
${error.message}`);
      } else {
        new Notice(`\u6B63\u5728\u542F\u52A8: ${displayName}`);
      }
    });
  }
  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
};
var ExeLauncherPlugin = class extends import_obsidian.Plugin {
  async onload() {
    this.addRibbonIcon("play", "\u5FEB\u901F\u542F\u52A8\u5DE5\u5177", () => {
      new ExeLauncherModal(this.app).open();
    });
    this.addCommand({
      id: "exe-launcher-open",
      name: "\u6253\u5F00\u5FEB\u901F\u542F\u52A8\u5DE5\u5177",
      callback: () => {
        new ExeLauncherModal(this.app).open();
      }
    });
  }
  onunload() {
    console.log("ExeLauncherPlugin unloaded");
  }
};
