"""
Secure Wallet Endpoints
Demonstrates proper authentication and authorization patterns
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.api.deps import (
    get_current_user,
    require_admin,
    validate_wallet_ownership,
    AuthContext
)
from app.services.wallet_service import wallet_service

router = APIRouter()


# ====================
# Request Models
# ====================

class SendRequest(BaseModel):
    """Send crypto from wallet"""
    destination_address: str
    amount: float
    asset: str
    memo: Optional[str] = None


class InternalTransferRequest(BaseModel):
    """Transfer between Discord users"""
    recipient_discord_id: str
    amount: float
    asset: str
    note: Optional[str] = None


# ====================
# Wallet Endpoints (User must own wallet)
# ====================

@router.get("/balance")
async def get_wallet_balance(
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get user's wallet balance

    Security:
    - Authenticated: User must be logged in (bot or web)
    - Authorization: User can only view their own balance
    - Validation: Roles synced automatically by bot

    The user context is provided by bot via headers:
    - X-Discord-User-ID: User's Discord ID
    - X-Discord-Roles: User's current roles
    """
    discord_id = auth.user.get("discord_id")

    # Get wallet (creates if doesn't exist)
    wallet = await wallet_service.get_or_create_wallet(discord_id)

    # Get balances
    balances = await wallet_service.get_all_balances(wallet["_id"])

    return {
        "discord_id": discord_id,
        "wallet_id": str(wallet["_id"]),
        "balances": balances,
        "total_value_usd": wallet.get("total_value_usd", 0)
    }


@router.post("/send")
async def send_from_wallet(
    request: SendRequest,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Send crypto from wallet to external address

    Security:
    - Authenticated: User must be logged in
    - Authorization: User can only send from their own wallet
    - Validation: Amount validated, sufficient balance checked
    - Audit: Transaction logged with user ID
    """
    discord_id = auth.user.get("discord_id")

    # Get wallet
    wallet = await wallet_service.get_or_create_wallet(discord_id)

    # Check balance
    balance = await wallet_service.get_balance(
        wallet_id=str(wallet["_id"]),
        asset=request.asset
    )

    if balance < request.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {balance} {request.asset}"
        )

    # Validate destination address
    if not await wallet_service.validate_address(
        address=request.destination_address,
        asset=request.asset
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid destination address"
        )

    # Process send
    transaction = await wallet_service.send_external(
        wallet_id=str(wallet["_id"]),
        discord_id=discord_id,
        destination=request.destination_address,
        amount=request.amount,
        asset=request.asset,
        memo=request.memo
    )

    return {
        "success": True,
        "transaction_id": str(transaction["_id"]),
        "status": transaction["status"],
        "amount": request.amount,
        "asset": request.asset,
        "destination": request.destination_address,
        "txid": transaction.get("blockchain_txid")
    }


@router.post("/transfer")
async def internal_transfer(
    request: InternalTransferRequest,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Transfer crypto to another Discord user

    Security:
    - Authenticated: User must be logged in
    - Authorization: User can only send from their own wallet
    - Validation:
        - Sender has sufficient balance
        - Recipient exists
        - Cannot send to self
    - Atomic: Database transaction ensures consistency
    """
    sender_discord_id = auth.user.get("discord_id")

    # Cannot send to self
    if sender_discord_id == request.recipient_discord_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot transfer to yourself"
        )

    # Check recipient exists
    from app.services.user_service import user_service
    recipient = await user_service.get_by_discord_id(request.recipient_discord_id)
    if not recipient:
        raise HTTPException(
            status_code=404,
            detail="Recipient not found"
        )

    # Get sender wallet
    sender_wallet = await wallet_service.get_or_create_wallet(sender_discord_id)

    # Check balance
    balance = await wallet_service.get_balance(
        wallet_id=str(sender_wallet["_id"]),
        asset=request.asset
    )

    if balance < request.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {balance} {request.asset}"
        )

    # Process transfer
    transaction = await wallet_service.internal_transfer(
        sender_discord_id=sender_discord_id,
        recipient_discord_id=request.recipient_discord_id,
        amount=request.amount,
        asset=request.asset,
        note=request.note
    )

    return {
        "success": True,
        "transaction_id": str(transaction["_id"]),
        "sender": sender_discord_id,
        "recipient": request.recipient_discord_id,
        "amount": request.amount,
        "asset": request.asset
    }


@router.get("/transactions")
async def get_wallet_transactions(
    limit: int = 50,
    offset: int = 0,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get user's wallet transaction history

    Security:
    - Authenticated: User must be logged in
    - Authorization: User can only view their own transactions
    """
    discord_id = auth.user.get("discord_id")

    # Get wallet
    wallet = await wallet_service.get_or_create_wallet(discord_id)

    # Get transactions
    transactions = await wallet_service.get_transactions(
        wallet_id=str(wallet["_id"]),
        limit=min(limit, 100),
        offset=offset
    )

    return {
        "transactions": transactions,
        "limit": limit,
        "offset": offset
    }


@router.get("/deposit-address/{asset}")
async def get_deposit_address(
    asset: str,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get deposit address for asset

    Security:
    - Authenticated: User must be logged in
    - Authorization: User can only get their own deposit addresses
    - Validation: Asset must be supported
    """
    discord_id = auth.user.get("discord_id")

    # Get wallet
    wallet = await wallet_service.get_or_create_wallet(discord_id)

    # Get or generate deposit address
    address = await wallet_service.get_deposit_address(
        wallet_id=str(wallet["_id"]),
        asset=asset.upper()
    )

    if not address:
        raise HTTPException(
            status_code=400,
            detail=f"Asset {asset} not supported"
        )

    return {
        "asset": asset.upper(),
        "address": address.get("address"),
        "memo": address.get("memo"),
        "qr_code": address.get("qr_code")
    }


# ====================
# Admin Endpoints (Admin only)
# ====================

@router.get("/admin/all", dependencies=[Depends(require_admin)])
async def list_all_wallets(
    skip: int = 0,
    limit: int = 100,
    auth: AuthContext = Depends(require_admin)
):
    """
    List all wallets (admin only)

    Security:
    - Authenticated: Must be logged in
    - Authorization: Must have admin role
    - Validation: Role checked against Discord role IDs
    """
    from app.core.database import get_wallets_collection

    wallets_collection = get_wallets_collection()

    # Get wallets
    cursor = wallets_collection.find({}).skip(skip).limit(min(limit, 100))
    wallets = await cursor.to_list(length=limit)

    # Get total
    total = await wallets_collection.count_documents({})

    return {
        "wallets": [
            {
                "wallet_id": str(w["_id"]),
                "owner_discord_id": w.get("owner_discord_id"),
                "total_value_usd": w.get("total_value_usd", 0),
                "created_at": w.get("created_at")
            }
            for w in wallets
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/admin/{discord_id}/wallet", dependencies=[Depends(require_admin)])
async def admin_view_wallet(
    discord_id: str,
    auth: AuthContext = Depends(require_admin)
):
    """
    View any user's wallet (admin only)

    Security:
    - Authenticated: Must be logged in
    - Authorization: Must have admin role
    - Audit: Admin action logged
    """
    # Get wallet
    wallet = await wallet_service.get_or_create_wallet(discord_id)

    # Get balances
    balances = await wallet_service.get_all_balances(str(wallet["_id"]))

    # Get transactions
    transactions = await wallet_service.get_transactions(
        wallet_id=str(wallet["_id"]),
        limit=10
    )

    # Log admin action
    from app.services.user_service import user_service
    await user_service.log_action(
        user_id=str(auth.user.get("_id")),
        action="admin.view_wallet",
        details={
            "target_discord_id": discord_id,
            "admin_discord_id": auth.user.get("discord_id")
        }
    )

    return {
        "wallet_id": str(wallet["_id"]),
        "owner_discord_id": discord_id,
        "balances": balances,
        "recent_transactions": transactions,
        "total_value_usd": wallet.get("total_value_usd", 0)
    }


@router.post("/admin/{discord_id}/freeze", dependencies=[Depends(require_admin)])
async def admin_freeze_wallet(
    discord_id: str,
    reason: str,
    auth: AuthContext = Depends(require_admin)
):
    """
    Freeze user's wallet (admin only)

    Prevents all wallet operations
    Used for security/fraud prevention

    Security:
    - Authenticated: Must be logged in
    - Authorization: Must have admin role
    - Audit: Action logged with reason
    """
    # Get wallet
    wallet = await wallet_service.get_or_create_wallet(discord_id)

    # Freeze wallet
    await wallet_service.freeze_wallet(
        wallet_id=str(wallet["_id"]),
        reason=reason,
        admin_id=auth.user.get("discord_id")
    )

    # Log action
    from app.services.user_service import user_service
    await user_service.log_action(
        user_id=str(auth.user.get("_id")),
        action="admin.freeze_wallet",
        details={
            "target_discord_id": discord_id,
            "reason": reason,
            "admin_discord_id": auth.user.get("discord_id")
        }
    )

    return {
        "success": True,
        "message": f"Wallet frozen for {discord_id}",
        "reason": reason
    }
