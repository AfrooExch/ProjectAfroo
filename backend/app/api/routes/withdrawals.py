"""
Withdrawal Routes - Automated crypto withdrawals from Afroo Wallets
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.api.dependencies import get_current_user
from app.services.withdrawal_service import WithdrawalService

router = APIRouter()


class WithdrawalCalculateRequest(BaseModel):
    """Request to calculate withdrawal fees"""
    asset: str
    amount: float = Field(gt=0, le=1000000, description="Amount must be greater than 0 and less than 1,000,000")


class WithdrawalInitiateRequest(BaseModel):
    """Request to initiate withdrawal"""
    asset: str
    amount: float = Field(gt=0, le=1000000, description="Amount must be greater than 0 and less than 1,000,000")
    to_address: str = Field(..., min_length=20, max_length=100, description="Valid blockchain address")
    memo: Optional[str] = Field(None, max_length=200, description="Optional memo/tag")


@router.post("/withdrawals/calculate-fee")
async def calculate_withdrawal_fee(
    request: WithdrawalCalculateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Calculate withdrawal fees before initiating"""
    try:
        fee_info = await WithdrawalService.calculate_withdrawal_fee(
            asset=request.asset,
            amount=request.amount
        )

        return {
            "success": True,
            "fee_info": fee_info
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/withdrawals/initiate")
async def initiate_withdrawal(
    request: WithdrawalInitiateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Initiate automated withdrawal"""
    try:
        success, message, withdrawal_data = await WithdrawalService.initiate_withdrawal(
            user_id=str(current_user["_id"]),
            asset=request.asset,
            amount=request.amount,
            to_address=request.to_address,
            memo=request.memo
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "success": True,
            "message": message,
            "withdrawal": withdrawal_data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Withdrawal failed: {str(e)}"
        )


@router.get("/withdrawals/history")
async def get_withdrawal_history(
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get user's withdrawal history"""
    try:
        history = await WithdrawalService.get_withdrawal_history(
            user_id=str(current_user["_id"]),
            limit=limit
        )

        return {
            "success": True,
            "withdrawals": history
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/withdrawals/{withdrawal_id}")
async def get_withdrawal_details(
    withdrawal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific withdrawal details"""
    try:
        withdrawal = await WithdrawalService.get_withdrawal_details(withdrawal_id)

        if not withdrawal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Withdrawal not found"
            )

        # Verify ownership
        if str(withdrawal["user_id"]) != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )

        return {
            "success": True,
            "withdrawal": withdrawal
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/withdrawals/{withdrawal_id}/cancel")
async def cancel_withdrawal(
    withdrawal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel pending withdrawal (before blockchain send)"""
    try:
        success, message = await WithdrawalService.cancel_withdrawal(
            withdrawal_id=withdrawal_id,
            user_id=str(current_user["_id"])
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
