"""Authentication and user-management endpoints.

Security properties enforced here:

* Request bodies are parsed through allow-listed Pydantic schemas with
  ``extra="forbid"``; unknown or privileged fields are rejected (422).
* The database ``User`` is built with *explicit* field mapping — never
  ``User(**request_data)`` — so no request can reach a privileged column.
* Privileged fields (``role``, ``is_admin``, ``is_superuser``) are set only by
  server-side logic; registration always produces an unprivileged user.
* Profile edits require authentication and only ever touch the caller's own
  record. Changing another user or any privileged field requires an admin.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    AdminUserUpdate,
    TokenResponse,
    UserOut,
    UserProfileUpdate,
    UserSignup,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


# --- Registration & login ---------------------------------------------------


@auth_router.post(
    "/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
def signup(payload: UserSignup, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Explicit field mapping. Privileged columns are set server-side to safe
    # defaults regardless of what the request contained.
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="user",
        is_admin=False,
        is_superuser=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@auth_router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    # OAuth2 form uses ``username``; we treat it as the email.
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled"
        )
    return TokenResponse(access_token=create_access_token(user.id))


# --- Self-service profile ---------------------------------------------------


@users_router.get("/me", response_model=UserOut)
def read_own_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@users_router.patch("/me", response_model=UserOut)
def update_own_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    updates = payload.model_dump(exclude_unset=True)

    if "email" in updates and updates["email"] != current_user.email:
        clash = (
            db.query(User).filter(User.email == updates["email"]).first()
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

    # Explicit, allow-listed field mapping. The schema cannot carry privileged
    # fields, but we still map each field by name rather than bulk-assigning.
    if "name" in updates:
        current_user.name = updates["name"]
    if "email" in updates:
        current_user.email = updates["email"]
    if "password" in updates:
        current_user.hashed_password = hash_password(updates["password"])

    db.commit()
    db.refresh(current_user)
    return current_user


# --- Admin user management --------------------------------------------------


@users_router.get("", response_model=list[UserOut])
def list_users(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.id).all()


@users_router.get("/{user_id}", response_model=UserOut)
def read_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    # A user may read their own record; otherwise admin privileges are required.
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted to access this user",
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@users_router.patch("/{user_id}", response_model=UserOut)
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdate,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    updates = payload.model_dump(exclude_unset=True)

    if "email" in updates and updates["email"] != user.email:
        clash = db.query(User).filter(User.email == updates["email"]).first()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

    # Explicit mapping of the admin-permitted fields only.
    if "name" in updates:
        user.name = updates["name"]
    if "email" in updates:
        user.email = updates["email"]
    if "role" in updates:
        user.role = updates["role"]
    if "is_admin" in updates:
        user.is_admin = updates["is_admin"]
    if "is_superuser" in updates:
        user.is_superuser = updates["is_superuser"]
    if "is_active" in updates:
        user.is_active = updates["is_active"]

    db.commit()
    db.refresh(user)
    return user
