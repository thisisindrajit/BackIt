from fastapi import APIRouter

from app.config import get_settings
from app.schemas import PublicConfig

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_config() -> PublicConfig:
    s = get_settings()
    return PublicConfig(
        paypal_mode=s.paypal_mode,
        paypal_client_id=s.paypal_client_id if s.paypal_mode == "sandbox" else None,
        ai_enabled=s.ai_enabled,
        platform_fee_bps=s.platform_fee_bps,
        hold_days=s.hold_days,
        payout_minimum_cents=s.payout_minimum_cents,
        environment=s.environment,
    )
