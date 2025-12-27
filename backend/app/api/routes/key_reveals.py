"""
Key Reveal Routes - Secure private key reveal with rate limiting
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel

from app.api.dependencies import get_current_user, require_exchanger
from app.services.key_reveal_service import KeyRevealService

router = APIRouter()


class KeyRevealRequest(BaseModel):
    """Request to reveal private key"""
    asset: str


@router.post("/key-reveals/reveal", dependencies=[Depends(require_exchanger)])
async def reveal_private_key(
    request: KeyRevealRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Reveal private key for exchanger deposit wallet.

    **Rate Limits:**
    - 5 reveals per hour
    - 20 reveals per day

    **Security:**
    - Key is only revealed for 5 minutes
    - All reveals are logged with IP address
    - Only exchanger role can access

    **Warning:** Keep your private key safe! Never share it with anyone.
    """
    try:
        # Get IP address
        ip_address = http_request.client.host
        user_agent = http_request.headers.get("user-agent", "")

        success, message, reveal_data = await KeyRevealService.request_key_reveal(
            user_id=str(current_user["_id"]),
            asset=request.asset,
            ip_address=ip_address,
            user_agent=user_agent
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "success": True,
            "message": message,
            "private_key": reveal_data["private_key"],
            "expires_at": reveal_data["expires_at"],
            "reveal_window_seconds": reveal_data["reveal_window_seconds"],
            "remaining_hourly": reveal_data["remaining_hourly"],
            "remaining_daily": reveal_data["remaining_daily"],
            "warning": "Keep this key safe! Never share it with anyone. This key will only be shown once."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/key-reveals/limits", dependencies=[Depends(require_exchanger)])
async def get_reveal_limits(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current reveal limits for user.

    Shows how many reveals remaining for the hour and day.
    """
    try:
        limits = await KeyRevealService.get_reveal_limits(str(current_user["_id"]))

        return {
            "success": True,
            "limits": limits
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/key-reveals/history", dependencies=[Depends(require_exchanger)])
async def get_reveal_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's key reveal history.

    **Note:** This does not include the actual keys, only the reveal timestamps.
    """
    try:
        history = await KeyRevealService.get_reveal_history(
            user_id=str(current_user["_id"]),
            limit=limit
        )

        return {
            "success": True,
            "history": history
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
