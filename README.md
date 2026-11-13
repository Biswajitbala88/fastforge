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
  db/
    database.py          # SQLite database connection & schema initialization
    repositories/
      user_repository.py # user persistence CRUD operations
  schemas/
    chat.py              # Chat and room status schemas
    user.py              # Pydantic schemas (UserCreate, UserResponse, Token)
  services/
    chat_manager.py      # Room-based connection manager (max 2 users)
tests/                   # test suite
```

## Authentication

Authentication uses **Argon2id** password hashing via `pwdlib` and signed JWT access tokens via `PyJWT`.

### Endpoints
- `POST /auth/register`: Register a new user with Argon2id-hashed password
- `POST /auth/login`: Authenticate with JSON `{ "email": "...", "password": "..." }` and receive a JWT token
- `POST /auth/token`: OAuth2 password form login (used by Swagger UI `/docs` "Authorize")
- `GET /auth/me`: Get current user profile (requires `Authorization: Bearer <token>`)

## 2-User WebSocket Chat

Real-time 1-on-1 chat rooms with a strict 2-user capacity limit.

### Endpoints & Pages
- `WS /ws/chat/{room_id}?client_id={username}`: Real-time WebSocket connection. A 3rd connection attempt is rejected with WS code `1008` (Policy Violation).
- `GET /api/chat/rooms/{room_id}`: Inspect room participant count and capacity status.
- `GET /chat/{room_id}`: Built-in responsive HTML chat client to easily test 2 users chatting in real time across browser tabs.

