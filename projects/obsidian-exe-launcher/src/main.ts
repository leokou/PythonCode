import { App, Modal, Plugin, Setting, Notice } from 'obsidian'
import { exec } from 'child_process'
import * as path from 'path'
import * as fs from 'fs'

interface ExeConfig {
  name: string
  description: string
  exeName: string
  icon: string
  exeDir?: string
  promptRequired?: boolean
  promptLabel?: string
  promptPlaceholder?: string
}

interface PluginData {
  buttonOrder: string[]
  buttonSize: number
}

const DEFAULT_DATA: PluginData = {
  buttonOrder: [],
  buttonSize: 140,
}

const EXE_CONFIGS: ExeConfig[] = [
  {
    name: '索引更新工具',
    description: '更新所有目录索引',
    exeName: 'Obsidian - index_updater.exe',
    icon: '📇',
  },
  {
    name: 'Home修改同步目录',
    description: '修改了home文件后运行',
    exeName: 'Obsidian - Home修改同步移动文件.exe',
    icon: '🔄',
  },
  {
    name: '目录修改同步home',
    description: '修改了🧩目录文件后运行',
    exeName: 'Obsidian - 目录修改同步home.exe',
    icon: '🔁',
  },
  {
    name: '文件名标题检查',
    description: '检查所有.md文件标题',
    exeName: 'Obsidian - renamepy.exe',
    icon: '✅',
  },
  {
    name: '备份笔记',
    description: '备份Obsidian笔记（弹窗输入备注）',
    exeName: 'Obsidian -备份笔记.exe',
    icon: '📝',
    promptRequired: true,
    promptLabel: '备注',
    promptPlaceholder: '输入本次备份的备注信息...',
  },
  {
    name: '备份python代码',
    description: '备份Python代码到GitHub（弹窗输入版本说明）',
    exeName: '备份python代码.exe',
    icon: '🐍',
    promptRequired: true,
    promptLabel: '版本说明',
    promptPlaceholder: '输入本次版本的变更说明...',
  },
  {
    name: '备份Claude Skill',
    description: '备份skills到本地（弹窗输入备注）',
    exeName: 'claude-skill.exe',
    icon: '💾',
    promptRequired: true,
    promptLabel: '备注',
    promptPlaceholder: '输入本次备份的备注信息...',
  },
  {
    name: 'Skill同步GitHub',
    description: '同步Claude Skills到GitHub（弹窗输入版本说明）',
    exeName: 'Skill同步GitHub.exe',
    icon: '☁️',
    promptRequired: true,
    promptLabel: '版本说明',
    promptPlaceholder: '输入本次版本的变更说明...',
  },
  {
    name: '备份Python代码本地',
    description: '本地备份Python代码（弹窗输入备注）',
    exeName: 'python-local-backup.exe',
    icon: '🖥️',
    promptRequired: true,
    promptLabel: '备注',
    promptPlaceholder: '输入本次备份的备注信息...',
  },
  {
    name: '文件合并上传GitHub',
    description: '合并多个文件并上传到GitHub',
    exeName: 'Obsidian -文件合并上传GitHub.exe',
    icon: '📤',
  },
]

function getOrderedConfigs(data: PluginData): ExeConfig[] {
  const configMap = new Map(EXE_CONFIGS.map(c => [c.exeName, c]))
  const result: ExeConfig[] = []
  const seen = new Set<string>()

  for (const name of data.buttonOrder) {
    const config = configMap.get(name)
    if (config) {
      result.push(config)
      seen.add(name)
    }
  }

  for (const config of EXE_CONFIGS) {
    if (!seen.has(config.exeName)) {
      result.push(config)
    }
  }

  return result
}

class PromptModal extends Modal {
  plugin: ExeLauncherPlugin
  config: ExeConfig
  private inputEl!: HTMLInputElement
  private resolved: ((value: string) => void) | null = null

  constructor(app: App, plugin: ExeLauncherPlugin, config: ExeConfig) {
    super(app)
    this.plugin = plugin
    this.config = config
  }

  onOpen() {
    this.modalEl.addClass('exe-launcher-prompt-modal')

    const { contentEl } = this
    contentEl.empty()

    const container = contentEl.createDiv('exe-launcher-prompt-container')
    container.createEl('h3', { text: `${this.config.icon} ${this.config.name}` })

    const label = this.config.promptLabel || '备注'
    container.createEl('p', { text: `请输入${label}：`, cls: 'exe-launcher-prompt-label' })

    this.inputEl = container.createEl('input', {
      type: 'text',
      cls: 'exe-launcher-prompt-input',
      attr: {
        placeholder: this.config.promptPlaceholder || '',
      },
    })

    this.inputEl.focus()

    const btnRow = container.createDiv('exe-launcher-prompt-btns')

    const cancelBtn = btnRow.createEl('button', {
      text: '取消',
      cls: 'exe-launcher-prompt-cancel',
    })
    cancelBtn.addEventListener('click', () => {
      this.close()
      if (this.resolved) this.resolved('')
    })

    const okBtn = btnRow.createEl('button', {
      text: '确认',
      cls: 'exe-launcher-prompt-ok',
    })
    okBtn.addEventListener('click', () => {
      const value = this.inputEl.value.trim()
      this.close()
      if (this.resolved) this.resolved(value)
    })

    this.inputEl.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        const value = this.inputEl.value.trim()
        this.close()
        if (this.resolved) this.resolved(value)
      }
      if (e.key === 'Escape') {
        this.close()
        if (this.resolved) this.resolved('')
      }
    })
  }

  onClose() {
    this.modalEl.removeClass('exe-launcher-prompt-modal')
    this.contentEl.empty()
  }

  waitForInput(): Promise<string> {
    return new Promise((resolve) => {
      this.resolved = resolve
    })
  }
}

class SettingsModal extends Modal {
  plugin: ExeLauncherPlugin
  onApply: (size: number) => void
  private previewSize: number

  constructor(app: App, plugin: ExeLauncherPlugin, onApply: (size: number) => void) {
    super(app)
    this.plugin = plugin
    this.onApply = onApply
    this.previewSize = plugin.data.buttonSize
  }

  onOpen() {
    this.modalEl.addClass('exe-launcher-settings-modal')

    const { contentEl } = this
    contentEl.empty()

    const container = contentEl.createDiv('exe-launcher-settings-container')
    container.createEl('h3', { text: '⚙️ 设置' })

    const sizeSetting = new Setting(container)
      .setName('按钮大小')
      .setDesc('调整方形按钮的尺寸 (80-240px)')

    const sliderContainer = sizeSetting.controlEl
    sliderContainer.empty()

    const valueLabel = sliderContainer.createEl('span', {
      text: `${this.previewSize}px`,
      cls: 'exe-launcher-size-label',
    })

    const slider = sliderContainer.createEl('input', {
      type: 'range',
      cls: 'exe-launcher-size-slider',
      attr: {
        min: '80',
        max: '240',
        step: '10',
        value: String(this.previewSize),
      },
    })

    slider.addEventListener('input', (e: Event) => {
      const val = parseInt((e.target as HTMLInputElement).value)
      this.previewSize = val
      valueLabel.setText(`${val}px`)
      previewBox.style.setProperty('--btn-size', `${val}px`)
    })

    container.createEl('div', { cls: 'exe-launcher-preview-label', text: '实时预览:' })
    const previewBox = container.createEl('div', { cls: 'exe-launcher-preview' })
    previewBox.style.setProperty('--btn-size', `${this.previewSize}px`)
    previewBox.createEl('span', { text: '📋', cls: 'exe-launcher-btn-icon' })
    previewBox.createEl('div', { text: '示例按钮', cls: 'exe-launcher-btn-label' })

    container.createEl('div', { cls: 'exe-launcher-apply-area' })
    const applyBtn = container.createEl('button', {
      cls: 'exe-launcher-apply-btn',
      text: '✅ 应用并关闭',
    })

    applyBtn.addEventListener('click', async () => {
      this.plugin.data.buttonSize = this.previewSize
      await this.plugin.saveData(this.plugin.data)
      this.onApply(this.previewSize)
      this.close()
    })

    new Setting(container)
      .setName('恢复默认顺序')
      .setDesc('将按钮顺序重置为默认')
      .addButton(btn =>
        btn
          .setButtonText('重置')
          .setWarning()
          .onClick(async () => {
            this.plugin.data.buttonOrder = []
            await this.plugin.saveData(this.plugin.data)
            this.onApply(this.plugin.data.buttonSize)
            this.close()
          })
      )
  }

  onClose() {
    this.modalEl.removeClass('exe-launcher-settings-modal')
    this.contentEl.empty()
  }
}

class ExeLauncherModal extends Modal {
  plugin: ExeLauncherPlugin
  /** 所有拖拽事件清理函数的集合，关闭弹窗时统一移除 */
  private dragCleanups: (() => void)[] = []

  constructor(app: App, plugin: ExeLauncherPlugin) {
    super(app)
    this.plugin = plugin
  }

  onOpen() {
    this.modalEl.addClass('exe-launcher-modal-large')
    this.dragCleanups = []

    const { contentEl } = this
    contentEl.empty()

    const configs = getOrderedConfigs(this.plugin.data)

    const header = contentEl.createDiv('exe-launcher-header')
    const headerLeft = header.createDiv('exe-launcher-header-left')
    headerLeft.createEl('span', { text: '⚡', cls: 'exe-launcher-logo' })
    const headerText = headerLeft.createDiv('exe-launcher-header-text')
    headerText.createEl('h2', { text: '快速启动工具' })
    headerText.createEl('p', { text: '拖拽 ⋮⋮ 手柄调整顺序 · 点击启动', cls: 'exe-launcher-subtitle' })

    const settingsBtn = header.createEl('button', {
      cls: 'exe-launcher-settings-btn',
      text: '⚙️',
      attr: { title: '设置' },
    })
    settingsBtn.addEventListener('click', () => {
      this.cleanupDragListeners()
      new SettingsModal(this.app, this.plugin, () => {
        this.onOpen()
      }).open()
    })

    const grid = contentEl.createDiv('exe-launcher-grid')
    grid.style.setProperty('--btn-size', `${this.plugin.data.buttonSize}px`)

    configs.forEach((config) => {
      const btn = grid.createEl('div', {
        cls: 'exe-launcher-btn-square',
        attr: {
          'data-exe': config.exeName,
          title: config.description,
        },
      })

      const grip = btn.createEl('div', {
        cls: 'exe-launcher-drag-grip',
        text: '⋮⋮',
        attr: { title: '拖拽调整顺序' },
      })

      btn.createEl('span', { text: config.icon, cls: 'exe-launcher-btn-icon' })
      btn.createEl('div', { text: config.name, cls: 'exe-launcher-btn-label' })

      let isDragging = false
      let hasMoved = false
      let lastSwapTarget: HTMLElement | null = null

      const onMouseDown = (e: MouseEvent) => {
        isDragging = true
        hasMoved = false
        lastSwapTarget = null
        btn.addClass('exe-launcher-draggable-active')
        grid.addClass('is-dragging')
        // 禁用按钮上的 transition 以避免拖拽时动画干扰
        grid.querySelectorAll('.exe-launcher-btn-square').forEach(el =>
          (el as HTMLElement).style.transition = 'none'
        )
        e.preventDefault()
        e.stopPropagation()
      }

      const onMouseMove = (e: MouseEvent) => {
        if (!isDragging) return
        const rect = btn.getBoundingClientRect()
        const dx = e.clientX - (rect.left + rect.width / 2)
        const dy = e.clientY - (rect.top + rect.height / 2)
        if (!hasMoved && Math.abs(dx) < 8 && Math.abs(dy) < 8) return

        if (!hasMoved) {
          hasMoved = true
          btn.addClass('exe-launcher-dragging')
        }

        // 移动端预览：将拖拽按钮做轻微视觉偏移，跟随鼠标
        btn.style.transform = `translate(${dx * 0.4}px, ${dy * 0.4}px) scale(1.06)`
        btn.style.zIndex = '100'

        // 精确命中检测：遍历所有兄弟按钮，找鼠标所在的
        const siblings = Array.from(grid.children) as HTMLElement[]
        let target: HTMLElement | null = null
        for (const sibling of siblings) {
          if (sibling === btn) continue
          if (!sibling.classList.contains('exe-launcher-btn-square')) continue
          const sr = sibling.getBoundingClientRect()
          if (
            e.clientX >= sr.left && e.clientX <= sr.right &&
            e.clientY >= sr.top && e.clientY <= sr.bottom
          ) {
            target = sibling
            break
          }
        }

        // 避免来回抖动：同一个 target 只交换一次
        if (target && target !== lastSwapTarget) {
          lastSwapTarget = target

          // 基于 DOM 索引而非几何位置判断：始终让被拖按钮紧贴到目标旁边
          const btnIdx = Array.from(grid.children).indexOf(btn)
          const targetIdx = Array.from(grid.children).indexOf(target)

          if (btnIdx < targetIdx) {
            // btn 在目标之前 → 把 btn 移到目标之后（向前/右下）
            if (target.nextSibling) {
              grid.insertBefore(btn, target.nextSibling)
            } else {
              grid.appendChild(btn)
            }
          } else {
            // btn 在目标之后 → 把 btn 移到目标之前（向后/左上）
            grid.insertBefore(btn, target)
          }
        } else if (!target) {
          lastSwapTarget = null
        }
      }

      const onMouseUp = () => {
        if (!isDragging) return
        isDragging = false

        // 恢复按钮样式
        btn.style.transform = ''
        btn.style.zIndex = ''
        btn.removeClass('exe-launcher-draggable-active')
        btn.removeClass('exe-launcher-dragging')
        grid.removeClass('is-dragging')

        // 恢复 transition
        grid.querySelectorAll('.exe-launcher-btn-square').forEach(el =>
          (el as HTMLElement).style.transition = ''
        )

        if (hasMoved) {
          // 直接从 DOM 顺序读取新排序，保存数据，不重新渲染
          const newOrder: string[] = []
          grid.querySelectorAll(':scope > .exe-launcher-btn-square').forEach(el => {
            const name = el.getAttribute('data-exe')
            if (name) newOrder.push(name)
          })
          this.plugin.data.buttonOrder = newOrder
          this.plugin.saveData(this.plugin.data)
        }
      }

      grip.addEventListener('mousedown', onMouseDown)
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)

      // 记录清理函数
      this.dragCleanups.push(() => {
        grip.removeEventListener('mousedown', onMouseDown)
        document.removeEventListener('mousemove', onMouseMove)
        document.removeEventListener('mouseup', onMouseUp)
      })

      btn.addEventListener('click', async (e: Event) => {
        if (hasMoved) {
          e.preventDefault()
          e.stopPropagation()
          return
        }
        if (config.promptRequired) {
          const modal = new PromptModal(this.app, this.plugin, config)
          modal.open()
          const input = await modal.waitForInput()
          if (!input) return
          this.launchExe(config, input)
        } else {
          this.launchExe(config)
        }
      })
    })
  }

  /** 清理所有拖拽相关的事件监听器 */
  private cleanupDragListeners() {
    for (const cleanup of this.dragCleanups) {
      cleanup()
    }
    this.dragCleanups = []
  }

  private async launchExe(config: ExeConfig, arg?: string) {
    const baseDir = config.exeDir ?? 'D:\\Python\\dist'
    const exePath = path.join(baseDir, config.exeName)

    if (!fs.existsSync(exePath)) {
      new Notice(`EXE不存在: ${config.exeName}`)
      return
    }

    try {
      let cmd = `"${exePath}"`
      if (arg) {
        cmd += ` --remark "${arg.replace(/"/g, '\\"')}"`
      }

      exec(cmd, (error) => {
        if (error) {
          new Notice(`启动失败: ${config.name}\n${error.message}`)
        } else {
          new Notice(`已启动: ${config.name}`)
        }
      })
    } catch (err: any) {
      new Notice(`启动失败: ${config.name}\n${err?.message ?? err}`)
    }
  }

  onClose() {
    this.cleanupDragListeners()
    this.modalEl.removeClass('exe-launcher-modal-large')
    this.contentEl.empty()
  }
}

export default class ExeLauncherPlugin extends Plugin {
  data: PluginData = { ...DEFAULT_DATA }

  async onload() {
    const loaded = await this.loadData()
    if (loaded) {
      this.data = { ...DEFAULT_DATA, ...loaded }
    }
    if (!this.data.buttonSize) {
      this.data.buttonSize = DEFAULT_DATA.buttonSize
    }

    this.addRibbonIcon('play', '快速启动工具', () => {
      new ExeLauncherModal(this.app, this).open()
    })

    this.addCommand({
      id: 'exe-launcher-open',
      name: '打开快速启动工具',
      callback: () => {
        new ExeLauncherModal(this.app, this).open()
      },
    })
  }

  onunload() {
    console.log('ExeLauncherPlugin unloaded')
  }
}