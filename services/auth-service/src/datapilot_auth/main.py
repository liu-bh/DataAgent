"""Auth Service 入口。"""

from __future__ import annotations

import uvicorn

from datapilot_auth.config import settings


def main() -> None:
    uvicorn.run(
        "datapilot_auth.app:app",
        host="0.0.0.0",
        port=settings.auth_port,
    )


if __name__ == "__main__":
    main()
