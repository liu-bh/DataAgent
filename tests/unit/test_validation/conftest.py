"""SQL 验证模块测试配置和共享 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保项目源码路径可被导入
project_root = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "services"
    / "sql-generator-service"
    / "src"
)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 同时确保 libs 路径可被导入
libs_root = (
    Path(__file__).resolve().parent.parent.parent.parent / "libs"
)
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))
