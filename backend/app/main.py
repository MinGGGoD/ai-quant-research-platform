from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from backend.app.config import get_settings

APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: Literal["ok"]


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        description="Research and education platform API.",
    )

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return application


app = create_app()
