"""归因分析器。"""

from __future__ import annotations

from typing import Any

from datapilot_agent.rca.models import AttributionResult, DrillDownResult


class AttributionAnalyzer:
    """综合各维度下钻结果，进行归因分析。

    算法：
    1. 汇总各维度的 top_contributors
    2. 按贡献度绝对值降序排列
    3. 累计贡献度达到 80% 的作为 key_drivers
    """

    def analyze(
        self,
        drill_downs: list[DrillDownResult],
        total_change: float,
    ) -> AttributionResult:
        """综合各维度下钻结果，计算归因。

        Args:
            drill_downs: 各维度的下钻结果
            total_change: 总变化量

        Returns:
            AttributionResult: 归因分析结果
        """
        # 总变化百分比
        total_change_percent = 0.0
        if total_change != 0:
            # total_change 是实际差值，需要基于基线计算百分比
            # 此处 total_change_percent 由调用方设置或使用原始值
            total_change_percent = total_change

        # 汇总各维度的 top_contributors
        all_contributors: list[dict[str, Any]] = []
        for dd in drill_downs:
            for dv in dd.top_contributors:
                all_contributors.append(
                    {
                        "dimension": dd.dimension_name,
                        "value": dv.value,
                        "current": dv.current,
                        "baseline": dv.baseline,
                        "change": dv.change,
                        "change_percent": dv.change_percent,
                        "contribution": dv.contribution,
                        "contribution_percent": dv.contribution_percent,
                    }
                )

        # 按贡献度绝对值降序排列
        all_contributors.sort(key=lambda x: abs(x["contribution"]), reverse=True)

        # 提取关键驱动因素
        key_drivers = self._extract_key_drivers(all_contributors)

        return AttributionResult(
            total_change=total_change,
            total_change_percent=total_change_percent,
            dimensions=all_contributors,
            key_drivers=key_drivers,
        )

    def _extract_key_drivers(
        self,
        dimensions: list[dict[str, Any]],
        threshold_percent: float = 0.8,
    ) -> list[str]:
        """提取关键驱动因素。

        累计贡献度绝对值占总贡献度绝对值达到阈值的维度值。
        每个维度值用 "维度名:维度值" 的格式表示。

        Args:
            dimensions: 按贡献度绝对值降序排列的维度贡献列表
            threshold_percent: 累计贡献度阈值，默认 0.8（80%）

        Returns:
            关键驱动因素列表
        """
        if not dimensions:
            return []

        # 计算总贡献绝对值
        total_abs_contribution = sum(abs(d["contribution"]) for d in dimensions)
        if total_abs_contribution == 0:
            return []

        key_drivers: list[str] = []
        cumulative = 0.0

        for d in dimensions:
            cumulative += abs(d["contribution"])
            # 用 "维度名:维度值" 的格式
            driver_label = f"{d['dimension']}:{d['value']}"
            key_drivers.append(driver_label)

            # 累计贡献达到阈值后停止
            if cumulative / total_abs_contribution >= threshold_percent:
                break

        return key_drivers
