import { App, Modal, Plugin, Setting, RibbonIcon } from 'obsidian'
import { exec } from 'child_process'
import { homedir } from 'os'
import * as path from 'path'

interface ExeConfig {
  name: string
  description: string
  exeName: string
  icon: string
}

const EXE_CONFIGS: ExeConfig[] = [
  {
    name: '索引更新工具',
    description: '更新所有目录索引',
    exeName: '索引更新工具.exe',
    icon: '📋',
  },
  {
    name: 'Home修改同步目录',
    description: '修改了home文件后运行',
    exeName: 'Home修改同步目录.exe',
    icon: '🔄',
  },
  {
    name: '目录修改同步home',
    description: '修改了🧩目录文件后运行',
    exeName: '目录修改同步home.exe',
    icon: '🔁',
  },
  {
    name: '文件名标题检查',
    description: '检查所有.md文件标题',
    exeName: '文件名标题检查.exe',
    icon: '✏️',
  },
  {
    name: '备份笔记',
    description: '备份Obsidian笔记',
    exeName: 'Obsidian -备份笔记.exe',
    icon: '📦',
  },
  {
    name: '同步GitHub',
    description: '同步到GitHub仓库',
    exeName: 'Obsidian -同步GitHub.exe',
    icon: '🚀',
  },
  {
    name: '备份python代码',
    description: '备份Python代码到GitHub',
    exeName: 'Obsidian -备份python代码.exe',
    icon: '🐍',
  },
]

class ExeLauncherModal extends Modal {
  constructor(app: App) {
    super(app)
  }

  onOpen() {
    const { contentEl } = this

    // 头部区域
    const header = contentEl.createDiv('exe-launcher-header')
    header.createEl('span', { text: '⚡', cls: 'exe-launcher-logo' })
    const headerText = header.createDiv('exe-launcher-header-text')
    headerText.createEl('h2', { text: '快速启动工具' })
    headerText.createEl('p', { text: '选择需要运行的工具', cls: 'exe-launcher-subtitle' })

    // 按钮列表区域
    const buttonContainer = contentEl.createDiv('exe-launcher-buttons')

    EXE_CONFIGS.forEach((config) => {
      const btn = buttonContainer.createEl('button', {
        cls: 'exe-launcher-btn',
      })

      // 图标
      btn.createEl('span', { text: config.icon, cls: 'exe-launcher-btn-icon' })

      // 标题
      btn.createEl('div', { text: config.name, cls: 'exe-launcher-btn-title' })

      // 箭头
      btn.createEl('span', { text: '›', cls: 'exe-launcher-btn-arrow' })

      btn.setAttribute('title', config.description)

      btn.onClickEvent(() => {
        this.launchExe(config.exeName, config.name)
      })
    })
  }

  private launchExe(exeName: string, displayName: string) {
    const exePath = path.join('D:', 'Python', 'dist', exeName)

    exec(`"${exePath}"`, (error) => {
      if (error) {
        console.error(`启动失败: ${error.message}`)
        new Notice(`启动失败: ${displayName}\n${error.message}`)
      } else {
        new Notice(`正在启动: ${displayName}`)
      }
    })
  }

  onClose() {
    const { contentEl } = this
    contentEl.empty()
  }
}

export default class ExeLauncherPlugin extends Plugin {
  async onload() {
    // 添加左侧 ribbon 图标
    this.addRibbonIcon('play', '快速启动工具', () => {
      new ExeLauncherModal(this.app).open()
    })

    // 添加命令
    this.addCommand({
      id: 'exe-launcher-open',
      name: '打开快速启动工具',
      callback: () => {
        new ExeLauncherModal(this.app).open()
      },
    })
  }

  onunload() {
    console.log('ExeLauncherPlugin unloaded')
  }
}
