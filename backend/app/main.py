from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import Base, engine
from app.mcp_app import MCPMiddleware
from app.mcp_app import mcp as mcp_server
from app.routers import admin, auth, dashboard, tasks, weekly_reports

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # streamable-http MCP の session manager を起動（mount したサブアプリの
    # lifespan は親が起動しないため、ここで明示的に run する）。
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(title="28teamworks API", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /mcp 配下を Starlette ルーティング前段で横取りし、JWT 認証して MCP アプリへ委譲する。
app.add_middleware(MCPMiddleware)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(weekly_reports.router, prefix="/api/weekly-reports", tags=["weekly-reports"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# React SPA の静的ファイル配信（本番: backend/static/ に Vite ビルド成果物を配置）
if STATIC_DIR.is_dir():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
