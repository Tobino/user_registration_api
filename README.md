# User Registration API

A service that registers users and activates their
accounts with a time-limited 4-digit code emailed through a third-party provider.

Built with **FastAPI** (async, dependency injection, Pydantic validation,
lifespan events, exception handlers), **PostgreSQL** (raw SQL via `asyncpg` - **no ORM**),
**Redis** for everything that expires, and **Webhook.site** as a stand-in for the third-party email API.

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
    webhooksite[Webhook.Site<br/>mock email API]

    client --> proxy --> api
    api -->|asyncpg, no ORM| pg
    api -->|codes w/ TTL,<br/>rate-limit windows| redis
    api -->|httpx + retry| webhooksite
```