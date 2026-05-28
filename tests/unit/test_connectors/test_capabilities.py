"""数据源能力矩阵单元测试。

测试能力矩阵的定义、get_capabilities 和 check_feature 方法。
"""

from __future__ import annotations

import pytest

from datapilot_queryexec.connectors.capabilities import (
    CAPABILITY_MATRIX,
    DataSourceCapabilities,
    check_feature,
    get_capabilities,
)


class TestDataSourceCapabilities:
    """DataSourceCapabilities 数据类测试。"""

    def test_default_values(self) -> None:
        """默认值测试。"""
        caps = DataSourceCapabilities()
        assert caps.supports_window_functions is False
        assert caps.supports_cte is False
        assert caps.supports_json is False
        assert caps.supports_array is False
        assert caps.max_query_length == 1048576
        assert caps.pool_size == 10
        assert caps.extra == {}

    def test_custom_values(self) -> None:
        """自定义值测试。"""
        caps = DataSourceCapabilities(
            supports_window_functions=True,
            supports_cte=True,
            pool_size=20,
            extra={"key": "value"},
        )
        assert caps.supports_window_functions is True
        assert caps.supports_cte is True
        assert caps.pool_size == 20
        assert caps.extra == {"key": "value"}


class TestCapabilityMatrix:
    """CAPABILITY_MATRIX 能力矩阵完整性测试。"""

    def test_all_dialects_present(self) -> None:
        """所有方言都已定义能力。"""
        expected_dialects = {"mysql", "postgresql", "doris", "starrocks", "clickhouse"}
        actual_dialects = set(CAPABILITY_MATRIX.keys())
        assert actual_dialects == expected_dialects

    def test_mysql_capabilities(self) -> None:
        """MySQL 能力测试。"""
        caps = CAPABILITY_MATRIX["mysql"]
        assert caps.supports_window_functions is True
        assert caps.supports_cte is True
        assert caps.supports_json is True
        assert caps.supports_array is False
        assert caps.pool_size == 10
        assert caps.max_query_length == 16777216

    def test_postgresql_capabilities(self) -> None:
        """PostgreSQL 能力测试。"""
        caps = CAPABILITY_MATRIX["postgresql"]
        assert caps.supports_window_functions is True
        assert caps.supports_cte is True
        assert caps.supports_json is True
        assert caps.supports_array is True
        assert caps.pool_size == 10

    def test_doris_capabilities(self) -> None:
        """Doris 能力测试。"""
        caps = CAPABILITY_MATRIX["doris"]
        assert caps.supports_window_functions is True
        assert caps.supports_cte is True
        assert caps.pool_size == 20
        assert caps.extra.get("protocol") == "mysql"
        assert caps.extra.get("supports_stream_load") is True

    def test_starrocks_capabilities(self) -> None:
        """StarRocks 能力测试。"""
        caps = CAPABILITY_MATRIX["starrocks"]
        assert caps.supports_window_functions is True
        assert caps.supports_cte is True
        assert caps.pool_size == 20
        assert caps.extra.get("protocol") == "mysql"
        assert caps.extra.get("supports_stream_load") is True

    def test_clickhouse_capabilities(self) -> None:
        """ClickHouse 能力测试。"""
        caps = CAPABILITY_MATRIX["clickhouse"]
        assert caps.supports_window_functions is True
        assert caps.supports_cte is True
        assert caps.pool_size == 15
        assert caps.extra.get("column_oriented") is True


class TestGetCapabilities:
    """get_capabilities 函数测试。"""

    def test_get_mysql(self) -> None:
        """获取 MySQL 能力。"""
        caps = get_capabilities("mysql")
        assert isinstance(caps, DataSourceCapabilities)
        assert caps.pool_size == 10

    def test_get_postgresql(self) -> None:
        """获取 PostgreSQL 能力。"""
        caps = get_capabilities("postgresql")
        assert isinstance(caps, DataSourceCapabilities)

    def test_get_doris(self) -> None:
        """获取 Doris 能力。"""
        caps = get_capabilities("doris")
        assert isinstance(caps, DataSourceCapabilities)
        assert caps.pool_size == 20

    def test_get_starrocks(self) -> None:
        """获取 StarRocks 能力。"""
        caps = get_capabilities("starrocks")
        assert isinstance(caps, DataSourceCapabilities)

    def test_get_clickhouse(self) -> None:
        """获取 ClickHouse 能力。"""
        caps = get_capabilities("clickhouse")
        assert isinstance(caps, DataSourceCapabilities)

    def test_case_insensitive(self) -> None:
        """方言名称不区分大小写。"""
        caps_upper = get_capabilities("MYSQL")
        caps_lower = get_capabilities("mysql")
        assert caps_upper.pool_size == caps_lower.pool_size

    def test_unsupported_dialect(self) -> None:
        """不支持的方言抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的方言"):
            get_capabilities("oracle")

    def test_empty_dialect(self) -> None:
        """空字符串方言抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的方言"):
            get_capabilities("")


class TestCheckFeature:
    """check_feature 函数测试。"""

    def test_mysql_supports_window_functions(self) -> None:
        """MySQL 支持窗口函数。"""
        assert check_feature("mysql", "supports_window_functions") is True

    def test_mysql_supports_array(self) -> None:
        """MySQL 不支持数组类型。"""
        assert check_feature("mysql", "supports_array") is False

    def test_postgresql_supports_array(self) -> None:
        """PostgreSQL 支持数组类型。"""
        assert check_feature("postgresql", "supports_array") is True

    def test_postgresql_supports_cte(self) -> None:
        """PostgreSQL 支持 CTE。"""
        assert check_feature("postgresql", "supports_cte") is True

    def test_doris_pool_size_not_a_bool_feature(self) -> None:
        """pool_size 不是布尔特性，但 check_feature 仍返回其真值。"""
        # pool_size=20，真值为 True
        assert check_feature("doris", "pool_size") is True

    def test_unknown_feature(self) -> None:
        """未知特性名称抛出 ValueError。"""
        with pytest.raises(ValueError, match="未知的特性名称"):
            check_feature("mysql", "nonexistent_feature")

    def test_unsupported_dialect(self) -> None:
        """不支持的方言抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的方言"):
            check_feature("oracle", "supports_cte")
