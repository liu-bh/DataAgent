"""沙箱环境信息检测。

提供当前 Python 运行环境的检测功能，包括版本、平台和可用模块。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class SandboxEnvironment:
    """沙箱环境信息。

    Attributes:
        python_version: Python 解释器版本号。
        platform: 操作系统平台标识。
        available_modules: 可用模块名称列表。
    """

    # 标准库模块白名单（用于环境检测）
    STANDARD_LIBRARY_MODULES: ClassVar[list[str]] = [
        "json", "math", "datetime", "re", "collections", "itertools",
        "functools", "hashlib", "base64", "struct", "time",
        "random", "statistics", "decimal", "fractions", "copy",
        "pprint", "textwrap", "unicodedata", "string", "difflib",
        "csv", "sqlite3", "io", "pathlib", "os",
        "logging", "unittest", "typing", "dataclasses", "enum",
        "abc", "contextlib", "asyncio", "concurrent",
    ]

    python_version: str = sys.version.split()[0]
    platform: str = sys.platform
    available_modules: list[str] = field(default_factory=list)

    @classmethod
    def detect(cls) -> SandboxEnvironment:
        """检测当前环境的 Python 版本和可用模块。

        通过尝试导入标准库模块列表来确定哪些模块可用，
        同时记录当前 Python 版本和运行平台。

        Returns:
            包含环境信息的 SandboxEnvironment 实例。
        """
        modules: list[str] = []

        for module_name in cls.STANDARD_LIBRARY_MODULES:
            if _is_module_available(module_name):
                modules.append(module_name)

        return cls(
            python_version=sys.version.split()[0],
            platform=sys.platform,
            available_modules=sorted(modules),
        )

    @staticmethod
    def check_module(module_name: str) -> bool:
        """检查模块是否可用（不导入）。

        通过 importlib.util.find_spec 检查模块是否存在，
        不会实际执行模块代码。

        Args:
            module_name: 模块名称。

        Returns:
            模块存在时返回 True。
        """
        return _is_module_available(module_name)


def _is_module_available(module_name: str) -> bool:
    """检查模块是否可导入。

    Args:
        module_name: 模块名称。

    Returns:
        模块存在时返回 True。
    """
    import importlib.util

    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ValueError, ModuleNotFoundError):
        return False
