from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import admin, auth, dashboard, tasks, weekly_reports

STATIC_DIR = Path(__file__).parent.parent / "static"


def _ensure_schema_patches(sync_conn) -> None:
    """create_all で追加されない既存テーブルへの列を冪等に追加する。

    本番/ローカルの SQLite DB は create_all 管理（alembic 未適用）のため、
    create_all は既存テーブルに新しい列を足さない。起動時に列の有無を検査し、
    無ければ ALTER TABLE で追加する（再実行しても安全）。
    """
    inspector = inspect(sync_conn)
    cols = {c["name"] for c in inspector.get_columns("weekly_reports")}
    if "feedback_seen_at" not in cols:
        sync_conn.execute(
            text("ALTER TABLE weekly_reports ADD COLUMN feedback_seen_at TIMESTAMP")
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_schema_patches)
    yield


app = FastAPI(title="28teamworks API", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
