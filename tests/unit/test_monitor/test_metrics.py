"""datapilot_queryexec.monitor.metrics 单元测试。

覆盖 Prometheus 指标的记录功能。
"""

from __future__ import annotations

from datapilot_queryexec.monitor import metrics

# ---------------------------------------------------------------------------
# 使用独立的 registry 避免测试间污染
# ---------------------------------------------------------------------------


class TestRecordQueryMetrics:
    """查询指标记录测试。"""

    def test_record_success_query(self) -> None:
        """记录成功查询指标。"""
        metrics.QUERY_TOTAL.labels(
            datasource_id="ds-1",
            dialect="postgres",
            status="success",
        ).inc()
        metrics.QUERY_LATENCY.labels(
            datasource_id="ds-1",
            dialect="postgres",
        ).observe(0.05)

        # 验证指标已注册（能获取到值说明注册成功）
        sample = metrics.QUERY_TOTAL.labels(
            datasource_id="ds-1",
            dialect="postgres",
            status="success",
        )
        # 指标值 > 0 说明 inc 成功
        assert sample._value.get() > 0  # type: ignore[union-attr]

    def test_record_error_query(self) -> None:
        """记录错误查询指标。"""
        metrics.QUERY_TOTAL.labels(
            datasource_id="ds-2",
            dialect="mysql",
            status="error",
        ).inc()
        metrics.QUERY_ERRORS.labels(
            datasource_id="ds-2",
            dialect="mysql",
            error_type="timeout",
        ).inc()
        metrics.QUERY_LATENCY.labels(
            datasource_id="ds-2",
            dialect="mysql",
        ).observe(5.0)

        error_sample = metrics.QUERY_ERRORS.labels(
            datasource_id="ds-2",
            dialect="mysql",
            error_type="timeout",
        )
        assert error_sample._value.get() > 0  # type: ignore[union-attr]

    def test_record_query_metrics_helper(self) -> None:
        """通过 helper 函数记录查询指标。"""
        metrics.record_query_metrics(
            datasource_id="ds-3",
            dialect="clickhouse",
            success=True,
            latency_ms=100.0,
        )

        sample = metrics.QUERY_TOTAL.labels(
            datasource_id="ds-3",
            dialect="clickhouse",
            status="success",
        )
        assert sample._value.get() > 0  # type: ignore[union-attr]

    def test_record_query_metrics_helper_with_error(self) -> None:
        """helper 函数记录错误查询指标。"""
        metrics.record_query_metrics(
            datasource_id="ds-4",
            dialect="postgres",
            success=False,
            latency_ms=5000.0,
            error_type="connection_refused",
        )

        total_sample = metrics.QUERY_TOTAL.labels(
            datasource_id="ds-4",
            dialect="postgres",
            status="error",
        )
        assert total_sample._value.get() > 0  # type: ignore[union-attr]

        error_sample = metrics.QUERY_ERRORS.labels(
            datasource_id="ds-4",
            dialect="postgres",
            error_type="connection_refused",
        )
        assert error_sample._value.get() > 0  # type: ignore[union-attr]


class TestRecordHealthMetrics:
    """健康指标记录测试。"""

    def test_record_healthy(self) -> None:
        """记录健康数据源指标。"""
        metrics.record_health_metrics(
            datasource_id="ds-1",
            dialect="postgres",
            healthy=True,
            pool_used=5,
            pool_size=10,
        )

        health_sample = metrics.DATASOURCE_HEALTH.labels(datasource_id="ds-1")
        # 健康时值为 1
        assert health_sample._value.get() == 1.0  # type: ignore[union-attr]

        pool_sample = metrics.CONNECTOR_POOL_USED.labels(
            datasource_id="ds-1", dialect="postgres"
        )
        assert pool_sample._value.get() == 5  # type: ignore[union-attr]

    def test_record_unhealthy(self) -> None:
        """记录不健康数据源指标。"""
        metrics.record_health_metrics(
            datasource_id="ds-2",
            dialect="mysql",
            healthy=False,
            pool_used=0,
            pool_size=10,
        )

        health_sample = metrics.DATASOURCE_HEALTH.labels(datasource_id="ds-2")
        # 不健康时值为 0
        assert health_sample._value.get() == 0.0  # type: ignore[union-attr]

    def test_record_pool_size(self) -> None:
        """记录连接池大小指标。"""
        metrics.record_health_metrics(
            datasource_id="ds-3",
            dialect="clickhouse",
            healthy=True,
            pool_used=3,
            pool_size=20,
        )

        pool_size_sample = metrics.CONNECTOR_POOL_SIZE.labels(
            datasource_id="ds-3", dialect="clickhouse"
        )
        assert pool_size_sample._value.get() == 20  # type: ignore[union-attr]

    def test_update_health_status(self) -> None:
        """更新健康状态。"""
        # 先设为健康
        metrics.record_health_metrics(
            "ds-4", dialect="postgres", healthy=True, pool_used=1, pool_size=5
        )
        # 再设为不健康
        metrics.record_health_metrics(
            "ds-4", dialect="postgres", healthy=False, pool_used=0, pool_size=5
        )

        health_sample = metrics.DATASOURCE_HEALTH.labels(datasource_id="ds-4")
        assert health_sample._value.get() == 0.0  # type: ignore[union-attr]
