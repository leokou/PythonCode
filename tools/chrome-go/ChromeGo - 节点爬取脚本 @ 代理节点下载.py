import os
import requests
from urllib.parse import urlparse


def save_url_content_to_file(url, save_directory, proxies=None, verify_ssl=True):
    """从指定 URL 下载内容并保存到本地文件。

    参数:
        url: 要下载的文件 URL。
        save_directory: 本地保存的根目录。
        proxies: 可选的代理设置，格式为 {'http': ..., 'https': ...}。
        verify_ssl: 是否验证 SSL 证书，默认 True。
    """
    try:
        # 使用 requests 发送 GET 请求，支持代理和 SSL 验证设置
        response = requests.get(url, proxies=proxies, verify=verify_ssl)
        if response.status_code == 200:
            # 解析 URL 以便从路径中提取相对保存路径
            parsed_url = urlparse(url)
            master_value = parsed_url.path.split("master/")[1]

            # 构建完整的本地保存路径
            save_path = os.path.join(save_directory, master_value)

            # 确保保存文件所需的目录已创建
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 将响应文本写入本地文件，使用 UTF-8 编码
            with open(save_path, 'w', encoding='utf-8') as file:
                file.write(response.text)

            print(f"文件保存成功：{save_path}")
        else:
            print(f"获取网址内容失败，状态码：{response.status_code}")
    except Exception as e:
        print(f"获取网址内容并保存到文件过程中出现错误：{e}")


# 需要下载并保存的 URL 列表
urls_to_save = [
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/hysteria2/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/hysteria2/1/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/hysteria2/13/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/hysteria2/2/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/xray/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/xray/1/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/xray/2/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/xray/3/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/singbox/config.json",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/singbox/1/config.json",
    "https://www.gitlabip.xyz/Alvin9999/PAC/master/naiveproxy/1/config.json",
    "https://www.githubip.xyz/Alvin9999/PAC/master/naiveproxy/config.json",
]

# 本地保存根目录
save_directory = r"D:\APP\·00 -翻墙软件\ChromeGo\syn"

# 代理设置，用于通过本地代理服务器访问网络
proxies = {
    'http': 'http://192.168.10.38:10808',
    'https': 'http://192.168.10.38:10808',
}

# 遍历 URL 列表，依次下载并保存文件
for url in urls_to_save:
    save_url_content_to_file(url, save_directory, proxies=proxies, verify_ssl=True)
