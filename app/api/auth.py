from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_current_user, get_user_repository
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password, verify_and_update_password
from app.db.repositories.user_repository import UserRepository
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    user_in: UserCreate,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserResponse:
    existing_user = user_repo.get_by_email(user_in.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password with Argon2id
    hashed_password = hash_password(user_in.password)
    user = user_repo.create_user(
        email=user_in.email,
        hashed_password=hashed_password,
    )

    return UserResponse(
        id=user["id"],
        email=user["email"],
        is_active=bool(user["is_active"]),
        created_at=datetime.fromisoformat(user["created_at"]),
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Login with email and password (JSON)",
)
def login(
    credentials: UserLogin,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> Token:
    user = user_repo.get_by_email(credentials.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_valid, updated_hash = verify_and_update_password(
        credentials.password, user["hashed_password"]
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Persist updated hash if password hasher parameters changed
    if updated_hash:
        user_repo.update_password(user["id"], updated_hash)

    access_token = create_access_token(
        subject=user["id"],
        expires_delta=None,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 password form login (for Swagger UI)",
)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> Token:
    user = user_repo.get_by_email(form_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_valid, updated_hash = verify_and_update_password(
        form_data.password, user["hashed_password"]
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    if updated_hash:
        user_repo.update_password(user["id"], updated_hash)

    access_token = create_access_token(
        subject=user["id"],
        expires_delta=None,
    )
    return Token(access_token=access_token, token_type="bearer")



@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def read_current_user(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> UserResponse:
    return current_user
