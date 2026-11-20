# syntax=docker/dockerfile:1.7

# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --frozen-lockfile

COPY . .

# Optional, public build-time override of the API base (default: same-origin "/api" via nginx).
# Never pass credentials as VITE_* variables: they are embedded in the JavaScript bundle.
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

RUN pnpm run build

# ── Stage 2: serve with unprivileged nginx (non-root, port 8080) ──────────────
FROM nginxinc/nginx-unprivileged:1.31-alpine AS runner

LABEL org.opencontainers.image.title="Bucket Studio frontend" \
      org.opencontainers.image.description="Web UI for Bucket Studio, served by unprivileged nginx" \
      org.opencontainers.image.licenses="MIT"

# Rendered at container start by the image's envsubst entrypoint (CSP origins).
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/security-headers.conf.template /etc/nginx/templates/snippets/security-headers.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html

# Defaults for the config template (override with environment variables).
ENV BACKEND_URL=http://backend:8000 \
    CLIENT_MAX_BODY_SIZE=25m \
    REAL_IP_FROM=127.0.0.1/32 \
    CSP_CONNECT_SRC= \
    CSP_IMG_SRC=

EXPOSE 8080
