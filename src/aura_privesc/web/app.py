"""FastAPI app factory — serves API + React SPA."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .db import close_db, get_engine

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    await get_engine()
    yield
    # Shutdown: close database
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="aura-privesc",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — only allow localhost origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8888",
            "http://127.0.0.1:8888",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router)

    # Serve static files if they exist (production build)
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        # Mount assets directory for JS/CSS bundles
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def spa_catch_all(request: Request, full_path: str):
            """SPA catch-all: serve index.html for all non-API routes."""
            # Try to serve static file first
            static_file = STATIC_DIR / full_path
            if full_path and static_file.exists() and static_file.is_file():
                return FileResponse(str(static_file))
            # Otherwise serve index.html for SPA routing
            return FileResponse(str(STATIC_DIR / "index.html"))
    else:
        @app.get("/")
        async def dev_placeholder():
            return HTMLResponse(
                "<html><body style='background:#1a1a2e;color:#e0e0e0;font-family:system-ui;padding:2rem'>"
                "<h1 style='color:#00bcd4'>aura-privesc</h1>"
                "<p>Web UI not built yet. Run <code>cd frontend && npm run build</code> to build the React app.</p>"
                "<p>API is available at <a href='/api/presets' style='color:#00bcd4'>/api/presets</a></p>"
                "</body></html>"
            )

    return app
