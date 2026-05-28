"""NL2SQL API 路由。

提供聊天消息处理、SSE 流式返回和 SQL 执行 API。
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ...generator.models import NL2SQLResult

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sqlgen"])


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class ChatMessageRequest(BaseModel):
    """聊天消息请求体。

    Attributes:
        session_id: 会话 ID。
        content: 用户消息内容（自然语言问题）。
    """

    session_id: str = Field(..., min_length=1, description="会话 ID")
    content: str = Field(..., min_length=1, max_length=2000, description="用户问题")

    model_config = ConfigDict(from_attributes=True)


class ChatMessageResponse(BaseModel):
    """聊天消息响应体。

    Attributes:
        session_id: 会话 ID。
        content: 回复内容（闲聊/超出范围时的文本）。
        sql: 生成的 SQL 语句。
        sql_dialect: SQL 方言。
        sql_explanation: SQL 自然语言解释。
        confidence: 置信度 0~1。
        data: 查询结果数据（Phase1 为空，Sprint 4 完善）。
        trace_id: 链路追踪 ID。
        intent: 意图类型。
        warnings: 警告信息列表。
    """

    session_id: str
    content: str = ""
    sql: str = ""
    sql_dialect: str = ""
    sql_explanation: str = ""
    confidence: float = 0.0
    data: list[dict[str, Any]] | None = None
    trace_id: str = ""
    intent: str = "sql_query"
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class StreamChatRequest(BaseModel):
    """流式聊天请求体（SSE stub）。"""

    session_id: str = Field(..., min_length=1, description="会话 ID")
    content: str = Field(..., min_length=1, max_length=2000, description="用户问题")

    model_config = ConfigDict(from_attributes=True)


class ExecuteSQLRequest(BaseModel):
    """SQL 执行请求体（Phase1 stub）。

    Attributes:
        session_id: 会话 ID。
        original_sql: 原始生成的 SQL。
        edited_sql: 用户编辑后的 SQL。
        datasource_id: 数据源 ID。
    """

    session_id: str = Field(..., min_length=1, description="会话 ID")
    original_sql: str = Field(..., description="原始 SQL")
    edited_sql: str = Field(..., description="编辑后的 SQL")
    datasource_id: str = Field(..., description="数据源 ID")

    model_config = ConfigDict(from_attributes=True)


class ExecuteSQLResponse(BaseModel):
    """SQL 执行响应体（Phase1 stub）。"""

    success: bool
    message: str
    data: list[dict[str, Any]] | None = None
    row_count: int = 0
    trace_id: str = ""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 依赖注入 — Pipeline 获取
# ---------------------------------------------------------------------------

# 全局 pipeline 实例（在 app 启动时设置）
_pipeline: Any = None


def get_pipeline() -> Any:
    """获取 NL2SQLPipeline 实例。

    在 FastAPI 的 Depends 中使用。
    Phase1 使用全局单例，后续可改为请求级实例。
    """
    return _pipeline


def set_pipeline(pipeline: Any) -> None:
    """设置全局 Pipeline 实例（app 启动时调用）。"""
    global _pipeline
    _pipeline = pipeline


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.post(
    "/chat/message",
    response_model=ChatMessageResponse,
    summary="聊天消息处理",
    description="接收用户自然语言问题，返回生成的 SQL 或文本回复。",
)
async def chat_message(
    request: ChatMessageRequest,
    pipeline: Any = Depends(get_pipeline),
) -> ChatMessageResponse:
    """处理聊天消息，调用 NL2SQL Pipeline 生成 SQL。

    根据意图类型返回不同内容：
    - sql_query：返回生成的 SQL
    - chitchat：返回闲聊文本
    - out_of_scope：返回友好提示
    """
    trace_id = uuid.uuid4().hex[:16]

    logger.info(
        "收到聊天消息",
        session_id=request.session_id,
        content=request.content[:50],
        trace_id=trace_id,
    )

    if pipeline is None:
        logger.error("Pipeline 未初始化", trace_id=trace_id)
        return ChatMessageResponse(
            session_id=request.session_id,
            content="服务暂不可用，请稍后重试。",
            trace_id=trace_id,
        )

    try:
        result: NL2SQLResult = await pipeline.generate(
            question=request.content,
            session_id=request.session_id,
            tenant_id="",  # Phase1 从 JWT 解析
        )

        response = ChatMessageResponse(
            session_id=request.session_id,
            content=result.text_response,
            sql=result.sql,
            sql_dialect=result.sql_dialect,
            sql_explanation=result.explanation,
            confidence=result.confidence,
            trace_id=trace_id,
            intent=result.intent,
            warnings=result.warnings,
        )

        logger.info(
            "聊天消息处理完成",
            trace_id=trace_id,
            intent=result.intent,
            has_sql=bool(result.sql),
            confidence=result.confidence,
        )

        return response

    except Exception as e:
        logger.error(
            "聊天消息处理失败",
            trace_id=trace_id,
            error=str(e),
        )
        return ChatMessageResponse(
            session_id=request.session_id,
            content="处理您的问题时出现了错误，请稍后重试。",
            trace_id=trace_id,
        )


@router.post(
    "/chat/stream",
    summary="流式聊天（SSE stub）",
    description="Phase1 stub，Sprint 5 完善。返回 SSE 事件流：thinking → sql → message → done。",
)
async def chat_stream(
    request: StreamChatRequest,
) -> dict[str, str]:
    """流式聊天消息处理（Phase1 stub）。

    Sprint 5 将实现完整的 SSE 流式返回。
    当前仅返回提示信息。
    """
    trace_id = uuid.uuid4().hex[:16]
    logger.info(
        "收到流式聊天请求（stub）",
        session_id=request.session_id,
        trace_id=trace_id,
    )
    return {
        "message": "SSE 流式接口尚未实现，将在 Sprint 5 完善。",
        "trace_id": trace_id,
    }


@router.post(
    "/chat/execute-sql",
    response_model=ExecuteSQLResponse,
    summary="执行 SQL（Phase1 stub）",
    description="Phase1 stub，Sprint 4 完善。用于执行用户编辑后的 SQL。",
)
async def execute_sql(
    request: ExecuteSQLRequest,
) -> ExecuteSQLResponse:
    """执行 SQL（Phase1 stub）。

    Sprint 4 将对接 Query Executor Service 完整实现。
    """
    trace_id = uuid.uuid4().hex[:16]
    logger.info(
        "收到 SQL 执行请求（stub）",
        session_id=request.session_id,
        datasource_id=request.datasource_id,
        trace_id=trace_id,
    )

    return ExecuteSQLResponse(
        success=False,
        message="SQL 执行接口尚未实现，将在 Sprint 4 完善。",
        trace_id=trace_id,
    )
