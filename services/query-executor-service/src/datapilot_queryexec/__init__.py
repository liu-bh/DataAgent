"""DataPilot Query Executor Service."""
__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="DataPilot Query Executor Service", version=__version__)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "queryexec"}


if __name__ == "__main__":
    port = int(os.getenv("QUERYEXEC_PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
