# clash-clear 清理脚本

一键彻底清除 Clash 代理残留环境（进程 / 环境变量 / 系统代理 / 各类代理配置）。

## 功能说明

| 功能 | 实现方式 |
|------|----------|
| 杀进程 | `taskkill /F /IM` 强制终止 clash / mihomo / verge |
| 清环境变量 | `winreg` 直接操作注册表 HKCU/HKLM |
| 重置系统代理 | 修改 Internet Settings 注册表项 |
| 重置 WinHTTP | `netsh winhttp reset proxy` |
| 刷新 DNS | `ipconfig /flushdns` |
| 删 curl 配置 | 删除多个路径的 `_curlrc` |
| 清 Git 代理 | `git config --global --unset` |
| 清当前会话 | 删除 Python 进程内的代理环境变量 |
| 验证结果 | 遍历注册表 + 检查环境变量全链路验证 |

## 使用方式

```bash
python "不用clash清除环境.py"
```

打包 exe 后运行 `clash-clear.exe` 即可。

## 注意事项

- **需要管理员权限**：脚本自动检测并提示以管理员身份运行
- 清除范围：`127.0.0.1:7897` 相关的代理配置

## 打包 exe

运行 `build-exe.bat`，产物输出到 `D:\Python\dist\clash-clear.exe`。
