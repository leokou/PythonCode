#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LD-DVA Final 健康检查脚本
========================
系统性检查 AI 检索加速层的完整性、新鲜度、连通性。

用法：
  python health_check.py                # 执行全部检查
  python health_check.py --report path  # 执行并保存报告
  python health_check.py --quick        # 快速检查（仅关键项）
"""

import sys
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from obsidian_common import VAULT_ROOT, should_skip_dir, should_skip_file, read_text_safe

PYTHON_DIR = Path(__file__).parent.parent

def _find_script(rel_path: str) -> Path:
    for sub in ["src", "scripts", "lib", "tests", "."]:
        d = PYTHON_DIR / sub if sub != "." else PYTHON_DIR
        candidate = d / rel_path
        if candidate.exists():
            return candidate
    return PYTHON_DIR / rel_path

AI_INDEX_DIR = VAULT_ROOT / "🤖AI_INDEX"
REQUIRED_INDEX_FILES = [
    ("retrieval-index.md", "关键词倒排索引", 100),
    ("tag-index.md", "标签关联索引", 50),
    ("entity-index.md", "实体关系索引", 10),
    ("query-cache.json", "查询缓存", 50),
    ("index-state.json", "索引状态追踪", 500),
]

CORE_RULE_DIR = VAULT_ROOT / "8- 📜核心规则"
REQUIRED_CORE_RULES = [
    ("知识双视图原则.md", "双视图隔离、单一数据源"),
    ("检索协议.md", "L0-L2读取协议、检索链路"),
    ("Schema规范.md", "Frontmatter标准化、三段式摘要"),
]

SKILL_DIR = Path(r"C:\Users\leokou\.claude\skills\Obsidian")
SKILL_CHECKS = [
    {
        "skill": "obsidian-knowledge-queryer",
        "name": "知识查询",
        "required_markers": [
            ("AI 视图检索协议（LD-DVA Final 强制）", "AI视图检索协议章节"),
            ("cache-read", "缓存读取命令"),
            ("cache-write", "缓存写入命令"),
            ("retrieval-index.md", "第一读取入口引用"),
            ("tag-index.md", "标签索引降级引用"),
            ("entity-index.md", "实体索引降级引用"),
        ],
    },
    {
        "skill": "obsidian-knowledge-compiler",
        "name": "知识编译",
        "required_markers": [
            ("AI_INDEX 扩展字段", "AI_INDEX扩展字段定义"),
            ("三段式摘要", "摘要格式规范"),
            ("entities", "实体字段引用"),
            ("keywords", "关键词字段引用"),
        ],
    },
    {
        "skill": "obsidian-knowledge-organizer",
        "name": "知识归档",
        "required_markers": [
            ("ai_index_builder.py incremental", "归档后增量更新触发"),
            ("AI 索引更新", "索引更新章节"),
        ],
    },
    {
        "skill": "obsidian-pipeline",
        "name": "知识流水线",
        "required_markers": [
            ("AI_INDEX 触发", "流水线Step6触发"),
            ("ai_index_builder.py incremental", "增量更新调用"),
        ],
    },
    {
        "skill": "obsidian-mulu-fenlei-summary",
        "name": "目录分类",
        "required_markers": [
            ("AI_INDEX 同步", "目录更新后同步"),
            ("ai_index_builder.py rebuild", "全量重建调用"),
        ],
    },
    {
        "skill": "obsidian-fire-rename",
        "name": "文件重命名",
        "required_markers": [
            ("AI_INDEX 同步", "重命名后同步"),
            ("ai_index_builder.py rename", "重命名命令调用"),
        ],
    },
]


@dataclass
class CheckResult:
    category: str
    name: str
    status: str  # pass / warn / fail
    detail: str
    remediation: str = ""
    weight: int = 1

    @property
    def score(self) -> int:
        return {"pass": 100, "warn": 50, "fail": 0}.get(self.status, 0)


class HealthChecker:
    def __init__(self, vault_root: Optional[Path] = None):
        self.vault_root = vault_root or VAULT_ROOT
        self.results: List[CheckResult] = []
        self.start_time = datetime.now()

    def add(self, category: str, name: str, status: str, detail: str, remediation: str = "", weight: int = 1):
        r = CheckResult(category=category, name=name, status=status, detail=detail, remediation=remediation, weight=weight)
        self.results.append(r)
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "?")
        print(f"  {icon} [{category}] {name}: {detail}")
        return r

    # ============================================================
    # 1. 文件完整性检查
    # ============================================================
    def check_file_integrity(self):
        print("\n📁 1. 文件完整性检查")
        print("-" * 40)

        for fname, desc, min_size in REQUIRED_INDEX_FILES:
            fpath = AI_INDEX_DIR / fname
            if not fpath.exists():
                self.add("文件完整性", fname, "fail",
                         f"{desc} 文件不存在: {fpath}",
                         f"运行: python ai_index_builder.py rebuild", weight=3)
                continue

            size = fpath.stat().st_size
            if size < min_size:
                self.add("文件完整性", fname, "warn",
                         f"{desc} 文件过小 ({size} bytes)，可能不完整",
                         f"运行: python ai_index_builder.py rebuild", weight=2)
                continue

            if fname.endswith('.json'):
                try:
                    data = json.loads(fpath.read_text(encoding='utf-8-sig'))
                    self.add("文件完整性", fname, "pass",
                             f"{desc} 存在且JSON格式有效 ({size:,} bytes)", weight=1)
                except json.JSONDecodeError as e:
                    self.add("文件完整性", fname, "fail",
                             f"{desc} JSON格式错误: {e}",
                             f"运行: python ai_index_builder.py rebuild", weight=3)
            else:
                content = read_text_safe(fpath)
                stripped = content.lstrip()
                if stripped.startswith('---') and '\n---\n' in stripped:
                    self.add("文件完整性", fname, "pass",
                             f"{desc} 存在且格式正确 ({size:,} bytes)", weight=1)
                else:
                    self.add("文件完整性", fname, "warn",
                             f"{desc} 存在但frontmatter可能缺失",
                             f"运行: python ai_index_builder.py rebuild", weight=2)

    # ============================================================
    # 2. 索引新鲜度检查
    # ============================================================
    def check_index_freshness(self):
        print("\n🔄 2. 索引新鲜度检查")
        print("-" * 40)

        state_file = AI_INDEX_DIR / "index-state.json"
        if not state_file.exists():
            self.add("索引新鲜度", "index-state.json", "fail",
                     "index-state.json 不存在，无法检查新鲜度",
                     f"运行: python ai_index_builder.py rebuild", weight=3)
            return

        state = json.loads(state_file.read_text(encoding='utf-8-sig'))
        last_rebuild = state.get('last_full_rebuild', '')
        tracked = state.get('tracked_files', 0)
        files_dict = state.get('files', {})

        if last_rebuild:
            try:
                rebuild_time = datetime.fromisoformat(last_rebuild)
                age = datetime.now() - rebuild_time
                if age > timedelta(hours=24):
                    self.add("索引新鲜度", "全量重建时间", "fail",
                             f"最后全量重建已超过24小时 ({age})，索引可能过时",
                             f"运行: python ai_index_builder.py rebuild", weight=3)
                elif age > timedelta(hours=4):
                    self.add("索引新鲜度", "全量重建时间", "warn",
                             f"最后全量重建 ({age})，建议检查",
                             f"运行: python ai_index_builder.py incremental", weight=1)
                else:
                    self.add("索引新鲜度", "全量重建时间", "pass",
                             f"最后全量重建于 {last_rebuild} ({age.seconds // 3600}小时前)", weight=1)
            except (ValueError, TypeError):
                self.add("索引新鲜度", "全量重建时间", "warn",
                         f"时间格式异常: {last_rebuild}", weight=1)

        self.add("索引新鲜度", "追踪文件数", "pass",
                 f"index-state.json 追踪 {tracked} 个文件，{len(files_dict)} 条记录", weight=1)

        current_files = self._count_knowledge_files()
        if abs(current_files - tracked) > 10:
            self.add("索引新鲜度", "文件数漂移", "fail",
                     f"当前知识库 {current_files} 个文件 vs 索引追踪 {tracked} 个，差异过大",
                     f"运行: python ai_index_builder.py rebuild", weight=3)
        elif current_files != tracked:
            self.add("索引新鲜度", "文件数漂移", "warn",
                     f"当前 {current_files} 个 vs 索引 {tracked} 个，差 {current_files - tracked}",
                     f"运行: python ai_index_builder.py incremental", weight=2)
        else:
            self.add("索引新鲜度", "文件数漂移", "pass",
                     f"当前文件数与索引一致 ({current_files})", weight=1)

        stale_entries = []
        for path, info in files_dict.items():
            updated = info.get('updated_at', '')
            if updated:
                try:
                    t = datetime.fromisoformat(updated)
                    if datetime.now() - t > timedelta(days=7):
                        stale_entries.append(path)
                except (ValueError, TypeError):
                    pass

        if stale_entries:
            self.add("索引新鲜度", "过时索引条目", "warn",
                     f"有 {len(stale_entries)} 个索引条目超过7天未更新",
                     f"运行: python ai_index_builder.py rebuild", weight=1)
        else:
            self.add("索引新鲜度", "过时索引条目", "pass",
                     "所有索引条目在7天内更新", weight=1)

    # ============================================================
    # 3. Skill 集成检查
    # ============================================================
    def check_skill_integration(self):
        print("\n🔌 3. Skill 集成检查")
        print("-" * 40)

        for skill_info in SKILL_CHECKS:
            skill_name = skill_info["skill"]
            skill_label = skill_info["name"]
            skill_path = SKILL_DIR / skill_name / "SKILL.md"

            if not skill_path.exists():
                self.add("Skill集成", skill_label, "fail",
                         f"SKILL.md 不存在: {skill_path}",
                         f"检查 {skill_name} 插件是否正确安装", weight=3)
                continue

            content = read_text_safe(skill_path)
            missing = []
            for marker, desc in skill_info["required_markers"]:
                if marker not in content:
                    missing.append(f"{desc}({marker})")

            if missing:
                self.add("Skill集成", skill_label, "fail",
                         f"缺失 {len(missing)} 个关键标记: {', '.join(missing)}",
                         f"重新打开 {skill_name} 进行 LD-DVA Final 改造", weight=3)
            else:
                self.add("Skill集成", skill_label, "pass",
                         f"全部 {len(skill_info['required_markers'])} 个关键标记正常", weight=1)

            self._check_skill_command_executable(skill_label, content)

    def _check_skill_command_executable(self, skill_label: str, content: str):
        commands = re.findall(r'python\s+[^\s]+ai_index_builder\.py\s+(\S+)', content)
        if not commands:
            return

        ai_builder = _find_script("ai_index_builder.py")
        for cmd in set(commands):
            if not ai_builder.exists():
                self.add("Skill集成", f"{skill_label}→{cmd}", "fail",
                         f"ai_index_builder.py 未找到（搜索路径: {PYTHON_DIR}）",
                         "检查 ai_index_builder.py 是否在正确位置", weight=3)
                continue

            if cmd in ('incremental', 'rebuild', 'update', 'rename', 'cache-read',
                       'cache-write', 'cache-invalidate', 'cache-clear', 'status'):
                try:
                    import subprocess
                    result = subprocess.run(['python', str(ai_builder), '--help'],
                                           capture_output=True, text=True, timeout=10,
                                           encoding='utf-8', errors='replace')
                    if result.returncode == 0 and cmd in (result.stdout or ''):
                        self.add("Skill集成", f"{skill_label}→{cmd}", "pass",
                                 f"命令 {cmd} 在 ai_index_builder.py 中可用", weight=1)
                    else:
                        self.add("Skill集成", f"{skill_label}→{cmd}", "fail",
                                 f"命令 {cmd} 不存在或不可用",
                                 f"ai_index_builder.py 中缺少 {cmd} 命令", weight=2)
                except Exception as e:
                    self.add("Skill集成", f"{skill_label}→{cmd}", "warn",
                             f"无法验证命令: {e}", weight=1)

    # ============================================================
    # 4. 核心规则文件检查
    # ============================================================
    def check_core_rules(self):
        print("\n📜 4. 核心规则文件检查")
        print("-" * 40)

        if not CORE_RULE_DIR.exists():
            self.add("核心规则", "目录存在", "fail",
                     f"核心规则目录不存在: {CORE_RULE_DIR}",
                     "创建 8- 📜核心规则 目录", weight=3)
            return

        for fname, desc in REQUIRED_CORE_RULES:
            fpath = CORE_RULE_DIR / fname
            if not fpath.exists():
                self.add("核心规则", fname, "fail",
                         f"{desc} 文件不存在",
                         f"创建 {fname} 并写入 LD-DVA Final 规范", weight=3)
                continue

            content = read_text_safe(fpath)
            if len(content.strip()) < 50:
                self.add("核心规则", fname, "warn",
                         f"{desc} 文件内容过少，可能不完整",
                         f"补充 {fname} 内容", weight=2)
            else:
                self.add("核心规则", fname, "pass",
                         f"{desc} 文件存在且内容充足 ({len(content)} chars)", weight=1)

    # ============================================================
    # 5. 路径一致性检查
    # ============================================================
    def check_path_consistency(self):
        print("\n🔗 5. 路径一致性检查")
        print("-" * 40)

        retrieval_file = AI_INDEX_DIR / "retrieval-index.md"
        if not retrieval_file.exists():
            self.add("路径一致性", "retrieval-index.md", "fail",
                     "retrieval-index.md 不存在",
                     "运行: python ai_index_builder.py rebuild", weight=3)
            return

        content = read_text_safe(retrieval_file)
        paths = re.findall(r'\*\*Path\*\*:\s*`([^`]+)`', content)
        if not paths:
            self.add("路径一致性", "路径提取", "fail",
                     "未能从 retrieval-index.md 中提取任何路径",
                     "检查 retrieval-index.md 格式是否正确", weight=3)
            return

        total = len(paths)
        missing = 0
        sample_size = min(100, total)
        for p in paths[:sample_size]:
            full_path = self.vault_root / p
            if not full_path.exists():
                missing += 1

        self.add("路径一致性", "索引路径总数", "pass",
                 f"retrieval-index.md 包含 {total} 个文件路径", weight=1)

        if missing > 0:
            pct = (missing / sample_size) * 100
            self.add("路径一致性", "路径有效性", "fail",
                     f"抽样 {sample_size} 个路径中有 {missing} 个不存在 ({pct:.1f}%)",
                     f"运行: python ai_index_builder.py rebuild 重建索引", weight=3)
        else:
            self.add("路径一致性", "路径有效性", "pass",
                     f"抽样 {sample_size} 个路径全部有效", weight=1)

    # ============================================================
    # 6. 缓存健康检查
    # ============================================================
    def check_cache_health(self):
        print("\n💾 6. 缓存健康检查")
        print("-" * 40)

        cache_file = AI_INDEX_DIR / "query-cache.json"
        if not cache_file.exists():
            self.add("缓存健康", "query-cache.json", "warn",
                     "query-cache.json 不存在（首次使用会自动创建）", weight=1)
            return

        try:
            cache_data = json.loads(cache_file.read_text(encoding='utf-8-sig'))
        except json.JSONDecodeError as e:
            self.add("缓存健康", "query-cache.json", "fail",
                     f"JSON解析错误: {e}",
                     f"运行: python ai_index_builder.py cache-clear", weight=3)
            return

        cache = cache_data.get("cache", [])
        config = cache_data.get("config", {})
        stats = cache_data.get("stats", {})

        self.add("缓存健康", "缓存条目数", "pass",
                 f"当前缓存 {len(cache)} 条", weight=1)

        max_entries = config.get("max_entries", 500)
        ttl_seconds = config.get("ttl_seconds", 86400)
        self.add("缓存健康", "缓存配置", "pass",
                 f"最大 {max_entries} 条, TTL {ttl_seconds}s ({ttl_seconds // 3600}h)", weight=1)

        now = datetime.now()
        expired = 0
        for entry in cache:
            expires_at = entry.get("expires_at", "")
            if expires_at:
                try:
                    exp = datetime.fromisoformat(expires_at)
                    if now > exp:
                        expired += 1
                except (ValueError, TypeError):
                    expired += 1

        if expired > 0:
            self.add("缓存健康", "过期条目", "warn",
                     f"有 {expired} 条缓存已过期但未清理",
                     f"运行: python ai_index_builder.py cache-clear", weight=2)
        else:
            self.add("缓存健康", "过期条目", "pass",
                     "所有缓存条目均在有效期内", weight=1)

        total_entries = stats.get("total_entries", len(cache))
        hit_rate = stats.get("hit_rate", 0)
        tokens_saved = stats.get("tokens_saved", 0)
        self.add("缓存健康", "统计数据", "pass",
                 f"总条目 {total_entries}, 命中率 {hit_rate:.1%}, 预估节省 {tokens_saved:,} tokens", weight=1)

    # ============================================================
    # 7. Python 环境检查
    # ============================================================
    def check_python_environment(self):
        print("\n🐍 7. Python 环境检查")
        print("-" * 40)

        try:
            import obsidian_common
            self.add("Python环境", "obsidian_common 导入", "pass",
                     f"导入成功, VAULT_ROOT={obsidian_common.VAULT_ROOT}", weight=1)
        except ImportError as e:
            self.add("Python环境", "obsidian_common 导入", "fail",
                     f"导入失败: {e}",
                     "检查 obsidian_common.py 是否在 src/ 目录下", weight=3)

        expected_vault = Path(r"D:\Obsidian\LeoDiary")
        if VAULT_ROOT == expected_vault:
            self.add("Python环境", "VAULT_ROOT 路径", "pass",
                     f"VAULT_ROOT 正确指向 {VAULT_ROOT}", weight=1)
        else:
            self.add("Python环境", "VAULT_ROOT 路径", "fail",
                     f"VAULT_ROOT={VAULT_ROOT} 与预期 {expected_vault} 不一致",
                     f"修改 obsidian_common.py 中的 VAULT_ROOT", weight=3)

        if self.vault_root.exists():
            self.add("Python环境", "Vault 根目录", "pass",
                     f"Vault 根目录存在: {self.vault_root}", weight=1)
        else:
            self.add("Python环境", "Vault 根目录", "fail",
                     f"Vault 根目录不存在: {self.vault_root}",
                     "检查 Vault 路径配置", weight=3)

        index_dir = self.vault_root / "🤖AI_INDEX"
        if index_dir.exists():
            self.add("Python环境", "AI_INDEX 目录", "pass",
                     f"AI_INDEX 目录存在: {index_dir}", weight=1)
        else:
            self.add("Python环境", "AI_INDEX 目录", "fail",
                     f"AI_INDEX 目录不存在: {index_dir}",
                     "运行: python ai_index_builder.py rebuild", weight=3)

    # ============================================================
    # 8. 配置一致性检查
    # ============================================================
    def check_config_consistency(self):
        print("\n⚙️ 8. 配置一致性检查")
        print("-" * 40)

        script_path = _find_script("ai_index_builder.py")
        if not script_path.exists():
            self.add("配置一致性", "ai_index_builder.py", "fail",
                     f"ai_index_builder.py 未找到（搜索路径: {PYTHON_DIR}）",
                     "确保 ai_index_builder.py 在正确子目录下（scripts/）", weight=3)
            return

        content = read_text_safe(script_path)

        vault_refs = re.findall(r'(?:VAULT_ROOT\s*=\s*Path\(|from obsidian_common import)', content)
        if vault_refs or 'from obsidian_common import VAULT_ROOT' in content:
            self.add("配置一致性", "ai_index_builder.py 路径", "pass",
                     "ai_index_builder.py 通过 obsidian_common 导入 VAULT_ROOT", weight=1)
        elif 'VAULT_ROOT' in content:
            self.add("配置一致性", "ai_index_builder.py 路径", "pass",
                     "ai_index_builder.py 包含 VAULT_ROOT 引用", weight=1)
        else:
            self.add("配置一致性", "ai_index_builder.py 路径", "warn",
                     "未能确认 ai_index_builder.py 中的 VAULT_ROOT 引用", weight=1)

        expected_skills_dir = SKILL_DIR
        if expected_skills_dir.exists():
            skill_count = len(list(expected_skills_dir.glob("*/SKILL.md")))
            self.add("配置一致性", "Skill 插件目录", "pass",
                     f"Skill 目录存在: {expected_skills_dir}, 共 {skill_count} 个插件", weight=1)
        else:
            self.add("配置一致性", "Skill 插件目录", "fail",
                     f"Skill 目录不存在: {expected_skills_dir}", weight=3)

    # ============================================================
    # 9. 索引内容质量检查
    # ============================================================
    def check_index_quality(self):
        print("\n📊 9. 索引内容质量检查")
        print("-" * 40)

        retrieval_file = AI_INDEX_DIR / "retrieval-index.md"
        if not retrieval_file.exists():
            self.add("索引质量", "retrieval-index.md", "fail",
                     "retrieval-index.md 不存在", weight=3)
            return

        content = read_text_safe(retrieval_file)
        sections = re.findall(r'^###\s+(.+)', content, re.MULTILINE)
        self.add("索引质量", "文档条目数", "pass",
                 f"retrieval-index.md 包含 {len(sections)} 个文档条目", weight=1)

        has_keywords = '**Keywords**' in content
        has_tags = '**Tags**' in content
        has_summary = '**Summary**' in content
        has_path = '**Path**' in content
        missing_fields = []
        if not has_keywords:
            missing_fields.append("Keywords")
        if not has_tags:
            missing_fields.append("Tags")
        if not has_summary:
            missing_fields.append("Summary")
        if not has_path:
            missing_fields.append("Path")

        if missing_fields:
            self.add("索引质量", "必需字段", "fail",
                     f"缺少字段: {', '.join(missing_fields)}",
                     "运行: python ai_index_builder.py rebuild", weight=3)
        else:
            self.add("索引质量", "必需字段", "pass",
                     "所有必需字段 (Path/Summary/Keywords/Tags) 均存在", weight=1)

        tag_file = AI_INDEX_DIR / "tag-index.md"
        if tag_file.exists():
            tag_content = read_text_safe(tag_file)
            tag_count = len(re.findall(r'^###\s+`', tag_content, re.MULTILINE))
            self.add("索引质量", "标签索引", "pass",
                     f"tag-index.md 包含 {tag_count} 个标签分类", weight=1)

        entity_file = AI_INDEX_DIR / "entity-index.md"
        if entity_file.exists():
            entity_content = read_text_safe(entity_file)
            entity_count = len(re.findall(r'^###\s+`', entity_content, re.MULTILINE))
            self.add("索引质量", "实体索引", "pass",
                     f"entity-index.md 包含 {entity_count} 个实体", weight=1)

    # ============================================================
    # 10. 数据质量深度检查
    # ============================================================
    def check_data_quality(self):
        print("\n🔍 10. 数据质量深度检查")
        print("-" * 40)

        state_file = AI_INDEX_DIR / "index-state.json"
        if not state_file.exists():
            self.add("数据质量", "索引状态", "fail",
                     "index-state.json 不存在，无法检查数据质量",
                     "运行: python ai_index_builder.py rebuild", weight=3)
            return

        state = json.loads(state_file.read_text(encoding='utf-8-sig'))
        files_dict = state.get('files', {})
        if not files_dict:
            self.add("数据质量", "索引状态", "fail",
                     "index-state.json 中无文件记录",
                     "运行: python ai_index_builder.py rebuild", weight=3)
            return

        total_files = len(files_dict)
        summaries_ok = 0
        summaries_short = 0
        summaries_empty = 0
        empty_summary_files = []
        keywords_count = 0
        keywords_quality_issues = 0
        tags_quality_issues = 0
        body_preview_missing = 0

        for path, info in files_dict.items():
            doc = info.get('doc', {})
            if not doc:
                continue

            summary = doc.get('summary', '')
            if not summary or len(summary.strip()) < 10:
                summaries_empty += 1
                empty_summary_files.append((path, summary, len(summary.strip()) if summary else 0))
            elif len(summary) < 30:
                summaries_short += 1
            else:
                summaries_ok += 1

            kws = doc.get('keywords', [])
            keywords_count += len(kws)
            for kw in kws:
                kw_str = str(kw)
                if len(kw_str) <= 1 or kw_str.isdigit():
                    keywords_quality_issues += 1
                    break

            tags = doc.get('tags', [])
            for tag in tags:
                tag_str = str(tag)
                if tag_str.isdigit() or len(tag_str) <= 1:
                    tags_quality_issues += 1
                    break

            if not doc.get('body_preview', ''):
                body_preview_missing += 1

        sample_size = total_files

        if summaries_empty > 0:
            file_list_str = "\n".join(
                f"    {i+1}. {p}  (摘要: {repr(s[:60]) if s else '(空)'}, 长度: {l})"
                for i, (p, s, l) in enumerate(empty_summary_files)
            )
            self.add("数据质量", "摘要完整性", "fail",
                     f"抽样 {sample_size} 个文件，{summaries_empty} 个摘要为空或过短 (<10字):\n{file_list_str}",
                     "运行: python frontmatter_enrich.py --apply 补全摘要，或手动编辑以下文件", weight=3)
        else:
            self.add("数据质量", "摘要完整性", "pass",
                     f"抽样 {sample_size} 个文件，摘要完整率 {(summaries_ok/sample_size*100):.0f}%", weight=1)

        if summaries_short > sample_size * 0.3:
            self.add("数据质量", "摘要质量", "warn",
                     f"{summaries_short} 个摘要过短 (<30字)，可能不符合三段式规范",
                     "建议重新生成摘要", weight=2)
        else:
            self.add("数据质量", "摘要质量", "pass",
                     f"摘要平均长度良好，过短摘要占比 {summaries_short/sample_size*100:.0f}%", weight=1)

        if keywords_quality_issues > 0:
            self.add("数据质量", "关键词质量", "warn",
                     f"发现 {keywords_quality_issues} 个文件存在低质量关键词 (单字/纯数字)",
                     "建议清理无意义关键词", weight=2)
        else:
            self.add("数据质量", "关键词质量", "pass",
                     f"抽样文件关键词质量良好", weight=1)

        if tags_quality_issues > 0:
            self.add("数据质量", "标签质量", "warn",
                     f"发现 {tags_quality_issues} 个文件存在低质量标签 (单字/纯数字)",
                     "建议清理无意义标签", weight=2)
        else:
            self.add("数据质量", "标签质量", "pass",
                     f"抽样文件标签质量良好", weight=1)

        if body_preview_missing > 0:
            self.add("数据质量", "body_preview", "warn",
                     f"{body_preview_missing} 个文件缺少 body_preview，将影响正文匹配",
                     "运行: python ai_index_builder.py rebuild", weight=2)
        else:
            self.add("数据质量", "body_preview", "pass",
                     f"所有抽样文件均包含 body_preview", weight=1)

        cache_file = AI_INDEX_DIR / "query-cache.json"
        if cache_file.exists():
            cache_data = json.loads(cache_file.read_text(encoding='utf-8-sig'))
            cache_entries = cache_data.get('cache', [])
            if cache_entries:
                test_entries = sum(1 for e in cache_entries
                                   if 'test.md' in str(e.get('matched_files', '')))
                if test_entries > 0:
                    self.add("数据质量", "缓存有效性", "fail",
                             f"发现 {test_entries} 条测试垃圾数据 (指向 test.md)",
                             "运行: python ai_index_builder.py cache-clear", weight=3)
                else:
                    self.add("数据质量", "缓存有效性", "pass",
                             f"缓存数据有效，共 {len(cache_entries)} 条", weight=1)
            else:
                self.add("数据质量", "缓存有效性", "pass",
                         "缓存为空（正常状态）", weight=1)

        try:
            import subprocess
            ai_builder = _find_script("ai_index_builder.py")
            result = subprocess.run(
                ['python', str(ai_builder), 'search', 'test'],
                capture_output=True, text=True, timeout=15,
                encoding='utf-8', errors='replace'
            )
            if result.returncode == 0 and '命中' in (result.stdout or ''):
                self.add("数据质量", "search 命令", "pass",
                         "search 命令运行正常", weight=1)
            else:
                self.add("数据质量", "search 命令", "warn",
                         f"search 命令运行异常: {result.stderr[:100] if result.stderr else '无输出'}",
                         "检查 ai_index_builder.py 是否正常", weight=2)
        except Exception as e:
            self.add("数据质量", "search 命令", "fail",
                     f"search 命令测试失败: {e}",
                     "检查 ai_index_builder.py 是否正常", weight=3)

        try:
            import subprocess
            result = subprocess.run(
                ['python', str(ai_builder), 'status'],
                capture_output=True, text=True, timeout=10,
                encoding='utf-8', errors='replace'
            )
            if result.returncode == 0:
                self.add("数据质量", "status 命令", "pass",
                         "status 命令运行正常", weight=1)
            else:
                self.add("数据质量", "status 命令", "warn",
                         f"status 命令运行异常",
                         "检查 ai_index_builder.py 是否正常", weight=2)
        except Exception as e:
            self.add("数据质量", "status 命令", "fail",
                     f"status 命令测试失败: {e}",
                     "检查 ai_index_builder.py 是否正常", weight=3)

        try:
            import subprocess
            fm_enrich = _find_script("frontmatter_enrich.py")
            result = subprocess.run(
                ['python', str(fm_enrich), '--help'],
                capture_output=True, text=True, timeout=10,
                encoding='utf-8', errors='replace'
            )
            if result.returncode == 0:
                self.add("数据质量", "frontmatter_enrich 命令", "pass",
                         "frontmatter_enrich.py --help 运行正常", weight=1)
            else:
                self.add("数据质量", "frontmatter_enrich 命令", "warn",
                         f"frontmatter_enrich.py 运行异常",
                         "检查 frontmatter_enrich.py 是否正常", weight=2)
        except Exception as e:
            self.add("数据质量", "frontmatter_enrich 命令", "fail",
                     f"frontmatter_enrich 测试失败: {e}",
                     "检查 frontmatter_enrich.py 是否存在", weight=3)

    # ============================================================
    # 辅助方法
    # ============================================================
    def _count_knowledge_files(self) -> int:
        count = 0
        prefixes = ("0-", "1-", "2-", "3-", "4-", "5-", "6-", "7-", "8-")
        for entry in self.vault_root.iterdir():
            if not entry.is_dir():
                continue
            if should_skip_dir(entry.name):
                continue
            if not entry.name.startswith(prefixes):
                continue
            for root, dirs, files in os.walk(entry):
                dirs[:] = [d for d in dirs if not should_skip_dir(d)]
                for f in files:
                    if not f.endswith('.md'):
                        continue
                    if should_skip_file(f):
                        continue
                    count += 1
        return count

    def run_full_check(self) -> Dict:
        print("=" * 60)
        print("🤖 LD-DVA Final 健康检查报告")
        print(f"时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Vault: {self.vault_root}")
        print("=" * 60)

        self.check_file_integrity()
        self.check_index_freshness()
        self.check_skill_integration()
        self.check_core_rules()
        self.check_path_consistency()
        self.check_cache_health()
        self.check_python_environment()
        self.check_config_consistency()
        self.check_index_quality()
        self.check_data_quality()

        return self._generate_report()

    def _generate_report(self) -> Dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == 'pass')
        warnings = sum(1 for r in self.results if r.status == 'warn')
        failed = sum(1 for r in self.results if r.status == 'fail')

        total_weight = sum(r.weight for r in self.results)
        weighted_score = sum(r.score * r.weight for r in self.results) / max(total_weight, 1)

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        print("\n" + "=" * 60)
        print("📊 健康检查汇总")
        print("=" * 60)
        print(f"  总检查项: {total}")
        print(f"  ✅ 通过: {passed}")
        print(f"  ⚠️ 警告: {warnings}")
        print(f"  ❌ 失败: {failed}")
        print(f"  加权得分: {weighted_score:.1f}/100")
        print(f"  耗时: {duration:.1f}s")

        if failed > 0:
            print(f"\n  🔥 需要立即修复的问题:")
            for r in self.results:
                if r.status == 'fail':
                    print(f"    [{r.category}] {r.name}: {r.detail}")
                    if r.remediation:
                        print(f"      → {r.remediation}")

        report = {
            "report_title": "LD-DVA Final 健康检查报告",
            "generated_at": self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "duration_seconds": duration,
            "vault_root": str(self.vault_root),
            "summary": {
                "total": total,
                "passed": passed,
                "warnings": warnings,
                "failed": failed,
                "weighted_score": round(weighted_score, 1),
            },
            "checks": [
                {
                    "category": r.category,
                    "name": r.name,
                    "status": r.status,
                    "detail": r.detail,
                    "remediation": r.remediation,
                    "weight": r.weight,
                }
                for r in self.results
            ],
        }
        return report

    def save_report(self, report: Dict, output_path: Optional[Path] = None):
        if output_path is None:
            output_path = AI_INDEX_DIR / "health-report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📄 报告已保存: {output_path}")

        md_path = output_path.with_suffix('.md')
        md_content = self._generate_md_report(report)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"📄 Markdown报告已保存: {md_path}")

    def _generate_md_report(self, report: Dict) -> str:
        s = report["summary"]
        emoji_score = "🟢" if s["weighted_score"] >= 80 else ("🟡" if s["weighted_score"] >= 60 else "🔴")
        lines = []
        lines.append("---")
        lines.append("report_type: LD-DVA-Health-Check")
        lines.append("version: 2.1")
        lines.append(f"generated_at: {report['generated_at']}")
        lines.append(f"weighted_score: {s['weighted_score']}")
        lines.append("---")
        lines.append("")
        lines.append("# 🩺 LD-DVA Final 健康检查报告")
        lines.append("")
        lines.append(f"> 生成时间: {report['generated_at']}  ")
        lines.append(f"> Vault: {report['vault_root']}  ")
        lines.append(f"> 耗时: {report['duration_seconds']:.1f}s")
        lines.append("")
        lines.append("## 📊 总览")
        lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 加权得分 | {emoji_score} **{s['weighted_score']:.1f}/100** |")
        lines.append(f"| 总检查项 | {s['total']} |")
        lines.append(f"| ✅ 通过 | {s['passed']} |")
        lines.append(f"| ⚠️ 警告 | {s['warnings']} |")
        lines.append(f"| ❌ 失败 | {s['failed']} |")
        lines.append("")

        categories = {}
        for c in report["checks"]:
            cat = c["category"]
            categories.setdefault(cat, []).append(c)

        for cat, checks in categories.items():
            lines.append(f"## {cat}")
            lines.append("")
            lines.append("| 状态 | 检查项 | 详情 | 修复建议 |")
            lines.append("|------|--------|------|----------|")
            for c in checks:
                icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(c["status"], "?")
                detail = c["detail"].replace("|", "\\|").replace("\n", "<br>")
                remed = (c["remediation"] or "-").replace("|", "\\|").replace("\n", "<br>")
                lines.append(f"| {icon} | {c['name']} | {detail} | {remed} |")
            lines.append("")

        if s["failed"] > 0:
            lines.append("## 🔥 必须修复")
            lines.append("")
            for c in report["checks"]:
                if c["status"] == "fail":
                    lines.append(f"- **[{c['category']}] {c['name']}**: {c['detail']}")
                    if c["remediation"]:
                        lines.append(f"  - 💡 {c['remediation']}")
            lines.append("")

        if s["warnings"] > 0:
            lines.append("## ⚠️ 建议优化")
            lines.append("")
            for c in report["checks"]:
                if c["status"] == "warn":
                    lines.append(f"- **[{c['category']}] {c['name']}**: {c['detail']}")
                    if c["remediation"]:
                        lines.append(f"  - 💡 {c['remediation']}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(f"*报告由 LD-DVA Final health_check.py 自动生成*")
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LD-DVA Final Health Check")
    parser.add_argument("--vault", default=None, help="Vault root path")
    parser.add_argument("--report", default=None, help="Save report to path (additionally saves to AI_INDEX)")
    parser.add_argument("--quick", action="store_true", help="Quick check only")
    args = parser.parse_args()

    vault = Path(args.vault) if args.vault else None
    checker = HealthChecker(vault_root=vault)
    report = checker.run_full_check()

    checker.save_report(report)

    if args.report:
        checker.save_report(report, Path(args.report))


if __name__ == "__main__":
    main()
