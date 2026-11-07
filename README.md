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
    user.py              # Pydantic schemas (UserCreate, UserResponse, Token)
tests/                   # test suite
```

## Authentication

Authentication uses **Argon2id** password hashing via `pwdlib` and signed JWT access tokens via `PyJWT`.

### Endpoints
- `POST /auth/register`: Register a new user with Argon2id-hashed password
- `POST /auth/login`: Authenticate with JSON `{ "email": "...", "password": "..." }` and receive a JWT token
- `POST /auth/token`: OAuth2 password form login (used by Swagger UI `/docs` "Authorize")
- `GET /auth/me`: Get current user profile (requires `Authorization: Bearer <token>`)
