"""
Afroo Wallet API Routes
V4 custodial wallet system for users
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.afroo_wallet_service import AfrooWalletService
from app.api.dependencies import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/afroo-wallets", tags=["afroo_wallets"])


class WalletCreate(BaseModel):
    asset: str


class InternalTransfer(BaseModel):
    to_user_id: str
    asset: str
    amount: float = Field(gt=0, le=1000000, description="Amount must be greater than 0 and less than 1,000,000")


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_wallet(
    data: WalletCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create Afroo wallet for asset"""
    try:
        wallet = await AfrooWalletService.create_wallet(
            user_id=str(current_user["_id"]),
            asset=data.asset
        )

        # Serialize ObjectIds
        wallet["_id"] = str(wallet["_id"])
        wallet["user_id"] = str(wallet["user_id"])

        return {
            "success": True,
            "wallet": wallet,
            "message": f"Afroo wallet created for {data.asset}"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create wallet: {str(e)}"
        )


@router.get("/list")
async def list_wallets(
    current_user: dict = Depends(get_current_user)
):
    """List all Afroo wallets for current user"""
    try:
        wallets = await AfrooWalletService.list_wallets(
            user_id=str(current_user["_id"])
        )

        # Serialize ObjectIds
        for wallet in wallets:
            wallet["_id"] = str(wallet["_id"])
            wallet["user_id"] = str(wallet["user_id"])

        return {
            "success": True,
            "wallets": wallets,
            "count": len(wallets)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list wallets: {str(e)}"
        )


@router.get("/balance/{asset}")
async def get_balance(
    asset: str,
    current_user: dict = Depends(get_current_user)
):
    """Get balance for specific asset"""
    try:
        balance = await AfrooWalletService.get_balance(
            user_id=str(current_user["_id"]),
            asset=asset
        )

        return {
            "success": True,
            "balance": balance
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get balance: {str(e)}"
        )


@router.post("/transfer")
async def internal_transfer(
    data: InternalTransfer,
    current_user: dict = Depends(get_current_user)
):
    """
    Internal transfer to another user.
    Instant and free - no blockchain transaction.
    """
    try:
        result = await AfrooWalletService.internal_transfer(
            from_user_id=str(current_user["_id"]),
            to_user_id=data.to_user_id,
            asset=data.asset,
            amount=data.amount
        )

        return {
            "success": True,
            "transfer": result,
            "message": f"Transferred {data.amount} {data.asset}"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transfer: {str(e)}"
        )


@router.get("/deposit-address/{asset}")
async def get_deposit_address(
    asset: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get deposit address for funding Afroo wallet.
    Returns platform address - deposits credited after confirmation.
    """
    # Get platform deposit address from environment variables
    try:
        address = settings.get_admin_wallet(asset)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Asset {asset} not supported: {e}"
        )

    return {
        "success": True,
        "asset": asset,
        "address": address,
        "note": "Deposits will be credited after blockchain confirmation"
    }
