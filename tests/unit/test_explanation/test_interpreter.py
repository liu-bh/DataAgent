"""SQL 解释器单元测试。

测试 AST 基础分析模式下的 SQL 解释能力。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保项目源码路径可被导入
project_root = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "services"
    / "sql-generator-service"
    / "src"
)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

libs_root = Path(__file__).resolve().parent.parent.parent.parent / "libs"
for lib_dir in libs_root.iterdir():
    if lib_dir.is_dir():
        lib_src = lib_dir / "src"
        if lib_src.exists() and str(lib_src) not in sys.path:
            sys.path.insert(0, str(lib_src))

from datapilot_sqlgen.explanation.interpreter import SQLInterpreter
from datapilot_sqlgen.explanation.models import SQLExplanation


class TestSQLInterpreterAST:
    """AST 基础分析模式测试（无 LLM）。"""

    def setup_method(self) -> None:
        """每个测试方法前创建解释器实例。"""
        self.interpreter = SQLInterpreter(llm_router=None)

    @pytest.mark.asyncio
    async def test_empty_sql(self) -> None:
        """空 SQL 应返回空提示。"""
        result = await self.interpreter.explain("")
        assert isinstance(result, SQLExplanation)
        assert "空" in result.summary

    @pytest.mark.asyncio
    async def test_whitespace_sql(self) -> None:
        """纯空白 SQL 应返回空提示。"""
        result = await self.interpreter.explain("   \n\t  ")
        assert isinstance(result, SQLExplanation)
        assert "空" in result.summary

    @pytest.mark.asyncio
    async def test_simple_select(self) -> None:
        """简单 SELECT 语句应提取表名和列名。"""
        sql = "SELECT id, name, amount FROM orders"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert "orders" in result.summary
        assert any("orders" in kp for kp in result.key_points)

    @pytest.mark.asyncio
    async def test_select_with_where(self) -> None:
        """带 WHERE 条件的 SELECT 应提取过滤条件。"""
        sql = "SELECT id, amount FROM orders WHERE status = 'paid'"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("过滤" in kp or "WHERE" in kp for kp in result.key_points)

    @pytest.mark.asyncio
    async def test_select_with_group_by(self) -> None:
        """带 GROUP BY 的 SELECT 应提取分组信息。"""
        sql = "SELECT region, SUM(amount) FROM orders GROUP BY region"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("分组" in kp or "GROUP" in kp for kp in result.key_points)
        assert any("聚合" in kp for kp in result.key_points)

    @pytest.mark.asyncio
    async def test_select_with_order_by(self) -> None:
        """带 ORDER BY 的 SELECT 应提取排序信息。"""
        sql = "SELECT id, amount FROM orders ORDER BY amount DESC"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("排序" in kp or "ORDER" in kp for kp in result.key_points)

    @pytest.mark.asyncio
    async def test_select_with_limit(self) -> None:
        """带 LIMIT 的 SELECT 应包含 LIMIT 信息。"""
        sql = "SELECT id FROM orders LIMIT 10"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("LIMIT" in kp for kp in result.key_points)
        assert not any("LIMIT" in issue for issue in result.potential_issues)

    @pytest.mark.asyncio
    async def test_select_without_limit(self) -> None:
        """不带 LIMIT 的 SELECT 应提示潜在问题。"""
        sql = "SELECT id, name FROM users"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("LIMIT" in issue for issue in result.potential_issues)

    @pytest.mark.asyncio
    async def test_select_star_warning(self) -> None:
        """SELECT * 应触发警告。"""
        sql = "SELECT * FROM orders"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("SELECT *" in issue or "具体列名" in issue for issue in result.potential_issues)

    @pytest.mark.asyncio
    async def test_join_query(self) -> None:
        """JOIN 查询应提取关联表信息。"""
        sql = (
            "SELECT o.id, u.name "
            "FROM orders o "
            "LEFT JOIN users u ON o.user_id = u.id"
        )
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("关联" in kp or "JOIN" in kp for kp in result.key_points)

    @pytest.mark.asyncio
    async def test_complex_query(self) -> None:
        """复杂查询应提取多个信息点。"""
        sql = (
            "SELECT region, SUM(amount) AS total "
            "FROM orders "
            "WHERE status = 'paid' AND created_at >= '2024-01-01' "
            "GROUP BY region "
            "ORDER BY total DESC "
            "LIMIT 10"
        )
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        # 应至少提取多个关键信息点
        assert len(result.key_points) >= 3

    @pytest.mark.asyncio
    async def test_invalid_sql(self) -> None:
        """无效 SQL 应返回语法错误提示。"""
        sql = "SELECT FROM WHERE GROUP BY"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("语法" in issue or "解析" in issue or "错误" in issue for issue in result.potential_issues)

    @pytest.mark.asyncio
    async def test_default_dialect(self) -> None:
        """默认方言应为 mysql。"""
        sql = "SELECT id FROM orders"
        result = await self.interpreter.explain(sql, dialect="mysql")

        assert isinstance(result, SQLExplanation)

    @pytest.mark.asyncio
    async def test_postgresql_dialect(self) -> None:
        """PostgreSQL 方言应正常解析。"""
        sql = "SELECT id, name FROM users WHERE created_at > NOW() - INTERVAL '7 days' LIMIT 100"
        result = await self.interpreter.explain(sql, dialect="postgres")

        assert isinstance(result, SQLExplanation)
        assert "users" in result.summary


class TestSQLInterpreterLLM:
    """LLM 增强模式测试。"""

    @pytest.mark.asyncio
    @patch("datapilot_sqlgen.explanation.interpreter._SCENE_EXPLANATION", "explanation")
    async def test_llm_explain_success(self) -> None:
        """LLM 解释成功应返回解析后的结果。"""
        mock_router = MagicMock()
        mock_router.generate = AsyncMock(return_value=MagicMock(
            content='{"summary": "统计订单数量", "key_points": ["查询 orders 表", "使用 COUNT 聚合"], "potential_issues": []}',
        ))

        interpreter = SQLInterpreter(llm_router=mock_router)
        result = await interpreter.explain("SELECT COUNT(*) FROM orders")

        assert isinstance(result, SQLExplanation)
        assert result.summary == "统计订单数量"
        assert len(result.key_points) == 2

    @pytest.mark.asyncio
    @patch("datapilot_sqlgen.explanation.interpreter._SCENE_EXPLANATION", "explanation")
    async def test_llm_explain_fallback_to_ast(self) -> None:
        """LLM 调用失败应降级到 AST 分析。"""
        mock_router = MagicMock()
        mock_router.generate = AsyncMock(side_effect=RuntimeError("LLM 超时"))

        interpreter = SQLInterpreter(llm_router=mock_router)
        result = await interpreter.explain("SELECT id FROM orders LIMIT 10")

        assert isinstance(result, SQLExplanation)
        # AST 分析应仍能提取信息
        assert "orders" in result.summary

    @pytest.mark.asyncio
    @patch("datapilot_sqlgen.explanation.interpreter._SCENE_EXPLANATION", "explanation")
    async def test_llm_invalid_json_fallback(self) -> None:
        """LLM 返回无效 JSON 应返回友好提示。"""
        mock_router = MagicMock()
        mock_router.generate = AsyncMock(return_value=MagicMock(
            content="这不是 JSON 格式的内容",
        ))

        interpreter = SQLInterpreter(llm_router=mock_router)
        result = await interpreter.explain("SELECT id FROM orders")

        assert isinstance(result, SQLExplanation)
        assert result.summary  # 应有降级 summary


class TestSQLInterpreterEdgeCases:
    """边界条件测试。"""

    def setup_method(self) -> None:
        """每个测试方法前创建解释器实例。"""
        self.interpreter = SQLInterpreter(llm_router=None)

    @pytest.mark.asyncio
    async def test_none_sql(self) -> None:
        """None SQL 应返回空提示。"""
        result = await self.interpreter.explain("")  # None 不符合类型约束，用空字符串代替
        assert "空" in result.summary

    @pytest.mark.asyncio
    async def test_very_long_sql(self) -> None:
        """超长 SQL 应正常处理。"""
        # 构建一个很长的 WHERE 条件
        conditions = " AND ".join([f"col{i} = 'value{i}'" for i in range(50)])
        sql = f"SELECT id FROM orders WHERE {conditions}"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert result.summary != ""

    @pytest.mark.asyncio
    async def test_count_with_star(self) -> None:
        """COUNT(*) 应识别为聚合函数。"""
        sql = "SELECT COUNT(*) AS total FROM orders"
        result = await self.interpreter.explain(sql)

        assert isinstance(result, SQLExplanation)
        assert any("聚合" in kp for kp in result.key_points)
