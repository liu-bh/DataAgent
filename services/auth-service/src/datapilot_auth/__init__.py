"""DataPilot Auth Service."""
__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="DataPilot Auth Service", version=__version__)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}


if __name__ == "__main__":
    port = int(os.getenv("AUTH_PORT", "8004"))
    uvicorn.run(app, host="0.0.0.0", port=port)
