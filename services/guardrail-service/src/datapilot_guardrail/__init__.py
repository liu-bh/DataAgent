"""DataPilot Guardrail Service."""
__version__ = "0.1.0"

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="DataPilot Guardrail Service", version=__version__)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "guardrail"}


if __name__ == "__main__":
    port = int(os.getenv("GUARDRAIL_PORT", "8005"))
    uvicorn.run(app, host="0.0.0.0", port=port)
