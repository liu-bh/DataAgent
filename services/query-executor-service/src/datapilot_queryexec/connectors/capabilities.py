"""数据源能力矩阵。

定义各数据源方言的 SQL 语法支持情况、连接池大小等元数据。
用于在 SQL 生成阶段进行方言适配，以及连接器工厂选择默认参数。

用法::

    from datapilot_queryexec.connectors.capabilities import get_capabilities, check_feature

    caps = get_capabilities("mysql")
    if check_feature("mysql", "supports_cte"):
        # 安全使用 CTE
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataSourceCapabilities:
    """数据源能力描述。

    Attributes:
        supports_window_functions: 是否支持窗口函数。
        supports_cte: 是否支持 CTE (WITH 子句)。
        supports_json: 是否支持 JSON 类型/函数。
        supports_array: 是否支持数组类型。
        max_query_length: 单条 SQL 最大长度（字节）。
        pool_size: 默认连接池大小。
        extra: 其他扩展属性。
    """

    supports_window_functions: bool = False
    supports_cte: bool = False
    supports_json: bool = False
    supports_array: bool = False
    max_query_length: int = 1048576
    pool_size: int = 10
    extra: dict[str, Any] = field(default_factory=dict)


# 各方言的能力矩阵
CAPABILITY_MATRIX: dict[str, DataSourceCapabilities] = {
    "mysql": DataSourceCapabilities(
        supports_window_functions=True,
        supports_cte=True,
        supports_json=True,
        max_query_length=16777216,
        pool_size=10,
    ),
    "postgresql": DataSourceCapabilities(
        supports_window_functions=True,
        supports_cte=True,
        supports_json=True,
        supports_array=True,
        pool_size=10,
    ),
    "doris": DataSourceCapabilities(
        supports_window_functions=True,
        supports_cte=True,
        supports_json=True,
        max_query_length=16777216,
        pool_size=20,
        extra={"supports_stream_load": True, "protocol": "mysql"},
    ),
    "starrocks": DataSourceCapabilities(
        supports_window_functions=True,
        supports_cte=True,
        supports_json=True,
        max_query_length=16777216,
        pool_size=20,
        extra={"supports_stream_load": True, "protocol": "mysql"},
    ),
    "clickhouse": DataSourceCapabilities(
        supports_window_functions=True,
        supports_cte=True,
        supports_json=True,
        pool_size=15,
        extra={
            "supports_materialized_view": True,
            "supports_dictionary": True,
            "column_oriented": True,
        },
    ),
}


def get_capabilities(dialect: str) -> DataSourceCapabilities:
    """获取指定方言的数据源能力。

    Args:
        dialect: 方言名称，如 "mysql"、"postgresql"。

    Returns:
        对应方言的能力描述。

    Raises:
        ValueError: 不支持的方言。
    """
    capabilities = CAPABILITY_MATRIX.get(dialect.lower())
    if capabilities is None:
        supported = ", ".join(sorted(CAPABILITY_MATRIX.keys()))
        raise ValueError(f"不支持的方言: {dialect!r}，支持的方言: {supported}")
    return capabilities


def check_feature(dialect: str, feature: str) -> bool:
    """检查指定方言是否支持某项特性。

    Args:
        dialect: 方言名称。
        feature: 特性名称，对应 DataSourceCapabilities 的字段名，
                 如 "supports_window_functions"、"supports_cte" 等。

    Returns:
        是否支持该特性。

    Raises:
        ValueError: 不支持的方言或未知的特性名称。
    """
    caps = get_capabilities(dialect)
    if not hasattr(caps, feature):
        valid_features = [f for f in vars(DataSourceCapabilities) if not f.startswith("_")]
        raise ValueError(f"未知的特性名称: {feature!r}，有效特性: {valid_features}")
    return bool(getattr(caps, feature))
