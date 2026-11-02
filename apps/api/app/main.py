from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.routers import auth, cadastro, contracts, meta, planning, workforce
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    # Create tables (Alembic also available for versioned migrations)
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="FieldOps — Field Operations SaaS MVP (PR2 planning ops)",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_prefix
    app.include_router(auth.router, prefix=prefix)
    app.include_router(cadastro.router, prefix=prefix)
    app.include_router(contracts.router, prefix=prefix)
    app.include_router(planning.router, prefix=prefix)
    app.include_router(workforce.router, prefix=prefix)
    app.include_router(meta.router, prefix=prefix)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "fieldops-api"}

    return app


app = create_app()
