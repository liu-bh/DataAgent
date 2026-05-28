"""数据源配置管理 API。

提供数据源配置的 CRUD 接口。当前 Sprint 使用内存 dict 存储，
后续版本将接入数据库。
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")

# ---------------------------------------------------------------------------
# 内存存储（Sprint 4 暂时不接入数据库）
# ---------------------------------------------------------------------------

_configs: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------


class DataSourceConfig(BaseModel):
    """数据源配置完整模型。"""

    model_config = ConfigDict(from_attributes=True)

    datasource_id: str
    name: str
    dialect: str
    host: str
    port: int
    database: str
    username: str
    password: str = ""
    pool_size: int | None = None


class DataSourceConfigCreate(BaseModel):
    """创建数据源配置的请求模型。"""

    name: str
    dialect: str
    host: str
    port: int = Field(gt=0, le=65535)
    database: str
    username: str
    password: str
    pool_size: int | None = Field(default=None, gt=0)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _mask_password(config: dict) -> dict:
    """遮蔽密码字段，不返回给前端。

    Args:
        config: 原始配置字典。

    Returns:
        密码被遮蔽的配置字典。
    """
    masked = dict(config)
    if masked.get("password"):
        masked["password"] = "******"
    return masked


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.get("/datasources/config")
async def list_datasource_configs() -> list[dict]:
    """列出所有数据源配置（不返回密码）。"""
    return [_mask_password(c) for c in _configs.values()]


@router.post("/datasources/config")
async def create_datasource_config(config: DataSourceConfigCreate) -> dict:
    """创建数据源配置。

    Args:
        config: 数据源配置数据。

    Returns:
        创建成功的配置（密码遮蔽）。
    """
    datasource_id = str(uuid.uuid4())
    config_dict = config.model_dump()
    config_dict["datasource_id"] = datasource_id

    _configs[datasource_id] = config_dict

    logger.info(
        "数据源配置已创建",
        datasource_id=datasource_id,
        name=config.name,
        dialect=config.dialect,
    )

    return _mask_password(config_dict)


@router.get("/datasources/config/{datasource_id}")
async def get_datasource_config(datasource_id: str) -> dict:
    """获取单个数据源配置。

    Args:
        datasource_id: 数据源唯一标识。

    Returns:
        数据源配置（密码遮蔽）。

    Raises:
        HTTPException: 数据源不存在时返回 404。
    """
    config = _configs.get(datasource_id)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"数据源配置 {datasource_id} 不存在",
        )
    return _mask_password(config)


@router.delete("/datasources/config/{datasource_id}")
async def delete_datasource_config(datasource_id: str) -> dict:
    """删除数据源配置。

    Args:
        datasource_id: 数据源唯一标识。

    Returns:
        删除结果。

    Raises:
        HTTPException: 数据源不存在时返回 404。
    """
    if datasource_id not in _configs:
        raise HTTPException(
            status_code=404,
            detail=f"数据源配置 {datasource_id} 不存在",
        )

    del _configs[datasource_id]

    logger.info("数据源配置已删除", datasource_id=datasource_id)

    return {"datasource_id": datasource_id, "deleted": True}
