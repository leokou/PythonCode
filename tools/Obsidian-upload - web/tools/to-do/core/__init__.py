"""Leo Todo 核心层：数据模型 / 任务管理 / 同步引擎 / 配置 / 前端桥接。

本层不依赖任何外部任务来源（Microsoft / GitHub 等），
外部来源一律通过 adapters 层转换后进入本层。
"""

__version__ = "0.1.0"
