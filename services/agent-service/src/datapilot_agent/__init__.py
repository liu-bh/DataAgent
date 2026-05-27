"""DataPilot Agent Service."""
__version__ = "0.1.0"

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="DataPilot Agent Service", version=__version__)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent"}


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
