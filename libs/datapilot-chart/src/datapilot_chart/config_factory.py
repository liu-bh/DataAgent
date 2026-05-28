"""ECharts 配置工厂。

根据 ChartSpec 生成完整的 ECharts option 字典。
"""

from __future__ import annotations

from typing import Any

from datapilot_chart.models import ChartSeries, ChartSpec, ChartTheme, ChartType
from datapilot_chart.themes import DARK_THEME


class ChartConfigFactory:
    """ECharts 配置生成工厂。"""

    def build_option(self, spec: ChartSpec) -> dict[str, Any]:
        """根据 ChartSpec 生成 ECharts option 字典。

        Args:
            spec: 图表规范。

        Returns:
            可直接传给 ECharts 的 option 字典。
        """
        theme = spec.theme or DARK_THEME
        option: dict[str, Any] = {
            "backgroundColor": theme.background_color,
            "color": theme.colors,
            "textStyle": {"fontFamily": theme.font_family, "color": theme.text_color},
        }

        # 标题
        if spec.title:
            option["title"] = {"text": spec.title, "left": "center", "textStyle": {"color": theme.text_color}}

        # 图表类型对应的构建方法
        builder_map: dict[ChartType, Any] = {
            ChartType.LINE: self._build_line,
            ChartType.BAR: self._build_bar,
            ChartType.PIE: self._build_pie,
            ChartType.SCATTER: self._build_scatter,
            ChartType.HEATMAP: self._build_heatmap,
            ChartType.RADAR: self._build_radar,
            ChartType.GAUGE: self._build_gauge,
            ChartType.TABLE: self._build_table,
            ChartType.FUNNEL: self._build_funnel,
            ChartType.TREEMAP: self._build_treemap,
            ChartType.BOXPLOT: self._build_boxplot,
        }

        builder = builder_map.get(spec.chart_type, self._build_bar)
        chart_config = builder(spec, theme)
        option.update(chart_config)

        # tooltip
        tooltip = spec.tooltip if spec.tooltip else {"trigger": "axis"}
        option["tooltip"] = tooltip

        # legend
        if spec.legend or spec.series:
            legend_data = [s.name for s in spec.series] if spec.series else []
            option["legend"] = spec.legend or {
                "data": legend_data,
                "bottom": 0,
                "textStyle": {"color": theme.text_color},
            }

        return option

    def _build_line(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建折线图配置。"""
        config: dict[str, Any] = {"xAxis": {}, "yAxis": {}, "series": []}

        if spec.x_axis:
            config["xAxis"] = {
                "type": spec.x_axis.type.value,
                "name": spec.x_axis.name or spec.x_axis.field,
                "data": self._extract_axis_data(spec.series, is_x=True),
                "axisLabel": {"color": theme.text_color},
            }
        if spec.y_axis:
            config["yAxis"] = {
                "type": spec.y_axis.type.value,
                "name": spec.y_axis.name or spec.y_axis.field,
                "axisLabel": {"color": theme.text_color},
                "splitLine": {"lineStyle": {"color": "#444"}},
            }

        for s in spec.series:
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "line",
                "data": s.data,
                "smooth": True,
            }
            if s.item_style:
                series_item["itemStyle"] = s.item_style
            config["series"].append(series_item)

        return config

    def _build_bar(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建柱状图配置。"""
        config: dict[str, Any] = {"xAxis": {}, "yAxis": {}, "series": []}

        if spec.x_axis:
            config["xAxis"] = {
                "type": spec.x_axis.type.value,
                "name": spec.x_axis.name or spec.x_axis.field,
                "data": self._extract_axis_data(spec.series, is_x=True),
                "axisLabel": {"color": theme.text_color},
            }
        if spec.y_axis:
            config["yAxis"] = {
                "type": spec.y_axis.type.value,
                "name": spec.y_axis.name or spec.y_axis.field,
                "axisLabel": {"color": theme.text_color},
                "splitLine": {"lineStyle": {"color": "#444"}},
            }

        for s in spec.series:
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "bar",
                "data": s.data,
            }
            if s.item_style:
                series_item["itemStyle"] = s.item_style
            config["series"].append(series_item)

        return config

    def _build_pie(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建饼图配置。"""
        config: dict[str, Any] = {"series": []}

        for s in spec.series:
            # 饼图数据需要 name-value 格式
            pie_data = self._convert_to_name_value(s)
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "pie",
                "radius": "55%",
                "center": ["50%", "55%"],
                "data": pie_data,
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}},
            }
            if s.item_style:
                series_item["itemStyle"] = s.item_style
            config["series"].append(series_item)

        return config

    def _build_scatter(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建散点图配置。"""
        config: dict[str, Any] = {"xAxis": {}, "yAxis": {}, "series": []}

        config["xAxis"] = {
            "type": "value",
            "name": spec.x_axis.name if spec.x_axis else "",
            "axisLabel": {"color": theme.text_color},
            "splitLine": {"lineStyle": {"color": "#444"}},
        }
        config["yAxis"] = {
            "type": "value",
            "name": spec.y_axis.name if spec.y_axis else "",
            "axisLabel": {"color": theme.text_color},
            "splitLine": {"lineStyle": {"color": "#444"}},
        }

        for s in spec.series:
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "scatter",
                "data": s.data,
            }
            config["series"].append(series_item)

        return config

    def _build_heatmap(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建热力图配置。"""
        config: dict[str, Any] = {"xAxis": {}, "yAxis": {}, "series": [], "visualMap": {}}

        config["xAxis"] = {
            "type": "category",
            "data": spec.x_axis.name if spec.x_axis else [],
            "splitArea": {"show": True},
        }
        config["yAxis"] = {
            "type": "category",
            "data": spec.y_axis.name if spec.y_axis else [],
            "splitArea": {"show": True},
        }
        config["visualMap"] = {
            "min": 0,
            "max": 100,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": "5%",
        }

        for s in spec.series:
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "heatmap",
                "data": s.data,
            }
            config["series"].append(series_item)

        return config

    def _build_radar(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建雷达图配置。"""
        config: dict[str, Any] = {"radar": {}, "series": []}

        indicators = []
        if spec.x_axis:
            # 使用 x_axis 的 field 作为指示器名称
            x_data = self._extract_axis_data(spec.series, is_x=True)
            indicators = [{"name": str(d), "max": 100} for d in x_data]

        config["radar"] = {"indicator": indicators}
        series_data = []
        for s in spec.series:
            series_data.append({
                "value": s.data,
                "name": s.name,
            })
        config["series"] = [{
            "type": "radar",
            "data": series_data,
        }]

        return config

    def _build_gauge(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建仪表盘配置。"""
        config: dict[str, Any] = {"series": []}

        for s in spec.series:
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "gauge",
                "detail": {"formatter": "{value}%"},
                "data": s.data,
                "axisLine": {"lineStyle": {"color": [[0.3, "#67e0e3"], [0.7, "#37a2da"], [1, "#fd666d"]]}},
            }
            config["series"].append(series_item)

        return config

    def _build_table(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建表格配置（返回空 series，前端自行渲染表格）。"""
        return {"series": []}

    def _build_funnel(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建漏斗图配置。"""
        config: dict[str, Any] = {"series": []}

        for s in spec.series:
            pie_data = self._convert_to_name_value(s)
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "funnel",
                "data": pie_data,
            }
            config["series"].append(series_item)

        return config

    def _build_treemap(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建矩形树图配置。"""
        config: dict[str, Any] = {"series": []}

        for s in spec.series:
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "treemap",
                "data": s.data,
            }
            config["series"].append(series_item)

        return config

    def _build_boxplot(self, spec: ChartSpec, theme: ChartTheme) -> dict[str, Any]:
        """构建箱线图配置。"""
        config: dict[str, Any] = {"xAxis": {}, "yAxis": {}, "series": []}

        config["xAxis"] = {
            "type": "category",
            "data": [],
            "axisLabel": {"color": theme.text_color},
        }
        config["yAxis"] = {
            "type": "value",
            "axisLabel": {"color": theme.text_color},
            "splitLine": {"lineStyle": {"color": "#444"}},
        }

        for s in spec.series:
            series_item: dict[str, Any] = {
                "name": s.name,
                "type": "boxplot",
                "data": s.data,
            }
            config["series"].append(series_item)

        return config

    @staticmethod
    def _extract_axis_data(series_list: list[ChartSeries], is_x: bool) -> list:
        """从系列数据中提取轴标签数据。

        对于 x 轴，提取第一个系列的 data 作为标签。
        """
        if not series_list:
            return []
        first = series_list[0]
        if isinstance(first.data, list) and first.data and isinstance(first.data[0], list):
            # [[x, y], ...] 格式，提取 x 值
            return [item[0] for item in first.data if isinstance(item, (list, tuple))]
        return first.data

    @staticmethod
    def _convert_to_name_value(series: ChartSeries) -> list[dict[str, Any]]:
        """将系列数据转换为 [{name, value}] 格式，用于饼图/漏斗图。"""
        if not series.data:
            return []
        if isinstance(series.data[0], dict):
            return series.data
        if isinstance(series.data[0], (list, tuple)) and len(series.data[0]) >= 2:
            return [{"name": item[0], "value": item[1]} for item in series.data]
        return [{"name": series.name, "value": v} for v in series.data]
