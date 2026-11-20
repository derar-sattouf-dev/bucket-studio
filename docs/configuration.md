# Configuration

Bucket Studio is configured in two places:

1. **Environment variables** (`.env`): only secrets and what the server needs to start (accounts,
   storage credentials, AI API keys, paths, ports). Secrets are never stored in the database or shown in the UI.
2. **The Settings and Presets pages** (stored in the database): every behavioural option, such as
   grouping, sync, concurrency, limits, session length, login throttling, bucket prefixes, object ACL,
   publish derivatives, source filters and AI model names. Changes apply immediately, with no restart.
   Where an environment variable with the same name exists, it only provides the **initial default**.

**Settings → Environment** shows the read-only values that come from `.env` (bucket, endpoint, which AI
keys are configured, version).

`./scripts/init-env.sh` creates a `.env` from [`.env.example`](../.env.example) with random secrets.

## Environment variables

### Required

| Variable | Description |
|---|---|
| `JWT_SECRET` | Signs login tokens. At least 32 characters (`openssl rand -hex 32`); the backend refuses to start otherwise. |
| `AUTH_USERNAME`, `AUTH_PASSWORD` | Built-in admin account. More users can be created in the UI (**Users**), where they can also be deactivated (signed out at once, sign-in refused) and reactivated. |
| `ADMIN_PASSWORD` | Second password asked for sensitive actions (users, bucket prefixes, publish settings, database reset). At least 8 characters. Wrong guesses are throttled (5 per 15 minutes per account). |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_REGION` | Your S3-compatible storage. Leave both keys empty to use the standard AWS credential chain (instance profile, IRSA, …). |

### Storage

| Variable | Default | Description |
|---|---|---|
| `S3_PUBLIC_ENDPOINT_URL` | *(same as `S3_ENDPOINT_URL`)* | Endpoint used to sign the image URLs your browser opens. Needed when the backend reaches storage by an internal name (the dev stack sets it to `http://localhost:9000`). |
| `S3_OBJECT_ACL` | *(none)* | Canned ACL for written images, e.g. `public-read`. Leave empty for buckets with ACLs disabled (the AWS default); serve images with a bucket policy or CDN instead. |
| `S3_ADDRESSING_STYLE` | `auto` | `path` (bucket in the URL path; MinIO and most self-hosted stores) or `virtual` (bucket in the host name). `auto` lets the SDK decide. |
| `S3_CHECKSUM_MODE` | `when_required` | `when_required` sends integrity checksums only where the API demands them, which every S3-compatible provider accepts. `when_supported` adds CRC checksums to every upload (AWS only, or providers that support them). |
| `PRESIGN_EXPIRES_SECONDS` | `3600` | Lifetime of signed image URLs. |
| `S3_AUTO_CREATE_BUCKET` | `false` | Create the bucket on startup (used by the dev stack). |
| `SOURCE_PREFIX` | `images/` | Where your original images live. |
| `OUTPUT_PREFIX` | `processed/` | Where processed results are written before publishing. |
| `BACKUP_PREFIX` | `backup/` | Where originals are backed up when you publish. |

The three prefixes must end with `/`, be different and not be nested inside each other; the backend
refuses to start otherwise. They can be changed later in **Settings → Storage & publishing**. Each
published image remembers where its backup was written, so changing `BACKUP_PREFIX` later does not
affect restoring images that are already published.

### Limits & security

| Variable | Default | Description |
|---|---|---|
| `SESSION_MINUTES` | `720` | Session length (5 min – 7 days). |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES` | `5`, `15` | Failed-login throttling per client IP + username (one IP gets four times the budget across usernames). Behind a reverse proxy, set `REAL_IP_FROM` or every visitor shares one budget. |
| `API_KEY` | *(off)* | Optional key for server-to-server calls (`X-API-Key` header), with admin rights. At least 16 characters (`openssl rand -hex 24`). Never expose it to a browser. |
| `MAX_UPLOAD_MB` | `20` | Largest Playground upload. |
| `MAX_REMOTE_FETCH_MB` | `20` | Largest image fetched by URL import or Playground URL mode. |
| `MAX_IMAGE_MEGAPIXELS` | `80` | Decompression-bomb guard for every decoded image. |
| `API_DOCS_ENABLED` | `false` (`true` in the dev stack) | Serve Swagger UI at `/docs`. |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Only needed if the UI is served from a different origin than the API. |

### Settings defaults

The variables in this section and the storage options above (`S3_OBJECT_ACL`, `PRESIGN_EXPIRES_SECONDS`,
the prefixes), limits and security values (`SESSION_MINUTES`, `LOGIN_*`, `MAX_*`) and the AI model names
only seed the **Settings** page. After the first start, change them there.

| Variable | Default | Description |
|---|---|---|
| `GROUP_DEPTH` | `1` | How many folder levels after the source prefix form a group in the UI (0 = no grouping). |
| `SYNC_INTERVAL_MINUTES` | `30` | Automatic bucket sync interval (0 = manual only). |
| `AUTO_PROCESS_AFTER_SYNC` | `false` | Start a batch job with the default preset when sync finds new images. |
| `PROCESS_CONCURRENCY` | `2` | Images processed in parallel on the CPU. |
| `AI_CONCURRENCY` | `2` | Parallel requests to AI engines. |
| `MAX_RETRY_COUNT` | `999` | How many attempts a failed image gets from "Retry failed". Images at the limit are skipped and reported separately from ones skipped because they are already being processed. |

### AI engines (optional)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | | Enables the OpenAI engine. |
| `OPENAI_IMAGE_MODEL` | `gpt-image-1.5` | OpenAI image-edit model. |
| `GEMINI_API_KEY` | | Enables the Google Gemini engine. |
| `GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Gemini image model. |

Images are only sent to a provider when a key is configured **and** a preset or a run selects that engine.

### Paths & deployment

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `backend/data` (`/app/data` in Docker) | SQLite database location. |
| `MODELS_DIR` | `backend/models` (`/models` in Docker) | Model weights, downloaded on first use. |
| `APP_NAME` | `Bucket Studio` | Name shown in the API docs. |
| `BIND_ADDRESS` | `127.0.0.1` | Interface the prod stack publishes on. |
| `HTTP_PORT` | `3000` | Port of the prod stack. |
| `REAL_IP_FROM` | `127.0.0.1/32` | CIDR of your reverse proxy, so nginx trusts its `X-Forwarded-For`. |
| `CLIENT_MAX_BODY_SIZE` | `25m` | nginx request size limit (keep it above `MAX_UPLOAD_MB`). |
| `BACKEND_IMAGE`, `FRONTEND_IMAGE` | GHCR images | Override the prod image references. |
| `CSP_IMG_SRC` | *(empty)* | Extra `img-src` origins for the UI's Content-Security-Policy. Any `https:` origin is already allowed; add `http://…` origins only if your storage serves images over plain HTTP. |
| `CSP_CONNECT_SRC` | *(empty)* | Extra `connect-src` origins; only needed if the UI talks to an API on another origin. |
| `VITE_API_URL` | `/api` | Build-time API base for the UI. Only set it if the API is served from a different origin (then also set `CORS_ORIGINS` and `CSP_CONNECT_SRC`). Never put secrets in `VITE_*` variables. |
| `JWT_ISSUER` | `bucket-studio` | Issuer claim of login tokens. Changing it signs everyone out. |

## Presets

A preset is a named recipe. Every stage can be switched off:

| Stage | Options |
|---|---|
| **Contrast** | factor 0.5–2.0 |
| **Background** | remove with a rembg model (`birefnet-general` default, lighter `u2netp`, `isnet-general-use`…), skip when the image already has a plain background, alpha matting |
| **Autocrop** | crop to the subject with padding |
| **Upscale** | 2× when the longest side is below a threshold (Real-ESRGAN or Lanczos) |
| **Canvas** | place on a fixed-size canvas with a fill ratio and a colour or transparency |
| **Resize** | maximum width/height (when no canvas) |
| **Output** | keep the source format or convert to JPEG/PNG/WebP, quality, optional maximum file size |
| **AI** | regenerate with OpenAI or Gemini instead of local processing, always or only for small images |

Built-in presets: **White background (square)** (default), **Transparent cutout**, **Upscale only**, **Web optimize**.

Publishing copies the processed image over the original key, so the preset's output format must match the
source format; **Keep** does that automatically.

## Publish derivatives

When you publish an image, Bucket Studio can write extra files next to it (thumbnails, WebP copies),
defined in **Settings → Storage & publishing → Publish derivatives**. None are configured by default. Each one has a name template, a size, a fit (`contain`/`cover`), a format
and a quality.

Templates use `{stem}` (file name without extension) and `{ext}`:

| Template | For `photos/2024/beach.jpg` |
|---|---|
| `{stem}_thumb.{ext}` | `photos/2024/beach_thumb.jpg` |
| `{stem}-large.{ext}` | `photos/2024/beach-large.jpg` |
| `{stem}.webp` *(format WebP)* | `photos/2024/beach.webp` (rejected if `.webp` files are also sources) |

Files matching a derivative template are never picked up as sources by sync.

## Source filters

**Settings → Storage & publishing → Source filters** chooses which files in the source prefix are treated as images:
the allowed extensions (`jpg`, `jpeg`, `png`, `webp`) and optional exclusion patterns such as `*_raw.*`
or `draft-*`.
