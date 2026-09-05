import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.process import router as process_router
from backend.app.api.routes.evaluation import router as evaluation_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "DepthWizard SIH 2026: Single-view optical remote-sensing image to "
        "relative height estimation and metric elevation calibration API. "
        "Strictly powered by real AI models with zero placeholder/fake outputs."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local development and frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(health_router, prefix=settings.API_PREFIX)
app.include_router(process_router, prefix=settings.API_PREFIX)
app.include_router(evaluation_router, prefix=settings.API_PREFIX)

# Frontend SPA integration
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static_assets")

@app.on_event("startup")
async def startup_event():
    print(f"[{settings.PROJECT_NAME}] Starting API server on {settings.TARGET_DEVICE}...")
    if settings.MODEL_PATH.exists():
        print(f"[{settings.PROJECT_NAME}] Verified model checkpoint at: {settings.MODEL_PATH}")
    else:
        print(f"[{settings.PROJECT_NAME}] WARNING: Model checkpoint missing at: {settings.MODEL_PATH}")

@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_prefix": settings.API_PREFIX,
        "app_url": "/app" if FRONTEND_DIST.exists() else None
    }

@app.get("/app", include_in_schema=False)
@app.get("/viewer", include_in_schema=False)
async def serve_app():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "Frontend build not found. Run 'npm run build' in frontend/ directory."}

@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon():
    favicon_file = FRONTEND_DIST / "favicon.svg"
    if favicon_file.exists():
        return FileResponse(favicon_file)
    return {"error": "Favicon not found"}
