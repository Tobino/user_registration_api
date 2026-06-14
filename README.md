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

## Testing

Run the full suite in a container (no local Python needed):

```bash
docker compose run --rm tests
```