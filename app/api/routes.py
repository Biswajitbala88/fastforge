from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    return {"message": f"Welcome to {settings.app_name}"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
