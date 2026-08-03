"""临时测试脚本 - 诊断主题系统问题"""
import os
import webview

base_dir = os.path.dirname(os.path.abspath(__file__))
test_html = os.path.join(base_dir, "web", "test-theme.html")

print(f"测试页面路径: {test_html}")
print(f"文件存在: {os.path.exists(test_html)}")

window = webview.create_window("主题测试", url=test_html, width=700, height=500)
webview.start(debug=True, gui="edgechromium")
