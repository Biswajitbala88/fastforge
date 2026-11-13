from fastapi import FastAPI

from app.api.routes import router
from app.api.users import auth_router, users_router
from app.core.config import settings
from app.core.database import Base, engine

# Import models so their tables are registered on the metadata before create_all.
from app.models import user as _user_model  # noqa: F401

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Create database tables on startup. For real migrations use Alembic; this keeps
# the scaffold runnable out of the box.
Base.metadata.create_all(bind=engine)

app.include_router(router)
app.include_router(auth_router)
app.include_router(users_router)
