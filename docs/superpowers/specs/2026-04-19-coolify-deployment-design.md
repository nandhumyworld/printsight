# Coolify Deployment Design — PrintSight

**Date:** 2026-04-19  
**Domain:** `printsight.eyediaworks.in`  
**Status:** Approved

---

## Overview

Deploy PrintSight (FastAPI backend + React/Vite frontend) to a Coolify-managed server on Hostinger as a single Docker Compose stack, using Coolify's managed PostgreSQL for the database.

---

## Architecture

```
Internet
    │
    ▼
Traefik (port 80/443, managed by Coolify)
    │
    ├─ /api/*, /health, /docs, /redoc, /uploads/* ──► backend (port 8000)
    │
    └─ /* ──────────────────────────────────────────► frontend (port 80)

backend ──► Coolify managed PostgreSQL (internal Docker network only)
```

### Key decisions
- **Database:** Coolify managed PostgreSQL — internal only, no host port binding (host port 5432 is already occupied by another container)
- **Deployment unit:** Single Docker Compose stack (backend + frontend); `postgres` service removed
- **Routing:** Path-based via Traefik labels — no subdomain split needed
- **`VITE_API_URL`:** `https://printsight.eyediaworks.in` — the frontend appends `/api/v1` itself, so no path stripping is needed in Traefik

---

## docker-compose.yml Changes

Remove from current file:
- `postgres` service entirely
- `postgres_data` volume
- `printsight-net` network block
- All host port mappings (`8001:8000`, `3000:80`, `5432:5432`)

Add to each service:
- Traefik labels for path-based routing
- `networks: coolify` to join Coolify's managed network

### Backend Traefik labels
Route requests matching `/api`, `/health`, `/docs`, `/redoc`, or `/uploads` to backend port 8000.

### Frontend Traefik labels
Catch-all for `printsight.eyediaworks.in` to frontend port 80. Backend router has higher Traefik priority (PathPrefix rules auto-rank higher than bare Host rules).

---

## Environment Variables

All set in Coolify UI — nothing sensitive committed to the repo.

### Backend (runtime env vars)

| Variable | Production Value |
|---|---|
| `DATABASE_URL` | From Coolify managed PostgreSQL connection string |
| `SECRET_KEY` | Generate: `openssl rand -hex 32` |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` |
| `ALLOWED_ORIGINS` | `https://printsight.eyediaworks.in` |
| `APP_ENV` | `production` |
| `MAX_CSV_UPLOAD_SIZE_MB` | `10` |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASSWORD` | your app password |
| `EMAILS_FROM_NAME` | `PrintSight` |
| `TELEGRAM_BOT_TOKEN` | your bot token |

### Frontend (Docker build arg)

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://printsight.eyediaworks.in` |

---

## Coolify Setup Steps (high level)

1. **Provision managed PostgreSQL** in Coolify → note the internal connection string
2. **Create Docker Compose service** in Coolify pointing to the GitHub repo, selecting `docker-compose.yml`
3. **Set all env vars** listed above in Coolify's environment variable UI
4. **Set `VITE_API_URL` as a build arg** (separate from runtime env vars in Coolify)
5. **Deploy** — Coolify builds images, runs Alembic migrations on startup, serves via Traefik

---

## Host Port Constraints

- Port `5432`: already bound by existing container — Coolify managed PostgreSQL must stay internal
- Port `80`: Coolify's Traefik proxy — our services must NOT bind host ports, only use Traefik labels

---

## Out of Scope

- SSL/HTTPS termination — handled automatically by Coolify/Traefik with Let's Encrypt
- CI/CD pipeline — Coolify can auto-deploy on git push (configure separately in Coolify UI)
- Persistent file storage for uploads — `uploads/printers` is currently ephemeral inside the container; not addressed in this deployment
