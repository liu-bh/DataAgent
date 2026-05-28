"""DataPilot 图表推荐模块。

提供 LLM 智能图表推荐、图表类型推断、自然语言描述生成等能力。
"""

from datapilot_agent.chart.description import ChartDescriptionGenerator
from datapilot_agent.chart.recommender import ChartRecommendation, ChartRecommender

__all__ = [
    "ChartDescriptionGenerator",
    "ChartRecommendation",
    "ChartRecommender",
]
