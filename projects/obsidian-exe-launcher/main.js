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
var fs = __toESM(require("fs"));
var DEFAULT_DATA = {
  buttonOrder: [],
  buttonSize: 140
};
var EXE_CONFIGS = [
  {
    name: "\u7D22\u5F15\u66F4\u65B0\u5DE5\u5177",
    description: "\u66F4\u65B0\u6240\u6709\u76EE\u5F55\u7D22\u5F15",
    exeName: "Obsidian - index_updater.exe",
    icon: "\u{1F4C7}"
  },
  {
    name: "Home\u4FEE\u6539\u540C\u6B65\u76EE\u5F55",
    description: "\u4FEE\u6539\u4E86home\u6587\u4EF6\u540E\u8FD0\u884C",
    exeName: "Obsidian - Home\u4FEE\u6539\u540C\u6B65\u79FB\u52A8\u6587\u4EF6.exe",
    icon: "\u{1F504}"
  },
  {
    name: "\u76EE\u5F55\u4FEE\u6539\u540C\u6B65home",
    description: "\u4FEE\u6539\u4E86\u{1F9E9}\u76EE\u5F55\u6587\u4EF6\u540E\u8FD0\u884C",
    exeName: "Obsidian - \u76EE\u5F55\u4FEE\u6539\u540C\u6B65home.exe",
    icon: "\u{1F501}"
  },
  {
    name: "\u6587\u4EF6\u540D\u6807\u9898\u68C0\u67E5",
    description: "\u68C0\u67E5\u6240\u6709.md\u6587\u4EF6\u6807\u9898",
    exeName: "Obsidian - renamepy.exe",
    icon: "\u2705"
  },
  {
    name: "\u5907\u4EFD\u7B14\u8BB0",
    description: "\u5907\u4EFDObsidian\u7B14\u8BB0\uFF08\u5F39\u7A97\u8F93\u5165\u5907\u6CE8\uFF09",
    exeName: "Obsidian -\u5907\u4EFD\u7B14\u8BB0.exe",
    icon: "\u{1F4DD}",
    promptRequired: true,
    promptLabel: "\u5907\u6CE8",
    promptPlaceholder: "\u8F93\u5165\u672C\u6B21\u5907\u4EFD\u7684\u5907\u6CE8\u4FE1\u606F..."
  },
  {
    name: "\u5907\u4EFDpython\u4EE3\u7801",
    description: "\u5907\u4EFDPython\u4EE3\u7801\u5230GitHub\uFF08\u5F39\u7A97\u8F93\u5165\u7248\u672C\u8BF4\u660E\uFF09",
    exeName: "\u5907\u4EFDpython\u4EE3\u7801.exe",
    icon: "\u{1F40D}",
    promptRequired: true,
    promptLabel: "\u7248\u672C\u8BF4\u660E",
    promptPlaceholder: "\u8F93\u5165\u672C\u6B21\u7248\u672C\u7684\u53D8\u66F4\u8BF4\u660E..."
  },
  {
    name: "\u5907\u4EFDClaude Skill",
    description: "\u5907\u4EFDskills\u5230\u672C\u5730\uFF08\u5F39\u7A97\u8F93\u5165\u5907\u6CE8\uFF09",
    exeName: "claude-skill.exe",
    icon: "\u{1F4BE}",
    promptRequired: true,
    promptLabel: "\u5907\u6CE8",
    promptPlaceholder: "\u8F93\u5165\u672C\u6B21\u5907\u4EFD\u7684\u5907\u6CE8\u4FE1\u606F..."
  },
  {
    name: "Skill\u540C\u6B65GitHub",
    description: "\u540C\u6B65Claude Skills\u5230GitHub\uFF08\u5F39\u7A97\u8F93\u5165\u7248\u672C\u8BF4\u660E\uFF09",
    exeName: "Skill\u540C\u6B65GitHub.exe",
    icon: "\u2601\uFE0F",
    promptRequired: true,
    promptLabel: "\u7248\u672C\u8BF4\u660E",
    promptPlaceholder: "\u8F93\u5165\u672C\u6B21\u7248\u672C\u7684\u53D8\u66F4\u8BF4\u660E..."
  },
  {
    name: "\u5907\u4EFDPython\u4EE3\u7801\u672C\u5730",
    description: "\u672C\u5730\u5907\u4EFDPython\u4EE3\u7801\uFF08\u5F39\u7A97\u8F93\u5165\u5907\u6CE8\uFF09",
    exeName: "python-local-backup.exe",
    icon: "\u{1F5A5}\uFE0F",
    promptRequired: true,
    promptLabel: "\u5907\u6CE8",
    promptPlaceholder: "\u8F93\u5165\u672C\u6B21\u5907\u4EFD\u7684\u5907\u6CE8\u4FE1\u606F..."
  },
  {
    name: "\u6587\u4EF6\u5408\u5E76\u4E0A\u4F20GitHub",
    description: "\u5408\u5E76\u591A\u4E2A\u6587\u4EF6\u5E76\u4E0A\u4F20\u5230GitHub",
    exeName: "Obsidian -\u6587\u4EF6\u5408\u5E76\u4E0A\u4F20GitHub.exe",
    icon: "\u{1F4E4}"
  },
  {
    name: "Skill\u540C\u6B65\u5176\u4ED6Agent",
    description: "\u540C\u6B65Claude Skills\u5230\u5176\u4ED6Agent\uFF08Codex/Trae/WorkBuddy/Qoder/project\uFF09",
    exeName: "claude\u76EE\u5F55skill\u540C\u6B65\u5230\u5176\u4ED6agentcode.py",
    icon: "\u{1F500}",
    exeDir: "D:\\Python\\tools\\skill-sync"
  }
];
var PYTHON_EXE = "python";
function getOrderedConfigs(data) {
  const configMap = new Map(EXE_CONFIGS.map((c) => [c.exeName, c]));
  const result = [];
  const seen = /* @__PURE__ */ new Set();
  for (const name of data.buttonOrder) {
    const config = configMap.get(name);
    if (config) {
      result.push(config);
      seen.add(name);
    }
  }
  for (const config of EXE_CONFIGS) {
    if (!seen.has(config.exeName)) {
      result.push(config);
    }
  }
  return result;
}
var PromptModal = class extends import_obsidian.Modal {
  plugin;
  config;
  inputEl;
  resolved = null;
  constructor(app, plugin, config) {
    super(app);
    this.plugin = plugin;
    this.config = config;
  }
  onOpen() {
    this.modalEl.addClass("exe-launcher-prompt-modal");
    const { contentEl } = this;
    contentEl.empty();
    const container = contentEl.createDiv("exe-launcher-prompt-container");
    container.createEl("h3", { text: `${this.config.icon} ${this.config.name}` });
    const label = this.config.promptLabel || "\u5907\u6CE8";
    container.createEl("p", { text: `\u8BF7\u8F93\u5165${label}\uFF1A`, cls: "exe-launcher-prompt-label" });
    this.inputEl = container.createEl("input", {
      type: "text",
      cls: "exe-launcher-prompt-input",
      attr: {
        placeholder: this.config.promptPlaceholder || ""
      }
    });
    this.inputEl.focus();
    const btnRow = container.createDiv("exe-launcher-prompt-btns");
    const cancelBtn = btnRow.createEl("button", {
      text: "\u53D6\u6D88",
      cls: "exe-launcher-prompt-cancel"
    });
    cancelBtn.addEventListener("click", () => {
      this.close();
      if (this.resolved)
        this.resolved("");
    });
    const okBtn = btnRow.createEl("button", {
      text: "\u786E\u8BA4",
      cls: "exe-launcher-prompt-ok"
    });
    okBtn.addEventListener("click", () => {
      const value = this.inputEl.value.trim();
      this.close();
      if (this.resolved)
        this.resolved(value);
    });
    this.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const value = this.inputEl.value.trim();
        this.close();
        if (this.resolved)
          this.resolved(value);
      }
      if (e.key === "Escape") {
        this.close();
        if (this.resolved)
          this.resolved("");
      }
    });
  }
  onClose() {
    this.modalEl.removeClass("exe-launcher-prompt-modal");
    this.contentEl.empty();
  }
  waitForInput() {
    return new Promise((resolve) => {
      this.resolved = resolve;
    });
  }
};
var SettingsModal = class extends import_obsidian.Modal {
  plugin;
  onApply;
  previewSize;
  constructor(app, plugin, onApply) {
    super(app);
    this.plugin = plugin;
    this.onApply = onApply;
    this.previewSize = plugin.data.buttonSize;
  }
  onOpen() {
    this.modalEl.addClass("exe-launcher-settings-modal");
    const { contentEl } = this;
    contentEl.empty();
    const container = contentEl.createDiv("exe-launcher-settings-container");
    container.createEl("h3", { text: "\u2699\uFE0F \u8BBE\u7F6E" });
    const sizeSetting = new import_obsidian.Setting(container).setName("\u6309\u94AE\u5927\u5C0F").setDesc("\u8C03\u6574\u65B9\u5F62\u6309\u94AE\u7684\u5C3A\u5BF8 (80-240px)");
    const sliderContainer = sizeSetting.controlEl;
    sliderContainer.empty();
    const valueLabel = sliderContainer.createEl("span", {
      text: `${this.previewSize}px`,
      cls: "exe-launcher-size-label"
    });
    const slider = sliderContainer.createEl("input", {
      type: "range",
      cls: "exe-launcher-size-slider",
      attr: {
        min: "80",
        max: "240",
        step: "10",
        value: String(this.previewSize)
      }
    });
    slider.addEventListener("input", (e) => {
      const val = parseInt(e.target.value);
      this.previewSize = val;
      valueLabel.setText(`${val}px`);
      previewBox.style.setProperty("--btn-size", `${val}px`);
    });
    container.createEl("div", { cls: "exe-launcher-preview-label", text: "\u5B9E\u65F6\u9884\u89C8:" });
    const previewBox = container.createEl("div", { cls: "exe-launcher-preview" });
    previewBox.style.setProperty("--btn-size", `${this.previewSize}px`);
    previewBox.createEl("span", { text: "\u{1F4CB}", cls: "exe-launcher-btn-icon" });
    previewBox.createEl("div", { text: "\u793A\u4F8B\u6309\u94AE", cls: "exe-launcher-btn-label" });
    container.createEl("div", { cls: "exe-launcher-apply-area" });
    const applyBtn = container.createEl("button", {
      cls: "exe-launcher-apply-btn",
      text: "\u2705 \u5E94\u7528\u5E76\u5173\u95ED"
    });
    applyBtn.addEventListener("click", async () => {
      this.plugin.data.buttonSize = this.previewSize;
      await this.plugin.saveData(this.plugin.data);
      this.onApply(this.previewSize);
      this.close();
    });
    new import_obsidian.Setting(container).setName("\u6062\u590D\u9ED8\u8BA4\u987A\u5E8F").setDesc("\u5C06\u6309\u94AE\u987A\u5E8F\u91CD\u7F6E\u4E3A\u9ED8\u8BA4").addButton(
      (btn) => btn.setButtonText("\u91CD\u7F6E").setWarning().onClick(async () => {
        this.plugin.data.buttonOrder = [];
        await this.plugin.saveData(this.plugin.data);
        this.onApply(this.plugin.data.buttonSize);
        this.close();
      })
    );
  }
  onClose() {
    this.modalEl.removeClass("exe-launcher-settings-modal");
    this.contentEl.empty();
  }
};
var ExeLauncherModal = class extends import_obsidian.Modal {
  plugin;
  /** 所有拖拽事件清理函数的集合，关闭弹窗时统一移除 */
  dragCleanups = [];
  constructor(app, plugin) {
    super(app);
    this.plugin = plugin;
  }
  onOpen() {
    this.modalEl.addClass("exe-launcher-modal-large");
    this.dragCleanups = [];
    const { contentEl } = this;
    contentEl.empty();
    const configs = getOrderedConfigs(this.plugin.data);
    const header = contentEl.createDiv("exe-launcher-header");
    const headerLeft = header.createDiv("exe-launcher-header-left");
    headerLeft.createEl("span", { text: "\u26A1", cls: "exe-launcher-logo" });
    const headerText = headerLeft.createDiv("exe-launcher-header-text");
    headerText.createEl("h2", { text: "\u5FEB\u901F\u542F\u52A8\u5DE5\u5177" });
    headerText.createEl("p", { text: "\u62D6\u62FD \u22EE\u22EE \u624B\u67C4\u8C03\u6574\u987A\u5E8F \xB7 \u70B9\u51FB\u542F\u52A8", cls: "exe-launcher-subtitle" });
    const settingsBtn = header.createEl("button", {
      cls: "exe-launcher-settings-btn",
      text: "\u2699\uFE0F",
      attr: { title: "\u8BBE\u7F6E" }
    });
    settingsBtn.addEventListener("click", () => {
      this.cleanupDragListeners();
      new SettingsModal(this.app, this.plugin, () => {
        this.onOpen();
      }).open();
    });
    const grid = contentEl.createDiv("exe-launcher-grid");
    grid.style.setProperty("--btn-size", `${this.plugin.data.buttonSize}px`);
    configs.forEach((config) => {
      const btn = grid.createEl("div", {
        cls: "exe-launcher-btn-square",
        attr: {
          "data-exe": config.exeName,
          title: config.description
        }
      });
      const grip = btn.createEl("div", {
        cls: "exe-launcher-drag-grip",
        text: "\u22EE\u22EE",
        attr: { title: "\u62D6\u62FD\u8C03\u6574\u987A\u5E8F" }
      });
      btn.createEl("span", { text: config.icon, cls: "exe-launcher-btn-icon" });
      btn.createEl("div", { text: config.name, cls: "exe-launcher-btn-label" });
      let isDragging = false;
      let hasMoved = false;
      let lastSwapTarget = null;
      const onMouseDown = (e) => {
        isDragging = true;
        hasMoved = false;
        lastSwapTarget = null;
        btn.addClass("exe-launcher-draggable-active");
        grid.addClass("is-dragging");
        grid.querySelectorAll(".exe-launcher-btn-square").forEach(
          (el) => el.style.transition = "none"
        );
        e.preventDefault();
        e.stopPropagation();
      };
      const onMouseMove = (e) => {
        if (!isDragging)
          return;
        const rect = btn.getBoundingClientRect();
        const dx = e.clientX - (rect.left + rect.width / 2);
        const dy = e.clientY - (rect.top + rect.height / 2);
        if (!hasMoved && Math.abs(dx) < 8 && Math.abs(dy) < 8)
          return;
        if (!hasMoved) {
          hasMoved = true;
          btn.addClass("exe-launcher-dragging");
        }
        btn.style.transform = `translate(${dx * 0.4}px, ${dy * 0.4}px) scale(1.06)`;
        btn.style.zIndex = "100";
        const siblings = Array.from(grid.children);
        let target = null;
        for (const sibling of siblings) {
          if (sibling === btn)
            continue;
          if (!sibling.classList.contains("exe-launcher-btn-square"))
            continue;
          const sr = sibling.getBoundingClientRect();
          if (e.clientX >= sr.left && e.clientX <= sr.right && e.clientY >= sr.top && e.clientY <= sr.bottom) {
            target = sibling;
            break;
          }
        }
        if (target && target !== lastSwapTarget) {
          lastSwapTarget = target;
          const btnIdx = Array.from(grid.children).indexOf(btn);
          const targetIdx = Array.from(grid.children).indexOf(target);
          if (btnIdx < targetIdx) {
            if (target.nextSibling) {
              grid.insertBefore(btn, target.nextSibling);
            } else {
              grid.appendChild(btn);
            }
          } else {
            grid.insertBefore(btn, target);
          }
        } else if (!target) {
          lastSwapTarget = null;
        }
      };
      const onMouseUp = () => {
        if (!isDragging)
          return;
        isDragging = false;
        btn.style.transform = "";
        btn.style.zIndex = "";
        btn.removeClass("exe-launcher-draggable-active");
        btn.removeClass("exe-launcher-dragging");
        grid.removeClass("is-dragging");
        grid.querySelectorAll(".exe-launcher-btn-square").forEach(
          (el) => el.style.transition = ""
        );
        if (hasMoved) {
          const newOrder = [];
          grid.querySelectorAll(":scope > .exe-launcher-btn-square").forEach((el) => {
            const name = el.getAttribute("data-exe");
            if (name)
              newOrder.push(name);
          });
          this.plugin.data.buttonOrder = newOrder;
          this.plugin.saveData(this.plugin.data);
        }
      };
      grip.addEventListener("mousedown", onMouseDown);
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
      this.dragCleanups.push(() => {
        grip.removeEventListener("mousedown", onMouseDown);
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
      });
      btn.addEventListener("click", async (e) => {
        if (hasMoved) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        if (config.promptRequired) {
          const modal = new PromptModal(this.app, this.plugin, config);
          modal.open();
          const input = await modal.waitForInput();
          if (!input)
            return;
          this.launchExe(config, input);
        } else {
          this.launchExe(config);
        }
      });
    });
  }
  /** 清理所有拖拽相关的事件监听器 */
  cleanupDragListeners() {
    for (const cleanup of this.dragCleanups) {
      cleanup();
    }
    this.dragCleanups = [];
  }
  async launchExe(config, arg) {
    const isPython = config.exeName.toLowerCase().endsWith(".py");
    const baseDir = config.exeDir ?? "D:\\Python\\dist";
    const exePath = path.join(baseDir, config.exeName);
    if (!fs.existsSync(exePath)) {
      new import_obsidian.Notice(`\u6587\u4EF6\u4E0D\u5B58\u5728: ${config.exeName}`);
      return;
    }
    try {
      let cmd;
      if (isPython) {
        cmd = `"${PYTHON_EXE}" "${exePath}"`;
      } else {
        cmd = `"${exePath}"`;
        if (arg) {
          cmd += ` --remark "${arg.replace(/"/g, '\\"')}"`;
        }
      }
      (0, import_child_process.exec)(cmd, { maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
        if (error) {
          new import_obsidian.Notice(`\u542F\u52A8\u5931\u8D25: ${config.name}
${error.message}`);
          return;
        }
        if (isPython) {
          const out = (stdout || stderr || "").trim().split("\n").filter(Boolean);
          const summary = out.slice(-5).join("\n") || "\u5B8C\u6210";
          new import_obsidian.Notice(`\u2705 ${config.name} \u5B8C\u6210
${summary}`);
        } else {
          new import_obsidian.Notice(`\u5DF2\u542F\u52A8: ${config.name}`);
        }
      });
    } catch (err) {
      new import_obsidian.Notice(`\u542F\u52A8\u5931\u8D25: ${config.name}
${err?.message ?? err}`);
    }
  }
  onClose() {
    this.cleanupDragListeners();
    this.modalEl.removeClass("exe-launcher-modal-large");
    this.contentEl.empty();
  }
};
var ExeLauncherPlugin = class extends import_obsidian.Plugin {
  data = { ...DEFAULT_DATA };
  async onload() {
    const loaded = await this.loadData();
    if (loaded) {
      this.data = { ...DEFAULT_DATA, ...loaded };
    }
    if (!this.data.buttonSize) {
      this.data.buttonSize = DEFAULT_DATA.buttonSize;
    }
    this.addRibbonIcon("play", "\u5FEB\u901F\u542F\u52A8\u5DE5\u5177", () => {
      new ExeLauncherModal(this.app, this).open();
    });
    this.addCommand({
      id: "exe-launcher-open",
      name: "\u6253\u5F00\u5FEB\u901F\u542F\u52A8\u5DE5\u5177",
      callback: () => {
        new ExeLauncherModal(this.app, this).open();
      }
    });
  }
  onunload() {
    console.log("ExeLauncherPlugin unloaded");
  }
};
