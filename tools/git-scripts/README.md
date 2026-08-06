# git-scripts (cnb.cool) - tools 独立仓库

cnb.cool 平台的 Git 快捷脚本集（`.bat` 双击入口 + `.ps1` 实际逻辑）。

> 本目录是纯 `.bat/.ps1` 脚本，无 Python，不需要 PyInstaller 打包 exe。
> **仓库根是 `D:\Python\tools`**（独立 git 仓库，同步到 `cnb.cool/leokous/Python-tools`）。

## 包含脚本

| 脚本 | 功能 |
|------|------|
| `git_init_cnb.bat` | 首次初始化并推送 cnb.cool（双击运行） |
| `git_init_cnb.ps1` | init 逻辑：git init → 首次提交 → 绑定 origin → main 分支 → push |
| `git_push.bat` | 日常同步入口（双击运行） |
| `git_push.ps1` | 拉取/推送/拉取+推送 菜单逻辑 |

## 使用方式

```bash
# 首次初始化（在 D:\Python\tools 目录下）
D:\Python\tools\git-scripts\git_init_cnb.bat

# 日常同步
D:\Python\tools\git-scripts\git_push.bat
```

## 注意事项

- 需要 cnb.cool 的 Git Username（一般填 `cnb`）与访问令牌 Token
- 凭据通过 `git config credential.helper=store` 保存，后续免密
- 相关文件修改时注意 UTF-8 编码
- bat 文件保持 ASCII-only（中文说明放本 README）
