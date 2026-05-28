"""datapilot-prompt：Prompt 管理库。

提供 Prompt 版本管理、A/B 测试和 Token 预算控制功能。

主要导出:
    PromptManager — Prompt 版本管理器（CRUD + 激活 + A/B 测试查询）
    TokenBudgetManager — Token 预算管理器（估算 + 裁剪 + 组装）
    ABTestingManager — A/B 测试管理器（分流 + 效果记录 + 统计对比）
    PromptVersion — Prompt 版本 SQLAlchemy 模型
"""

from .ab_testing import ABTestingManager
from .budget import TokenBudgetManager
from .models import PromptVersion
from .service import PromptManager

__all__ = [
    "PromptManager",
    "TokenBudgetManager",
    "ABTestingManager",
    "PromptVersion",
]
