# D:\Python - AI 速查手册
> 工作区级规则。项目级规则见各 `projects/*/CLAUDE.md`。
## 1. 目录结构
```
D:\Python/
├── projects/              # 正式项目（独立 Git）
│   ├── leodiarycode/      # LeoDiary 工具链（Python）
│   └── obsidian-exe-launcher/  # Obsidian 插件（TypeScript）
├── tools/                 # 独立工具
│   ├── Obsidian-upload/   # LeoDiary Capture（pywebview 快速记录工具）
│   ├── sync-GitHub/
│   ├── chrome-go/
│   └── logseq-cleanup/
├── experiments/           # 实验验证
├── archive/               # 历史归档
└── tmp/                   # 临时目录
```
## 2. CLAUDE.md 三层体系
| 层级 | 文件 | 职责 |
|------|------|------|
| 工作区 | `D:\Python\CLAUDE.md` | 项目容器、命名、编码、通用规则 |
| 项目 | `projects/*/CLAUDE.md` | 技术栈、import 方式、运行命令 |
| 目录 | （子目录自有规则） | 具体模块分工 |
## 3. 项目速查
### projects/leodiarycode（Python）
核心目录结构：
```
leodiarycode/
├── src/                   # importable 模块
│   ├── obsidian_common.py
│   ├── obsidian_skill_utils.py
│   ├── frontmatter_enrich.py
│   ├── health_check.py
│   └── check_*.py
├── scripts/               # CLI 入口
│   ├── ai_index_builder_v2.py    # ⭐ AI 检索 Builder（Router/Cache/Search/Domain）
│   ├── batch_skill_test.py       # ⭐ 25 查询批量测试脚本
│   ├── ai_retrieval_healthcheck.py  # ⭐ 58 项全链路健康检查
│   ├── ai_index_builder.py
│   ├── index-updater.py
│   ├── home-to-mulu-sync.py
│   ├── mulu-to-home-sync.py
│   ├── rename-check.py
│   ├── Obsidian -备份笔记.py
│   └── Obsidian -备份python代码.py
├── lib/                   # leo-os-tools 子包
├── tests/
└── docs/
```
### projects/obsidian-exe-launcher（TypeScript）
```
obsidian-exe-launcher/
├── src/main.ts
├── manifest.json
├── package.json
├── esbuild.config.mjs
└── main.js
```
## 4. 独立工具（tools/）
| 工具 | 路径 |
|------|------|
| LeoDiary Capture | `tools/Obsidian-upload/`（README.md 见其目录；打包 `build.bat`，规则见该目录 CLAUDE.md） |
| Skill 同步 | `tools/sync-GitHub/skill-sync-agentcode.py` |
| 代理节点爬取 | `tools/chrome-go/ChromeGo - 节点爬取脚本 @ 代理节点下载.py` |
| Logseq 附件清理 | `tools/logseq-cleanup/Logseq - 附件清理脚本 @ 清理无用文件.py` |
## 5. 历史归档（archive/）
原 `_archive_oneoff/` 内容迁移至此。不再维护，参考用。
## 6. Python 脚本 vs Obsidian Skills 分工（防死循环）
> Skills 位于 `C:\Users\leokou\.claude\skills\`。
| 维度 | Python 脚本 | Obsidian Skills |
|------|------------|-----------------|
| 驱动方式 | 手动运行 / EXE 点击 | AI 自然语言调用 |
| 核心能力 | 结构维护、批量操作、快、不用模型 | 内容理解、分类、摘要、语义判断 |
| 处理 🧩目录文件 | 仅删除失效链接 | 分类区域、✍️摘要、frontmatter、重排 |
| 处理 📖目录 索引.md | `目录结构树` + `统计摘要` | `按领域分组`（分类+✍️摘要+状态） |
| 处理文件标题 | 无 frontmatter 文件的标题修正 | 有 frontmatter 文件的标题（Python 跳过） |
**核心原则**：Python 只做行级增删，不重排、不分类、不加摘要；Skill 做内容加工，可以随意重排。
## 7. 常用运行命令
```bash
# AI 检索 - Router 分类
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py router "查询内容"
# AI 检索 - 搜索
python D:\Python\projects\leodiarycode\scripts\ai_index_builder_v2.py search "查询内容" --top 5
# AI 检索 - 批量测试（25 查询）
python D:\Python\projects\leodiarycode\scripts\batch_skill_test.py
# AI 检索 - 全链路健康检查（58 项）
python D:\Python\projects\leodiarycode\scripts\ai_retrieval_healthcheck.py
# 索引更新
python D:\Python\projects\leodiarycode\scripts\index-updater.py
# Skill 一致性检查
python D:\Python\projects\leodiarycode\src\obsidian_skill_utils.py skill-health-check "C:\Users\leokou\.claude\skills\Obsidian" "D:\Obsidian\LeoDiary"
```
## 8. 打包 EXE
在 `D:\Python\projects\leodiarycode` 下运行：
```bash
pyinstaller --onefile --name "工具名" "scripts/脚本名.py"
```
EXE 输出到 `dist/`。

# 通用 AI 开发执行规则
## 一、开发基本原则
所有开发必须遵守：
1. 稳定性优先
2. 数据安全优先
3. 最小修改原则
4. 模块化设计
5. 可维护性优先
6. 向后兼容优先
禁止：
- 未分析直接修改代码
- 大范围重构解决小问题
- 删除已有功能
- 修改未知影响范围的公共接口
- 引入无必要依赖
- 提交临时代码
## 二、AI 修改代码流程
修改代码前：
1. 阅读项目 CLAUDE.md
2. 阅读 README.md
3. 理解目录结构
4. 查找相关模块
5. 分析调用关系
6. 确认修改范围
修改原则：
优先新增模块。
其次扩展已有模块。
最后修改核心代码。
完成后验证：
- 功能正常
- 原功能未破坏
- 日志正常
- 配置正常
- 启动正常
- 打包正常
## 三、模块化设计规则
原则：
一个模块负责一个主要职责。
禁止：
- 单文件持续堆积业务代码
- UI、业务、数据混合
- 复制粘贴重复逻辑
公共能力必须抽离：
- 文件操作
- JSON处理
- 日期处理
- 日志
- 路径管理
统一放入：
utils/
common/
services/
## 四、职责分离
UI层：
负责：
- 页面
- 输入
- 显示
- 交互
业务层：
负责：
- 流程
- 规则
- 数据处理
数据层：
负责：
- 文件
- 数据库
- 存储
禁止：
按钮事件直接处理核心业务。
## 五、配置管理
禁止硬编码：
错误：
```python
PATH="D:\\data"
正确：
config.json
所有可变化内容必须配置化：
路径
参数
开关
用户设置
六、错误处理
所有外部操作必须处理异常：
包括：
文件
网络
系统调用
数据解析
要求：
捕获异常
写日志
返回明确结果
禁止：
静默失败。
七、日志规范
正式项目必须具有日志。
记录：
启动
错误
核心操作
外部调用
禁止：
正式代码大量使用 print。
八、数据安全
涉及用户数据：
必须：
避免覆盖
保留恢复能力
明确影响范围
禁止：
未经确认删除数据。
九、测试要求
新增功能必须验证：
正常流程：
正常输入
正常运行
异常流程：
空数据
错误输入
文件不存在
网络失败
修改核心模块：
必须测试旧功能。
十、Git规范
Commit 类型：
feat:
fix:
refactor:
docs:
chore:
禁止提交：
缓存文件
密钥
临时文件
编译垃圾
十一、AI禁止行为
禁止：
未读取规则直接修改
自行改变架构
自行替换技术栈
删除已有模块
重写整个项目
修改无关文件
添加未经说明功能
十二、最终目标
所有项目达到：
模块清晰
低耦合
易测试
易扩展
易维护
长期演进
开发原则：
小步迭代。
最小影响。
可验证。
可回滚。
