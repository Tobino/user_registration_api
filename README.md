# User Registration API

A service that registers users and activates their
accounts with a time-limited 4-digit code emailed through a third-party provider.

Built with **FastAPI** (async, dependency injection, Pydantic validation,
lifespan events, exception handlers), **PostgreSQL** (raw SQL via `asyncpg` - **no ORM**),
**Redis** for everything that expires, and **ealen/echo-server** as a stand-in for the third-party email API.

---

## Use cases

1. **Register** — `POST /users` with an email + password. Creates the account and emails a 4-digit code.
2. **Activate** — `POST /users/activate` with HTTP **Basic auth** (email + password) and the code. Valid for **60 seconds**.

---

## Architecture

```mermaid
flowchart LR
    client([Client])
    proxy[nginx proxy<br/>:8080]
    api[FastAPI app<br/>:8081]
    pg[(PostgreSQL<br/>users)]
    redis[(Redis<br/>codes + rate limits)]
    ealenechoserver[ealen/echo-server<br/>mock email API]

    client --> proxy --> api
    api -->|asyncpg, no ORM| pg
    api -->|codes w/ TTL,<br/>rate-limit windows| redis
    api -->|httpx + retry| ealenechoserver
```
---

## Running it

Only Docker + Docker Compose are required.

```bash
docker compose up --build
```

The API is served through the nginx proxy at **http://localhost:8080**.
Interactive docs: **http://localhost:8080/docs**.
And documentation: **http://localhost:8080/redoc**.

### Try it end-to-end

```bash
# 1) Register — always returns a generic 202 (no account enumeration)
curl -i -X POST http://localhost:8080/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"secretpw!"}'
```


---

## Observability

### Structured JSON logs

The app logs to **stdout** as one JSON object per line, so the output can be
ingested as-is by a log collector. Each record carries `timestamp`, `level`,
`logger`, `message`, the `request_id` (see below) when emitted inside a request,
an `exception` traceback on errors, and any structured `extra` fields:

```json
{"timestamp":"2026-06-14T19:41:43.973+00:00","level":"INFO","logger":"app.services.user_service","message":"register: start email=jerome@botineau.com","request_id":"9f1c…","email":"jerome@botineau.com"}
```

The verbosity is controlled by the **`LOG_LEVEL`** environment variable
(`DEBUG`, `INFO`, `WARNING`, `ERROR`; default **`INFO`**).

### Correlation IDs (`X-Request-ID`)

Every request is tagged with a correlation ID so its logs can be traced
end-to-end:

- if the request comes in with an **`X-Request-ID`** header it is reused,
  otherwise a fresh one is generated;
- the ID is **echoed back** in the response `X-Request-ID` header;
- it appears as `request_id` on every log line produced while handling the
  request (routes, services and repositories alike).

```bash
curl -i -X POST http://localhost:8080/users \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: trace-42' \
  -d '{"email":"jerome@botineau.com","password":"secretpw!"}'
# -> response includes:  X-Request-ID: trace-42
```

---

## Configuration

All settings are read from **environment variables**, validated by Pydantic in
[`app/core/config.py`](backend/app/core/config.py). The defaults below match the
Docker Compose setup, so nothing has to be set to run locally.

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`). |
| `DATABASE_URL` | *(unset)* | Full asyncpg DSN. Wins over the `DB_*` parts when set. |
| `DB_HOST` / `DB_PORT` | `db` / `5432` | PostgreSQL host and port. |
| `DB_USER` / `DB_NAME` | `postgres` / `users` | PostgreSQL user and database. |
| `DB_PASSWORD` | `postgres` | PostgreSQL password (ignored if `DB_PASSWORD_FILE` is set). |
| `DB_PASSWORD_FILE` | *(unset)* | Path to a Docker secret file holding the password. |
| `DB_POOL_MIN_SIZE` / `DB_POOL_MAX_SIZE` | `1` / `10` | asyncpg connection pool bounds. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL. |
| `CODE_TTL_SECONDS` | `60` | Activation-code validity window (Redis TTL). |
| `ACTIVATION_MAX_ATTEMPTS` | `3` | Max code guesses per issued code before lockout. |
| `SIGNUP_RATE_LIMIT` | `50` | Max registrations per IP within the window (see below). |
| `SIGNUP_RATE_LIMIT_WINDOW_SECONDS` | `3600` | Rolling window for the per-IP signup limit. |
| `EMAIL_API_URL` | `http://email/` | Third-party email API endpoint. |
| `EMAIL_API_TIMEOUT_SECONDS` | `5.0` | Per-request timeout for the email API. |
| `EMAIL_API_RETRY_ATTEMPTS` | `3` | Retry attempts when sending the activation email. |

---

## Rate limiting

`POST /users` is capped at **50 registrations per IP per hour** — a sliding
window stored in Redis. Once the budget is spent the endpoint returns **`429 Too
Many Requests`** with a **`Retry-After`** header, before any account work is
done. Tune it with `SIGNUP_RATE_LIMIT` / `SIGNUP_RATE_LIMIT_WINDOW_SECONDS`.

The client IP comes from `X-Forwarded-For` (uvicorn runs with `--proxy-headers`
behind the nginx proxy). Activation is separately protected by a per-code guess
cap (`ACTIVATION_MAX_ATTEMPTS`, default 3).

---

## Testing

Run the full suite in a container (no local Python needed):

First choose a db password and store it :
```
echo <your-password> > db/password.txt
```

```bash
docker compose run --rm tests
```