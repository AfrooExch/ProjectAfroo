"""
Webhook API Routes
Endpoints for receiving blockchain event webhooks from Tatum
"""

from fastapi import APIRouter, Request, HTTPException, Header, status, Depends
from typing import Optional
import logging

from app.services.webhook_service import WebhookService
from app.api.dependencies import require_admin
from app.core.config import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/tatum")
async def tatum_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Tatum-Signature")
):
    """
    Receive Tatum blockchain webhook.
    Processes incoming transactions and credits deposits.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        webhook_data = await request.json()

        # Verify signature
        if x_signature:
            is_valid = WebhookService.verify_signature(body, x_signature)
            if not is_valid:
                logger.warning("Invalid webhook signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )
        else:
            logger.warning("No signature provided in webhook")

        # Log webhook received
        logger.info(f"Tatum webhook received: {webhook_data.get('txId')}")

        # Process transaction
        result = await WebhookService.process_incoming_transaction(webhook_data)

        return {
            "success": True,
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Return 200 to prevent Tatum from retrying
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/tatum/test")
async def test_webhook(
    webhook_data: dict,
    admin: dict = Depends(require_admin)
):
    """
    Test endpoint for simulating Tatum webhooks.

    **Security:** Admin only, development/staging environments only.
    """
    # Block in production
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoint not available in production"
        )

    logger.info(f"Test webhook received from admin {admin.get('discord_id')}: {webhook_data}")

    result = await WebhookService.process_incoming_transaction(webhook_data)

    return {
        "success": True,
        "result": result,
        "warning": "This is a test endpoint - use only in development"
    }


@router.get("/health")
async def webhook_health():
    """Webhook endpoint health check"""
    return {
        "status": "healthy",
        "service": "webhooks"
    }
