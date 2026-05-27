-- DataPilot 数据库初始化脚本
-- 由 docker-compose.dev.yml 在 PG 首次启动时自动执行

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 确保 schema 存在
CREATE SCHEMA IF NOT EXISTS public;

-- 授权提示
-- 注意：PostgreSQL 16 中 pgvector 扩展需要超级用户权限创建
-- 如果创建失败，请手动执行：CREATE EXTENSION vector;
