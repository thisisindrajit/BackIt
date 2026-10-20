from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import RequestIdMiddleware, install_error_handlers
from app.routers import api_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BackIt API",
        version="1.0.0",
        description="Founding-backer campaigns with referral commissions (PayPal + AI MVP).",
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Idempotent-Replayed"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router)

    @app.get("/healthz", tags=["health"], include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
