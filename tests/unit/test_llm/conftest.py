"""test_llm 测试配置与共享 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent
libs_path = project_root / "libs" / "datapilot-llm" / "src"
common_path = project_root / "libs" / "datapilot-common" / "src"
for p in (libs_path, common_path):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)


@pytest.fixture
def llm_settings():
    """创建测试用 LLM 配置（使用测试 API Key）。"""
    from datapilot_llm.config import LLMSettings

    return LLMSettings(
        qwen_api_key="test-qwen-key",
        deepseek_api_key="test-deepseek-key",
        timeout=10,
        max_retries=1,
    )
