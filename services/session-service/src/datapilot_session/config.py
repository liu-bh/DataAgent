"""服务配置。

TODO: 迁移到 datapilot-common
"""

import os


class Settings:
    """Session 服务配置，从环境变量读取。"""

    # 数据库
    database_url: str = os.getenv(
        "SESSION_DATABASE_URL",
        "postgresql+asyncpg://datapilot:datapilot@localhost:5432/datapilot_session",
    )

    # 服务
    debug: bool = os.getenv("DEBUG", "0") == "1"
    session_port: int = int(os.getenv("SESSION_PORT", "8006"))

    # 会话配置
    session_expire_minutes: int = int(os.getenv("SESSION_EXPIRE_MINUTES", "30"))
    max_messages_per_session: int = int(os.getenv("MAX_MESSAGES_PER_SESSION", "50"))


settings = Settings()
