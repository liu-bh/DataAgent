"""意图识别模块测试 fixture。"""

from __future__ import annotations

from datetime import date

import pytest

from datapilot_sqlgen.intent.types import (
    FilterCondition,
    LinkedDimension,
    LinkedMetric,
    ParsedIntent,
    QueryType,
    SemanticContext,
    SortDirection,
    SortSpec,
    TimeRange,
)


@pytest.fixture
def sample_parsed_intent() -> ParsedIntent:
    """创建示例 ParsedIntent。"""
    return ParsedIntent(
        query_type=QueryType.AGGREGATION,
        target_metrics=["GMV", "订单量"],
        target_dimensions=["地区", "时间"],
        time_range=TimeRange(
            start=date(2026, 4, 1),
            end=date(2026, 4, 30),
            raw_text="上月",
            granularity="month",
        ),
        filters=[
            FilterCondition(
                column="地区",
                operator="=",
                value="华东",
                raw_text="华东",
            )
        ],
        sort_by=[SortSpec(column="GMV", direction=SortDirection.DESC)],
        limit=10,
        raw_question="上月华东区GMV排名前10",
    )


@pytest.fixture
def sample_semantic_context() -> SemanticContext:
    """创建示例 SemanticContext。"""
    return SemanticContext(
        selected_tables=["orders", "users"],
        selected_metrics=[
            LinkedMetric(
                metric_id="m-001",
                name="GMV",
                calculation="SUM(orders.amount)",
                unit="元",
                table_id="t-001",
                table_name="orders",
                match_score=1.0,
                matched_by="synonym",
            ),
            LinkedMetric(
                metric_id="m-002",
                name="订单量",
                calculation="COUNT(DISTINCT orders.id)",
                unit="单",
                table_id="t-001",
                table_name="orders",
                match_score=1.0,
                matched_by="exact",
            ),
        ],
        selected_dimensions=[
            LinkedDimension(
                dimension_id="d-001",
                name="地区",
                column_name="region",
                table_id="t-002",
                table_name="users",
                synonyms=["区域", "大区"],
                match_score=0.9,
                matched_by="synonym",
            ),
            LinkedDimension(
                dimension_id="d-002",
                name="时间",
                column_name="created_at",
                table_id="t-001",
                table_name="orders",
                match_score=1.0,
                matched_by="exact",
            ),
        ],
        join_path=[],
        semantic_model_id="sm-001",
        filters=[
            FilterCondition(
                column="region",
                operator="=",
                value="华东",
                raw_text="华东",
            )
        ],
    )
