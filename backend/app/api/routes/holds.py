"""
Hold API Routes
Endpoints for fund locking/escrow in ticket system
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models.hold import HoldCreate, HoldRelease, HoldRefund
from app.services.hold_service import HoldService
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/holds", tags=["holds"])


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_hold(
    data: HoldCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create fund hold for ticket.
    Locks funds when exchanger claims a ticket.
    """
    try:
        hold = await HoldService.create_hold(
            ticket_id=data.ticket_id,
            user_id=str(current_user["_id"]),
            asset=data.asset,
            amount_units=data.amount_units,
            amount_usd=data.amount_usd
        )

        # Serialize ObjectId fields
        hold["_id"] = str(hold["_id"])
        hold["ticket_id"] = str(hold["ticket_id"])
        hold["user_id"] = str(hold["user_id"])

        return {
            "success": True,
            "hold": hold,
            "message": "Funds locked for ticket"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create hold: {str(e)}"
        )


@router.post("/release")
async def release_hold(
    data: HoldRelease,
    current_user: dict = Depends(get_current_user)
):
    """
    Release hold - complete ticket.
    Unlocks funds, deducts balance + platform fee.
    """
    try:
        hold = await HoldService.release_hold(
            hold_id=data.hold_id,
            deduct_fee=data.deduct_fee
        )

        # Serialize ObjectId fields
        hold["_id"] = str(hold["_id"])
        hold["ticket_id"] = str(hold["ticket_id"])
        hold["user_id"] = str(hold["user_id"])

        return {
            "success": True,
            "hold": hold,
            "message": "Hold released, funds deducted"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to release hold: {str(e)}"
        )


@router.post("/refund")
async def refund_hold(
    data: HoldRefund,
    current_user: dict = Depends(get_current_user)
):
    """
    Refund hold - cancel ticket.
    Unlocks funds, no deduction.
    """
    try:
        hold = await HoldService.refund_hold(
            hold_id=data.hold_id
        )

        # Serialize ObjectId fields
        hold["_id"] = str(hold["_id"])
        hold["ticket_id"] = str(hold["ticket_id"])
        hold["user_id"] = str(hold["user_id"])

        return {
            "success": True,
            "hold": hold,
            "message": "Hold refunded, funds unlocked"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refund hold: {str(e)}"
        )


@router.get("/active")
async def get_active_holds(
    current_user: dict = Depends(get_current_user)
):
    """
    Get active holds for current user.
    """
    try:
        holds = await HoldService.get_active_holds(
            user_id=str(current_user["_id"])
        )

        # Serialize ObjectId fields
        for hold in holds:
            hold["_id"] = str(hold["_id"])
            hold["ticket_id"] = str(hold["ticket_id"])
            hold["user_id"] = str(hold["user_id"])

        return {
            "success": True,
            "holds": holds,
            "count": len(holds)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active holds: {str(e)}"
        )


@router.get("/by-ticket/{ticket_id}")
async def get_hold_by_ticket(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get hold by ticket ID.
    """
    try:
        hold = await HoldService.get_hold_by_ticket(ticket_id)

        if not hold:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No hold found for ticket {ticket_id}"
            )

        # Serialize ObjectId fields
        hold["_id"] = str(hold["_id"])
        hold["ticket_id"] = str(hold["ticket_id"])
        hold["user_id"] = str(hold["user_id"])

        return {
            "success": True,
            "hold": hold
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get hold: {str(e)}"
        )
