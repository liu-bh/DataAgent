"""语义层模型导出。

导出所有 SQLAlchemy ORM 模型和 Pydantic Schema。
SourceTable、DataSource、DataSourceHealth 由 metadata 模块定义。
"""

from datapilot_semantic.metadata.models import DataSource, DataSourceHealth, SourceTable
from datapilot_semantic.models.dimension import Dimension
from datapilot_semantic.models.metric import Metric
from datapilot_semantic.models.metric_dimension import MetricDimension
from datapilot_semantic.models.semantic_model import SemanticModel
from datapilot_semantic.models.service import SemanticModelService
from datapilot_semantic.models.table_relationship import TableRelationship

# 所有 ORM 模型列表，供 Alembic autogenerate 使用
ALL_MODELS = [
    DataSource,
    DataSourceHealth,
    SourceTable,
    SemanticModel,
    Metric,
    Dimension,
    MetricDimension,
    TableRelationship,
]

__all__ = [
    "ALL_MODELS",
    "DataSource",
    "DataSourceHealth",
    "Dimension",
    "Metric",
    "MetricDimension",
    "SemanticModel",
    "SemanticModelService",
    "SourceTable",
    "TableRelationship",
]
