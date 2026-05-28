"""SQL Generator Service 入口。"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.getenv("SQLGEN_PORT", "8005"))
    uvicorn.run(
        "datapilot_sqlgen.app:app",
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
