from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from neroops.api import router
from neroops.config import get_settings
from neroops.database import SessionLocal
from neroops.models import Pet

project_root = Path(__file__).resolve().parents[2]


def apply_migrations() -> None:
    config = Config(str(project_root / "alembic.ini"))
    config.attributes["configure_logger"] = False
    config.set_main_option("script_location", str(project_root / "migrations"))
    command.upgrade(config, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.prepare_directories()
    apply_migrations()
    with SessionLocal() as session:
        if session.query(Pet).count() == 0:
            session.add(Pet(name="Неро", species="dog", breed="Лабрадор"))
            session.commit()
    yield


app = FastAPI(
    title="NeroOps API",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

frontend_dist = project_root / "frontend" / "dist"
assets_dir = frontend_dist / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def serve_spa(path: str) -> FileResponse:
    requested = (frontend_dist / path).resolve()
    if path and requested.is_relative_to(frontend_dist.resolve()) and requested.is_file():
        return FileResponse(requested)
    index = frontend_dist / "index.html"
    if index.exists():
        return FileResponse(index)
    fallback = project_root / "frontend" / "public" / "fallback.html"
    return FileResponse(fallback)
