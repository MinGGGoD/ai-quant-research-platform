from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from backend.app.api import api_router, resource_router
from backend.app.api.errors import install_error_handlers
from backend.app.api.schemas import HealthResponse
from backend.app.config import get_settings
from backend.app.main_constants import APP_VERSION


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        description="Research and education platform API.",
    )
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["DELETE", "GET", "POST"],
            allow_headers=["Accept", "Content-Type"],
        )
    install_error_handlers(application)

    @application.middleware("http")
    async def attach_request_id(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = uuid4()
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    application.include_router(api_router, prefix="/api/v1")
    application.include_router(resource_router, prefix="/api/v1")
    application.include_router(resource_router, include_in_schema=False)

    return application


app = create_app()
