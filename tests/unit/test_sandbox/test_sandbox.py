"""SandboxExecutor 抽象接口单元测试。"""

from __future__ import annotations

import inspect
from abc import ABC

import pytest

from datapilot_sandbox.models import SandboxConfig, SandboxInfo, SandboxResult
from datapilot_sandbox.sandbox import SandboxExecutor


class TestSandboxExecutorABC:
    """SandboxExecutor 抽象基类测试。"""

    def test_cannot_instantiate_directly(self) -> None:
        """SandboxExecutor 不能直接实例化。"""
        with pytest.raises(TypeError):
            SandboxExecutor()  # type: ignore[abstract]

    def test_is_abstract_base_class(self) -> None:
        """SandboxExecutor 应继承自 ABC。"""
        assert issubclass(SandboxExecutor, ABC)

    def test_execute_is_abstract(self) -> None:
        """execute 方法应为抽象方法。"""
        assert hasattr(SandboxExecutor, "execute")
        method = getattr(SandboxExecutor, "execute")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_health_check_is_abstract(self) -> None:
        """health_check 方法应为抽象方法。"""
        assert hasattr(SandboxExecutor, "health_check")
        method = getattr(SandboxExecutor, "health_check")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_get_info_is_abstract(self) -> None:
        """get_info 方法应为抽象方法。"""
        assert hasattr(SandboxExecutor, "get_info")
        method = getattr(SandboxExecutor, "get_info")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_execute_signature(self) -> None:
        """execute 方法签名应为 async def execute(self, code, config=None)。"""
        sig = inspect.signature(SandboxExecutor.execute)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "code" in params
        assert "config" in params

    def test_execute_is_coroutine(self) -> None:
        """execute 方法应为协程函数。"""
        assert inspect.iscoroutinefunction(SandboxExecutor.execute)

    def test_health_check_is_coroutine(self) -> None:
        """health_check 方法应为协程函数。"""
        assert inspect.iscoroutinefunction(SandboxExecutor.health_check)

    def test_get_info_is_coroutine(self) -> None:
        """get_info 方法应为协程函数。"""
        assert inspect.iscoroutinefunction(SandboxExecutor.get_info)

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        """实现了所有抽象方法的子类应能正常实例化。"""

        class DummyExecutor(SandboxExecutor):
            async def execute(self, code: str, config: SandboxConfig | None = None) -> SandboxResult:
                return SandboxResult(success=True)

            async def health_check(self) -> bool:
                return True

            async def get_info(self) -> SandboxInfo:
                return SandboxInfo()

        executor = DummyExecutor()
        assert isinstance(executor, SandboxExecutor)
        assert isinstance(executor, ABC)

    def test_incomplete_subclass_cannot_be_instantiated(self) -> None:
        """未实现所有抽象方法的子类不能实例化。"""

        class IncompleteExecutor(SandboxExecutor):
            async def execute(self, code: str, config: SandboxConfig | None = None) -> SandboxResult:
                return SandboxResult(success=True)

            # 缺少 health_check 和 get_info

        with pytest.raises(TypeError):
            IncompleteExecutor()  # type: ignore[abstract]

    async def test_concrete_execute_returns_result(self) -> None:
        """具体子类的 execute 方法应返回 SandboxResult。"""

        class DummyExecutor(SandboxExecutor):
            async def execute(self, code: str, config: SandboxConfig | None = None) -> SandboxResult:
                return SandboxResult(success=True, stdout="ok")

            async def health_check(self) -> bool:
                return True

            async def get_info(self) -> SandboxInfo:
                return SandboxInfo()

        executor = DummyExecutor()
        result = await executor.execute("print(1)")
        assert result.success is True
        assert result.stdout == "ok"

    async def test_concrete_health_check_returns_bool(self) -> None:
        """具体子类的 health_check 方法应返回布尔值。"""

        class DummyExecutor(SandboxExecutor):
            async def execute(self, code: str, config: SandboxConfig | None = None) -> SandboxResult:
                return SandboxResult(success=True)

            async def health_check(self) -> bool:
                return False

            async def get_info(self) -> SandboxInfo:
                return SandboxInfo()

        executor = DummyExecutor()
        healthy = await executor.health_check()
        assert healthy is False

    async def test_concrete_get_info_returns_info(self) -> None:
        """具体子类的 get_info 方法应返回 SandboxInfo。"""

        class DummyExecutor(SandboxExecutor):
            async def execute(self, code: str, config: SandboxConfig | None = None) -> SandboxResult:
                return SandboxResult(success=True)

            async def health_check(self) -> bool:
                return True

            async def get_info(self) -> SandboxInfo:
                return SandboxInfo(
                    python_version="3.11.0",
                    sandbox_type="k8s-pod",
                    max_memory_mb=1024,
                )

        executor = DummyExecutor()
        info = await executor.get_info()
        assert isinstance(info, SandboxInfo)
        assert info.python_version == "3.11.0"
        assert info.sandbox_type == "k8s-pod"
        assert info.max_memory_mb == 1024

    def test_execute_with_none_config_signature(self) -> None:
        """execute 方法的 config 参数默认值应为 None。"""
        sig = inspect.signature(SandboxExecutor.execute)
        assert sig.parameters["config"].default is None
