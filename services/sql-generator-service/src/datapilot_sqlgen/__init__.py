"""DataPilot SQL Generator Service."""
__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="DataPilot SQL Generator Service", version=__version__)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sqlgen"}


if __name__ == "__main__":
    port = int(os.getenv("SQLGEN_PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
