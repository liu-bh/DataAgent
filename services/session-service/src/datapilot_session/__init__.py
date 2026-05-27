"""DataPilot Session Service."""
__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="DataPilot Session Service", version=__version__)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "session"}


if __name__ == "__main__":
    port = int(os.getenv("SESSION_PORT", "8006"))
    uvicorn.run(app, host="0.0.0.0", port=port)
