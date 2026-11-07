import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


class UserRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_user(self, email: str, hashed_password: str) -> dict[str, Any]:
        """Create a new user and return the record as a dictionary."""
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO users (id, email, hashed_password, is_active, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (user_id, email.lower().strip(), hashed_password, created_at),
            )
        return {
            "id": user_id,
            "email": email.lower().strip(),
            "hashed_password": hashed_password,
            "is_active": True,
            "created_at": created_at,
        }

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch a user by email."""
        cursor = self.conn.execute(
            """
            SELECT id, email, hashed_password, is_active, created_at
            FROM users
            WHERE email = ?
            """,
            (email.lower().strip(),),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Fetch a user by user_id."""
        cursor = self.conn.execute(
            """
            SELECT id, email, hashed_password, is_active, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def update_password(self, user_id: str, new_hashed_password: str) -> None:
        """Update a user's hashed password (e.g., when Argon2 parameters are rehashed)."""
        with self.conn:
            self.conn.execute(
                """
                UPDATE users
                SET hashed_password = ?
                WHERE id = ?
                """,
                (new_hashed_password, user_id),
            )
