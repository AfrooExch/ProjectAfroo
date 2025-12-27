"""
Admin Routes for AutoMM and Swaps
HEAD ADMIN & ASSISTANT ADMIN ONLY
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.api.dependencies import require_assistant_admin_or_higher_bot
from app.core.database import get_database
from app.core.encryption import get_encryption_service

router = APIRouter(tags=["Admin - AutoMM & Swaps"])
logger = logging.getLogger(__name__)


@router.get("/automm/search/{mm_id}")
async def search_automm_by_mm_id(
    mm_id: str,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot),
    db = Depends(get_database)
):
    """
    Search for AutoMM escrow by MM ID (short ID like 9362C5D8)
    HEAD ADMIN & ASSISTANT ADMIN ONLY
    """
    try:
        # Try to find by mm_id field first
        escrow = await db.automm_escrow.find_one({"mm_id": mm_id.upper()})

        if escrow:
            from app.services.automm_service import serialize_escrow
            return {
                "success": True,
                "escrow": serialize_escrow(escrow)
            }

        # Try as full ObjectId
        try:
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(mm_id)})
            if escrow:
                from app.services.automm_service import serialize_escrow
                return {
                    "success": True,
                    "escrow": serialize_escrow(escrow)
                }
        except:
            pass

        raise HTTPException(status_code=404, detail=f"AutoMM escrow {mm_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search AutoMM: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search AutoMM")


@router.get("/automm/{escrow_id}/reveal-key")
async def reveal_automm_private_key(
    escrow_id: str,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot),
    db = Depends(get_database)
):
    """
    Reveal AutoMM escrow private key for dispute resolution
    HEAD ADMIN & ASSISTANT ADMIN ONLY
    """
    try:
        # Try to find by mm_id first (short ID like 9362C5D8)
        escrow = await db.automm_escrow.find_one({"mm_id": escrow_id.upper()})

        # If not found, try as ObjectId
        if not escrow:
            try:
                escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})
            except:
                pass

        if not escrow:
            raise HTTPException(status_code=404, detail="AutoMM escrow not found")

        encrypted_key = escrow.get("encrypted_key")

        if not encrypted_key:
            raise HTTPException(status_code=404, detail="No private key found for this escrow")

        # Decrypt private key
        encryption_service = get_encryption_service()
        try:
            private_key = encryption_service.decrypt_private_key(encrypted_key)
        except Exception as e:
            logger.error(f"Failed to decrypt AutoMM key for escrow {escrow_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt private key")

        # Log critical action
        logger.critical(
            f"ADMIN {admin_id} revealed private key for AutoMM escrow {escrow_id} "
            f"(MM#{escrow.get('mm_id')}) - Status: {escrow.get('status')}"
        )

        return {
            "success": True,
            "private_key": private_key,
            "escrow_id": str(escrow["_id"]),
            "mm_id": escrow.get("mm_id"),
            "crypto": escrow.get("crypto"),
            "deposit_address": escrow.get("deposit_address"),
            "balance": escrow.get("balance", 0),
            "status": escrow.get("status")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reveal AutoMM key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reveal private key")


@router.get("/swaps/{swap_id}")
async def get_swap_details_admin(
    swap_id: str,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot),
    db = Depends(get_database)
):
    """
    Get swap details (admin - bypasses ownership check)
    HEAD ADMIN & ASSISTANT ADMIN ONLY
    """
    try:
        # Get swap from database
        swap = await db.afroo_swaps.find_one({"_id": ObjectId(swap_id)})

        if not swap:
            raise HTTPException(status_code=404, detail="Swap not found")

        # Convert ObjectId to string for JSON serialization
        swap["_id"] = str(swap["_id"])
        if "user_id" in swap and isinstance(swap["user_id"], ObjectId):
            swap["user_id"] = str(swap["user_id"])

        # Convert datetime fields to ISO format
        datetime_fields = ["created_at", "updated_at", "completed_at"]
        for field in datetime_fields:
            if field in swap and swap[field]:
                swap[field] = swap[field].isoformat()

        logger.info(f"Admin {admin_id} viewed swap details for {swap_id}")

        return {
            "success": True,
            "swap": swap
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get swap details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get swap details")


@router.get("/swaps/{swap_id}/external-status")
async def get_swap_external_status(
    swap_id: str,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot),
    db = Depends(get_database)
):
    """
    Get external ChangeNOW status for a swap
    HEAD ADMIN & ASSISTANT ADMIN ONLY
    """
    try:
        # Get swap from database
        swap = await db.afroo_swaps.find_one({"_id": ObjectId(swap_id)})

        if not swap:
            raise HTTPException(status_code=404, detail="Swap not found")

        changenow_id = swap.get("changenow_exchange_id")

        if not changenow_id:
            return {
                "success": True,
                "external_data": None,
                "message": "No ChangeNOW exchange ID found"
            }

        # Get ChangeNOW status
        from app.services.changenow_service import ChangeNowService

        try:
            status_data = await ChangeNowService.get_exchange_status(changenow_id)

            logger.info(f"Admin {admin_id} viewed external status for swap {swap_id}")

            return {
                "success": True,
                "external_data": status_data,
                "changenow_id": changenow_id
            }

        except Exception as e:
            logger.error(f"Failed to get ChangeNOW status for {changenow_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to get ChangeNOW status: {str(e)}",
                "changenow_id": changenow_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get swap external status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get external status")
