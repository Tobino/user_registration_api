"""Aggregates the v1 routers under a single router."""

from fastapi import APIRouter

from app.api.v1.routes import users

api_router = APIRouter()
api_router.include_router(users.router)
