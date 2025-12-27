"""
Ticket Action Routes - Dashboard actions for exchange tickets
Handles client-sent, amount/fee changes, unclaim, close, payouts
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional
from pydantic import BaseModel

from app.api.dependencies import get_user_from_bot_request
from app.services.ticket_action_service import TicketActionService

router = APIRouter(tags=["Ticket Actions"])


class AmountChangeRequest(BaseModel):
    """Request to change ticket amount"""
    new_amount: float
    reason: str


class FeeChangeRequest(BaseModel):
    """Request to change ticket fee"""
    new_fee_percentage: float
    reason: str


class PayoutRequest(BaseModel):
    """External payout submission"""
    client_address: str
    tx_hash: str


@router.post("/{ticket_id}/client-sent")
async def mark_client_sent(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Client marks that they've sent their funds"""
    try:
        ticket = await TicketActionService.mark_client_sent(ticket_id, discord_user_id)

        return {
            "message": "Marked as sent successfully",
            "ticket": {
                "id": str(ticket["_id"]),
                "status": ticket["status"],
                "client_sent_at": ticket.get("client_sent_at"),
                "receiving_amount": ticket.get("receiving_amount"),
                "receive_method": ticket.get("receive_method"),
                "receive_crypto": ticket.get("receive_crypto"),
                "exchanger_discord_id": ticket.get("exchanger_discord_id")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/exchanger-confirmed")
async def exchanger_confirmed_receipt(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Exchanger confirms they received customer's fiat payment"""
    try:
        ticket = await TicketActionService.exchanger_confirmed_receipt(ticket_id, discord_user_id)

        return {
            "message": "Exchanger confirmed receipt",
            "ticket": {
                "id": str(ticket["_id"]),
                "status": ticket["status"],
                "exchanger_confirmed_at": ticket.get("exchanger_confirmed_at")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/payment-sent")
async def payment_sent(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Exchanger confirms they sent payment to customer (fiat-to-fiat)"""
    try:
        ticket = await TicketActionService.payment_sent(ticket_id, discord_user_id)

        return {
            "message": "Payment sent confirmation recorded",
            "ticket": {
                "id": str(ticket["_id"]),
                "status": ticket["status"],
                "payment_sent_at": ticket.get("payment_sent_at")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/request-amount-change")
async def request_amount_change(
    ticket_id: str,
    request_data: AmountChangeRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Request to change the ticket amount (requires both parties to agree)"""
    try:
        ticket = await TicketActionService.request_amount_change(
            ticket_id,
            discord_user_id,
            request_data.new_amount,
            request_data.reason
        )

        return {
            "message": "Amount change request created",
            "ticket": {
                "id": str(ticket["_id"]),
                "pending_amount_change": ticket.get("pending_amount_change")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/approve-amount-change")
async def approve_amount_change(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Approve pending amount change"""
    try:
        ticket = await TicketActionService.approve_amount_change(ticket_id, discord_user_id)

        return {
            "message": "Amount change approved and applied",
            "ticket": {
                "id": str(ticket["_id"]),
                "amount_usd": ticket["amount_usd"],
                "receiving_amount": ticket["receiving_amount"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/request-fee-change")
async def request_fee_change(
    ticket_id: str,
    request_data: FeeChangeRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Request to change the ticket fee (requires both parties to agree)"""
    try:
        ticket = await TicketActionService.request_fee_change(
            ticket_id,
            discord_user_id,
            request_data.new_fee_percentage,
            request_data.reason
        )

        return {
            "message": "Fee change request created",
            "ticket": {
                "id": str(ticket["_id"]),
                "pending_fee_change": ticket.get("pending_fee_change")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/approve-fee-change")
async def approve_fee_change(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Approve pending fee change"""
    try:
        ticket = await TicketActionService.approve_fee_change(ticket_id, discord_user_id)

        return {
            "message": "Fee change approved and applied",
            "ticket": {
                "id": str(ticket["_id"]),
                "fee_percentage": ticket["fee_percentage"],
                "fee_amount": ticket["fee_amount"],
                "receiving_amount": ticket["receiving_amount"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/request-unclaim")
async def request_unclaim(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Request to unclaim ticket (requires both parties to agree)"""
    try:
        ticket = await TicketActionService.request_unclaim(ticket_id, discord_user_id)

        return {
            "message": "Unclaim request created",
            "ticket": {
                "id": str(ticket["_id"]),
                "pending_unclaim": ticket.get("pending_unclaim")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/approve-unclaim")
async def approve_unclaim(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Approve unclaim - refunds hold and reopens ticket"""
    try:
        ticket = await TicketActionService.approve_unclaim(ticket_id, discord_user_id)

        # Return full ticket data for UI to repost exchange details embed
        return {
            "message": "Ticket unclaimed successfully, funds refunded",
            "ticket": {
                "id": str(ticket["_id"]),
                "ticket_id": str(ticket["_id"]),
                "ticket_number": ticket.get("ticket_number"),
                "status": ticket["status"],
                "send_method": ticket.get("send_method"),
                "receive_method": ticket.get("receive_method"),
                "send_crypto": ticket.get("send_crypto"),
                "receive_crypto": ticket.get("receive_crypto"),
                "amount_usd": ticket.get("amount_usd"),
                "fee_amount": ticket.get("fee_amount"),
                "fee_percentage": ticket.get("fee_percentage"),
                "receiving_amount": ticket.get("receiving_amount"),
                "client_discord_id": ticket.get("client_discord_id"),
                "client_username": ticket.get("client_username")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/request-close")
async def request_close_with_transcript(
    ticket_id: str,
    request: Request,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Request to close ticket with transcripts (requires both parties to agree)"""
    try:
        body = await request.json()
        reason = body.get("reason", "")

        ticket = await TicketActionService.request_close(ticket_id, discord_user_id, reason)

        return {
            "message": "Close request created",
            "ticket": {
                "id": str(ticket["_id"]),
                "pending_close": ticket.get("pending_close")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/approve-close")
async def approve_close(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Approve close request - generates transcripts and closes ticket"""
    try:
        ticket = await TicketActionService.approve_close(ticket_id, discord_user_id)

        return {
            "message": "Ticket closed successfully",
            "ticket": {
                "id": str(ticket["_id"]),
                "status": ticket["status"],
                "closed_at": ticket.get("closed_at")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/internal-payout")
async def internal_payout(
    ticket_id: str,
    request: Request,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Exchanger pays client using internal wallet (bot sends crypto)"""
    try:
        body = await request.json()
        # Support both "client_address" and "wallet_address" field names
        client_address = body.get("client_address") or body.get("wallet_address")
        # Optional: currency selection (if not provided, uses ticket's receive_crypto)
        selected_currency = body.get("currency")

        if not client_address:
            raise HTTPException(status_code=400, detail="Client address required")

        result = await TicketActionService.process_internal_payout(
            ticket_id,
            discord_user_id,
            client_address,
            selected_currency=selected_currency
        )

        ticket = result.get("ticket")
        tx_hash = result.get("tx_hash")
        tx_url = result.get("tx_url")
        asset = result.get("asset")
        amount = result.get("amount")

        return {
            "message": "Internal payout initiated",
            "tx_hash": tx_hash,
            "tx_url": tx_url,
            "asset": asset,
            "amount": amount,
            "ticket": {
                "id": str(ticket["_id"]),
                "status": ticket["status"],
                "payout_tx_hash": ticket.get("payout_tx_hash")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/external-payout")
async def external_payout(
    ticket_id: str,
    payout_data: PayoutRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Exchanger submits external payout TXID for verification"""
    try:
        ticket = await TicketActionService.process_external_payout(
            ticket_id,
            discord_user_id,
            payout_data.client_address,
            payout_data.tx_hash
        )

        return {
            "message": "External payout submitted for verification",
            "ticket": {
                "id": str(ticket["_id"]),
                "status": ticket["status"],
                "payout_tx_hash": ticket.get("payout_tx_hash"),
                "payout_verification_status": ticket.get("payout_verification_status"),
                "payout_verification_message": ticket.get("payout_verification_message")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
