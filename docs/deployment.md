# Deployment

Bucket Studio runs as two containers: the **backend** (API + processing) and the **frontend** (nginx serving
the UI and proxying `/api` to the backend). Only the frontend port is published; the backend is reachable
solely on the internal Compose network.

```
browser ──HTTPS──▶ your reverse proxy ──▶ frontend (nginx :8080) ──/api──▶ backend (:8000) ──▶ S3 bucket
                                                                                   └──▶ OpenAI / Gemini (optional)
```

## Requirements

- Docker with Compose v2, 2+ CPU cores and ~4 GB RAM (background removal and upscaling run on the CPU).
- An S3-compatible bucket and an access key that can list, read, write and delete objects in it.
- ~2 GB of disk for the models, which are downloaded on first use into the `models` volume.

## 1. Configure

```sh
git clone https://github.com/derar-sattouf-dev/bucket-studio.git && cd bucket-studio
./scripts/init-env.sh      # creates .env with random secrets
```

Then edit `.env` and point it at your bucket (all options: [configuration.md](configuration.md)):

```env
S3_ENDPOINT_URL=https://s3.eu-central-1.amazonaws.com   # or your R2 / Spaces / B2 / MinIO endpoint
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=my-images
S3_REGION=eu-central-1
```

## 2. Start

```sh
docker compose --profile prod up -d --build    # build the images locally
# or, once a release is published, use the prebuilt images from GHCR:
docker compose --profile prod up -d
```

The UI is now on `http://127.0.0.1:3000` (set `BIND_ADDRESS` / `HTTP_PORT` to change it).

## 3. Put HTTPS in front

Terminate TLS in a reverse proxy and forward to port 3000. Example with [Caddy](https://caddyserver.com/):

```caddyfile
images.example.com {
    reverse_proxy 127.0.0.1:3000
    header Strict-Transport-Security "max-age=31536000; includeSubDomains"
}
```

Login rate limiting counts failed attempts per client IP, so nginx has to learn the real client address
from your proxy. Set `REAL_IP_FROM` in `.env` to the address your proxy connects from. For a proxy on the
Docker host, that is the gateway of the Compose network (not Docker's default `172.17.0.1` bridge):

```sh
docker network inspect bucket-studio_default --format '{{(index .IPAM.Config 0).Gateway}}'
# e.g. 172.18.0.1  →  REAL_IP_FROM=172.18.0.1/32
```

Until this is set, every visitor appears to come from one address and shares a single login budget, so a
burst of failed logins from anyone locks everybody out for the lockout period. Only trust an address that
is really your proxy: a wider range lets clients forge `X-Forwarded-For` and dodge the throttle.

## Storage permissions

Minimal S3 policy for the bucket (AWS syntax; other providers have equivalents):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::my-images" },
    { "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::my-images/*" }
  ]
}
```

By default no ACL is sent, which works with buckets that have ACLs disabled (the AWS default for new
buckets). Serve published images through a CDN or a bucket policy. If you rely on object ACLs instead, set
**Settings → Storage & publishing → Object ACL** (or `S3_OBJECT_ACL`) to e.g. `public-read` and add
`s3:PutObjectAcl` to the policy above.

## Upgrading

```sh
docker compose --profile prod pull && docker compose --profile prod up -d
```

Database migrations run automatically on startup. Back up the database volume (`bucket-studio_sqlite_data`) before upgrading.

## Backups

- **Database:** the `bucket-studio_sqlite_data` volume (`/app/data/images.db`). Copy it while the backend is stopped, or
  use `sqlite3 images.db ".backup backup.db"`.
- **Images:** originals are kept under `BACKUP_PREFIX` when you publish; your bucket's own versioning or
  replication is still recommended.

## Optional: deploy from GitHub Actions

`.github/workflows/deploy.yml` can SSH into your server and run `git pull && docker compose up` after CI
passes on `main`. It is disabled by default; enable it by setting the repository variable
`DEPLOY_ENABLED=true` and the secrets listed at the top of the workflow.

`ops/healthcheck.sh` and `ops/cleanup.sh` are optional cron scripts for a single-server setup.

## Limits & scaling

The backend keeps job state in memory and must run as a **single process** (`--workers 1`, one replica).
For large libraries, scale vertically (more CPU cores and a higher `process_concurrency`).
