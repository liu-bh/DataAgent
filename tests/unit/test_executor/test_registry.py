"""执行器注册表单元测试。"""

from __future__ import annotations

import pytest

from datapilot_dag.executor.base import BaseTaskExecutor
from datapilot_dag.executor.registry import ExecutorRegistry
from datapilot_dag.executor.sql_executor import SQLTaskExecutor
from datapilot_dag.executor.llm_executor import LLMTaskExecutor
from datapilot_dag.executor.python_executor import PythonTaskExecutor


class _DummyExecutor(BaseTaskExecutor):
    """测试用虚拟执行器。"""

    async def execute(self, node_id: str, config: dict, context: dict) -> object:
        return {"dummy": True}

    async def cancel(self, node_id: str) -> bool:
        return True


class TestExecutorRegistry:
    """ExecutorRegistry 注册表测试。"""

    def test_register_and_get(self) -> None:
        """注册并获取执行器。"""
        registry = ExecutorRegistry()
        executor = _DummyExecutor()
        registry.register("dummy", executor)

        result = registry.get("dummy")
        assert result is executor

    def test_get_unknown_type_raises(self) -> None:
        """获取未注册的类型抛出 KeyError。"""
        registry = ExecutorRegistry()
        with pytest.raises(KeyError, match="unknown_type"):
            registry.get("unknown_type")

    def test_get_error_includes_available_types(self) -> None:
        """KeyError 消息包含已注册的类型列表。"""
        registry = ExecutorRegistry()
        registry.register("sql", SQLTaskExecutor())
        registry.register("llm", LLMTaskExecutor())

        with pytest.raises(KeyError, match="python"):
            registry.get("python")

    def test_register_override_warns(self) -> None:
        """重复注册同类型会覆盖（日志警告）。"""
        registry = ExecutorRegistry()
        executor1 = _DummyExecutor()
        executor2 = _DummyExecutor()
        registry.register("dummy", executor1)
        registry.register("dummy", executor2)

        result = registry.get("dummy")
        assert result is executor2

    def test_has(self) -> None:
        """has 方法正确返回是否已注册。"""
        registry = ExecutorRegistry()
        assert registry.has("sql") is False
        registry.register("sql", SQLTaskExecutor())
        assert registry.has("sql") is True

    def test_list_types(self) -> None:
        """list_types 返回所有已注册的类型。"""
        registry = ExecutorRegistry()
        registry.register("sql", SQLTaskExecutor())
        registry.register("llm", LLMTaskExecutor())

        types = registry.list_types()
        assert set(types) == {"sql", "llm"}

    def test_register_defaults(self) -> None:
        """register_defaults 注册所有默认执行器。"""
        registry = ExecutorRegistry()
        registry.register_defaults()

        assert registry.has("sql")
        assert registry.has("llm")
        assert registry.has("python")

        # 验证执行器类型
        assert isinstance(registry.get("sql"), SQLTaskExecutor)
        assert isinstance(registry.get("llm"), LLMTaskExecutor)
        assert isinstance(registry.get("python"), PythonTaskExecutor)

    def test_register_defaults_with_custom_url(self) -> None:
        """register_defaults 支持自定义 query_base_url。"""
        registry = ExecutorRegistry()
        registry.register_defaults(query_base_url="http://custom:8003")

        sql_executor = registry.get("sql")
        assert isinstance(sql_executor, SQLTaskExecutor)
        assert sql_executor._base_url == "http://custom:8003"

    def test_register_defaults_without_llm_router(self) -> None:
        """不传入 llm_router 时 LLM 执行器使用 mock 模式。"""
        registry = ExecutorRegistry()
        registry.register_defaults(llm_router=None)

        llm_executor = registry.get("llm")
        assert isinstance(llm_executor, LLMTaskExecutor)
        assert llm_executor._llm_router is None
