from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.middleware import RequestIdMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.imports.router import router as imports_router


settings = get_settings()


def create_app() -> FastAPI:
    application = FastAPI(
        title="E-commerce Sales Analytics API",
        version="0.1.0",
    )

    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(application)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(imports_router, prefix="/api/v1")

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "api"}

    return application


app = create_app()
