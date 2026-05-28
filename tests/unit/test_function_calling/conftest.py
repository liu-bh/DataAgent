"""test_function_calling 测试配置与共享 fixtures。"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目源码路径可被导入
project_root = Path(__file__).resolve().parent.parent.parent.parent
libs_path = project_root / "libs" / "datapilot-llm" / "src"
common_path = project_root / "libs" / "datapilot-common" / "src"
for p in (libs_path, common_path):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

# 注册 pytest-asyncio 标记
import pytest

pytest.register_assert_rewrite("datapilot_llm")
