"""图表推荐 Prompt 模板。

定义图表类型推荐和图表描述生成的 LLM Prompt 模板。
"""

from __future__ import annotations

CHART_RECOMMEND_PROMPT: str = """你是一个数据可视化专家。根据数据特征和用户问题，推荐最合适的图表类型。

## 数据信息
- 列信息: {columns}
- 数据行数: {row_count}
- 用户问题: {question}

## 可选图表类型
- line: 折线图，适合展示时间序列趋势
- bar: 柱状图，适合展示分类数据对比
- pie: 饼图，适合展示少量分类的占比
- scatter: 散点图，适合展示两个数值变量的相关性
- table: 表格，适合展示明细数据
- area: 面积图，适合展示累计趋势
- heatmap: 热力图，适合展示多维交叉数据

## 输出格式
请返回 JSON 数组，每个元素包含:
- type: 图表类型名称
- confidence: 推荐置信度 (0.0~1.0)

示例:
[{{"type": "line", "confidence": 0.9}}, {{"type": "bar", "confidence": 0.3}}]

请只返回 JSON，不要添加其他说明文字。"""


CHART_DESCRIPTION_PROMPT: str = """你是一个数据可视化专家。请根据图表配置和数据摘要，生成一段简洁的自然语言描述。

## 图表信息
- 图表类型: {chart_type}
- X 轴字段: {x_field}
- Y 轴字段: {y_fields}

## 数据摘要
{data_summary}

## 统计信息
{result_stats}

## 要求
1. 描述不超过 100 字
2. 突出数据的关键发现
3. 使用自然、专业的语言
4. 不使用 markdown 格式

请直接输出描述文本，不要添加引号或其他标记。"""


CHART_TITLE_PROMPT: str = """你是一个数据可视化专家。请根据图表信息生成一个简洁的标题。

## 图表信息
- 图表类型: {chart_type}
- X 轴字段: {x_field}
- Y 轴字段: {y_fields}

## 数据摘要
{data_summary}

## 要求
1. 标题不超过 20 字
2. 准确反映图表内容
3. 使用简洁专业的语言

请直接输出标题文本，不要添加引号或其他标记。"""
