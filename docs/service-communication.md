# 微服务通信规范

## 1. 通信方式选择

| 场景 | 协议 | 说明 |
|------|------|------|
| 服务间同步调用 | gRPC | 跨进程服务调用（Phase2 全部使用） |
| 进程内调用 | Python 函数 | Phase1 合并服务内部（如 Agent↔Chat、Semantic↔Metadata） |
| 异步事件通知 | RocketMQ | query.submitted, task.completed 等 |
| 前端消息推送 | SSE | Chat 消息流式输出（单向） |
| 前端实时推送 | WebSocket | DAG 执行进度（双向，Phase2） |
| 外部 API 调用 | HTTPS | LLM API, Embedding API |

### Phase1 vs Phase2 通信区别

```
Phase1（合并部署）：
  Agent Service [内部: Agent ↔ Chat, Python 函数调用]
       ↓ gRPC
  SQL Generator Service
       ↓ gRPC
  Semantic Service [内部: Semantic ↔ Metadata, Python 函数调用]
       ↓ gRPC
  Query Executor Service

Phase2（完整拆分）：
  Agent Gateway ──gRPC──> Chat Service
       └──gRPC──> Planner ──gRPC──> Semantic ──gRPC──> SQL Generator
                                                       └──gRPC──> Query Executor
```

## 2. gRPC 通信规范

### 2.1 Proto 文件约定

```protobuf
// 文件头
syntax = "proto3";
package datapilot.planner.v1;

// 引入公共类型
import "common/common.proto";

// Service 定义
service PlannerRuntimeService {
  // RPC 方法命名：动词 + 资源
  rpc ExecuteDAG(ExecuteDAGRequest) returns (stream DAGExecutionEvent);
  rpc ResolveSchema(ResolveSchemaRequest) returns (ResolveSchemaResponse);
}
```

### 2.2 消息定义规范

```protobuf
// Request 消息
message ExecuteDAGRequest {
  string query_id = 1;               // 必填
  string user_id = 2;
  repeated TaskNode tasks = 3;
  DagConfig config = 4;              // 可选
}

// Response 消息
message ResolveSchemaResponse {
  string query_id = 1;
  SchemaResolution result = 2;       // 业务数据
  Meta meta = 3;                     // 元信息（耗时、模型版本等）
}

// 公共元信息
message Meta {
  int64 duration_ms = 1;
  string trace_id = 2;
  string request_id = 3;
}
```

**规则：**
- 字段编号从 1 开始，连续分配，不重用已删除的字段号
- `repeated` 字段默认空列表，不返回 null
- `string` 类型的 UUID 字段用 `string`（proto 没有 UUID 类型）
- 时间字段用 `google.protobuf.Timestamp`
- 所有 Response 包含 `Meta meta` 字段

### 2.3 超时与重试

```python
# gRPC 客户端配置
import grpc

channel = grpc.aio.insecure_channel(
    target="planner-runtime:50051",
    options=[
        ("grpc.max_receive_message_length", 64 * 1024 * 1024),  # 64MB
        ("grpc.keepalive_time_ms", 30000),
        ("grpc.keepalive_timeout_ms", 10000),
    ],
)

# 调用时设置超时
response = await stub.ResolveSchema(
    request,
    timeout=10.0,  # 单次调用超时
)
```

| 场景 | 超时 | 重试策略 |
|------|------|---------|
| 普通查询 | 10s | 不重试 |
| SQL 生成 | 30s | 最多 1 次 |
| DAG 执行 | 120s | 不重试（由 DAG 引擎管理重试） |
| 元数据同步 | 60s | 指数退避，最多 3 次 |

### 2.4 错误处理

```python
from grpc import StatusCode

async def call_semantic_service(request):
    try:
        return await semantic_stub.ResolveSchema(request, timeout=10.0)
    except grpc.aio.AioRpcError as e:
        if e.code() == StatusCode.NOT_FOUND:
            raise NotFoundError("SemanticModel", request.model_id)
        elif e.code() == StatusCode.DEADLINE_EXCEEDED:
            raise DataPilotError("TIMEOUT", "语义服务超时", status=504)
        elif e.code() == StatusCode.UNAVAILABLE:
            raise DataPilotError("SERVICE_UNAVAILABLE", "语义服务不可用", status=503)
        else:
            raise DataPilotError("UPSTREAM_ERROR", str(e.detail()), status=502)
```

### 2.5 服务发现

- K8s Service DNS：`{service-name}.{namespace}.svc.cluster.local`
- 开发环境：docker-compose 服务名
- 不使用独立服务发现组件（Consul/Eureka），依赖 K8s DNS

## 3. RocketMQ 消息规范

### 3.1 Topic 命名

```
{domain}.{event_type}

示例：
query.submitted        # 查询已提交
query.completed        # 查询已完成
query.failed           # 查询失败
task.scheduled         # 任务已调度
task.completed         # 任务已完成
sandbox.result_ready   # 沙箱结果就绪
embedding.generated    # 向量生成完成
audit.event            # 审计事件
```

### 3.2 消息格式

```json
{
  "event_id": "uuid",
  "event_type": "query.completed",
  "timestamp": "2026-05-27T14:30:00+08:00",
  "trace_id": "abc123",
  "source": "sql-generator-service",
  "data": {
    "query_id": "uuid",
    "sql": "SELECT SUM(amount) FROM orders",
    "row_count": 15000,
    "duration_ms": 320
  }
}
```

**规则：**
- 所有消息必须包含 `event_id`, `event_type`, `timestamp`, `trace_id`, `source`
- `data` 字段包含业务数据
- 消息体不超过 256KB（RocketMQ 默认限制）
- 生产者必须设置 `keys`（用于消息追踪）和 `tags`（用于消费过滤）

### 3.3 消费者规则

```python
from rocketmq.client import PushConsumer

consumer = PushConsumer("datapilot-consumer-group")

@consumer.subscribe("query.completed", "sql-gen-*")
def on_query_completed(msg):
    """
    消费逻辑：
    1. 幂等检查（event_id 去重）
    2. 业务处理
    3. 失败重试（最多 3 次，间隔递增）
    """
    event = json.loads(msg.body)
    if is_duplicate(event["event_id"]):
        return  # 幂等：已处理过
    process_query_result(event["data"])
```

**消费规则：**
- 消费者组命名：`{service-name}-consumer-group`
- 消费者必须实现**幂等**（通过 event_id 去重）
- 失败消息进入**死信队列**（`%DLQ%{consumer-group}`）
- 消费超时：15 秒
- 顺序消息：同一 query_id 的消息发到同一 queue

### 3.4 消息可靠性

- 生产者：同步发送关键消息，异步发送日志/监控消息
- 事务消息：仅用于跨服务数据一致性场景（如查询状态更新）
- 延迟消息：用于超时检测（如查询 30s 未完成则告警）

## 4. SSE 通信规范

### 4.1 服务端实现

```python
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def stream_chat(req: ChatRequest):
    async def event_generator():
        try:
            # 思考中状态
            yield f"event: status\ndata: {json.dumps({'type': 'thinking'})}\n\n"

            # 流式文本
            async for chunk in agent.stream_chat(req.content):
                yield f"event: message\ndata: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

            # SQL 结果
            if result.sql:
                yield f"event: sql\ndata: {json.dumps({'type': 'sql', 'sql': result.sql})}\n\n"

            # 完成
            yield f"event: done\ndata: {json.dumps({'type': 'done', 'message_id': result.id})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
        },
    )
```

### 4.2 SSE 规则

- 每条消息以 `event: {type}\ndata: {json}\n\n` 格式
- 心跳：每 15 秒发送 `event: heartbeat\ndata: {}\n\n`
- 连接超时：5 分钟无活动自动断开
- APISIX SSE 代理需禁用 response buffer

## 5. WebSocket 通信规范

### 5.1 连接管理

```python
# 连接参数
WS_PATH = "/api/v1/dag/{execution_id}/progress"
WS_PING_INTERVAL = 30   # 秒
WS_PONG_TIMEOUT = 10     # 秒
WS_MAX_CONNECTIONS = 100 # 每用户
```

### 5.2 消息格式

```json
// 服务端推送
{ "event": "node_started", "data": { "node_id": "...", "status": "running" } }
{ "event": "node_completed", "data": { "node_id": "...", "duration_ms": 1200 } }
{ "event": "dag_completed", "data": { "total_duration_ms": 3500 } }

// 客户端发送（仅控制命令）
{ "action": "cancel", "execution_id": "uuid" }
```

**规则：**
- WebSocket 仅用于 DAG 进度推送，Chat 消息用 SSE
- 客户端只发送控制命令（cancel/pause），不发业务数据
- 断线重连后服务端发送当前完整 DAG 状态

## 6. 服务间调用关系图

```
                    ┌─────────────┐
                    │  Chat UI   │
                    │  (SSE)     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Chat Svc  │
                    └──────┬──────┘
                           │ gRPC
              ┌────────────▼────────────┐
              │     Agent Gateway       │
              │  (LLM调用/意图路由)      │
              └──┬─────────┬───────────┘
                 │gRPC     │gRPC
        ┌────────▼──┐  ┌──▼──────────┐
        │ Planner   │  │ Semantic    │
        │ Runtime   │  │ Service     │
        └──┬────────┘  └──┬──────────┘
           │gRPC          │gRPC
    ┌──────▼──────┐  ┌───▼───────────┐
    │ SQL Gen    │  │ Query Exec    │
    │            │  │               │
    └────────────┘  └───────────────┘

    RocketMQ:
    query.submitted → Planner
    task.completed → Agent Gateway
    embedding.generated → Metadata Svc
```
