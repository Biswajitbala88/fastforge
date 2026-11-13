"""Request and response schemas for user endpoints.

These Pydantic schemas are the allow-list boundary between untrusted request
bodies and the SQLAlchemy ``User`` model. Every request schema sets
``extra="forbid"`` so that unexpected fields (e.g. ``is_admin``, ``role``,
``permissions``, ``is_superuser``) are rejected with a 422 instead of being
silently accepted. Privileged fields are deliberately absent from the public
schemas and present only on the admin-only schema.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSignup(BaseModel):
    """Public registration payload. Accepts only these three fields."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserProfileUpdate(BaseModel):
    """Self-service profile update. No privileged fields are accepted."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminUserUpdate(BaseModel):
    """Admin-only update. Privileged fields are permitted here, and this
    schema is reachable only through an admin-guarded endpoint."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role: str | None = Field(default=None, max_length=50)
    is_admin: bool | None = None
    is_superuser: bool | None = None
    is_active: bool | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Response schema. Never exposes ``hashed_password``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: str
    is_admin: bool
    is_superuser: bool
    is_active: bool
    created_at: datetime
