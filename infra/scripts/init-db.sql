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

-- ============================================
-- 初始 admin 用户
-- email: admin@datapilot.com
-- password: admin123
-- bcrypt hash: $2b$12$LJ3m4ys3IHKP96J4S/R5LOzPGokxMJGfMxXHqZ/OKDcXZwWXFnH3K
-- ============================================
DO $$
BEGIN
    -- 仅在 users 表存在时插入（表由 SQLAlchemy/Alembic 迁移创建）
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'users'
    ) THEN
        INSERT INTO users (id, tenant_id, email, password_hash, display_name, role, is_active)
        VALUES (
            '00000000-0000-0000-0000-000000000001'::uuid,
            '00000000-0000-0000-0000-000000000000'::uuid,
            'admin@datapilot.com',
            '$2b$12$LJ3m4ys3IHKP96J4S/R5LOzPGokxMJGfMxXHqZ/OKDcXZwWXFnH3K',
            'Admin',
            'admin',
            true
        )
        ON CONFLICT (email) DO NOTHING;
    ELSE
        RAISE NOTICE 'users table does not exist yet, skipping admin user insertion. It will be created after Alembic migrations run.';
    END IF;
END
$$;
