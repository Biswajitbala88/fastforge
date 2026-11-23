import sqlite3
from datetime import datetime, timezone
from typing import Any


class PasswordResetRepository:
    """Persistence for password reset tokens. Only token hashes are stored."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_token(self, user_id: str, token_hash: str, expires_at: datetime) -> None:
        """Store a new reset token, invalidating any earlier unused ones for the user."""
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = ?
                WHERE user_id = ? AND used_at IS NULL
                """,
                (now, user_id),
            )
            self.conn.execute(
                """
                INSERT INTO password_reset_tokens (token_hash, user_id, expires_at, used_at, created_at)
                VALUES (?, ?, ?, NULL, ?)
                """,
                (token_hash, user_id, expires_at.isoformat(), now),
            )

    def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        cursor = self.conn.execute(
            """
            SELECT token_hash, user_id, expires_at, used_at, created_at
            FROM password_reset_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    def consume_and_set_password(
        self, token_hash: str, user_id: str, new_hashed_password: str
    ) -> bool:
        """Atomically mark the token used and update the password.

        Returns False if the token was already used (e.g. a concurrent request
        consumed it first); in that case nothing is changed.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = ?
                WHERE token_hash = ? AND used_at IS NULL
                """,
                (now, token_hash),
            )
            if cursor.rowcount != 1:
                return False
            self.conn.execute(
                "UPDATE users SET hashed_password = ? WHERE id = ?",
                (new_hashed_password, user_id),
            )
            # Any other outstanding tokens for this user are no longer valid.
            self.conn.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = ?
                WHERE user_id = ? AND used_at IS NULL
                """,
                (now, user_id),
            )
        return True
