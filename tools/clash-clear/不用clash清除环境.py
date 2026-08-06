#!/usr/bin/env python3
"""
彻底清除 Clash 代理残留 - 一键清理脚本
清理所有 127.0.0.1:7897 相关的代理配置
功能	实现方式
杀进程	taskkill /F /IM 强制终止 clash/mihomo/verge
清环境变量	winreg.DeleteValue 直接操作注册表 HKCU/HKLM
重置系统代理	winreg.SetValueEx 修改 Internet Settings 注册表项
重置 WinHTTP	netsh winhttp reset proxy
刷新 DNS	ipconfig /flushdns
删 curl 配置	os.remove 删除多个路径的 _curlrc
清 Git 代理	git config --global --unset
清当前会话	os.environ.pop() 删除 Python 进程内的代理变量
验证结果	遍历注册表 + 检查环境变量，全链路验证
import os
"""
# 这个 Python 脚本通过调用 Windows API 实现清理功能，比 bat 脚本更强大：

import os
import sys
import ctypes
import subprocess
import shutil
from typing import List, Optional

# Windows 特定导入
if sys.platform == "win32":
    import winreg


# ============ 工具函数 ============

def is_admin() -> bool:
    """检测当前是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_cmd(cmd: str) -> subprocess.CompletedProcess:
    """执行系统命令"""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30
    )


def print_step(step: int, total: int, title: str):
    """打印步骤标题"""
    print(f"\n[步骤 {step}/{total}] {title}")
    print("-" * 40)


def print_ok(msg: str = ""):
    """打印成功消息"""
    print(f"  ✓ {msg}")


def print_warn(msg: str):
    """打印警告消息"""
    print(f"  ⚠ {msg}")


def print_info(msg: str):
    """打印信息"""
    print(f"  → {msg}")


# ============ 清理函数 ============

def kill_clash_processes():
    """杀掉 Clash/Mihomo/Verge 残留进程"""
    if sys.platform != "win32":
        return

    killed = False
    for name in ["clash", "mihomo", "verge"]:
        proc = run_cmd(f'taskkill /F /IM "{name}.exe"')
        if proc.returncode == 0:
            killed = True
            print_info(f"已终止 {name}.exe")

    if killed:
        print_ok("残留进程已清理")
    else:
        print_ok("无残留进程")


def clean_env_variables(scope: str = "User"):
    """清理指定范围的代理环境变量"""
    if sys.platform != "win32":
        return

    proxy_vars = [
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "no_proxy",
        "ALL_PROXY", "all_proxy",
        "ICUBE_PROXY_HOST", "PREVIEW_PROXY_ENABLED"
    ]

    hkey = winreg.HKEY_CURRENT_USER if scope == "User" else winreg.HKEY_LOCAL_MACHINE
    subkey = r"Environment"

    try:
        with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_SET_VALUE) as key:
            removed = []
            for var in proxy_vars:
                try:
                    winreg.DeleteValue(key, var)
                    removed.append(var)
                except FileNotFoundError:
                    pass
                except PermissionError:
                    print_warn(f"无权限删除 {var}（需要管理员权限）")
            
            if removed:
                print_info(f"已删除: {', '.join(removed)}")
                print_ok(f"{scope}级环境变量已清理")
            else:
                print_ok(f"{scope}级环境变量干净")
    except FileNotFoundError:
        print_ok(f"{scope}级环境变量干净（注册表键不存在）")
    except PermissionError:
        print_warn(f"无权限访问注册表（{scope}级需要管理员权限）")
    except Exception as e:
        print_warn(f"清理环境变量时出错: {e}")


def clean_internet_settings():
    """重置 Windows 系统代理设置"""
    if sys.platform != "win32":
        return

    path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "")
            print_ok("系统代理已关闭 (ProxyEnable=0)")
    except Exception as e:
        print_warn(f"重置系统代理失败: {e}")


def reset_winhttp():
    """重置 WinHTTP 代理"""
    result = run_cmd("netsh winhttp reset proxy")
    if result.returncode == 0:
        print_ok("WinHTTP 代理已重置")
    else:
        print_warn("WinHTTP 代理重置可能需要管理员权限")


def flush_dns():
    """刷新 DNS 缓存"""
    result = run_cmd("ipconfig /flushdns")
    if "Successfully" in result.stdout or result.returncode == 0:
        print_ok("DNS 缓存已刷新")
    else:
        print_info(result.stdout.strip())


def delete_curl_configs():
    """删除 curl 配置文件 (_curlrc)"""
    paths_to_check = []
    
    appdata = os.environ.get("APPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")
    
    if appdata:
        paths_to_check.extend([
            os.path.join(appdata, "_curlrc"),
            os.path.join(appdata, ".curlrc"),
        ])
    if userprofile:
        paths_to_check.extend([
            os.path.join(userprofile, "_curlrc"),
            os.path.join(userprofile, ".curlrc"),
        ])

    deleted = []
    for path in paths_to_check:
        if os.path.isfile(path):
            try:
                os.remove(path)
                deleted.append(path)
                print_info(f"已删除: {path}")
            except Exception as e:
                print_warn(f"删除 {path} 失败: {e}")

    if deleted:
        print_ok(f"curl 配置文件已清理 ({len(deleted)} 个)")
    else:
        print_ok("curl 配置文件干净")


def clean_git_proxy():
    """清理 Git 全局代理配置"""
    git_path = shutil.which("git")
    if not git_path:
        print_info("Git 未安装，跳过")
        return

    for proxy_type in ["http.proxy", "https.proxy"]:
        run_cmd(f'git config --global --unset "{proxy_type}"')
    
    result = run_cmd("git config --global --get http.proxy")
    result2 = run_cmd("git config --global --get https.proxy")
    
    if not result.stdout.strip() and not result2.stdout.strip():
        print_ok("Git 全局代理已清理")
    else:
        print_info("Git 代理配置已处理")


def clean_current_session():
    """清理当前 Python 进程的代理环境变量"""
    proxy_keys = [
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "no_proxy",
        "ALL_PROXY", "all_proxy",
        "ICUBE_PROXY_HOST", "PREVIEW_PROXY_ENABLED"
    ]
    
    cleaned = []
    for key in proxy_keys:
        if key in os.environ:
            del os.environ[key]
            cleaned.append(key)
    
    if cleaned:
        print_info(f"已清除当前会话变量: {', '.join(cleaned)}")
        print_ok("当前会话代理变量已清除")
    else:
        print_ok("当前会话干净")


def verify_cleanup():
    """验证清理结果"""
    print("\n" + "=" * 50)
    print("  验证清理结果")
    print("=" * 50)

    all_clean = True

    if sys.platform == "win32":
        # 检查注册表环境变量
        for scope, hkey in [("用户级", winreg.HKEY_CURRENT_USER), ("系统级", winreg.HKEY_LOCAL_MACHINE)]:
            try:
                with winreg.OpenKey(hkey, r"Environment") as key:
                    i = 0
                    found = []
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            if name.lower().endswith("_proxy") or name in ["NO_PROXY", "no_proxy"]:
                                found.append(f"{name}={value}")
                            i += 1
                        except WindowsError:
                            break
                    
                    if found:
                        print_warn(f"[{scope}] 仍有残留: {', '.join(found)}")
                        all_clean = False
                    else:
                        print_ok(f"[{scope}] 无代理变量")
            except FileNotFoundError:
                print_ok(f"[{scope}] 无代理变量")
            except PermissionError:
                print_info(f"[{scope}] 无法读取（需要管理员权限）")

        # 检查系统代理状态
        try:
            path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
                if enabled == 0:
                    print_ok("系统代理已关闭")
                else:
                    print_warn("系统代理仍然开启！")
                    all_clean = False
        except Exception:
            pass

    # 检查当前环境变量
    current_proxy = [k for k in os.environ if "proxy" in k.lower()]
    if current_proxy:
        print_warn(f"当前会话仍有: {', '.join(current_proxy)}")
        all_clean = False
    else:
        print_ok("当前会话无代理变量")

    # 检查 curl 配置
    curl_paths = []
    appdata = os.environ.get("APPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")
    if appdata:
        curl_paths.extend([os.path.join(appdata, "_curlrc"), os.path.join(appdata, ".curlrc")])
    if userprofile:
        curl_paths.extend([os.path.join(userprofile, "_curlrc"), os.path.join(userprofile, ".curlrc")])
    
    curl_found = [p for p in curl_paths if os.path.isfile(p)]
    if curl_found:
        print_warn(f"curl 配置文件仍存在: {', '.join(curl_found)}")
        all_clean = False
    else:
        print_ok("curl 配置文件干净")

    return all_clean


# ============ 主程序 ============

def main():
    print("=" * 50)
    print("  彻底清除 Clash 代理残留")
    print("  一键清理所有 127.0.0.1:7897 代理配置")
    print("=" * 50)

    if sys.platform != "win32":
        print("\n⚠ 本脚本仅支持 Windows 系统")
        sys.exit(1)

    admin = is_admin()
    if not admin:
        print("\n⚠ 当前未以管理员权限运行")
        print("  系统级环境变量和 WinHTTP 代理重置需要管理员权限")
        print("  右键本脚本 → 以管理员身份运行可完成全部清理")
        print()

    total_steps = 10

    # 步骤 1: 杀进程
    print_step(1, total_steps, "杀掉 Clash/Mihomo/Verge 残留进程")
    kill_clash_processes()

    # 步骤 2: 清用户级环境变量
    print_step(2, total_steps, "清理用户级持久环境变量（注册表 HKCU）")
    clean_env_variables("User")

    # 步骤 3: 清系统级环境变量
    print_step(3, total_steps, "清理系统级持久环境变量（注册表 HKLM）")
    clean_env_variables("Machine")

    # 步骤 4: 重置系统代理
    print_step(4, total_steps, "重置 Windows 系统代理设置")
    clean_internet_settings()

    # 步骤 5: 重置 WinHTTP
    print_step(5, total_steps, "重置 WinHTTP 代理")
    reset_winhttp()

    # 步骤 6: 刷 DNS
    print_step(6, total_steps, "刷新 DNS 缓存")
    flush_dns()

    # 步骤 7: 删 curl 配置
    print_step(7, total_steps, "删除 curl 配置文件 (_curlrc)")
    delete_curl_configs()

    # 步骤 8: 清 Git 代理
    print_step(8, total_steps, "清理 Git 全局代理配置")
    clean_git_proxy()

    # 步骤 9: 清当前会话
    print_step(9, total_steps, "清理当前会话的代理环境变量")
    clean_current_session()

    # 步骤 10: 验证
    print_step(10, total_steps, "验证清理结果")
    all_clean = verify_cleanup()

    # 总结
    print("\n" + "=" * 50)
    if all_clean:
        print("  ✅ 清理完成！所有代理配置已清除。")
    else:
        print("  ⚠ 部分项目需要管理员权限，请以管理员身份重新运行。")
    
    print("\n  重要：请重启电脑让环境变量完全刷新。")
    print("  重启后验证：")
    print('    PowerShell: Get-ChildItem Env: | Where-Object { $_.Name -match "proxy" }')
    print('    PowerShell: curl.exe ifconfig.me')
    print("=" * 50)

    try:
        input("\n按回车键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
