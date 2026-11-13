import sqlite3
from datetime import datetime
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security.jwt import decode_access_token
from app.db.database import get_db
from app.db.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_user_repository(
    conn: Annotated[sqlite3.Connection, Depends(get_db)]
) -> UserRepository:
    return UserRepository(conn)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        subject: str | None = payload.get("sub")
        if subject is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = user_repo.get_by_id(subject)
    if user is None:
        user = user_repo.get_by_email(subject)
    if user is None:
        raise credentials_exception

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return UserResponse(
        id=user["id"],
        email=user["email"],
        is_active=bool(user["is_active"]),
        created_at=datetime.fromisoformat(user["created_at"]),
    )
