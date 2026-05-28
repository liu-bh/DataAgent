"""维度下钻分析器。"""

from __future__ import annotations

from datapilot_agent.rca.models import DimensionValue, DrillDownResult


class DimensionDrillDown:
    """按维度拆解数据，计算每个维度值的变化量和贡献度。"""

    async def drill(
        self,
        dimension_name: str,
        dimension_values: dict[str, float],
        baseline_values: dict[str, float],
        total_change: float,
    ) -> DrillDownResult:
        """按维度拆解数据。

        计算每个维度值的变化量和贡献度。
        结果按 |contribution| 降序排列。

        Args:
            dimension_name: 维度名称（如"城市"）
            dimension_values: 当前时段各维度值 {"上海": 500000, "北京": 800, ...}
            baseline_values: 对比时段各维度值（同结构）
            total_change: 指标的总变化量

        Returns:
            DrillDownResult: 维度下钻结果
        """
        all_keys = set(dimension_values.keys()) | set(baseline_values.keys())
        dimension_results: list[DimensionValue] = []

        for key in all_keys:
            current = dimension_values.get(key, 0.0)
            baseline = baseline_values.get(key, 0.0)

            # 变化量
            change = current - baseline

            # 变化百分比
            if baseline == 0:
                change_percent = 100.0 if current != 0 else 0.0
            else:
                change_percent = (current - baseline) / abs(baseline) * 100

            # 贡献值和贡献百分比
            contribution, contribution_percent = self._calculate_contribution(
                current, baseline, total_change
            )

            dv = DimensionValue(
                value=key,
                current=current,
                baseline=baseline,
                change=change,
                change_percent=change_percent,
                contribution=contribution,
                contribution_percent=contribution_percent,
            )
            dimension_results.append(dv)

        # 按 |contribution| 降序排列
        dimension_results.sort(key=lambda x: abs(x.contribution), reverse=True)

        # 取 top_contributors（贡献度最大的，取全部）
        top_contributors = list(dimension_results)

        return DrillDownResult(
            dimension_name=dimension_name,
            values=dimension_results,
            top_contributors=top_contributors,
        )

    def _calculate_contribution(
        self,
        current: float,
        baseline: float,
        total_change: float,
    ) -> tuple[float, float]:
        """计算单个维度的贡献值和贡献百分比。

        贡献值 = current - baseline（该维度自身的变化量）
        贡献百分比 = 贡献值 / |total_change| * 100

        Args:
            current: 维度当前值
            baseline: 维度基线值
            total_change: 指标总变化量

        Returns:
            (贡献值, 贡献百分比)
        """
        contribution = current - baseline

        contribution_percent = 0.0 if total_change == 0 else contribution / abs(total_change) * 100

        return contribution, round(contribution_percent, 2)
