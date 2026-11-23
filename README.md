# FastForge

A basic FastAPI application.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
fastapi dev app/main.py
```

The API runs at http://127.0.0.1:8000, with interactive docs at `/docs`.

## Test

```bash
pytest
```

## Layout

```
app/
  main.py                # application entry point and lifespan
  api/
    auth.py              # authentication endpoints (register, login, token, me)
    chat.py              # 2-user WebSocket chat and web test page
    deps.py              # authentication and database dependencies
    routes.py            # root router
  core/
    config.py            # settings loaded from .env
    security/
      jwt.py             # JWT token creation and verification
      password.py        # Argon2id password hashing and verification
      reset_token.py     # password reset token generation and hashing
  db/
    database.py          # SQLite database connection & schema initialization
    repositories/
      user_repository.py # user persistence CRUD operations
      password_reset_repository.py # password reset token storage
  schemas/
    chat.py              # Chat and room status schemas
    user.py              # Pydantic schemas (UserCreate, UserResponse, Token)
  services/
    chat_manager.py      # Room-based connection manager (max 2 users)
    email.py             # outgoing email (password reset links; logs for now)
tests/                   # test suite
```

## Authentication

Authentication uses **Argon2id** password hashing via `pwdlib` and signed JWT access tokens via `PyJWT`.

### Endpoints
- `POST /auth/register`: Register a new user with Argon2id-hashed password
- `POST /auth/login`: Authenticate with JSON `{ "email": "...", "password": "..." }` and receive a JWT token
- `POST /auth/token`: OAuth2 password form login (used by Swagger UI `/docs` "Authorize")
- `GET /auth/me`: Get current user profile (requires `Authorization: Bearer <token>`)
- `POST /auth/forgot-password`: Request a reset link with JSON `{ "email": "..." }`. Always returns the same message, whether or not the email is registered.
- `POST /auth/reset-password`: Set a new password with JSON `{ "token": "...", "new_password": "..." }`. Returns `400` for an invalid, expired or already-used token.

### Password reset

- Reset tokens are random, single-use and expire after `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` (default 15). Only a SHA-256 hash of each token is stored, and requesting a new token invalidates earlier ones.
- The link sent to the user is `PASSWORD_RESET_URL?token=<token>`.
- No email provider is wired up yet: `app/services/email.py` writes the reset link to the server log. Replace `send_password_reset_email` with a real sender before production.
- With `DEBUG=true`, `/auth/forgot-password` also returns `reset_token` in the response for local testing. Never enable `DEBUG` in production.

## 2-User WebSocket Chat

Real-time 1-on-1 chat rooms with a strict 2-user capacity limit.

### Endpoints & Pages
- `WS /ws/chat/{room_id}?client_id={username}`: Real-time WebSocket connection. A 3rd connection attempt is rejected with WS code `1008` (Policy Violation).
- `GET /api/chat/rooms/{room_id}`: Inspect room participant count and capacity status.
- `GET /chat/{room_id}`: Built-in responsive HTML chat client to easily test 2 users chatting in real time across browser tabs.

