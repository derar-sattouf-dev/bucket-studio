# Contributing to Bucket Studio

Thanks for your interest! Bug reports, docs fixes and pull requests are all welcome.

## Before you start

- For anything bigger than a small fix, **open an issue first** so we can agree on the approach.
- Security issues: see [SECURITY.md](SECURITY.md) — please don't file them publicly.

## Development setup

```sh
./scripts/init-env.sh                     # creates .env with random secrets
docker compose --profile dev up --build   # MinIO + backend (hot reload) + Vite
```

UI: http://localhost:5173 · API docs: http://localhost:8000/docs · MinIO console: http://localhost:9001

### Running checks locally

Backend (Python 3.11, from `backend/`):

```sh
python -m venv .venv && source .venv/bin/activate
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check . && mypy app && pytest
```

Frontend (Node 22 + pnpm, from `frontend/`):

```sh
pnpm install && pnpm lint && pnpm typecheck && pnpm build
```

CI runs the same commands plus `pip-audit`, `pnpm audit` and Docker builds.

## Guidelines

- **Keep `api/` thin.** Routes validate input and map errors; logic lives in `services/` and `core/`.
- **Never fetch a user-supplied URL with a plain HTTP client.** Use `app.core.net.safe_get` (SSRF protection).
- **Schema changes** need an Alembic revision: `alembic revision --autogenerate -m "describe change"` (from `backend/`).
- **Dependencies:** edit `backend/requirements.in` and regenerate the lock with the command at its top.
- **Tests:** add or update tests for behaviour changes. Tests must not download models or call external services.
- **Frontend:** one folder per feature under `src/features/`, typed API modules in `src/api/`, no secrets in `VITE_*` variables.
- Keep pull requests focused, and describe *why* the change is needed.

## Commit messages

Use the imperative mood ("Add preset import", not "Added …"). Conventional-commit prefixes
(`feat:`, `fix:`, `docs:`…) are welcome but not required.

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
