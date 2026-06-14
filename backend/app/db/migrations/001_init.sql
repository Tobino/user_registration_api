-- Initial schema for the user registration service.
-- gen_random_uuid() is built into PostgreSQL 13+ (no extension required).

CREATE TABLE IF NOT EXISTS users (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text        NOT NULL UNIQUE,
    password_hash text        NOT NULL,
    is_active     boolean     NOT NULL DEFAULT FALSE,
    created_at    timestamptz NOT NULL DEFAULT now(),
    activated_at  timestamptz
);
