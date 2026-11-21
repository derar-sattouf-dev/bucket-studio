# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## What this is

**Bucket Studio**: an MIT-licensed, self-hosted image pipeline for S3-compatible buckets.
Sync a bucket → process images in bulk with a **preset** → review before/after → **publish** in place
(original backed up) → **restore**. Also: batch jobs, Playground, import from URLs, optional OpenAI/Gemini
engines, users with roles.

User-facing docs are the source of truth. Keep them in sync when behaviour changes:
[README.md](README.md), [docs/configuration.md](docs/configuration.md),
[docs/architecture.md](docs/architecture.md) (pipeline, lifecycle, **security model**, layout),
[docs/deployment.md](docs/deployment.md).

## Running & checks

```sh
./scripts/init-env.sh && docker compose --profile dev up --build   # UI :5173, API :8000, MinIO :9001
./scripts/seed-demo.sh                                              # sample images via /imports

# backend (backend/, Python 3.11)
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check . && mypy app && pytest

# frontend (frontend/)
pnpm install && pnpm lint && pnpm typecheck && pnpm build

# README screenshots (needs a running dev stack with demo data + local Chrome)
cd scripts/screenshots && pnpm install && pnpm capture
```

## Rules of the codebase

- **api/ stays thin** (validation + HTTP error mapping); logic in `services/` (use cases) and `core/` (building blocks).
- **Never fetch a user-supplied URL with a plain HTTP client**: use `app.core.net.safe_get` (SSRF guard).
- **Never put secrets in `VITE_*` variables**: they end up in the JS bundle. The UI calls the API same-origin at `/api`.
- **No tokens in URLs.** SSE uses `fetch` + `Authorization` (`streamEvents` in `frontend/src/api/client.ts`).
- **Every request model has bounds** (lengths, ranges, list sizes); storage keys must be validated against the
  runtime prefixes.
- **Error responses never contain exception text**; log details server-side.
- **Schema change → Alembic revision** (`alembic revision --autogenerate -m "..."` from `backend/`).
- **Dependencies:** edit `backend/requirements.in`, regenerate `requirements.txt` with the command at its top.
  torch is installed separately (CPU index) and is not in the lock. numpy is 2.x (rembg needs it).
- **Tests never download models or hit the network** (guarded by autouse fixtures in `tests/conftest.py`:
  model loading and any real socket connection fail; in-memory S3 in `tests/fakes.py`).
- **`app/` type-checks with mypy** (config in `backend/pyproject.toml`). Prefer real types over
  `# type: ignore`; an unavoidable ignore names its error code and the reason.
- Backend runs as **one process**: job/task/rate-limit state is in memory.
- Frontend: one folder per feature in `src/features/`, typed API modules in `src/api/`, files under ~300 lines.
- Wording: images are grouped by **folder/group** (`group_key`, `GROUP_DEPTH`). Don't reintroduce
  domain-specific terms ("product", etc.); the tool is general-purpose.

## Domain essentials

- Prefixes: `SOURCE_PREFIX` (originals), `OUTPUT_PREFIX` (processed results), `BACKUP_PREFIX` (originals
  saved on publish). They must end with `/`, be distinct and not nested.
- Status: `pending → processing → processed | failed`; `is_published` set on publish, cleared on restore.
  Re-publishing a published image is refused (protects the backup).
- Publish copies the processed bytes over the source key, so output format must match the source
  (presets default to `keep`), then writes **derivatives** from name templates (`{stem}`, `{ext}`; must contain
  `{stem}`). Files matching derivative templates are excluded from sync.
- Presets: `core/preset_config.py` (`PresetConfig`, seeds). Exactly one default preset (partial unique index).
- Models download on first use into `MODELS_DIR` (`core/model_store.py`); Real-ESRGAN is SHA-256 verified.
