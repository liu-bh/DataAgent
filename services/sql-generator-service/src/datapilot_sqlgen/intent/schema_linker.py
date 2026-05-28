"""Schema Linker 模块。

将用户意图中的指标/维度名称映射到语义层的具体表和字段，
推导 JOIN 路径，选择合适的语义模型。
支持精确匹配、同义词匹配、模糊匹配和向量相似度匹配。
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

import structlog

from datapilot_sqlgen.intent.types import (
    FilterCondition,
    JoinStep,
    LinkedDimension,
    LinkedMetric,
    ParsedIntent,
    SemanticContext,
)

logger = structlog.get_logger(__name__)


# ============================================================
# Mock 数据结构（DB 查询 placeholder）
# ============================================================


class _MockMetric:
    """指标 Mock 数据。"""

    def __init__(
        self,
        metric_id: str,
        name: str,
        calculation: str,
        unit: str | None,
        table_id: str | None,
        table_name: str | None,
        semantic_model_id: str,
        synonyms: list[str] | None = None,
    ) -> None:
        self.id = metric_id
        self.name = name
        self.calculation = calculation
        self.unit = unit
        self.table_id = table_id
        self.table_name = table_name
        self.semantic_model_id = semantic_model_id
        self.synonyms = synonyms or []


class _MockDimension:
    """维度 Mock 数据。"""

    def __init__(
        self,
        dimension_id: str,
        name: str,
        column_name: str,
        table_id: str | None,
        table_name: str | None,
        semantic_model_id: str,
        synonyms: list[str] | None = None,
        is_virtual: bool = False,
    ) -> None:
        self.id = dimension_id
        self.name = name
        self.column_name = column_name
        self.table_id = table_id
        self.table_name = table_name
        self.semantic_model_id = semantic_model_id
        self.synonyms = synonyms or []
        self.is_virtual = is_virtual


class _MockRelationship:
    """表关系 Mock 数据。"""

    def __init__(
        self,
        left_table_id: str,
        right_table_id: str,
        left_table_name: str,
        right_table_name: str,
        join_type: str,
        join_condition: str,
        semantic_model_id: str,
    ) -> None:
        self.left_table_id = left_table_id
        self.right_table_id = right_table_id
        self.left_table_name = left_table_name
        self.right_table_name = right_table_name
        self.join_type = join_type
        self.join_condition = join_condition
        self.semantic_model_id = semantic_model_id


# 匹配置信度阈值
_EXACT_THRESHOLD: float = 1.0
_SYNONYM_THRESHOLD: float = 0.9
_FUZZY_THRESHOLD: float = 0.7
_VECTOR_THRESHOLD: float = 0.6


class SchemaLinker:
    """Schema Linker。

    将 ParsedIntent 中的指标/维度名称映射到语义层的具体物理表和字段，
    推导表间 JOIN 路径，选择合适的语义模型。

    匹配优先级：精确匹配 > 同义词匹配 > 模糊匹配 > 向量匹配

    Usage::

        linker = SchemaLinker()
        context = linker.link(parsed_intent, tenant_id="t-001")
    """

    def __init__(self, *, use_vector_search: bool = True) -> None:
        """初始化 Schema Linker。

        Args:
            use_vector_search: 是否使用向量相似度辅助匹配。默认 True。
        """
        self._use_vector_search = use_vector_search
        logger.info("SchemaLinker 初始化", use_vector_search=use_vector_search)

    # ---- 公开接口 ----

    def link(
        self,
        parsed_intent: ParsedIntent,
        tenant_id: str,
        semantic_model_id: str | None = None,
    ) -> SemanticContext:
        """将解析后的意图映射到语义层。

        Args:
            parsed_intent: IntentParser 的输出。
            tenant_id: 租户 ID。
            semantic_model_id: 可选的语义模型 ID（限定搜索范围）。

        Returns:
            SemanticContext 包含匹配的表、指标、维度和 JOIN 路径。
        """
        warnings: list[str] = []

        # 1. 匹配指标
        linked_metrics = self._match_metrics(
            parsed_intent.target_metrics, tenant_id, semantic_model_id
        )
        unmatched_metrics = set(parsed_intent.target_metrics) - {
            m.name for m in linked_metrics
        }
        if unmatched_metrics:
            warnings.append(f"以下指标未匹配到语义层: {', '.join(unmatched_metrics)}")

        # 2. 匹配维度
        linked_dimensions = self._match_dimensions(
            parsed_intent.target_dimensions, tenant_id, semantic_model_id
        )
        unmatched_dims = set(parsed_intent.target_dimensions) - {
            d.name for d in linked_dimensions
        }
        if unmatched_dims:
            warnings.append(f"以下维度未匹配到语义层: {', '.join(unmatched_dims)}")

        # 3. 从过滤条件中提取额外的维度
        filter_linked_dims = self._match_filter_dimensions(
            parsed_intent.filters, tenant_id, semantic_model_id
        )
        for fd in filter_linked_dims:
            # 避免重复
            if not any(d.dimension_id == fd.dimension_id for d in linked_dimensions):
                linked_dimensions.append(fd)

        # 4. 收集需要的表
        needed_table_ids = self._collect_table_ids(linked_metrics, linked_dimensions)

        # 5. 推导 JOIN 路径
        join_path, selected_tables = self._build_join_path(
            needed_table_ids, tenant_id, semantic_model_id
        )

        # 6. 选择语义模型
        resolved_model_id, resolved_model_name = self._select_semantic_model(
            linked_metrics, linked_dimensions, tenant_id, semantic_model_id
        )

        # 7. 构建过滤条件
        resolved_filters = self._resolve_filters(
            parsed_intent.filters, linked_dimensions
        )

        logger.info(
            "Schema Linking 完成",
            metrics_count=len(linked_metrics),
            dimensions_count=len(linked_dimensions),
            tables_count=len(selected_tables),
            join_steps=len(join_path),
            warnings_count=len(warnings),
        )

        return SemanticContext(
            selected_tables=selected_tables,
            selected_metrics=linked_metrics,
            selected_dimensions=linked_dimensions,
            join_path=join_path,
            semantic_model_id=resolved_model_id,
            semantic_model_name=resolved_model_name,
            filters=resolved_filters,
            warnings=warnings,
        )

    # ---- 指标匹配 ----

    def _match_metrics(
        self,
        metric_names: list[str],
        tenant_id: str,
        semantic_model_id: str | None,
    ) -> list[LinkedMetric]:
        """匹配指标名称到语义层。"""
        # TODO: 实际实现需查询 metrics 表
        # SELECT * FROM metrics WHERE tenant_id = :tenant_id
        #   AND (semantic_model_id = :sm_id OR :sm_id IS NULL)
        mock_metrics = self._get_mock_metrics(tenant_id, semantic_model_id)

        result: list[LinkedMetric] = []
        for name in metric_names:
            best = self._find_best_metric_match(name, mock_metrics)
            if best:
                result.append(best)

        return result

    def _find_best_metric_match(
        self, name: str, candidates: list[_MockMetric]
    ) -> LinkedMetric | None:
        """在候选指标中找到最佳匹配。"""
        best_match: _MockMetric | None = None
        best_score: float = 0.0
        best_method: str = ""

        for candidate in candidates:
            # 精确匹配
            if candidate.name.lower() == name.lower():
                return LinkedMetric(
                    metric_id=candidate.id,
                    name=candidate.name,
                    calculation=candidate.calculation,
                    unit=candidate.unit,
                    table_id=candidate.table_id,
                    table_name=candidate.table_name,
                    match_score=1.0,
                    matched_by="exact",
                )

            # 同义词匹配
            if name.lower() in [s.lower() for s in candidate.synonyms]:
                score = _SYNONYM_THRESHOLD
                if score > best_score:
                    best_match = candidate
                    best_score = score
                    best_method = "synonym"

            # 模糊匹配
            fuzzy_score = SequenceMatcher(None, candidate.name.lower(), name.lower()).ratio()
            if fuzzy_score >= _FUZZY_THRESHOLD and fuzzy_score > best_score:
                best_match = candidate
                best_score = fuzzy_score
                best_method = "fuzzy"

        if best_match:
            return LinkedMetric(
                metric_id=best_match.id,
                name=best_match.name,
                calculation=best_match.calculation,
                unit=best_match.unit,
                table_id=best_match.table_id,
                table_name=best_match.table_name,
                match_score=best_score,
                matched_by=best_method,
            )

        return None

    # ---- 维度匹配 ----

    def _match_dimensions(
        self,
        dimension_names: list[str],
        tenant_id: str,
        semantic_model_id: str | None,
    ) -> list[LinkedDimension]:
        """匹配维度名称到语义层。"""
        # TODO: 实际实现需查询 dimensions 表
        mock_dims = self._get_mock_dimensions(tenant_id, semantic_model_id)

        result: list[LinkedDimension] = []
        for name in dimension_names:
            best = self._find_best_dimension_match(name, mock_dims)
            if best:
                result.append(best)

        return result

    def _find_best_dimension_match(
        self, name: str, candidates: list[_MockDimension]
    ) -> LinkedDimension | None:
        """在候选维度中找到最佳匹配。"""
        best_match: _MockDimension | None = None
        best_score: float = 0.0
        best_method: str = ""

        for candidate in candidates:
            # 精确匹配
            if candidate.name.lower() == name.lower():
                return LinkedDimension(
                    dimension_id=candidate.id,
                    name=candidate.name,
                    column_name=candidate.column_name,
                    table_id=candidate.table_id,
                    table_name=candidate.table_name,
                    synonyms=candidate.synonyms,
                    is_virtual=candidate.is_virtual,
                    match_score=1.0,
                    matched_by="exact",
                )

            # 同义词匹配（双向：用户新词匹配维度的同义词，用户词匹配维度名）
            all_names = [candidate.name] + candidate.synonyms
            for syn in all_names:
                if name.lower() == syn.lower():
                    score = _SYNONYM_THRESHOLD
                    if score > best_score:
                        best_match = candidate
                        best_score = score
                        best_method = "synonym"
                    break

            # 模糊匹配
            fuzzy_score = SequenceMatcher(
                None, candidate.name.lower(), name.lower()
            ).ratio()
            if fuzzy_score >= _FUZZY_THRESHOLD and fuzzy_score > best_score:
                best_match = candidate
                best_score = fuzzy_score
                best_method = "fuzzy"

        if best_match:
            return LinkedDimension(
                dimension_id=best_match.id,
                name=best_match.name,
                column_name=best_match.column_name,
                table_id=best_match.table_id,
                table_name=best_match.table_name,
                synonyms=best_match.synonyms,
                is_virtual=best_match.is_virtual,
                match_score=best_score,
                matched_by=best_method,
            )

        return None

    def _match_filter_dimensions(
        self,
        filters: list[FilterCondition],
        tenant_id: str,
        semantic_model_id: str | None,
    ) -> list[LinkedDimension]:
        """从过滤条件中提取维度匹配。"""
        # TODO: 实际实现需查询 dimensions 表
        mock_dims = self._get_mock_dimensions(tenant_id, semantic_model_id)

        result: list[LinkedDimension] = []
        for f in filters:
            best = self._find_best_dimension_match(f.column, mock_dims)
            if best:
                result.append(best)

        return result

    # ---- 表收集与 JOIN 路径推导 ----

    def _collect_table_ids(
        self,
        metrics: list[LinkedMetric],
        dimensions: list[LinkedDimension],
    ) -> set[str]:
        """收集所有需要的表 ID。"""
        table_ids: set[str] = set()
        for m in metrics:
            if m.table_id:
                table_ids.add(m.table_id)
        for d in dimensions:
            if d.table_id:
                table_ids.add(d.table_id)
        return table_ids

    def _build_join_path(
        self,
        table_ids: set[str],
        tenant_id: str,
        semantic_model_id: str | None,
    ) -> tuple[list[JoinStep], list[str]]:
        """推导表间 JOIN 路径。

        使用图遍历算法找到连接所有需要的表的最短路径。

        Returns:
            (join_path, selected_table_names) 元组。
        """
        if len(table_ids) <= 1:
            # 只需单表，无需 JOIN
            table_names: list[str] = []
            for tid in table_ids:
                name = self._get_table_name_by_id(tid, tenant_id, semantic_model_id)
                if name:
                    table_names.append(name)
            return [], table_names

        # TODO: 实际实现需查询 table_relationships 表
        # 构建邻接图，使用 BFS 找到连接所有表的最短 JOIN 路径
        mock_rels = self._get_mock_relationships(tenant_id, semantic_model_id)

        # 构建邻接图: table_id -> [(neighbor_id, join_info)]
        graph: dict[str, list[tuple[str, _MockRelationship]]] = {}
        for rel in mock_rels:
            graph.setdefault(rel.left_table_id, []).append((rel.right_table_id, rel))
            graph.setdefault(rel.right_table_id, []).append((rel.left_table_id, rel))

        # 使用 BFS 找到连接所有表的 JOIN 路径
        join_steps = self._bfs_join_path(table_ids, graph)

        # 收集所有涉及的表名
        involved_table_ids = set(table_ids)
        for step in join_steps:
            involved_table_ids.add(step.left_table)
            involved_table_ids.add(step.right_table)

        table_names = []
        for tid in involved_table_ids:
            name = self._get_table_name_by_id(tid, tenant_id, semantic_model_id)
            if name:
                table_names.append(name)

        return join_steps, table_names

    def _bfs_join_path(
        self,
        target_ids: set[str],
        graph: dict[str, list[tuple[str, _MockRelationship]]],
    ) -> list[JoinStep]:
        """使用 BFS 搜索连接所有目标表的 JOIN 路径。

        简化实现：从一个起始表出发，逐步 BFS 到所有其他目标表。
        """
        if not target_ids:
            return []

        join_steps: list[JoinStep] = []
        visited: set[str] = set()
        remaining = set(target_ids)

        # 选择第一个表作为起始
        start = next(iter(remaining))
        visited.add(start)
        remaining.discard(start)

        while remaining:
            # 从已访问的边界扩展到最近的未访问目标表
            found = False
            for current in list(visited):
                if current not in graph:
                    continue
                for neighbor, rel in graph[current]:
                    if neighbor in remaining:
                        join_steps.append(
                            JoinStep(
                                left_table=rel.left_table_name,
                                right_table=rel.right_table_name,
                                join_type=rel.join_type,
                                join_condition=rel.join_condition,
                            )
                        )
                        visited.add(neighbor)
                        remaining.discard(neighbor)
                        found = True
                        break
                if found:
                    break
            if not found:
                logger.warning(
                    "无法找到连接所有表的 JOIN 路径",
                    unconnected_tables=remaining,
                )
                break

        return join_steps

    # ---- 语义模型选择 ----

    def _select_semantic_model(
        self,
        metrics: list[LinkedMetric],
        dimensions: list[LinkedDimension],
        tenant_id: str,
        preferred_model_id: str | None,
    ) -> tuple[str | None, str | None]:
        """选择最合适的语义模型。

        如果指定了 preferred_model_id 则直接使用，
        否则根据匹配到的指标/维度所属语义模型投票决定。
        """
        if preferred_model_id:
            # TODO: 查询 semantic_models 表获取名称
            return preferred_model_id, None

        # 投票统计
        # TODO: 实际实现中从 LinkedMetric/LinkedDimension 中获取 semantic_model_id
        # 暂时返回 None
        return None, None

    # ---- 过滤条件解析 ----

    def _resolve_filters(
        self,
        filters: list[FilterCondition],
        linked_dimensions: list[LinkedDimension],
    ) -> list[FilterCondition]:
        """将过滤条件中的业务维度名映射到物理列名。"""
        dim_map: dict[str, str] = {}
        for dim in linked_dimensions:
            dim_map[dim.name.lower()] = dim.column_name
            for syn in dim.synonyms:
                dim_map[syn.lower()] = dim.column_name

        resolved: list[FilterCondition] = []
        for f in filters:
            col = dim_map.get(f.column.lower(), f.column)
            resolved.append(
                FilterCondition(
                    column=col,
                    operator=f.operator,
                    value=f.value,
                    raw_text=f.raw_text,
                )
            )

        return resolved

    # ---- Mock 数据方法 ----

    def _get_mock_metrics(
        self, tenant_id: str, semantic_model_id: str | None
    ) -> list[_MockMetric]:
        """获取 Mock 指标数据（实际应查询 DB）。"""
        # TODO: 替换为实际 DB 查询
        return [
            _MockMetric(
                metric_id="m-001",
                name="GMV",
                calculation="SUM(orders.amount)",
                unit="元",
                table_id="t-001",
                table_name="orders",
                semantic_model_id="sm-001",
                synonyms=["销售额", "成交额"],
            ),
            _MockMetric(
                metric_id="m-002",
                name="订单量",
                calculation="COUNT(DISTINCT orders.id)",
                unit="单",
                table_id="t-001",
                table_name="orders",
                semantic_model_id="sm-001",
                synonyms=["订单数", "订单总数"],
            ),
            _MockMetric(
                metric_id="m-003",
                name="客单价",
                calculation="SUM(orders.amount) / COUNT(DISTINCT orders.id)",
                unit="元",
                table_id="t-001",
                table_name="orders",
                semantic_model_id="sm-001",
                synonyms=["平均订单金额"],
            ),
            _MockMetric(
                metric_id="m-004",
                name="利润",
                calculation="SUM(orders.amount - orders.cost)",
                unit="元",
                table_id="t-001",
                table_name="orders",
                semantic_model_id="sm-001",
                synonyms=["净利润", "毛利润"],
            ),
        ]

    def _get_mock_dimensions(
        self, tenant_id: str, semantic_model_id: str | None
    ) -> list[_MockDimension]:
        """获取 Mock 维度数据（实际应查询 DB）。"""
        return [
            _MockDimension(
                dimension_id="d-001",
                name="地区",
                column_name="region",
                table_id="t-002",
                table_name="users",
                semantic_model_id="sm-001",
                synonyms=["区域", "大区", "省份"],
            ),
            _MockDimension(
                dimension_id="d-002",
                name="时间",
                column_name="created_at",
                table_id="t-001",
                table_name="orders",
                semantic_model_id="sm-001",
                synonyms=["日期", "月份", "季度"],
            ),
            _MockDimension(
                dimension_id="d-003",
                name="商品类目",
                column_name="category_name",
                table_id="t-003",
                table_name="products",
                semantic_model_id="sm-001",
                synonyms=["品类", "类目", "分类"],
            ),
            _MockDimension(
                dimension_id="d-004",
                name="渠道",
                column_name="channel",
                table_id="t-001",
                table_name="orders",
                semantic_model_id="sm-001",
                synonyms=["来源渠道", "获客渠道"],
            ),
        ]

    def _get_mock_relationships(
        self, tenant_id: str, semantic_model_id: str | None
    ) -> list[_MockRelationship]:
        """获取 Mock 表关系数据（实际应查询 DB）。"""
        return [
            _MockRelationship(
                left_table_id="t-001",
                right_table_id="t-002",
                left_table_name="orders",
                right_table_name="users",
                join_type="left",
                join_condition="orders.user_id = users.id",
                semantic_model_id="sm-001",
            ),
            _MockRelationship(
                left_table_id="t-001",
                right_table_id="t-004",
                left_table_name="orders",
                right_table_name="order_items",
                join_type="inner",
                join_condition="orders.id = order_items.order_id",
                semantic_model_id="sm-001",
            ),
            _MockRelationship(
                left_table_id="t-004",
                right_table_id="t-003",
                left_table_name="order_items",
                right_table_name="products",
                join_type="inner",
                join_condition="order_items.product_id = products.id",
                semantic_model_id="sm-001",
            ),
        ]

    def _get_table_name_by_id(
        self, table_id: str, tenant_id: str, semantic_model_id: str | None
    ) -> str | None:
        """根据表 ID 获取表名。"""
        id_to_name = {
            "t-001": "orders",
            "t-002": "users",
            "t-003": "products",
            "t-004": "order_items",
        }
        return id_to_name.get(table_id)

    # ---- 向量搜索（预留接口） ----

    async def _vector_search_metrics(
        self, query: str, tenant_id: str, semantic_model_id: str | None
    ) -> list[dict[str, Any]]:
        """通过向量搜索辅助匹配指标。

        调用 semantic-service 的 search API。
        """
        # TODO: 调用 semantic-service POST /api/v1/search
        # response = await httpx_client.post(
        #     f"{SEMANTIC_SERVICE_URL}/api/v1/search",
        #     json={
        #         "query": query,
        #         "tenant_id": tenant_id,
        #         "semantic_model_id": semantic_model_id,
        #         "search_type": "metric",
        #         "top_k": 5,
        #     },
        # )
        logger.debug("向量搜索指标（预留）", query=query)
        return []

    async def _vector_search_dimensions(
        self, query: str, tenant_id: str, semantic_model_id: str | None
    ) -> list[dict[str, Any]]:
        """通过向量搜索辅助匹配维度。"""
        # TODO: 调用 semantic-service POST /api/v1/search
        logger.debug("向量搜索维度（预留）", query=query)
        return []
