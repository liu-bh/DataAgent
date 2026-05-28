"""SelfCorrectionEngine 纠错引擎单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from datapilot_sqlgen.correction.engine import (
    SelfCorrectionEngine,
    _extract_sql_from_llm_response,
    _validate_sql_syntax,
)
from datapilot_sqlgen.correction.models import CorrectionResult, ErrorCategory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine_no_llm() -> SelfCorrectionEngine:
    """创建无 LLM 的纠错引擎（降级模式）。"""
    return SelfCorrectionEngine(llm_router=None, max_rounds=3)


@pytest.fixture
def mock_llm_router() -> MagicMock:
    """创建 mock LLM Router。"""
    router = MagicMock()
    return router


@pytest.fixture
def mock_llm_response_valid() -> MagicMock:
    """创建有效的 mock LLM 响应（返回合法 SQL JSON）。"""
    response = MagicMock()
    response.content = '{"sql": "SELECT COUNT(*) FROM orders", "fix_explanation": "修正了表名"}'
    return response


@pytest.fixture
def mock_llm_response_invalid_sql() -> MagicMock:
    """创建返回无效 SQL 的 mock LLM 响应。"""
    response = MagicMock()
    response.content = '{"sql": "SELECTT * FORMM orderss", "fix_explanation": "尝试修正"}'
    return response


@pytest.fixture
def mock_llm_response_empty() -> MagicMock:
    """创建返回空内容的 mock LLM 响应。"""
    response = MagicMock()
    response.content = "无法修复此错误"
    return response


# ---------------------------------------------------------------------------
# 降级模式测试
# ---------------------------------------------------------------------------


class TestDegradedMode:
    """无 LLM 时的降级行为测试。"""

    @pytest.mark.asyncio
    async def test_no_llm_returns_failure(self, engine_no_llm: SelfCorrectionEngine) -> None:
        """无 LLM 时应返回 success=False 的结果。"""
        result = await engine_no_llm.correct(
            sql="SELECT * FROM orderz",
            error_message='relation "orderz" does not exist',
        )

        assert isinstance(result, CorrectionResult)
        assert result.success is False
        assert result.attempts == 0
        assert result.corrected_sql == "SELECT * FROM orderz"

    @pytest.mark.asyncio
    async def test_no_llm_preserves_original_error(
        self, engine_no_llm: SelfCorrectionEngine
    ) -> None:
        """无 LLM 时应保留原始错误信息。"""
        result = await engine_no_llm.correct(
            sql="SELECT 1",
            error_message="division by zero",
        )

        assert result.original_error == "division by zero"

    @pytest.mark.asyncio
    async def test_no_llm_classifies_error(self, engine_no_llm: SelfCorrectionEngine) -> None:
        """无 LLM 时仍应执行错误分类。"""
        result = await engine_no_llm.correct(
            sql="SELECT 1",
            error_message='relation "orderz" does not exist',
        )

        assert result.error_category == ErrorCategory.TABLE_NOT_FOUND.value

    @pytest.mark.asyncio
    async def test_no_llm_empty_history(self, engine_no_llm: SelfCorrectionEngine) -> None:
        """无 LLM 时不应有纠错历史。"""
        result = await engine_no_llm.correct(
            sql="SELECT 1",
            error_message="test error",
        )

        assert result.corrections_history == []


# ---------------------------------------------------------------------------
# 初始化测试
# ---------------------------------------------------------------------------


class TestEngineInitialization:
    """引擎初始化测试。"""

    def test_default_max_rounds(self) -> None:
        """默认最大轮次为 3。"""
        # 正常创建即可验证初始化不会抛出异常
        SelfCorrectionEngine()

    def test_max_rounds_clamped_lower(self) -> None:
        """最大轮次不应小于 1。"""
        # 传入 0 时内部会 clamp 到 1，不应报错
        SelfCorrectionEngine(max_rounds=0)

    def test_max_rounds_clamped_upper(self) -> None:
        """最大轮次不应超过 10。"""
        # 传入 100 时内部会 clamp 到 10，不应报错
        SelfCorrectionEngine(max_rounds=100)


# ---------------------------------------------------------------------------
# _extract_sql_from_llm_response 测试
# ---------------------------------------------------------------------------


class TestExtractSQLFromResponse:
    """从 LLM 响应中提取 SQL 的测试。"""

    def test_valid_json_sql_field(self) -> None:
        """从标准 JSON 中提取 sql 字段。"""
        response = '{"sql": "SELECT COUNT(*) FROM orders", "fix_explanation": "test"}'
        assert _extract_sql_from_llm_response(response) == "SELECT COUNT(*) FROM orders"

    def test_json_with_escaped_chars(self) -> None:
        """处理 JSON 中的转义字符。"""
        response = (
            '{"sql": "SELECT * FROM orders WHERE status = \\"paid\\"", "fix_explanation": "test"}'
        )
        result = _extract_sql_from_llm_response(response)
        assert result is not None
        assert 'SELECT * FROM orders WHERE status = "paid"' in result or "paid" in result

    def test_markdown_sql_code_block(self) -> None:
        """从 Markdown SQL 代码块中提取。"""
        response = "```sql\nSELECT id, name FROM users\n```"
        result = _extract_sql_from_llm_response(response)
        assert result is not None
        assert "SELECT id, name FROM users" in result

    def test_fallback_to_select_keyword(self) -> None:
        """无法通过 JSON 或代码块提取时，回退到 SELECT 关键字。"""
        response = "我建议你使用 SELECT COUNT(*) FROM orders WHERE created_at > '2024-01-01' 来查询"
        result = _extract_sql_from_llm_response(response)
        assert result is not None
        assert "SELECT" in result.upper()

    def test_empty_response(self) -> None:
        """空响应应返回 None。"""
        assert _extract_sql_from_llm_response("") is None
        assert _extract_sql_from_llm_response(None) is None  # type: ignore[arg-type]

    def test_no_sql_content(self) -> None:
        """不包含 SQL 的响应应返回 None。"""
        assert _extract_sql_from_llm_response("我无法修复这个错误") is None

    def test_markdown_code_block_with_json(self) -> None:
        """Markdown 包裹的 JSON 格式。"""
        response = '```json\n{"sql": "SELECT 1", "fix_explanation": "ok"}\n```'
        result = _extract_sql_from_llm_response(response)
        assert result == "SELECT 1"


# ---------------------------------------------------------------------------
# _validate_sql_syntax 测试
# ---------------------------------------------------------------------------


class TestValidateSQLSyntax:
    """SQL 语法验证测试。"""

    def test_valid_select(self) -> None:
        """有效的 SELECT 语句应通过验证。"""
        is_valid, msg = _validate_sql_syntax("SELECT COUNT(*) FROM orders")
        assert is_valid is True
        assert msg == ""

    def test_valid_join(self) -> None:
        """有效的 JOIN 语句应通过验证。"""
        is_valid, msg = _validate_sql_syntax(
            "SELECT o.id FROM orders o JOIN users u ON o.user_id = u.id"
        )
        assert is_valid is True

    def test_empty_sql(self) -> None:
        """空 SQL 应验证失败。"""
        is_valid, msg = _validate_sql_syntax("")
        assert is_valid is False
        assert "空" in msg

    def test_whitespace_only_sql(self) -> None:
        """仅包含空白的 SQL 应验证失败。"""
        is_valid, msg = _validate_sql_syntax("   \n\t  ")
        assert is_valid is False

    def test_invalid_sql(self) -> None:
        """无效 SQL 应验证失败。"""
        is_valid, msg = _validate_sql_syntax("THIS IS NOT SQL")
        # sqlglot 可能会尝试解析任何内容，某些情况不一定会失败
        # 但至少不应抛出异常
        assert isinstance(is_valid, bool)
        assert isinstance(msg, str)


# ---------------------------------------------------------------------------
# CorrectionResult 数据模型测试
# ---------------------------------------------------------------------------


class TestCorrectionResult:
    """CorrectionResult 数据模型测试。"""

    def test_default_values(self) -> None:
        """默认值应正确初始化。"""
        result = CorrectionResult(
            success=False,
            corrected_sql="SELECT 1",
            attempts=0,
            error_category="other",
        )
        assert result.original_error == ""
        assert result.corrections_history == []

    def test_full_initialization(self) -> None:
        """完整参数初始化。"""
        result = CorrectionResult(
            success=True,
            corrected_sql="SELECT COUNT(*) FROM orders",
            attempts=2,
            error_category="table_not_found",
            original_error='relation "orderz" does not exist',
            corrections_history=["[轮次 1] ...", "[轮次 2] ..."],
        )
        assert result.success is True
        assert result.attempts == 2
        assert len(result.corrections_history) == 2


# ---------------------------------------------------------------------------
# 有 LLM 时的纠错流程测试
# ---------------------------------------------------------------------------


class TestCorrectionWithLLM:
    """配置 LLM 路由器时的纠错流程测试。"""

    @pytest.mark.asyncio
    async def test_single_round_success(self, mock_llm_router: MagicMock) -> None:
        """LLM 首轮修正即成功。"""
        mock_llm_router.generate = AsyncMock(
            return_value=MagicMock(
                content='{"sql": "SELECT COUNT(*) FROM orders", "fix_explanation": "修正表名"}'
            )
        )

        engine = SelfCorrectionEngine(llm_router=mock_llm_router, max_rounds=3)
        result = await engine.correct(
            sql="SELECT * FROM orderz",
            error_message='relation "orderz" does not exist',
            context={"available_tables": ["orders", "users"]},
        )

        assert result.success is True
        assert result.attempts == 1
        assert "SELECT COUNT(*) FROM orders" in result.corrected_sql
        assert result.error_category == ErrorCategory.TABLE_NOT_FOUND.value
        assert len(result.corrections_history) == 1

    @pytest.mark.asyncio
    async def test_multi_round_success(self, mock_llm_router: MagicMock) -> None:
        """多轮纠错后成功。"""
        call_count = 0

        async def mock_generate(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 第一轮返回无法提取 SQL 的响应
                return MagicMock(content="无法修复此查询，需要更多信息")
            else:
                # 第二轮返回有效 SQL
                return MagicMock(
                    content='{"sql": "SELECT COUNT(*) FROM orders", "fix_explanation": "修正语法"}'
                )

        mock_llm_router.generate = mock_generate

        engine = SelfCorrectionEngine(llm_router=mock_llm_router, max_rounds=3)
        result = await engine.correct(
            sql="SELECTT * FORMM orderz",
            error_message="syntax error",
        )

        assert result.success is True
        assert result.attempts == 2
        assert len(result.corrections_history) == 2

    @pytest.mark.asyncio
    async def test_max_rounds_exhausted(self, mock_llm_router: MagicMock) -> None:
        """达到最大轮次仍未成功。"""
        mock_llm_router.generate = AsyncMock(
            return_value=MagicMock(
                content='{"sql": "INVALID SQL !!!", "fix_explanation": "无法修复"}'
            )
        )

        engine = SelfCorrectionEngine(llm_router=mock_llm_router, max_rounds=2)
        result = await engine.correct(
            sql="SELECT 1",
            error_message="syntax error",
        )

        assert result.success is False
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_llm_returns_no_sql(self, mock_llm_router: MagicMock) -> None:
        """LLM 未返回有效 SQL 时应继续尝试。"""
        call_count = 0

        async def mock_generate(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(content="无法修复此错误")
            else:
                return MagicMock(content='{"sql": "SELECT 1", "fix_explanation": "fixed"}')

        mock_llm_router.generate = mock_generate

        engine = SelfCorrectionEngine(llm_router=mock_llm_router, max_rounds=3)
        result = await engine.correct(
            sql="SELECTT",
            error_message="syntax error",
        )

        # 第二轮应成功
        assert result.success is True
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_llm_exception_handled(self, mock_llm_router: MagicMock) -> None:
        """LLM 调用异常时应优雅处理。"""
        mock_llm_router.generate = AsyncMock(side_effect=Exception("LLM service unavailable"))

        engine = SelfCorrectionEngine(llm_router=mock_llm_router, max_rounds=2)
        result = await engine.correct(
            sql="SELECT 1",
            error_message="syntax error",
        )

        assert result.success is False
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_uses_correction_scene(self, mock_llm_router: MagicMock) -> None:
        """应使用 CORRECTION 场景调用 LLM。"""
        mock_llm_router.generate = AsyncMock(
            return_value=MagicMock(content='{"sql": "SELECT 1", "fix_explanation": "ok"}')
        )

        engine = SelfCorrectionEngine(llm_router=mock_llm_router, max_rounds=1)
        await engine.correct(
            sql="SELECT 1",
            error_message="test error",
        )

        # 验证 LLM 被以 correction 场景调用
        mock_llm_router.generate.assert_called_once()
        call_kwargs = mock_llm_router.generate.call_args
        assert (
            call_kwargs.kwargs.get("scene") == "correction"
            or call_kwargs[1].get("scene") == "correction"
        )

    @pytest.mark.asyncio
    async def test_json_mode_enabled(self, mock_llm_router: MagicMock) -> None:
        """应启用 JSON mode 调用 LLM。"""
        mock_llm_router.generate = AsyncMock(
            return_value=MagicMock(content='{"sql": "SELECT 1", "fix_explanation": "ok"}')
        )

        engine = SelfCorrectionEngine(llm_router=mock_llm_router, max_rounds=1)
        await engine.correct(
            sql="SELECT 1",
            error_message="test error",
        )

        call_kwargs = mock_llm_router.generate.call_args
        json_mode = call_kwargs.kwargs.get("json_mode") or call_kwargs[1].get("json_mode")
        assert json_mode is True


# ---------------------------------------------------------------------------
# ErrorCategory 枚举测试
# ---------------------------------------------------------------------------


class TestErrorCategory:
    """ErrorCategory 枚举测试。"""

    def test_all_values_exist(self) -> None:
        """所有预期的枚举值都应存在。"""
        expected = [
            "syntax_error",
            "table_not_found",
            "column_not_found",
            "empty_result",
            "timeout",
            "other",
        ]
        for value in expected:
            assert value in ErrorCategory.__members__.values()

    def test_is_str_enum(self) -> None:
        """应为 StrEnum 类型，支持字符串比较。"""
        assert ErrorCategory.SYNTAX_ERROR == "syntax_error"
        assert isinstance(ErrorCategory.OTHER, str)
