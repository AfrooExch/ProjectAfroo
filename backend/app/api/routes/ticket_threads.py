"""
Ticket Thread Routes - New thread-based ticket system
Handles exchanger threads, client threads, and payment workflows
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from app.api.dependencies import get_user_from_bot_request
from app.services.ticket_service import TicketService
from app.core.config import settings

router = APIRouter(tags=["Ticket Threads"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateExchangerThreadRequest(BaseModel):
    """Request to create exchanger thread after TOS acceptance"""
    ticket_id: str
    payment_method: str  # For role-specific visibility


class ClientInfoResponse(BaseModel):
    """Anonymous client statistics for exchanger"""
    account_age_days: Optional[int]
    exchange_count: int
    completion_rate: Optional[float]
    risk_level: str


class ConfirmReceiptRequest(BaseModel):
    """Exchanger confirms receipt of client payment"""
    confirmed: bool = True


class SelectPayoutMethodRequest(BaseModel):
    """Exchanger selects payout method"""
    method: str  # "internal" or "external"


class PayoutInternalRequest(BaseModel):
    """Internal wallet payout request"""
    currency: str  # BTC, ETH, SOL, etc.
    client_wallet: str  # Client's wallet address


class PayoutExternalRequest(BaseModel):
    """External wallet payout request"""
    txid: str  # Transaction ID
    client_wallet: str  # Client's wallet address
    currency: str  # Which crypto was sent


class ConfirmCompleteRequest(BaseModel):
    """Client confirms receipt of payout"""
    confirmed: bool = True


# ============================================================================
# Thread Management Endpoints
# ============================================================================

@router.post("/{ticket_id}/create-exchanger-thread")
async def create_exchanger_thread(
    ticket_id: str,
    request_data: CreateExchangerThreadRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Create exchanger thread after TOS acceptance
    Called AFTER TOS accept - creates hold FIRST, then thread

    Flow:
    1. Create multi-currency hold (locks funds from all exchangers)
    2. Create anonymous exchanger thread
    3. Return thread info for bot to post claim button
    """
    try:
        result = await TicketService.create_exchanger_thread(
            ticket_id=ticket_id,
            payment_method=request_data.payment_method
        )

        return {
            "success": True,
            "thread_id": result["exchanger_thread_id"],
            "hold_ids": result["hold_ids"],
            "hold_status": result["hold_status"],
            "available_exchangers": result["available_exchangers"],
            "estimated_profit": result["estimated_profit"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create exchanger thread: {str(e)}")


@router.get("/{ticket_id}/client-info")
async def get_client_info(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Get anonymous client statistics (for "Client Info" button)
    Shows risk assessment without revealing identity

    Returns:
    - Account age in days
    - Past exchange count
    - Completion rate (0.0 - 1.0)
    - Risk level (low, medium, high, unknown)
    """
    try:
        client_info = await TicketService.get_client_risk_info(ticket_id)

        return ClientInfoResponse(**client_info)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get client info: {str(e)}")


# ============================================================================
# Payment Confirmation Endpoints
# ============================================================================

@router.post("/{ticket_id}/client-sent-payment")
async def client_sent_payment(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Client marks payment as sent
    Triggers exchanger confirmation workflow (FIAT) or payout selection (CRYPTO)
    """
    try:
        result = await TicketService.mark_client_sent_payment(
            ticket_id=ticket_id,
            client_discord_id=discord_user_id
        )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "client_sent_at": result["client_sent_at"],
            "next_step": result["next_step"],  # "confirm_receipt" or "select_payout"
            "receive_method": result["receive_method"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark payment sent: {str(e)}")


@router.post("/{ticket_id}/confirm-receipt")
async def confirm_receipt(
    ticket_id: str,
    request_data: ConfirmReceiptRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Exchanger confirms received client's payment (FIAT receiving methods only)
    Unlocks payout buttons after confirmation
    """
    try:
        result = await TicketService.confirm_receipt(
            ticket_id=ticket_id,
            exchanger_discord_id=discord_user_id
        )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "exchanger_confirmed_at": result["exchanger_confirmed_receipt_at"],
            "next_step": "select_payout"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm receipt: {str(e)}")


# ============================================================================
# Payout Endpoints
# ============================================================================

@router.post("/{ticket_id}/select-payout-method")
async def select_payout_method(
    ticket_id: str,
    request_data: SelectPayoutMethodRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Exchanger selects payout method (internal or external wallet)

    Returns:
    - internal: Available crypto options from held wallets
    - external: TXID input form
    """
    try:
        result = await TicketService.select_payout_method(
            ticket_id=ticket_id,
            exchanger_discord_id=discord_user_id,
            method=request_data.method
        )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "payout_method": request_data.method,
            "options": result.get("available_cryptos") if request_data.method == "internal" else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to select payout method: {str(e)}")


@router.post("/{ticket_id}/payout-internal")
async def payout_internal(
    ticket_id: str,
    request_data: PayoutInternalRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Execute internal wallet payout
    Sends crypto from exchanger's held wallet to client's address

    Returns:
    - txid: Transaction ID
    - amount: Amount sent
    - verification_status: verified, pending, or unverified
    """
    try:
        result = await TicketService.execute_internal_payout(
            ticket_id=ticket_id,
            exchanger_discord_id=discord_user_id,
            currency=request_data.currency,
            client_wallet=request_data.client_wallet
        )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "txid": result["txid"],
            "amount": result["amount"],
            "currency": request_data.currency,
            "verification_status": result["verification_status"],
            "payout_sent_at": result["payout_sent_at"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute internal payout: {str(e)}")


@router.post("/{ticket_id}/payout-external")
async def payout_external(
    ticket_id: str,
    request_data: PayoutExternalRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Record external wallet payout
    Verifies TXID on blockchain

    Returns:
    - verification_status: verified, pending, or unverified
    """
    try:
        result = await TicketService.record_external_payout(
            ticket_id=ticket_id,
            exchanger_discord_id=discord_user_id,
            txid=request_data.txid,
            client_wallet=request_data.client_wallet,
            currency=request_data.currency
        )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "txid": request_data.txid,
            "verification_status": result["verification_status"],
            "payout_sent_at": result["payout_sent_at"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record external payout: {str(e)}")


@router.post("/{ticket_id}/confirm-complete")
async def confirm_complete(
    ticket_id: str,
    request_data: ConfirmCompleteRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Client confirms receipt of payout

    Triggers completion workflow:
    1. Releases holds with deduction
    2. Updates stats
    3. Generates transcripts
    4. Sends DMs
    5. Archives threads
    """
    try:
        result = await TicketService.confirm_complete(
            ticket_id=ticket_id,
            client_discord_id=discord_user_id
        )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": "completed",
            "completed_at": result["completed_at"],
            "profit": result["profit"],
            "server_fee": result["server_fee"],
            "transcript_url": result["transcript_url"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete ticket: {str(e)}")


# ============================================================================
# Claim Endpoint (Updated for Thread System)
# ============================================================================

@router.post("/{ticket_id}/claim-thread")
async def claim_ticket_thread(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Claim ticket in thread system

    NEW BEHAVIOR:
    - Hold already created on TOS accept
    - Just verifies exchanger has sufficient unheld balance
    - Assigns ticket to exchanger
    - Returns thread info for DM
    """
    try:
        result = await TicketService.claim_ticket_thread(
            ticket_id=ticket_id,
            exchanger_discord_id=discord_user_id
        )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "ticket_number": result["ticket_number"],
            "client_thread_id": result["client_thread_id"],
            "exchanger_thread_id": result["exchanger_thread_id"],
            "amount_held": result["amount_held"],
            "claimed_at": result["claimed_at"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to claim ticket: {str(e)}")


# ============================================================================
# Stats & Profit Calculation
# ============================================================================

@router.get("/{ticket_id}/estimated-profit")
async def get_estimated_profit(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Calculate estimated profit for exchanger

    Formula:
    - Platform fee (< $40: flat $4, >= $40: 10%, crypto-to-crypto: 5%)
    - Server fee (max($0.50, 2% of amount))
    - Profit = Platform fee - Server fee
    """
    try:
        result = await TicketService.calculate_estimated_profit(ticket_id)

        return {
            "ticket_id": ticket_id,
            "amount_usd": result["amount_usd"],
            "platform_fee": result["platform_fee"],
            "server_fee": result["server_fee"],
            "estimated_profit": result["estimated_profit"],
            "profit_percentage": result["profit_percentage"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate profit: {str(e)}")
