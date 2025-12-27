"""
Escrow / AutoMM API Routes
P2P cryptocurrency escrow system
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.api.deps import get_current_user_bot, AuthContext
from app.core.database import get_database
from app.services.automm_service import AutoMMService

router = APIRouter()


# ============================================================================
# AutoMM P2P Escrow Models
# ============================================================================

class AutoMMCreateRequest(BaseModel):
    party1_id: str = Field(..., description="Discord ID of party 1")
    party1_crypto: str = Field(..., description="Cryptocurrency party 1 is sending")
    party2_id: str = Field(..., description="Discord ID of party 2")
    party2_crypto: str = Field(..., description="Cryptocurrency party 2 is sending")
    channel_id: str = Field(..., description="Discord channel ID for this trade")


class AutoMMCompleteRequest(BaseModel):
    party1_destination: Optional[str] = Field(None, description="Destination address for party 1")
    party2_destination: Optional[str] = Field(None, description="Destination address for party 2")


class BuyerEscrowCreateRequest(BaseModel):
    buyer_id: str = Field(..., description="Discord ID of buyer")
    seller_id: str = Field(..., description="Discord ID of seller")
    amount: float = Field(..., gt=0, description="Amount buyer will pay")
    crypto: str = Field(..., description="Cryptocurrency (BTC, ETH, etc.)")
    service_description: str = Field(..., description="What buyer is purchasing")
    channel_id: str = Field(..., description="Discord channel ID")


class ReleaseFundsRequest(BaseModel):
    seller_address: str = Field(..., description="Seller's wallet address to receive funds")


# ============================================================================
# AutoMM Buyer-Protection Escrow Endpoints (V4)
# ============================================================================

@router.post("/automm/create-buyer-escrow")
async def create_buyer_escrow_endpoint(
    data: BuyerEscrowCreateRequest,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """
    Create buyer-protection escrow with single wallet for buyer deposit.

    Returns escrow_id and deposit_address for buyer.
    """
    try:
        result = await AutoMMService.create_buyer_escrow(
            buyer_id=data.buyer_id,
            seller_id=data.seller_id,
            amount=data.amount,
            crypto=data.crypto,
            service_description=data.service_description,
            channel_id=data.channel_id
        )

        return {
            "success": True,
            **result
        }

    except Exception as e:
        raise HTTPException(500, f"Failed to create escrow: {str(e)}")


@router.get("/automm/{escrow_id}/check-deposit")
async def check_buyer_deposit(
    escrow_id: str,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """
    Check if buyer has deposited funds to escrow wallet.

    Returns status (not_received, pending_confirmation, confirmed) and balance.
    """
    try:
        result = await AutoMMService.check_deposit(escrow_id)

        return {
            "success": True,
            **result
        }

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to check deposit: {str(e)}")


@router.post("/automm/{escrow_id}/release")
async def release_escrow_funds(
    escrow_id: str,
    data: ReleaseFundsRequest,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """
    Release funds from escrow to seller's wallet.

    Buyer triggers this after receiving service.
    """
    try:
        result = await AutoMMService.release_funds(
            escrow_id=escrow_id,
            seller_address=data.seller_address
        )

        return {
            "success": True,
            **result
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to release funds: {str(e)}")


@router.post("/automm/{escrow_id}/request-cancel")
async def request_cancel_escrow(
    escrow_id: str,
    data: dict,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """
    Request to cancel escrow. Both parties must approve.

    Tracks which parties have approved cancellation.
    """
    try:
        user_id = data.get("user_id")
        if not user_id:
            raise HTTPException(400, "Missing user_id")

        result = await AutoMMService.request_cancel(
            escrow_id=escrow_id,
            user_id=user_id
        )

        return {
            "success": True,
            **result
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to request cancel: {str(e)}")


class RefundRequest(BaseModel):
    buyer_address: str = Field(..., description="Buyer's wallet address for refund")


@router.post("/automm/{escrow_id}/refund")
async def refund_escrow(
    escrow_id: str,
    data: RefundRequest,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """
    Process refund to buyer after both parties agree to cancel.

    Returns funds from escrow wallet to buyer's wallet.
    """
    try:
        result = await AutoMMService.process_refund(
            escrow_id=escrow_id,
            buyer_address=data.buyer_address
        )

        return {
            "success": True,
            **result
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to process refund: {str(e)}")


# ============================================================================
# AutoMM P2P Swap Escrow Endpoints (Legacy - V4)
# ============================================================================

@router.post("/automm/create")
async def create_automm_escrow(
    data: AutoMMCreateRequest,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """
    Create P2P escrow trade with temporary wallets for both parties.

    Returns escrow_id and wallet addresses for both parties.
    """
    try:
        result = await AutoMMService.create_escrow(
            party1_id=data.party1_id,
            party1_crypto=data.party1_crypto,
            party2_id=data.party2_id,
            party2_crypto=data.party2_crypto,
            channel_id=data.channel_id
        )

        return {
            "success": True,
            **result
        }

    except Exception as e:
        raise HTTPException(500, f"Failed to create escrow: {str(e)}")


@router.get("/automm/{escrow_id}/check")
async def check_automm_blockchain(
    escrow_id: str,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """
    Check blockchain status for both parties' escrow wallets.

    Returns status (not_received, pending_confirmation, confirmed) and balances.
    """
    try:
        result = await AutoMMService.check_blockchain_status(escrow_id)

        return {
            "success": True,
            **result
        }

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to check blockchain: {str(e)}")


@router.post("/automm/{escrow_id}/complete")
async def complete_automm_escrow(
    escrow_id: str,
    data: AutoMMCompleteRequest = AutoMMCompleteRequest(),
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """
    Complete escrow transaction.

    - For buyer-protection escrow: Seller confirms receipt (final step)
    - For P2P swap escrow: Release funds to both parties (if addresses provided)
    """
    try:
        # Get escrow to determine type
        from bson import ObjectId
        escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

        if not escrow:
            raise HTTPException(404, "Escrow not found")

        # Check escrow type
        if escrow.get("type") == "buyer_protection":
            # Buyer-protection: Seller confirms receipt
            result = await AutoMMService.complete_escrow_transaction(escrow_id)
        else:
            # P2P swap: Release funds to both parties
            result = await AutoMMService.complete_escrow(
                escrow_id=escrow_id,
                party1_destination=data.party1_destination,
                party2_destination=data.party2_destination
            )

        return {
            "success": True,
            **result
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to complete escrow: {str(e)}")


@router.get("/automm/{escrow_id}")
async def get_automm_escrow(
    escrow_id: str,
    auth: AuthContext = Depends(get_current_user_bot)
):
    """Get escrow details by ID"""
    try:
        escrow = await AutoMMService.get_escrow(escrow_id)

        # Check if user is party to escrow or admin
        user_id = auth.user.get("discord_id") or str(auth.user.get("_id"))

        # Handle both buyer-protection and P2P swap escrows
        if escrow.get("type") == "buyer_protection":
            # Buyer-protection escrow: check buyer_id and seller_id
            if user_id not in [escrow.get("buyer_id"), escrow.get("seller_id")] and not auth.is_admin:
                raise HTTPException(403, "Not authorized to view this escrow")
        else:
            # P2P swap escrow: check party1_id and party2_id
            if user_id not in [escrow.get("party1_id"), escrow.get("party2_id")] and not auth.is_admin:
                raise HTTPException(403, "Not authorized to view this escrow")

        return {
            "success": True,
            "escrow": escrow
        }

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to get escrow: {str(e)}")


# ============================================================================
# Legacy Escrow Endpoints (V3 Compatibility)
# ============================================================================


@router.post("/escrow")
async def create_escrow(
    asset: str,
    amount: float,
    recipient_id: str,
    terms: str,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Create escrow transaction"""
    escrow_data = {
        "creator_id": auth.user["discord_id"],
        "creator_name": auth.user.get("username", "Unknown"),
        "recipient_id": recipient_id,
        "asset": asset.upper(),
        "amount": amount,
        "terms": terms,
        "status": "pending_deposit",  # pending_deposit, active, completed, cancelled, disputed
        "deposit_address": f"GENERATE_ADDRESS_{asset}",  # TODO: Generate real address
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "events": [
            {
                "type": "created",
                "timestamp": datetime.utcnow(),
                "user_id": auth.user["discord_id"]
            }
        ]
    }

    result = await db.escrow.insert_one(escrow_data)
    escrow_data["_id"] = str(result.inserted_id)
    escrow_data["escrow_id"] = str(result.inserted_id)

    return {"success": True, "escrow": escrow_data}


@router.get("/escrow/{escrow_id}")
async def get_escrow(
    escrow_id: str,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Get escrow by ID"""
    from bson import ObjectId

    escrow = await db.escrow.find_one({"_id": ObjectId(escrow_id)})
    if not escrow:
        raise HTTPException(404, "Escrow not found")

    # Check if user is party to escrow or admin
    user_id = auth.user["discord_id"]
    if user_id not in [escrow["creator_id"], escrow["recipient_id"]] and not auth.is_admin:
        raise HTTPException(403, "Not authorized")

    escrow["_id"] = str(escrow["_id"])
    return escrow


@router.post("/escrow/{escrow_id}/complete")
async def complete_escrow(
    escrow_id: str,
    notes: Optional[str] = None,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Complete escrow and release funds"""
    from bson import ObjectId

    escrow = await db.escrow.find_one({"_id": ObjectId(escrow_id)})
    if not escrow:
        raise HTTPException(404, "Escrow not found")

    # Only creator or admin can complete
    if escrow["creator_id"] != auth.user["discord_id"] and not auth.is_admin:
        raise HTTPException(403, "Only creator or admin can complete")

    result = await db.escrow.update_one(
        {"_id": ObjectId(escrow_id)},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "completed_by": auth.user["discord_id"],
                "completion_notes": notes
            },
            "$push": {
                "events": {
                    "type": "completed",
                    "timestamp": datetime.utcnow(),
                    "user_id": auth.user["discord_id"],
                    "notes": notes
                }
            }
        }
    )

    return {"success": True, "modified": result.modified_count}


@router.post("/escrow/{escrow_id}/cancel")
async def cancel_escrow(
    escrow_id: str,
    reason: str,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Cancel escrow and refund"""
    from bson import ObjectId

    escrow = await db.escrow.find_one({"_id": ObjectId(escrow_id)})
    if not escrow:
        raise HTTPException(404, "Escrow not found")

    # Either party or admin can cancel
    user_id = auth.user["discord_id"]
    if user_id not in [escrow["creator_id"], escrow["recipient_id"]] and not auth.is_admin:
        raise HTTPException(403, "Not authorized to cancel")

    result = await db.escrow.update_one(
        {"_id": ObjectId(escrow_id)},
        {
            "$set": {
                "status": "cancelled",
                "cancelled_at": datetime.utcnow(),
                "cancelled_by": user_id,
                "cancel_reason": reason
            },
            "$push": {
                "events": {
                    "type": "cancelled",
                    "timestamp": datetime.utcnow(),
                    "user_id": user_id,
                    "reason": reason
                }
            }
        }
    )

    return {"success": True, "modified": result.modified_count}


@router.post("/escrow/{escrow_id}/dispute")
async def dispute_escrow(
    escrow_id: str,
    reason: str,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Dispute escrow - opens admin ticket"""
    from bson import ObjectId

    escrow = await db.escrow.find_one({"_id": ObjectId(escrow_id)})
    if not escrow:
        raise HTTPException(404, "Escrow not found")

    # Either party can dispute
    user_id = auth.user["discord_id"]
    if user_id not in [escrow["creator_id"], escrow["recipient_id"]]:
        raise HTTPException(403, "Not authorized to dispute")

    result = await db.escrow.update_one(
        {"_id": ObjectId(escrow_id)},
        {
            "$set": {
                "status": "disputed",
                "disputed_at": datetime.utcnow(),
                "disputed_by": user_id,
                "dispute_reason": reason
            },
            "$push": {
                "events": {
                    "type": "disputed",
                    "timestamp": datetime.utcnow(),
                    "user_id": user_id,
                    "reason": reason
                }
            }
        }
    )

    return {"success": True, "modified": result.modified_count, "message": "Dispute opened - admin will review"}
