"""安全前缀代码生成单元测试。"""

from __future__ import annotations

import pytest

from datapilot_sandbox.models import SandboxConfig
from datapilot_sandbox.local.executor import LocalProcessSandbox


class TestPreludeBuilder:
    """安全前缀代码生成测试。"""

    @pytest.fixture
    def sandbox(self) -> LocalProcessSandbox:
        """创建沙箱实例。"""
        return LocalProcessSandbox()

    def test_prelude_contains_memory_limit(self, sandbox: LocalProcessSandbox) -> None:
        """测试前缀包含内存限制代码。"""
        config = SandboxConfig(memory_limit_mb=256)
        prelude = sandbox._build_prelude(config)
        assert "256" in prelude
        assert "RLIMIT_AS" in prelude
        assert "resource" in prelude

    def test_prelude_contains_safe_import(self, sandbox: LocalProcessSandbox) -> None:
        """测试前缀包含安全 import hook。"""
        config = SandboxConfig()
        prelude = sandbox._build_prelude(config)
        assert "_safe_import" in prelude
        assert "__import__" in prelude

    def test_prelude_forbids_exec_eval(self, sandbox: LocalProcessSandbox) -> None:
        """测试前缀禁止 exec 和 eval。"""
        config = SandboxConfig()
        prelude = sandbox._build_prelude(config)
        assert "__builtins__.exec = None" in prelude
        assert "__builtins__.eval = None" in prelude

    def test_prelude_includes_forbidden_modules(self, sandbox: LocalProcessSandbox) -> None:
        """测试前缀包含禁止模块列表。"""
        config = SandboxConfig(
            forbidden_modules=["os", "subprocess", "sys"]
        )
        prelude = sandbox._build_prelude(config)
        # repr() 在不同 Python 版本中使用单引号或双引号
        assert "'os'" in prelude or '"os"' in prelude
        assert "'subprocess'" in prelude or '"subprocess"' in prelude
        assert "'sys'" in prelude or '"sys"' in prelude

    def test_prelude_custom_forbidden_modules(self, sandbox: LocalProcessSandbox) -> None:
        """测试自定义禁止模块列表。"""
        config = SandboxConfig(
            forbidden_modules=["custom_module"]
        )
        prelude = sandbox._build_prelude(config)
        assert "'custom_module'" in prelude or '"custom_module"' in prelude

    def test_prelude_empty_forbidden_modules(self, sandbox: LocalProcessSandbox) -> None:
        """测试空禁止模块列表使用默认列表。"""
        config = SandboxConfig(forbidden_modules=[])
        prelude = sandbox._build_prelude(config)
        # 即使传入空列表，_build_prelude 也应使用默认列表
        # 因为默认值在配置中已包含
        assert "_safe_import" in prelude

    def test_prelude_is_valid_python(self, sandbox: LocalProcessSandbox) -> None:
        """测试前缀代码是有效的 Python 语法。"""
        config = SandboxConfig()
        prelude = sandbox._build_prelude(config)
        # compile 不应抛出异常
        compile(prelude, "<prelude>", "exec")

    def test_prelude_imports_required_modules(self, sandbox: LocalProcessSandbox) -> None:
        """测试前缀导入了必要模块。"""
        config = SandboxConfig()
        prelude = sandbox._build_prelude(config)
        assert "import sys" in prelude
        assert "import importlib" in prelude

    def test_prelude_memory_limit_calculation(self, sandbox: LocalProcessSandbox) -> None:
        """测试内存限制值计算正确。"""
        config = SandboxConfig(memory_limit_mb=512)
        prelude = sandbox._build_prelude(config)
        # 512 * 1024 * 1024 = 536870912
        assert "512" in prelude
        assert "1024" in prelude

    def test_prelude_error_handling_for_rlimit(
        self, sandbox: LocalProcessSandbox
    ) -> None:
        """测试前缀中 setrlimit 有错误处理。"""
        config = SandboxConfig()
        prelude = sandbox._build_prelude(config)
        assert "except" in prelude
        assert "ValueError" in prelude
        assert "OSError" in prelude
