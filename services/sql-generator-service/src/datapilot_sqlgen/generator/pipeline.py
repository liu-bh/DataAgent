"""NL2SQL 编排器。

编排完整的 NL2SQL 流程，包含 7 个步骤：
1. 意图路由（Intent Router）
2. 意图解析（Intent Parser）
3. 语义解析（Semantic Resolver）
4. Schema Linking（表/字段选择）
5. Prompt 组装
6. LLM 生成 SQL（JSON mode）
7. SQL 后处理（解析 -> sqlglot AST -> 验证 -> 渲染）

依赖 Track A/C 的 intent 模块提供的 IntentRouter、IntentParser、SchemaLinker。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from .models import (
    FewShotExample,
    NL2SQLResult,
    SemanticContext,
)

if TYPE_CHECKING:
    from datapilot_sqlgen.intent.parser import IntentParser
    from datapilot_sqlgen.intent.router import IntentRouter
    from datapilot_sqlgen.intent.schema_linker import SchemaLinker

    from .postprocess import SQLPostProcessor
    from .prompt_builder import PromptBuilder

logger = structlog.get_logger(__name__)


class NL2SQLPipeline:
    """NL2SQL Pipeline 编排器。

    协调意图识别、语义解析、Few-shot 匹配、Prompt 组装、LLM 调用
    和 SQL 后处理等步骤，完成完整的 NL2SQL 流程。

    Args:
        prompt_builder: Prompt 组装器。
        postprocessor: SQL 后处理器。
        fewshot_matcher: Few-shot 匹配器（可选）。
        intent_router: 意图路由器（可选，来自 intent 模块）。
        intent_parser: 意图解析器（可选，来自 intent 模块）。
        schema_linker: Schema Linker（可选，来自 intent 模块）。
        llm_router: LLM 路由器（可选，来自 datapilot-llm）。
    """

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        postprocessor: SQLPostProcessor,
        fewshot_matcher: object | None = None,
        intent_router: IntentRouter | None = None,
        intent_parser: IntentParser | None = None,
        schema_linker: SchemaLinker | None = None,
        llm_router: object | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._postprocessor = postprocessor
        self._fewshot_matcher = fewshot_matcher
        self._intent_router = intent_router
        self._intent_parser = intent_parser
        self._schema_linker = schema_linker
        self._llm_router = llm_router

    async def generate(
        self,
        question: str,
        session_id: str,
        tenant_id: str,
        context: SemanticContext | None = None,
    ) -> NL2SQLResult:
        """执行完整的 NL2SQL 生成流程。

        Args:
            question: 用户自然语言问题。
            session_id: 会话 ID。
            tenant_id: 租户 ID。
            context: 可选的语义上下文（如果不提供，由 Schema Linking 生成）。

        Returns:
            NL2SQLResult 生成结果。
        """
        start_time = time.monotonic()
        context = context or SemanticContext()

        logger.info(
            "NL2SQL Pipeline 开始",
            question=question,
            session_id=session_id,
            tenant_id=tenant_id,
        )

        # ---- 步骤 1：意图路由 ----
        intent_type, intent_confidence = self._step_intent_route(question)

        # 闲聊：直接返回文本
        if intent_type == "chitchat":
            return NL2SQLResult(
                sql="",
                sql_dialect="",
                intent="chitchat",
                text_response="你好！我是 DataPilot 数据助手，可以帮你查询数据。请问你想了解什么？",
                confidence=intent_confidence,
                latency_ms=int((time.monotonic() - start_time) * 1000),
            )

        # 超出范围：返回友好提示
        if intent_type == "out_of_scope":
            return NL2SQLResult(
                sql="",
                sql_dialect="",
                intent="out_of_scope",
                text_response=(
                    "抱歉，这个问题超出了我的能力范围。我可以帮你查询和分析数据，"
                    "比如销售数据、用户行为等。试试问我一个数据相关的问题吧！"
                ),
                confidence=intent_confidence,
                latency_ms=int((time.monotonic() - start_time) * 1000),
            )

        # ---- 步骤 2：意图解析 ----
        parsed_intent = self._step_intent_parse(question)

        # ---- 步骤 3+4：Schema Linking + 语义解析 ----
        linked_context = self._step_schema_link_and_resolve(
            question, parsed_intent, context, tenant_id
        )

        # ---- 步骤 5：Prompt 组装 ----
        prompt, used_few_shots = await self._step_build_prompt(
            question=question,
            context=linked_context,
            tenant_id=tenant_id,
        )

        # ---- 步骤 6：LLM 生成 SQL ----
        llm_output, explanation, llm_confidence = await self._step_llm_generate(
            prompt=prompt,
            dialect=linked_context.dialect,
            tenant_id=tenant_id,
        )

        # ---- 步骤 7：SQL 后处理 ----
        processed = self._postprocessor.process(
            llm_output=llm_output,
            dialect=linked_context.dialect,
        )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        result = NL2SQLResult(
            sql=processed.sql,
            sql_dialect=processed.dialect,
            explanation=explanation or processed.sql or "",
            confidence=llm_confidence,
            used_few_shots=[fs.question for fs in used_few_shots],
            latency_ms=latency_ms,
            intent=intent_type,
            warnings=processed.warnings,
        )

        logger.info(
            "NL2SQL Pipeline 完成",
            question=question,
            latency_ms=latency_ms,
            confidence=llm_confidence,
            warning_count=len(processed.warnings),
        )

        return result

    # ------------------------------------------------------------------
    # Pipeline 步骤实现
    # ------------------------------------------------------------------

    def _step_intent_route(self, question: str) -> tuple[str, float]:
        """步骤 1：意图路由。

        使用 intent 模块的 IntentRouter 判断用户问题意图。
        IntentRouter.classify() 是同步方法，返回 IntentResult。

        Args:
            question: 用户问题。

        Returns:
            (intent_type, confidence)：意图类型字符串和置信度。
        """
        if self._intent_router is not None:
            try:
                intent_result = self._intent_router.classify(question)
                intent = intent_result.intent_type.value
                confidence = intent_result.confidence
                logger.debug("意图路由完成", intent=intent, confidence=confidence)
                return intent, confidence
            except Exception as e:
                logger.warning("意图路由调用失败，降级为规则路由", error=str(e))

        # 降级：使用简单规则判断
        return self._rule_based_intent_route(question)

    @staticmethod
    def _rule_based_intent_route(question: str) -> tuple[str, float]:
        """基于规则的意图路由降级策略。

        Args:
            question: 用户问题。

        Returns:
            (intent_type, confidence)。
        """
        # 问候语
        greetings = ("你好", "hello", "hi", "嗨", "在吗", "谢谢", "感谢")
        q_lower = question.strip().lower()
        for g in greetings:
            if q_lower == g or q_lower.startswith(g):
                return "chitchat", 0.9

        # 数据查询关键词
        sql_keywords = (
            "多少",
            "统计",
            "排名",
            "趋势",
            "查询",
            "搜索",
            "多少条",
            "top",
            "最高",
            "最低",
            "总计",
            "汇总",
            "平均",
            "比例",
            "占比",
            "环比",
            "同比",
            "增长",
            "下降",
            "列出",
            "展示",
            "查看",
            "分析",
            "对比",
            "分布",
            "计数",
        )
        for kw in sql_keywords:
            if kw in question:
                return "sql_query", 0.7

        # 默认为 SQL 查询
        return "sql_query", 0.5

    def _step_intent_parse(self, question: str) -> Any:
        """步骤 2：意图解析。

        使用 intent 模块的 IntentParser 解析结构化意图。
        IntentParser.parse() 是同步方法，接受 question, context。

        Args:
            question: 用户问题。

        Returns:
            ParsedIntent 解析结果。
        """
        if self._intent_parser is not None:
            try:
                parsed = self._intent_parser.parse(question)
                logger.debug("意图解析完成", query_type=parsed.query_type.value)
                return parsed
            except Exception as e:
                logger.warning("意图解析调用失败", error=str(e))

        # 降级：返回一个空的 ParsedIntent
        from datapilot_sqlgen.intent.types import ParsedIntent

        return ParsedIntent(raw_question=question)

    def _step_schema_link_and_resolve(
        self,
        question: str,
        parsed_intent: Any,
        context: SemanticContext,
        tenant_id: str,
    ) -> SemanticContext:
        """步骤 3+4：Schema Linking + 语义解析。

        使用 intent 模块的 SchemaLinker 选择相关表和字段，
        并将 intent 层的 SemanticContext 转换为 generator 层的 SemanticContext。

        Args:
            question: 用户问题。
            parsed_intent: ParsedIntent 解析结果。
            context: 当前语义上下文。
            tenant_id: 租户 ID。

        Returns:
            丰富后的 SemanticContext（generator 层）。
        """
        if self._schema_linker is not None and self._intent_parser is not None:
            try:
                # 使用 SchemaLinker.link(parsed_intent, tenant_id) 获取 intent 层语义上下文
                intent_ctx = self._schema_linker.link(parsed_intent, tenant_id)

                # 将 intent 层的 SemanticContext 转换为 generator 层
                enriched = self._convert_intent_context(intent_ctx, context)
                logger.debug(
                    "Schema Linking 完成",
                    selected_tables=len(enriched.tables),
                )
                return enriched
            except Exception as e:
                logger.warning("Schema Linking 调用失败，使用传入上下文", error=str(e))

        return context

    @staticmethod
    def _convert_intent_context(
        intent_ctx: Any,
        base_ctx: SemanticContext,
    ) -> SemanticContext:
        """将 intent 层的 SemanticContext 转换为 generator 层的 SemanticContext。

        从 intent 层的 SemanticContext（Pydantic model）提取信息，
        补充到 generator 层的 SemanticContext（dataclass）。

        Args:
            intent_ctx: intent 层的 SemanticContext（来自 intent/types.py）。
            base_ctx: generator 层的基础 SemanticContext。

        Returns:
            丰富后的 generator 层 SemanticContext。
        """
        from datapilot_sqlgen.generator.models import (
            DimensionInfo,
            MetricInfo,
            TableInfo,
            TableRelationship,
        )

        # 如果 intent_ctx 是空的，直接返回 base_ctx
        if not intent_ctx.selected_tables and not intent_ctx.selected_metrics:
            return base_ctx

        # 从 intent 层提取表信息
        tables = list(base_ctx.tables)
        for table_name in intent_ctx.selected_tables:
            if not any(t.table_name == table_name for t in tables):
                tables.append(TableInfo(table_name=table_name))

        # 从 intent 层提取指标
        metrics = list(base_ctx.metrics)
        for metric in intent_ctx.selected_metrics:
            if not any(m.name == metric.name for m in metrics):
                metrics.append(
                    MetricInfo(
                        name=metric.name,
                        calculation=metric.calculation,
                        unit=metric.unit or "",
                    )
                )

        # 从 intent 层提取维度
        dimensions = list(base_ctx.dimensions)
        for dim in intent_ctx.selected_dimensions:
            if not any(d.name == dim.name for d in dimensions):
                dimensions.append(
                    DimensionInfo(
                        name=dim.name,
                        column_name=dim.column_name,
                        table_name=dim.table_name or "",
                        synonyms=dim.synonyms,
                    )
                )

        # 从 intent 层提取 JOIN 路径
        relationships = list(base_ctx.relationships)
        for join_step in intent_ctx.join_path:
            if not any(
                r.left_table == join_step.left_table and r.right_table == join_step.right_table
                for r in relationships
            ):
                relationships.append(
                    TableRelationship(
                        left_table=join_step.left_table,
                        right_table=join_step.right_table,
                        join_condition=join_step.join_condition,
                        join_type=join_step.join_type,
                    )
                )

        return SemanticContext(
            tables=tables,
            relationships=relationships,
            metrics=metrics,
            dimensions=dimensions,
            dialect=base_ctx.dialect,
        )

    async def _step_build_prompt(
        self,
        question: str,
        context: SemanticContext,
        tenant_id: str,
    ) -> tuple[str, list[FewShotExample]]:
        """步骤 5：Prompt 组装。

        匹配 Few-shot 并组装最终 Prompt。

        Args:
            question: 用户问题。
            context: 语义上下文。
            tenant_id: 租户 ID。

        Returns:
            (prompt, used_few_shots)。
        """
        # 匹配 Few-shot
        few_shots: list[FewShotExample] = []
        if self._fewshot_matcher is not None:
            try:
                few_shots = await self._fewshot_matcher.match(
                    question=question,
                    tenant_id=tenant_id,
                )
            except Exception as e:
                logger.warning("Few-shot 匹配失败", error=str(e))

        # 组装 Prompt
        prompt, used_few_shots = self._prompt_builder.build_nl2sql_prompt(
            semantic_context=context,
            few_shots=few_shots,
            question=question,
            dialect=context.dialect,
        )

        logger.debug(
            "Prompt 组装完成",
            few_shot_count=len(used_few_shots),
            prompt_length=len(prompt),
        )

        return prompt, used_few_shots

    async def _step_llm_generate(
        self,
        prompt: str,
        dialect: str,
        tenant_id: str,
    ) -> tuple[str, str, float]:
        """步骤 6：LLM 生成 SQL。

        使用 LLM 生成 SQL（JSON mode，要求结构化输出）。

        Args:
            prompt: 组装好的 Prompt。
            dialect: 目标 SQL 方言。
            tenant_id: 租户 ID。

        Returns:
            (llm_output, explanation, confidence)。
        """
        if self._llm_router is not None:
            try:
                # 通过 LLM 路由器调用（JSON mode）
                from datapilot_llm.router import Scene

                result = await self._llm_router.generate(
                    scene=Scene.NL2SQL,
                    prompt=prompt,
                    json_mode=True,
                )
                output = result.content
                explanation = ""
                confidence = 0.8
                return output, explanation, confidence
            except Exception as e:
                logger.warning("LLM 调用失败", error=str(e))

        # 没有配置 LLM 路由器时返回占位内容
        logger.warning("LLM 路由器未配置，返回占位 SQL")
        placeholder_sql = self._generate_placeholder_sql(dialect)
        return placeholder_sql, "占位 SQL（LLM 未配置）", 0.0

    @staticmethod
    def _generate_placeholder_sql(dialect: str) -> str:
        """生成占位 SQL（用于 LLM 未配置时的测试）。

        Args:
            dialect: SQL 方言。

        Returns:
            占位 JSON 输出。
        """
        import json

        sql = "SELECT 1 LIMIT 1"
        return json.dumps(
            {
                "sql": sql,
                "explanation": "占位查询（LLM 未配置）",
                "confidence": 0.0,
            },
            ensure_ascii=False,
        )
