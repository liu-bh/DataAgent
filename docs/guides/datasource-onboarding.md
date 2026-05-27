# 数据源接入指南

> 本文档说明如何将新的数据源接入 DataPilot 系统，完成从注册到可用查询的全流程。

## 1. 支持的数据源类型

| 类型 | 说明 | 连接池 | 向量化方言 |
|------|------|--------|-----------|
| MySQL | MySQL 5.7+ / 8.0+ | aiomysql | MySQL |
| PostgreSQL | PostgreSQL 13+ | asyncpg | PostgreSQL |
| Doris | Apache Doris 1.x / 2.x | 黑箱连接 | MySQL（兼容） |
| StarRocks | StarRocks 2.x / 3.x | 黑箱连接 | MySQL（兼容） |
| ClickHouse | ClickHouse 22.x+ | asynch | ClickHouse |
| API | RESTful API 数据源 | httpx | - |

## 2. 接入流程

```
确认需求 → 创建只读账号 → 配置网络 → 注册数据源 → 测试连接 → 同步元数据 → 验证表结构 → 配置语义模型 → 完成
```

### 2.1 前置准备

#### 数据库只读账号

```sql
-- MySQL
CREATE USER 'datapilot_readonly'@'%' IDENTIFIED BY 'StrongPassword!';
GRANT SELECT ON ecommerce.* TO 'datapilot_readonly'@'%';
FLUSH PRIVILEGES;

-- PostgreSQL
CREATE ROLE datapilot_readonly WITH LOGIN PASSWORD 'StrongPassword!';
GRANT CONNECT ON DATABASE ecommerce TO datapilot_readonly;
GRANT USAGE ON SCHEMA public TO datapilot_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO datapilot_readonly;

-- ClickHouse
CREATE USER datapilot_readonly IDENTIFIED BY 'StrongPassword!';
GRANT SELECT ON ecommerce.* TO datapilot_readonly;
```

> **安全要求**：只授予 SELECT 权限，禁止 DDL/DML 操作。

#### 网络连通

```bash
# 从 DataPilot 服务所在网络测试连通性
telnet <datasource_host> <port>

# 测试连接
mysql -h <host> -P 3306 -u datapilot_readonly -p -e "SELECT 1"
```

### 2.2 注册数据源

#### API 方式

```bash
POST /api/v1/data-sources
{
  "name": "电商业务库",
  "type": "mysql",
  "host": "10.0.1.100",
  "port": 3306,
  "database": "ecommerce",
  "username": "datapilot_readonly",
  "password": "加密后的密码",
  "pool_size": 10,
  "freshness_level": "daily",
  "freshness_cron": "0 6 * * *"
}
```

**参数说明**：

| 参数 | 说明 | 注意事项 |
|------|------|---------|
| `type` | 数据源类型 | 与实际数据库匹配 |
| `pool_size` | 连接池大小 | 根据并发量调整，参考 `environment-variables.md` |
| `freshness_level` | 数据新鲜度级别 | `realtime`/`hourly`/`daily`/`custom` |
| `freshness_cron` | 同步频率 | 仅 `custom` 时需要 |
| `password` | 加密存储 | 后端使用 Fernet 加密，不存明文 |

#### 管理界面

1. 进入 **数据管理 → 数据源**
2. 点击 **添加数据源**
3. 填写连接信息 → 点击 **测试连接**
4. 测试通过 → 点击 **保存**

### 2.3 测试连接

```bash
GET /api/v1/data-sources/{id}/health
```

响应示例：

```json
{
  "status": "healthy",
  "latency_ms": 15,
  "pool_usage": 0.1,
  "last_heartbeat": "2026-05-27T14:30:00+08:00",
  "details": {
    "database_version": "8.0.35",
    "table_count": 42,
    "charset": "utf8mb4"
  }
}
```

### 2.4 触发元数据同步

```bash
POST /api/v1/data-sources/{id}/sync
```

同步过程：

1. 读取数据库 `information_schema`
2. 提取所有表的列定义、类型、主键
3. 计算行数估算值（`COUNT(*)` 或估算）
4. 生成表级 Embedding 向量
5. 更新 `source_tables` 表

同步完成后查看已注册的表：

```bash
GET /api/v1/data-sources/{id}/tables
```

响应示例：

```json
{
  "data": [
    {
      "id": "table-uuid-1",
      "schema_name": "ecommerce",
      "table_name": "orders",
      "description": "订单表",
      "row_count": 1500000,
      "columns": [
        {"name": "id", "type": "BIGINT", "is_primary_key": true},
        {"name": "user_id", "type": "BIGINT"},
        {"name": "amount", "type": "DECIMAL(12,2)"},
        {"name": "status", "type": "VARCHAR(20)"},
        {"name": "created_at", "type": "DATETIME"}
      ],
      "last_synced_at": "2026-05-27T14:30:00+08:00"
    }
  ],
  "total": 42
}
```

### 2.5 补充表描述

表描述是 Schema Linking 的核心信息，直接影响语义匹配准确率：

```bash
# 通过管理界面编辑，或通过 API 更新
PATCH /api/v1/semantic-models/{model_id}
```

对每个表补充：
- **表描述**：一句话说明表的业务含义
- **列描述**：关键列的业务含义（如 `amount` → "订单支付金额（元）"）
- **排除不必要表**：日志表、临时表等不应纳入语义模型

## 3. 数据新鲜度管理

### 3.1 新鲜度级别

| 级别 | 说明 | 适用场景 | 用户提示 |
|------|------|---------|---------|
| `realtime` | 实时 | 核心业务指标 | "数据为实时数据" |
| `hourly` | 每小时 | 运营数据 | "数据截至 HH:00" |
| `daily` | 每天 | T+1 报表 | "数据截至昨日 23:59" |
| `custom` | 自定义 | 周报/月报 | "数据截至 YYYY-MM-DD" |

### 3.2 新鲜度展示

查询结果中自动携带 `freshness_note` 和 `data_cutoff`：

```json
{
  "freshness_note": "数据截至 2026-05-26 23:59",
  "data_cutoff": "2026-05-26T23:59:00+08:00"
}
```

## 4. 连接池管理

### 4.1 连接池配置

每个数据源独立的连接池，在 `data_sources.pool_size` 中配置：

| 数据源类型 | 推荐默认 | 高并发场景 |
|-----------|---------|-----------|
| MySQL | 10 | 20 |
| PostgreSQL | 10 | 20 |
| Doris/StarRocks | 20 | 50 |
| ClickHouse | 15 | 30 |

### 4.2 连接池监控

```bash
GET /api/v1/data-sources/{id}/health
```

关注指标：
- `pool_usage`：连接池使用率，超过 80% 需要扩容
- `avg_latency_ms`：平均查询延迟
- `status`：`healthy` / `degraded` / `down`

## 5. 多数据源场景

一个语义模型可关联多个数据源：

```json
{
  "name": "全渠道分析",
  "data_source_ids": [
    "ecommerce-mysql-uuid",
    "ad-clickhouse-uuid"
  ]
}
```

**跨源查询规则**：

| 场景 | 处理方式 |
|------|---------|
| 单源查询 | 直接路由到对应数据源 |
| 跨源查询 | 分别查询后在应用层合并（Phase1） |
| 跨源 JOIN | 暂不支持，提示用户拆分查询 |

## 6. API 数据源（Phase2）

RESTful API 数据源通过配置 Schema 映射接入：

```json
{
  "name": "天气数据 API",
  "type": "api",
  "base_url": "https://api.weather.com/v1",
  "auth_type": "bearer",
  "auth_token": "******",
  "endpoints": [
    {
      "path": "/daily",
      "method": "GET",
      "response_mapping": {
        "table_name": "weather_daily",
        "columns": [
          {"path": "date", "type": "DATE"},
          {"path": "temperature", "type": "FLOAT"},
          {"path": "city", "type": "VARCHAR(100)"}
        ]
      }
    }
  ]
}
```

## 7. 故障排查

| 问题 | 检查项 | 解决方案 |
|------|--------|---------|
| 连接超时 | 网络连通性、防火墙规则 | 检查安全组/网络 ACL |
| 认证失败 | 用户名密码、权限 | 重新创建只读账号 |
| 同步失败 | information_schema 权限 | 授予 SELECT 权限 |
| 连接池耗尽 | pool_size、慢查询 | 增大池或优化查询 |
| 中文乱码 | charset 设置 | 确保 UTF-8 编码 |
| 查询超时 | 数据量、索引 | 优化 SQL 或添加索引 |

```bash
# 检查数据源健康状态
curl http://localhost:8000/api/v1/data-sources/{id}/health

# 重新同步元数据
curl -X POST http://localhost:8000/api/v1/data-sources/{id}/sync
```
