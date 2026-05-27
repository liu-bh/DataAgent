# gRPC Proto 定义指南

> 本文档定义了 DataPilot 微服务间 gRPC 通信的完整 Proto 定义。
> Proto 文件统一存放于 `libs/datapilot-proto/protos/`，生成的代码进入各服务的 `src/` 目录。

## 1. 目录结构

```
libs/datapilot-proto/
├── protos/
│   ├── common/
│   │   └── common.proto          # 公共消息类型
│   ├── semantic/
│   │   └── semantic.proto        # 语义模型相关
│   ├── sqlgen/
│   │   └── sqlgen.proto          # SQL 生成相关
│   ├── queryexec/
│   │   └── query_executor.proto  # 查询执行相关
│   └── guardrail/
│       └── guardrail.proto       # 安全校验相关
├── buf.gen.yaml                   # buf 代码生成配置
├── buf.yaml                       # buf lint 配置
└── pyproject.toml
```

## 2. 公共类型 `common.proto`

```protobuf
syntax = "proto3";
package datapilot.common;

option go_package = "github.com/datapilot/common";

// 租户上下文，通过 metadata 传递
message TenantContext {
  string tenant_id = 1;
  string user_id = 2;
  string trace_id = 3;
}

// 通用响应包装
message ResponseMeta {
  string trace_id = 1;
  int64 latency_ms = 2;
}

// 数据源类型
enum DatasourceType {
  DATASOURCE_TYPE_UNSPECIFIED = 0;
  MYSQL = 1;
  POSTGRESQL = 2;
  DORIS = 3;
  STARROCKS = 4;
  CLICKHOUSE = 5;
}

// 分页请求
message PaginationRequest {
  int32 page = 1;
  int32 page_size = 2;
}

// 分页响应
message PaginationResponse {
  int32 page = 1;
  int32 page_size = 2;
  int64 total = 3;
  int32 total_pages = 4;
}
```

## 3. 语义模型服务 `semantic.proto`

```protobuf
syntax = "proto3";
package datapilot.semantic;

import "common/common.proto";

// 语义模型服务
service SemanticService {
  // 获取语义上下文（Schema Linking 使用）
  rpc GetSemanticContext(GetSemanticContextRequest) returns (GetSemanticContextResponse);
  // 获取关联的表和列信息
  rpc GetTableSchema(GetTableSchemaRequest) returns (GetTableSchemaResponse);
  // 获取指标详情
  rpc GetMetric(GetMetricRequest) returns (Metric);
  // 搜索语义元素（向量相似度 + 关键词混合搜索）
  rpc SearchSemanticElements(SearchRequest) returns (SearchResponse);
  // 获取表关联关系
  rpc GetTableRelationships(GetTableRelationshipsRequest) returns (TableRelationshipList);
}

message GetSemanticContextRequest {
  string tenant_id = 1;
  string question = 2;           // 用户原始问题
  repeated string keywords = 3;   // 从问题提取的关键词
}

message GetSemanticContextResponse {
  // 匹配到的表
  repeated TableInfo tables = 1;
  // 匹配到的指标
  repeated MetricInfo metrics = 2;
  // 匹配到的维度
  repeated DimensionInfo dimensions = 3;
  // 表间关系
  repeated TableRelation relationships = 4;
  // NL2SQL Few-shot 示例
  repeated Nl2SqlExample examples = 5;
}

message TableInfo {
  string table_id = 1;
  string schema_name = 2;
  string table_name = 3;
  string description = 4;
  repeated ColumnInfo columns = 5;
  float relevance_score = 6;       // 与问题的相关度 0-1
}

message ColumnInfo {
  string column_name = 1;
  string column_type = 2;
  string description = 3;
  bool is_primary_key = 4;
  bool is_nullable = 5;
}

message MetricInfo {
  string metric_id = 1;
  string name = 2;
  string description = 3;
  string calculation = 4;
  string unit = 5;
  repeated string tags = 6;
  float relevance_score = 7;
}

message DimensionInfo {
  string dimension_id = 1;
  string name = 2;
  string column_name = 3;
  string table_name = 4;
  repeated string synonyms = 5;
}

message TableRelation {
  string left_table = 1;
  string right_table = 2;
  string join_type = 3;           // inner/left/right/full
  string join_condition = 4;
}

message Nl2SqlExample {
  string question = 1;
  string sql = 2;
  string dialect = 3;
  float similarity = 4;
}

// 获取表 Schema 请求
message GetTableSchemaRequest {
  string tenant_id = 1;
  string table_id = 2;
}

message GetTableSchemaResponse {
  TableInfo table = 1;
  repeated string related_table_ids = 2;
}

// 获取指标请求
message GetMetricRequest {
  string tenant_id = 1;
  string metric_id = 2;
}

message Metric {
  string id = 1;
  string name = 2;
  string description = 3;
  string calculation = 4;
  string unit = 5;
  int32 version = 6;
  string semantic_model_id = 7;
  repeated DimensionInfo dimensions = 8;
}

// 搜索请求
message SearchRequest {
  string tenant_id = 1;
  string query = 2;
  repeated string filters = 3;     // domain/table_id 等过滤条件
  int32 limit = 4;
}

message SearchResponse {
  repeated MetricInfo metrics = 1;
  repeated DimensionInfo dimensions = 2;
  repeated TableInfo tables = 3;
}

// 获取表关系请求
message GetTableRelationshipsRequest {
  string tenant_id = 1;
  string semantic_model_id = 2;
}

message TableRelationshipList {
  repeated TableRelation relationships = 1;
}
```

## 4. SQL 生成服务 `sqlgen.proto`

```protobuf
syntax = "proto3";
package datapilot.sqlgen;

import "common/common.proto";

// SQL 生成服务
service SqlGeneratorService {
  // 生成 SQL
  rpc GenerateSQL(GenerateSQLRequest) returns (GenerateSQLResponse);
  // 验证 SQL
  rpc ValidateSQL(ValidateSQLRequest) returns (ValidateSQLResponse);
  // SQL 自校验
  rpc SelfCorrect(SelfCorrectRequest) returns (SelfCorrectResponse);
  // 解释 SQL
  rpc ExplainSQL(ExplainSQLRequest) returns (ExplainSQLResponse);
}

message GenerateSQLRequest {
  string tenant_id = 1;
  string question = 2;
  // 语义上下文（由 SemanticService 提供）
  SemanticContext context = 3;
  string dialect = 4;
  // RBAC 注入信息
  string row_filter = 5;
  repeated string hidden_columns = 6;
  int32 max_retries = 7;
}

message SemanticContext {
  repeated string table_ddls = 1;
  repeated string table_descriptions = 2;
  repeated string metric_definitions = 3;
  repeated string dimension_definitions = 4;
  repeated string relationships = 5;
  repeated Nl2SqlExample examples = 6;
}

message Nl2SqlExample {
  string question = 1;
  string sql = 2;
  string dialect = 3;
}

message GenerateSQLResponse {
  string sql = 1;
  string dialect = 2;
  string explanation = 3;           // SQL 自然语言解释
  repeated string warnings = 4;      // 生成过程中的警告
  int32 correction_rounds = 5;      // 自校验轮次
  bool success = 6;
  string error_message = 7;
}

message ValidateSQLRequest {
  string tenant_id = 1;
  string sql = 2;
  string dialect = 3;
  string datasource_id = 4;
}

message ValidateSQLResponse {
  bool is_valid = 1;
  repeated string syntax_errors = 2;
  repeated string warnings = 3;
  CostEstimate cost_estimate = 4;
}

message CostEstimate {
  int64 estimated_rows = 1;
  int64 estimated_cost = 2;         // PostgreSQL EXPLAIN 的 cost 值
  string risk_level = 3;            // low/medium/high
}

message SelfCorrectRequest {
  string tenant_id = 1;
  string question = 2;
  string sql = 3;
  string error_message = 4;         // 执行报错信息
  SemanticContext context = 5;
  string dialect = 6;
  int32 round = 7;                  // 当前已校验轮次
}

message SelfCorrectResponse {
  string sql = 1;
  string correction_log = 2;        // 校验过程记录
  bool resolved = 3;
}

message ExplainSQLRequest {
  string tenant_id = 1;
  string sql = 2;
  string dialect = 3;
}

message ExplainSQLResponse {
  string explanation = 1;           // 自然语言解释
  repeated SqlStep steps = 2;       // SQL 执行步骤分解
}

message SqlStep {
  string operation = 1;             // SCAN/FILTER/JOIN/AGGREGATE/SORT
  string table = 2;
  string description = 3;
}
```

## 5. 查询执行服务 `query_executor.proto`

```protobuf
syntax = "proto3";
package datapilot.queryexec;

import "common/common.proto";

// 查询执行服务
service QueryExecutorService {
  // 执行 SQL
  rpc ExecuteSQL(ExecuteSQLRequest) returns (ExecuteSQLResponse);
  // 获取大结果集的分页数据
  rpc FetchResultPage(FetchResultPageRequest) returns (FetchResultPageResponse);
  // 取消查询
  rpc CancelQuery(CancelQueryRequest) returns (CancelQueryResponse);
  // 导出结果
  rpc ExportResult(ExportResultRequest) returns (ExportResultResponse);
}

message ExecuteSQLRequest {
  string tenant_id = 1;
  string datasource_id = 2;
  string sql = 3;
  int32 default_limit = 4;          // 默认 LIMIT
  string row_filter = 5;            // 行级权限过滤
  repeated string mask_columns = 6;  // 需要脱敏的列
}

message ExecuteSQLResponse {
  bool success = 1;
  repeated ColumnMeta columns = 2;
  repeated RowData rows = 3;
  int64 total_rows = 4;             // 不含 LIMIT 的总行数（估算）
  int32 limit = 5;                  // 实际应用的 LIMIT
  bool has_more = 6;                // 是否有更多数据
  string cursor = 7;                // 游标（大结果集用）
  int64 latency_ms = 8;
  int64 scan_rows = 9;              // 扫描行数
  string error_message = 10;
  // 大结果集信息
  LargeResultInfo large_result = 11;
}

message ColumnMeta {
  string name = 1;
  string type = 2;
  string label = 3;                 // 显示名称
}

message RowData {
  repeated string values = 1;       // 所有值序列化为字符串
}

message LargeResultInfo {
  bool is_large = 1;                // 是否超过阈值
  string storage_path = 2;          // MinIO 存储路径
  int64 total_bytes = 3;
}

message FetchResultPageRequest {
  string tenant_id = 1;
  string cursor = 2;
  int32 limit = 3;
}

message FetchResultPageResponse {
  repeated ColumnMeta columns = 1;
  repeated RowData rows = 2;
  int64 total_rows = 3;
  bool has_more = 4;
  string cursor = 5;
}

message CancelQueryRequest {
  string tenant_id = 1;
  string query_id = 2;
}

message CancelQueryResponse {
  bool cancelled = 1;
}

message ExportResultRequest {
  string tenant_id = 1;
  string query_id = 2;
  string format = 3;                // csv/excel/json
  repeated string selected_columns = 4;
}

message ExportResultResponse {
  string download_url = 1;
  int64 file_size = 2;
  string format = 3;
  int32 row_count = 4;
}
```

## 6. 安全校验服务 `guardrail.proto`

```protobuf
syntax = "proto3";
package datapilot.guardrail;

import "common/common.proto";

// 安全校验服务
service GuardrailService {
  // SQL 风险检测
  rpc CheckSqlRisk(CheckSqlRiskRequest) returns (CheckSqlRiskResponse);
  // 用户配额检查
  rpc CheckUserQuota(CheckUserQuotaRequest) returns (CheckUserQuotaResponse);
  // 数据脱敏
  rpc MaskData(MaskDataRequest) returns (MaskDataResponse);
  // 审计日志记录
  rpc RecordAudit(RecordAuditRequest) returns (RecordAuditResponse);
}

message CheckSqlRiskRequest {
  string tenant_id = 1;
  string sql = 2;
  string dialect = 3;
  string datasource_id = 4;
}

message CheckSqlRiskResponse {
  bool allowed = 1;
  string risk_level = 2;            // none/low/medium/high/critical
  repeated string detected_risks = 3;
  string risk_detail = 4;
}

message CheckUserQuotaRequest {
  string tenant_id = 1;
  string user_id = 2;
  int64 estimated_scan_rows = 3;    // 预估扫描行数
}

message CheckUserQuotaResponse {
  bool allowed = 1;
  string denial_reason = 2;         // QUOTA_EXCEEDED_DAILY / QUOTA_EXCEEDED_HOURLY_SCAN
  int32 remaining_daily_queries = 3;
  int64 remaining_hourly_scan = 4;
}

message MaskDataRequest {
  string tenant_id = 1;
  string datasource_id = 2;
  repeated ColumnMask masks = 3;
  repeated RowData rows = 4;
}

message ColumnMask {
  string column_name = 1;
  string mask_type = 2;             // phone/id_card/bank_card/email/name
}

message MaskDataResponse {
  repeated RowData masked_rows = 1;
}

message RecordAuditRequest {
  string tenant_id = 1;
  string user_id = 2;
  string action = 3;                // query/export/configure
  string sql_text = 4;
  string datasource_id = 5;
  int64 scan_rows = 6;
  int64 duration_ms = 7;
  string risk_level = 8;
  string ip_address = 9;
}

message RecordAuditResponse {
  bool recorded = 1;
}
```

## 7. 代码生成

### 7.1 安装 buf

```bash
# macOS
brew install bufbuild/buf/buf

# Linux / WSL
curl -sSL "https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf
```

### 7.2 生成 Python 代码

```bash
cd libs/datapilot-proto

# 一次性生成所有 proto
buf generate

# 或单独生成某个服务
protoc -I protos \
  --python_betterproto_out=../generated/ \
  protos/semantic/semantic.proto
```

### 7.3 生成的文件位置

```
libs/datapilot-proto/generated/
├── datapilot/
│   ├── common/
│   │   └── common_pb2.py
│   ├── semantic/
│   │   └── semantic_pb2.py
│   ├── sqlgen/
│   │   └── sqlgen_pb2.py
│   ├── queryexec/
│   │   └── query_executor_pb2.py
│   └── guardrail/
│       └── guardrail_pb2.py
```

## 8. Phase1 进程内调用

Phase1 采用合并部署，gRPC 定义仅作为接口契约，实际通过 Python 函数直接调用：

```python
# Phase1: 直接导入调用（不走网络）
from datapilot_semantic.service import SemanticService

semantic_svc = SemanticService(db_session)
context = await semantic_svc.get_semantic_context(
    tenant_id="xxx",
    question="上月营收多少",
    keywords=["营收", "上月"],
)

# Phase2: 切换为 gRPC 客户端调用
# from datapilot.common.grpc_client import get_client
# semantic_svc = get_client("semantic", SemanticServiceStub)
# context = await semantic_svc.GetSemanticContext(request)
```

## 9. Proto 变更流程

1. **修改 `.proto` 文件**
2. **运行 Lint**: `buf lint`
3. **生成代码**: `buf generate`
4. **更新调用方代码**
5. **提交 PR**: Proto 变更和调用方代码在同一个 PR

### 向后兼容规则

- **可以**: 添加新字段（使用 `optional` 或新字段号）
- **可以**: 添加新 RPC 方法
- **不可以**: 删除或重命名字段
- **不可以**: 修改字段类型
- **不可以**: 修改字段编号
