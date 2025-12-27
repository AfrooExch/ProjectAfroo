"""
Payout Routes - Admin management of ticket payouts (internal & external)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.api.dependencies import get_current_user, require_admin
from app.services.payout_service import PayoutService

router = APIRouter()


class InternalPayoutRequest(BaseModel):
    """Request for internal payout (from exchanger deposit wallet)"""
    ticket_id: str
    exchanger_id: str
    client_id: str
    asset: str
    amount_units: float
    to_address: str


class ExternalPayoutVerifyRequest(BaseModel):
    """Request to verify external payout (manual payment)"""
    ticket_id: str
    exchanger_id: str
    client_id: str
    asset: str
    expected_amount: float
    to_address: str
    tx_hash: str


@router.post("/admin/payouts/internal", dependencies=[Depends(require_admin)])
async def initiate_internal_payout(
    request: InternalPayoutRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Initiate internal payout - send from exchanger's deposit wallet.
    Admin only endpoint.
    """
    try:
        success, tx_hash_or_error = await PayoutService.initiate_internal_payout(
            ticket_id=request.ticket_id,
            exchanger_id=request.exchanger_id,
            client_id=request.client_id,
            asset=request.asset,
            amount_units=request.amount_units,
            to_address=request.to_address
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=tx_hash_or_error
            )

        return {
            "success": True,
            "tx_hash": tx_hash_or_error,
            "message": "Internal payout initiated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/payouts/external/verify", dependencies=[Depends(require_admin)])
async def verify_external_payout(
    request: ExternalPayoutVerifyRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Verify external payout - exchanger paid manually.
    Verifies transaction on blockchain and records payout.
    Admin only endpoint.
    """
    try:
        success, message = await PayoutService.verify_external_payout(
            ticket_id=request.ticket_id,
            exchanger_id=request.exchanger_id,
            client_id=request.client_id,
            asset=request.asset,
            expected_amount=request.expected_amount,
            to_address=request.to_address,
            tx_hash=request.tx_hash
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "success": True,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/admin/payouts/history", dependencies=[Depends(require_admin)])
async def get_payout_history(
    user_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """
    Get payout history with optional filters.
    Admin only endpoint.
    """
    try:
        history = await PayoutService.get_payout_history(
            user_id=user_id,
            ticket_id=ticket_id,
            limit=limit
        )

        return {
            "success": True,
            "payouts": history,
            "count": len(history)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/payouts/{payout_id}/complete", dependencies=[Depends(require_admin)])
async def complete_payout(
    payout_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually mark payout as complete (after blockchain confirmation).
    Usually called automatically by webhooks.
    Admin only endpoint.
    """
    try:
        success = await PayoutService.complete_payout(payout_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to complete payout"
            )

        return {
            "success": True,
            "message": "Payout marked as complete"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
