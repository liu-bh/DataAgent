"""工具发现和执行 API。

提供工具注册中心的 REST 接口，支持工具发现、详情查询和执行。
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class ToolInfo(BaseModel):
    """工具信息。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    category: str = Field(..., description="工具分类")
    parameters: list[dict] = Field(default_factory=list, description="参数列表")
    version: str = Field(default="1.0.0", description="工具版本")


class ToolExecuteRequest(BaseModel):
    """工具执行请求。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, description="工具名称")
    arguments: dict = Field(default_factory=dict, description="执行参数")


class ToolExecuteResponse(BaseModel):
    """工具执行响应。"""

    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="是否执行成功")
    output: dict | None = Field(default=None, description="执行输出")
    error: str = Field(default="", description="错误信息")
    execution_time_ms: float = Field(default=0.0, description="执行耗时（毫秒）")


# ---------------------------------------------------------------------------
# 内置工具注册表（Phase1 内存实现）
# ---------------------------------------------------------------------------

# 内置工具定义
_builtin_tools: dict[str, ToolInfo] = {}


def _init_builtin_tools() -> None:
    """初始化内置工具。"""
    global _builtin_tools
    if _builtin_tools:
        return

    tools = [
        ToolInfo(
            name="sql_query",
            description="执行 SQL 查询，支持多种数据库方言",
            category="sql",
            parameters=[
                {"name": "sql", "type": "string", "description": "SQL 语句", "required": True},
                {"name": "dialect", "type": "string", "description": "SQL 方言", "required": False},
            ],
            version="1.0.0",
        ),
        ToolInfo(
            name="python_execute",
            description="在沙箱中执行 Python 代码",
            category="python",
            parameters=[
                {"name": "code", "type": "string", "description": "Python 代码", "required": True},
                {
                    "name": "timeout",
                    "type": "integer",
                    "description": "超时时间（秒）",
                    "required": False,
                },
            ],
            version="1.0.0",
        ),
        ToolInfo(
            name="rca_analyze",
            description="执行根因分析，检测指标异常并分析原因",
            category="analysis",
            parameters=[
                {"name": "question", "type": "string", "description": "分析问题", "required": True},
                {
                    "name": "metric_name",
                    "type": "string",
                    "description": "指标名称",
                    "required": True,
                },
            ],
            version="1.0.0",
        ),
        ToolInfo(
            name="semantic_search",
            description="语义模型搜索",
            category="search",
            parameters=[
                {"name": "query", "type": "string", "description": "搜索关键词", "required": True},
            ],
            version="1.0.0",
        ),
        ToolInfo(
            name="datasource_health",
            description="数据源健康检查",
            category="system",
            parameters=[
                {
                    "name": "datasource_id",
                    "type": "string",
                    "description": "数据源 ID",
                    "required": True,
                },
            ],
            version="1.0.0",
        ),
    ]
    _builtin_tools = {t.name: t for t in tools}


_init_builtin_tools()


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    """发现所有已注册的工具。

    Returns:
        已注册的工具信息列表。
    """
    return list(_builtin_tools.values())


@router.get("/{name}", response_model=ToolInfo)
async def get_tool(name: str) -> ToolInfo:
    """获取工具详情。

    Args:
        name: 工具名称。

    Returns:
        工具详细信息。

    Raises:
        HTTPException: 工具不存在时返回 404。
    """
    tool = _builtin_tools.get(name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"工具不存在: {name}")
    return tool


@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest) -> ToolExecuteResponse:
    """执行指定工具。

    Args:
        request: 工具执行请求。

    Returns:
        工具执行结果。

    Raises:
        HTTPException: 工具不存在时返回 404。
    """
    tool = _builtin_tools.get(request.name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"工具不存在: {request.name}")

    start_time = time.time()

    try:
        # Phase1 stub: 返回模拟执行结果
        output: dict = {
            "tool": request.name,
            "arguments": request.arguments,
            "result": f"[Stub] {tool.description} 执行完成",
        }
        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(
            "工具执行完成",
            tool=request.name,
            execution_time_ms=execution_time_ms,
        )

        return ToolExecuteResponse(
            success=True,
            output=output,
            execution_time_ms=execution_time_ms,
        )
    except Exception as exc:
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error("工具执行失败", tool=request.name, error=str(exc), exc_info=True)

        return ToolExecuteResponse(
            success=False,
            error=f"工具执行失败: {exc}",
            execution_time_ms=execution_time_ms,
        )
