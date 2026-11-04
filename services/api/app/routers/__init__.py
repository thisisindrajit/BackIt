from fastapi import APIRouter

from app.routers import (
    backings,
    builder,
    campaigns,
    claims,
    config,
    me,
    notifications,
    orders,
    payouts,
    products,
    public,
    webhooks,
)

api_router = APIRouter(prefix="/v1")
for module in (
    config, me, notifications, products, campaigns, public, orders, backings, builder, claims, payouts, webhooks,
):
    api_router.include_router(module.router)
