import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="DeployBox Demo")

@app.get("/")
def index():
    return {
        "service": "deploybox-demo",
        "version": os.getenv("APP_VERSION", "dev"),
    }

@app.get("/health")
def health():
    if os.getenv("FAIL_HEALTH", "0") == "1":
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy"},
        )
    return {"status": "healthy"}
