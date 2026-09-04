from fastapi import FastAPI

app = FastAPI(
    title="SurgePilot API",
    version="0.1.0",
    # Match the frozen source runtime OpenAPI base. The exporter still
    # normalizes browser-facing paths to /v1 and publishes server /api.
    servers=[{"url": "/api"}],
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
)


@app.get("/api/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
