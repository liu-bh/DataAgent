"""服务配置。

TODO: 迁移到 datapilot-common
"""

import os


class Settings:
    """Auth 服务配置，从环境变量读取。"""

    # JWT
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY", "dev-secret-key-change-in-production-min-32-chars!"
    )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # 数据库
    database_url: str = os.getenv(
        "AUTH_DATABASE_URL",
        "postgresql+asyncpg://datapilot:datapilot@localhost:5432/datapilot_auth",
    )

    # 服务
    debug: bool = os.getenv("DEBUG", "0") == "1"
    auth_port: int = int(os.getenv("AUTH_PORT", "8004"))


settings = Settings()
