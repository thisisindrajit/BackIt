from fastapi import APIRouter

from app.routers import (
    backings,
    builder,
    campaigns,
    config,
    me,
    orders,
    payouts,
    products,
    public,
    webhooks,
)

api_router = APIRouter(prefix="/v1")
for module in (config, me, products, campaigns, public, orders, backings, builder, payouts, webhooks):
    api_router.include_router(module.router)
