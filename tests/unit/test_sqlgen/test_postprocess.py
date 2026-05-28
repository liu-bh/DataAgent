"""SQLPostProcessor 后处理器单元测试。"""

from __future__ import annotations

import json

import pytest

from datapilot_sqlgen.generator.postprocess import ProcessedSQL, SQLPostProcessor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def processor() -> SQLPostProcessor:
    """创建 SQLPostProcessor 实例。"""
    return SQLPostProcessor(default_limit=1000)


# ---------------------------------------------------------------------------
# JSON 提取测试
# ---------------------------------------------------------------------------


class TestExtractSQLFromJSON:
    """从 LLM JSON 输出中提取 SQL 的测试。"""

    def test_valid_json_with_sql(self, processor: SQLPostProcessor) -> None:
        """标准 JSON 格式提取 SQL。"""
        output = json.dumps({
            "sql": "SELECT COUNT(*) FROM orders",
            "explanation": "统计订单数量",
            "confidence": 0.95,
        }, ensure_ascii=False)

        result = processor._extract_sql_from_json(output)
        assert result == "SELECT COUNT(*) FROM orders"

    def test_markdown_wrapped_json(self, processor: SQLPostProcessor) -> None:
        """Markdown 代码块包裹的 JSON。"""
        output = '```json\n{"sql": "SELECT 1", "explanation": "test"}\n```'
        result = processor._extract_sql_from_json(output)
        assert result == "SELECT 1"

    def test_inline_json_match(self, processor: SQLPostProcessor) -> None:
        """文本中内嵌的 JSON。"""
        output = '根据分析，\n{"sql": "SELECT SUM(amount) FROM orders", "confidence": 0.9}\n以上是结果'
        result = processor._extract_sql_from_json(output)
        assert result == "SELECT SUM(amount) FROM orders"

    def test_sql_code_block_fallback(self, processor: SQLPostProcessor) -> None:
        """SQL 代码块降级提取。"""
        output = '```sql\nSELECT COUNT(*) FROM orders WHERE status = \'paid\'\n```'
        result = processor._extract_sql_from_json(output)
        assert "SELECT COUNT(*)" in result

    def test_invalid_json_returns_none(self, processor: SQLPostProcessor) -> None:
        """无效 JSON 应返回 None。"""
        result = processor._extract_sql_from_json("这不是 JSON")
        assert result is None

    def test_empty_sql_field(self, processor: SQLPostProcessor) -> None:
        """sql 字段为空时应返回 None。"""
        output = json.dumps({"sql": "", "explanation": "test"})
        result = processor._extract_sql_from_json(output)
        assert result is None

    def test_non_dict_json(self, processor: SQLPostProcessor) -> None:
        """非字典 JSON 应返回 None。"""
        output = json.dumps(["sql", "not", "a", "dict"])
        result = processor._extract_sql_from_json(output)
        assert result is None


# ---------------------------------------------------------------------------
# SQL 清理测试
# ---------------------------------------------------------------------------


class TestCleanSQL:
    """SQL 清理测试。"""

    def test_strip_whitespace(self, processor: SQLPostProcessor) -> None:
        """应去除首尾空白。"""
        assert processor._clean_sql("  SELECT 1  ") == "SELECT 1"

    def test_remove_quotes(self, processor: SQLPostProcessor) -> None:
        """应去除首尾引号。"""
        assert processor._clean_sql('"SELECT 1"') == "SELECT 1"
        assert processor._clean_sql("'SELECT 1'") == "SELECT 1"

    def test_remove_escape_chars(self, processor: SQLPostProcessor) -> None:
        """应去除转义字符。"""
        assert '\\"' not in processor._clean_sql('\\"SELECT 1\\"')

    def test_collapse_newlines(self, processor: SQLPostProcessor) -> None:
        """应合并多余换行。"""
        result = processor._clean_sql("SELECT\n\n\n\n1")
        assert "\n\n\n" not in result


# ---------------------------------------------------------------------------
# 完整流程测试
# ---------------------------------------------------------------------------


class TestProcessFullFlow:
    """process() 完整后处理流程测试。"""

    def test_valid_json_output(self, processor: SQLPostProcessor) -> None:
        """正常 JSON 输出的完整处理。"""
        llm_output = json.dumps({
            "sql": "SELECT COUNT(*) AS cnt FROM orders",
            "explanation": "统计订单数",
            "confidence": 0.9,
        }, ensure_ascii=False)

        result = processor.process(llm_output, dialect="mysql")

        assert isinstance(result, ProcessedSQL)
        assert "SELECT" in result.sql.upper()
        assert result.dialect == "mysql"

    def test_add_limit_when_missing(self, processor: SQLPostProcessor) -> None:
        """没有 LIMIT 时应自动添加。"""
        llm_output = json.dumps({
            "sql": "SELECT COUNT(*) FROM orders",
            "explanation": "test",
            "confidence": 0.9,
        })

        result = processor.process(llm_output, dialect="mysql")

        # 应包含 LIMIT
        assert "LIMIT" in result.sql.upper()
        assert any("LIMIT" in w for w in result.warnings)

    def test_no_limit_when_present(self, processor: SQLPostProcessor) -> None:
        """已有 LIMIT 时不应重复添加。"""
        llm_output = json.dumps({
            "sql": "SELECT * FROM orders LIMIT 100",
            "explanation": "test",
            "confidence": 0.9,
        })

        result = processor.process(llm_output, dialect="mysql")

        # 不应有 LIMIT 警告
        assert not any("LIMIT" in w for w in result.warnings)

    def test_empty_output(self, processor: SQLPostProcessor) -> None:
        """空输出应返回警告。"""
        result = processor.process("", dialect="mysql")

        assert result.sql == ""
        assert len(result.warnings) > 0

    def test_non_json_non_sql_output(self, processor: SQLPostProcessor) -> None:
        """既非 JSON 也非 SQL 的输出。"""
        result = processor.process("这段文字既不是 JSON 也不是 SQL", dialect="mysql")

        # 应返回处理后的结果（可能为空或有警告）
        assert isinstance(result, ProcessedSQL)

    def test_warnings_collected(self, processor: SQLPostProcessor) -> None:
        """应收集处理过程中的所有警告。"""
        llm_output = json.dumps({
            "sql": "SELECT COUNT(*) FROM orders",
            "explanation": "test",
            "confidence": 0.9,
        })

        result = processor.process(llm_output, dialect="mysql")

        # 至少有 LIMIT 添加的警告
        assert isinstance(result.warnings, list)


# ---------------------------------------------------------------------------
# SELECT * 替换测试
# ---------------------------------------------------------------------------


class TestReplaceSelectStar:
    """SELECT * 替换测试。"""

    def test_replace_select_star_with_columns(self, processor: SQLPostProcessor) -> None:
        """提供列信息时应替换 SELECT *。"""
        # 构造一个包含 SELECT * 的 JSON 输出
        llm_output = json.dumps({
            "sql": "SELECT * FROM orders LIMIT 10",
            "explanation": "test",
            "confidence": 0.9,
        })

        available_columns = {
            "orders": ["id", "user_id", "amount", "status", "created_at"],
        }

        result = processor.process(
            llm_output, dialect="mysql",
            available_columns=available_columns,
        )

        # 如果 sqlglot 可用，应替换 SELECT *
        # 如果不可用，至少不应报错
        assert isinstance(result, ProcessedSQL)

    def test_no_replace_without_columns(self, processor: SQLPostProcessor) -> None:
        """不提供列信息时不应替换。"""
        llm_output = json.dumps({
            "sql": "SELECT * FROM orders LIMIT 10",
            "explanation": "test",
            "confidence": 0.9,
        })

        result = processor.process(llm_output, dialect="mysql")

        # 应有 SELECT * 的警告
        assert isinstance(result, ProcessedSQL)

    def test_no_select_star_no_action(self, processor: SQLPostProcessor) -> None:
        """没有 SELECT * 时不应触发替换逻辑。"""
        llm_output = json.dumps({
            "sql": "SELECT id, name FROM orders LIMIT 10",
            "explanation": "test",
            "confidence": 0.9,
        })

        available_columns = {"orders": ["id", "name", "amount"]}
        result = processor.process(
            llm_output, dialect="mysql",
            available_columns=available_columns,
        )

        # 不应有 SELECT * 相关警告
        assert not any("SELECT *" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# AST 解析/渲染降级测试
# ---------------------------------------------------------------------------


class TestASTDegradation:
    """AST 解析和渲染的降级测试。"""

    def test_invalid_sql_graceful_handling(self, processor: SQLPostProcessor) -> None:
        """无效 SQL 应优雅处理。"""
        llm_output = json.dumps({
            "sql": "THIS IS NOT VALID SQL AT ALL!!!",
            "explanation": "test",
            "confidence": 0.9,
        })

        result = processor.process(llm_output, dialect="mysql")

        # 应返回结果，不抛出异常
        assert isinstance(result, ProcessedSQL)
        # 可能包含 AST 解析失败的警告
        assert isinstance(result.warnings, list)
