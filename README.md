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
  main.py         # application entry point
  api/routes.py   # endpoints
  core/config.py  # settings, loaded from the environment or .env
tests/            # test suite
```
