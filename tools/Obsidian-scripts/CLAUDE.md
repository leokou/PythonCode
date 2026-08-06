# CLADE.md — Obsidian-scripts 开发规范

> 本目录为 LeoDiary 知识库的 Obsidian 结构维护 Python 脚本集。

## 1. 定位与职责

| 脚本 | 职责 | 触发 |
|------|------|------|
| `obsidian_common.py` | 共享配置/常量/工具 | 被其他脚本 import |
| `home-to-mulu-sync.py` | Home → 🧩 反向同步 + 搬移 + 标题 | 改 home 后运行 |
| `mulu-to-home-sync.py` | 🧩 搬移 + 重建 home + 标题 | 改 🧩 目录后运行 |
| `index-updater.py` | 索引自动管理（home/🧩/📖总路由） | 手动/Skill 调用 |
| `rename-check.py` | 文件名标题检查 | 手动 |

## 2. 核心约束
- **编码必须为 UTF-8**（所有 .py/.md/.bat）；`obsidian_common.py` 已做 `stdout` UTF-8 reconfigure。
- **Vault 路径统一用 `VAULT_ROOT` 常量**，禁止在业务脚本硬编码路径。
- **规则集中在 `obsidian_common.py`**（跳过目录/文件、PARA、标题修正），业务脚本只调用，不重复定义。
- 中文输出含 emoji（🩊/ℹ/🏷️），打包 exe 后注意控制台编码。

## 3. 设计原则（最小改动）
- `✅` 只做行级增删，`❌` 不重排、不分类、不加摘要（内容加工交给 Skills）。
- 不改变现有公共函数接口；扩展现有参数需保持默认值向后兼容。
- 记录文件访问、移动、同步等操作日志，不静默失败。

## 4. 打包
- 入口：`build-exe.bat` → 4 个入口脚本（home-to-mulu-sync / index-updater / mulu-to-home-sync / rename-check）打包到 `D:\Python\dist`。
- `obsidian_common.py` 与 `README.md` 随包复制。
- 依赖 PyInstaller（系统 python 已装）。打包命令：
  ```bash
  python -m PyInstaller --onefile --noconfirm --clean --distpath D:\Python\dist script.py
  ```
- **本目录 4 个 exe 均被 `obsidian-exe-launcher` 插件引用**，改脚本后必须重新打包，否则插件调用旧版本。

## 5. 测试
- 运行单个脚本（无参数）检查是否报错。
- `--check` / `--help` 参数仅检查不执行搬移（防误触发）。
- 改动共享配置后，需跑一遍 `home-to-mulu-sync.py` / `mulu-to-home-sync.py` 回归。