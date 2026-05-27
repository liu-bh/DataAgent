# Python 后端开发规范

## 1. 基础约定

- **Python 版本**：>= 3.11（利用 match-case、StrEnum、ExceptionGroup 等特性）
- **包管理**：每个微服务使用 `pyproject.toml`，根目录用 workspace 管理共享库
- **虚拟环境**：通过 `uv` 管理，禁止提交 `.venv/`
- **格式化**：Ruff（替代 black + isort + flake8）
- **类型检查**：mypy strict 模式（逐步开启）

## 2. 命名规范

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块/包 | `snake_case` | `semantic_service/`, `query_executor.py` |
| 类 | `PascalCase` | `SemanticModel`, `QueryExecutor` |
| 函数/方法 | `snake_case` | `resolve_schema()`, `build_sql_ast()` |
| 变量 | `snake_case` | `user_id`, `query_result` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT` |
| 私有成员 | 单下划线前缀 | `_cache`, `_validate_input()` |
| Pydantic Model | `PascalCase` + 后缀 | `MetricCreate`, `QueryRequest` |
| SQLAlchemy Model | `PascalCase` | `DataSource`, `SemanticModel` |
| gRPC Service | `PascalCase` | `PlannerRuntimeService` |
| gRPC Method | `PascalCase` | `ExecuteDAG`, `ResolveSchema` |

## 3. 类型注解

**所有函数必须有返回值类型注解，公共 API 必须有参数类型注解。**

```python
# 正确
async def resolve_schema(
    intent: QueryIntent,
    user_ctx: UserContext,
) -> SchemaResolution:
    ...

# 错误：缺少类型注解
async def resolve_schema(intent, user_ctx):
    ...
```

**常用类型：**

```python
from typing import Any
from collections.abc import Sequence, AsyncIterator

# 集合类型用内置类型（Python 3.9+）
def get_metrics(names: list[str]) -> dict[str, Metric]:
    ...

# 异步返回
async def stream_result(query_id: str) -> AsyncIterator[QueryChunk]:
    ...

# 可选值用 X | None（Python 3.10+）
def find_datasource(id: str) -> DataSource | None:
    ...
```

## 4. 异步编程

### 4.1 基本规则

- **I/O 操作必须用 async**：数据库查询、HTTP 请求、Redis 操作、文件读写
- **CPU 密集型任务放线程池**：`await asyncio.to_thread(cpu_bound_func)`
- **禁止在 async 函数中调用同步阻塞 API**

```python
# 正确：async 全链路
async def get_user(user_id: str) -> User:
    return await self.session.get(User, user_id)

# 错误：在 async 中用同步 DB 操作
async def get_user(user_id: str) -> User:
    return self.session.query(User).get(user_id)  # 同步！
```

### 4.2 并发控制

```python
import asyncio

# 并行执行独立任务
results = await asyncio.gather(
    fetch_metrics(dimensions),
    fetch_dimensions(metrics),
    check_permissions(user_id),
)

# 限制并发数
sem = asyncio.Semaphore(10)

async def bounded_query(sql: str) -> Result:
    async with sem:
        return await execute(sql)
```

### 4.3 超时设置

```python
import asyncio

# 必须为外部调用设置超时
async def call_llm(prompt: str) -> str:
    return await asyncio.wait_for(
        llm_provider.generate(prompt),
        timeout=30.0,
    )
```

## 5. FastAPI 约定

### 5.1 路由组织

```
services/agent-gateway/src/datapilot_agent/
├── api/
│   ├── __init__.py
│   ├── router.py          # 汇总所有子路由
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── chat.py        # /api/v1/chat/*
│   │   ├── sessions.py    # /api/v1/sessions/*
│   │   └── health.py      # /api/v1/health
│   └── deps.py            # 公共依赖注入
├── models/                # Pydantic 请求/响应模型
├── services/              # 业务逻辑层
└── main.py
```

### 5.2 依赖注入

```python
# deps.py
from fastapi import Depends, Request

async def get_db_session(request: Request) -> AsyncSession:
    return request.state.db_session

async def get_current_user(
    request: Request,
) -> User:
    token = request.headers["Authorization"]
    return await verify_jwt(token)

# 在路由中使用
@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    ...
```

### 5.3 响应模型

```python
from pydantic import BaseModel, Field

class ChatResponse(BaseModel):
    message_id: str
    content: str
    sql: str | None = None
    sql_explanation: str | None = None  # SQL 自然语言解释
    chart_spec: dict | None = None
    freshness_note: str | None = None  # 数据新鲜度提示，如"数据截至 2026-05-26"
    data_cutoff: str | None = None       # 数据截止时间 ISO 8601
    total_rows: int | None = None        # 总行数（大结果集分页时使用）
    has_more: bool | None = None         # 是否还有更多数据
    cursor: str | None = None            # 游标分页 token

    model_config = ConfigDict(from_attributes=True)
```

## 6. Pydantic v2 约定

```python
from pydantic import BaseModel, ConfigDict, Field

class MetricCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="指标名称")
    calculation: str = Field(..., description="计算表达式")
    unit: str | None = Field(default=None, max_length=20)
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        from_attributes=True,    # 替代旧版 orm_mode
        str_strip_whitespace=True,
        validate_default=True,
    )
```

**规则：**
- 请求/响应模型分离（`XxxRequest` / `XxxResponse`）
- 枚举用 `StrEnum`，不继承 `str` + `Enum`
- 配置统一用 `model_config = ConfigDict(...)`
- 验证逻辑用 `@field_validator`，不用 `@root_validator`（除非必要）

## 7. SQLAlchemy 2.0 约定

### 7.1 模型定义

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, func
from pgvector.sqlalchemy import Vector
import uuid

class Base(DeclarativeBase):
    pass

class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    calculation: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    dimensions: Mapped[list["Dimension"]] = relationship(
        secondary="metric_dimensions", back_populates="metrics"
    )
```

### 7.2 查询规则

```python
# 使用 2.0 select 语法
stmt = select(Metric).where(Metric.name.ilike("%营收%"))

# 关联加载，避免 N+1
stmt = (
    select(Metric)
    .options(selectinload(Metric.dimensions))
    .where(Metric.id == metric_id)
)
```

### 7.3 数据库迁移

```bash
# 生成迁移
alembic revision --autogenerate -m "add embedding column to metrics"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

**规则：**
- 每个 microservice 独立的 Alembic 配置
- 迁移文件只做加法（不删除列/表，标记 deprecated）
- 生产迁移必须先在 staging 验证

## 8. 错误处理

### 8.1 自定义异常体系

```python
# datapilot-common/exceptions.py
class DataPilotError(Exception):
    """所有业务异常基类"""
    def __init__(self, code: str, message: str, status: int = 500):
        self.code = code
        self.message = message
        self.status = status

class NotFoundError(DataPilotError):
    def __init__(self, resource: str, id: str):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource} {id} 不存在",
            status=404,
        )

class PermissionDeniedError(DataPilotError):
    def __init__(self, message: str = "权限不足"):
        super().__init__(code="PERMISSION_DENIED", message=message, status=403)

class SQLRiskError(DataPilotError):
    def __init__(self, reason: str, risk_level: str):
        super().__init__(
            code="SQL_RISK_DETECTED",
            message=f"SQL 风险: {reason}",
            status=400,
        )

class LLMError(DataPilotError):
    def __init__(self, provider: str, reason: str):
        super().__init__(
            code="LLM_ERROR",
            message=f"模型调用失败 [{provider}]: {reason}",
            status=502,
        )
```

### 8.2 FastAPI 全局异常处理

```python
@app.exception_handler(DataPilotError)
async def datapilot_error_handler(request: Request, exc: DataPilotError):
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {"code": exc.code, "message": exc.message},
            "trace_id": request.state.trace_id,
        },
    )
```

### 8.3 错误处理原则

- **业务异常**用自定义异常，让全局 handler 统一返回
- **第三方异常**（LLM API、数据库）捕获后转为业务异常，不暴露内部细节
- **异步任务异常**记录日志 + 发送到死信队列，不抛给调用方
- **禁止 bare except**：必须指定异常类型

## 9. 项目结构约定

每个微服务遵循统一结构：

```
services/{service-name}/
├── src/datapilot_{service}/
│   ├── __init__.py
│   ├── main.py              # FastAPI app 入口
│   ├── api/                 # 路由层
│   │   ├── router.py
│   │   ├── deps.py          # 依赖注入
│   │   └── v1/
│   ├── models/              # Pydantic 模型
│   ├── schemas/             # SQLAlchemy 模型
│   ├── services/            # 业务逻辑
│   ├── repositories/        # 数据访问层
│   └── core/                # 配置、安全、工具函数
├── tests/
├── alembic/
├── alembic.ini
├── pyproject.toml
└── Dockerfile
```

**分层原则：**
- `api/`：只做参数校验和调用 service，不含业务逻辑
- `services/`：业务逻辑编排，调用 repository 和外部服务
- `repositories/`：纯数据库操作，不含业务判断
- 禁止跨层调用（api 直接调 repository）

## 10. 配置管理

```python
# 使用 pydantic-settings
from pydantic_settings import BaseSettings

class ServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATASEMANTIC_")

    database_url: str
    redis_url: str
    llm_default_model: str = "deepseek-v3"
    llm_timeout: float = 30.0
    max_retry: int = 3
    tenant_id: str = "default"  # Phase1 单租户

config = ServiceConfig()
```

**规则：**
- 所有配置通过环境变量注入，不硬编码
- 敏感信息（密码、API Key）通过 K8s Secret / Vault 管理
- 本地开发用 `.env` 文件（已在 `.gitignore` 中）

## 11. 多租户规范

```python
# 所有 SQLAlchemy 模型继承 TenantBase
class TenantBase:
    """多租户基类，所有业务模型必须继承"""
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)

class Metric(TenantBase, Base):
    __tablename__ = "metrics"
    # ...
```

**规则：**
- Phase1：`tenant_id` 字段预留，值 hardcode 为默认租户
- Phase2：JWT Token 中提取 `tenant_id`，所有查询自动注入过滤条件
- 禁止跨租户数据访问（API 层 + ORM 层双重校验）

## 12. 熔断降级规范

```python
import circuitbreaker

@circuitbreaker.protect(failure_threshold=5, recovery_timeout=60, fallback_function=fallback_query)
async def call_llm(prompt: str) -> str:
    return await llm_provider.generate(prompt)

async def fallback_query(prompt: str) -> str:
    """降级：LLM 不可用时返回历史相似查询结果"""
    similar = await query_history.search_similar(prompt, limit=1)
    if similar:
        return f"由于服务繁忙，为您找到历史相似查询结果：{similar.sql}"
    return "当前服务繁忙，请稍后重试。"
```

**规则：**
- gRPC 调用必须配置熔断器（failure_threshold=5, recovery_timeout=60s）
- LLM 调用必须配置降级函数（返回缓存/历史查询）
- 熔断状态变更必须记录日志 + 上报 Prometheus 指标
