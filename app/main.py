from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.api.users import auth_router, users_router
from app.core.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(router)
app.include_router(auth_router)
app.include_router(users_router)
