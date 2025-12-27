"""
Account Recovery Routes
Handles recovery code generation and account transfer
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_user_from_bot_request
from app.services.recovery_service import RecoveryService
from app.core.database import get_users_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recovery", tags=["recovery"])


class TransferAccountRequest(BaseModel):
    """Request to transfer account using recovery code"""
    recovery_code: str = Field(..., description="One of the user's recovery codes")
    new_discord_id: str = Field(..., description="New Discord ID to transfer account to")


@router.get("/{discord_id}/info")
async def get_recovery_info(
    discord_id: str,
    current_discord_id: str = Depends(get_user_from_bot_request)
):
    """
    Get recovery information for user.
    Shows if codes exist and how many are unused.
    Accepts bot token authentication.
    """
    try:
        # Verify user is checking their own recovery info
        if discord_id != current_discord_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only check your own recovery information"
            )

        # Get user from Discord ID
        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get recovery info
        recovery_info = await RecoveryService.get_recovery_info(str(user["_id"]))

        if not recovery_info:
            return {
                "success": True,
                "has_codes": False,
                "message": "No recovery codes generated yet"
            }

        return {
            "success": True,
            **recovery_info
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recovery info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recovery info: {str(e)}"
        )


@router.post("/{discord_id}/generate")
async def generate_recovery_codes(
    discord_id: str,
    current_discord_id: str = Depends(get_user_from_bot_request)
):
    """
    Generate recovery codes for user.
    Returns the codes - ONLY TIME THEY WILL BE SHOWN.
    Accepts bot token authentication.
    """
    try:
        # Verify user is generating codes for themselves
        if discord_id != current_discord_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only generate codes for your own account"
            )

        # Get user from Discord ID
        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if codes already exist
        has_codes, _ = await RecoveryService.check_recovery_codes_exist(str(user["_id"]))

        if has_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recovery codes already exist. Use regenerate endpoint to create new ones."
            )

        # Generate codes
        success, codes, error = await RecoveryService.generate_recovery_codes(str(user["_id"]))

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error or "Failed to generate recovery codes"
            )

        return {
            "success": True,
            "codes": codes,
            "total": len(codes),
            "message": "Recovery codes generated. SAVE THESE CODES - they will not be shown again!"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate recovery codes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate codes: {str(e)}"
        )


@router.post("/{discord_id}/regenerate")
async def regenerate_recovery_codes(
    discord_id: str,
    current_discord_id: str = Depends(get_user_from_bot_request)
):
    """
    Regenerate recovery codes for user.
    Invalidates old codes and creates new ones.
    Accepts bot token authentication.
    """
    try:
        # Verify user is regenerating codes for themselves
        if discord_id != current_discord_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only regenerate codes for your own account"
            )

        # Get user from Discord ID
        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if codes exist
        has_codes, _ = await RecoveryService.check_recovery_codes_exist(str(user["_id"]))

        if not has_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No recovery codes exist yet. Use generate endpoint first."
            )

        # Regenerate codes (this will delete old ones and create new)
        success, codes, error = await RecoveryService.generate_recovery_codes(str(user["_id"]))

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error or "Failed to regenerate recovery codes"
            )

        return {
            "success": True,
            "codes": codes,
            "total": len(codes),
            "message": "Recovery codes regenerated. OLD CODES ARE NOW INVALID. Save these new codes!"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate recovery codes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate codes: {str(e)}"
        )


@router.post("/transfer")
async def transfer_account(data: TransferAccountRequest):
    """
    Transfer account to new Discord ID using recovery code.
    This endpoint does NOT require authentication (user may have lost Discord access).
    """
    try:
        # Validate and transfer account
        success, transfer_data, error = await RecoveryService.validate_and_transfer_account(
            recovery_code=data.recovery_code,
            new_discord_id=data.new_discord_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error or "Failed to transfer account"
            )

        return {
            "success": True,
            "message": "Account transferred successfully!",
            "transfer": transfer_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to transfer account: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transfer account: {str(e)}"
        )
