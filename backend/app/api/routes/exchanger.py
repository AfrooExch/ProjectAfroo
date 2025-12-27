"""
Exchanger API Routes - V4
Endpoints for exchanger deposit management, holds, and claim limits
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Optional
from decimal import Decimal

from app.models.exchanger import (
    CreateDepositRequest,
    DepositBalanceResponse,
    ClaimLimitResponse,
    HoldFundsRequest,
    ReleaseFundsRequest,
    WithdrawRequest
)
from app.services.exchanger_service import ExchangerService, SUPPORTED_CURRENCIES
from app.core.config import settings

router = APIRouter(prefix="/api/v1/exchanger", tags=["exchanger"])


# =============================
# Helper Functions
# =============================

async def get_current_user_id(request: Request) -> str:
    """
    Extract user ID from bot-authenticated request
    Same pattern as wallet routes
    """
    # Verify bot authentication
    x_bot_token = request.headers.get("X-Bot-Token")

    if not x_bot_token or x_bot_token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Bot authentication required")

    # Extract user ID from header
    user_id = request.headers.get("X-User-ID")

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")

    return user_id


@router.post("/deposits/create", status_code=status.HTTP_201_CREATED)
async def create_deposit_wallet(
    request: CreateDepositRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Create exchanger deposit wallet for currency
    Uses V4 wallet system
    """
    try:
        deposit = await ExchangerService.create_deposit_wallet(
            user_id=user_id,
            currency=request.currency
        )

        return {
            "success": True,
            "currency": deposit.currency,
            "wallet_address": deposit.wallet_address,
            "message": f"Deposit wallet created for {deposit.currency}"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create deposit wallet: {str(e)}"
        )


@router.get("/deposits/list")
async def list_deposits(
    user_id: str = Depends(get_current_user_id)
):
    """List all deposit wallets for exchanger"""
    try:
        deposits = await ExchangerService.list_deposits(user_id)

        return {
            "success": True,
            "deposits": [
                {
                    "currency": d.currency,
                    "wallet_address": d.wallet_address,
                    "balance": d.balance,
                    "held": d.held,
                    "fee_reserved": d.fee_reserved,
                    "available": str(d.get_available_decimal()),
                    "is_active": d.is_active
                }
                for d in deposits
            ],
            "count": len(deposits)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list deposits: {str(e)}"
        )


@router.get("/deposits/with-balances")
async def get_deposits_with_usd_balances(
    ticket_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get exchanger deposits with USD balance calculations
    Optionally filter by ticket requirement (ticket_id parameter)
    Only returns deposits with sufficient balance for the ticket amount
    """
    try:
        # Get all deposits
        deposits = await ExchangerService.list_deposits(user_id)

        # Get ticket amount if ticket_id provided
        ticket_amount_usd = Decimal("0")
        if ticket_id:
            from app.core.database import get_tickets_collection
            from bson.objectid import ObjectId
            tickets = get_tickets_collection()
            ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
            if ticket:
                ticket_amount_usd = Decimal(str(ticket.get("receiving_amount", 0)))

        # Calculate USD balances for each deposit
        from app.services.price_service import price_service
        result_deposits = []

        for deposit in deposits:
            currency = deposit.currency
            balance_crypto = Decimal(deposit.balance)

            # Get USD price
            try:
                price_usd = await price_service.get_price_usd(currency)
                balance_usd = float(balance_crypto * price_usd)

                # Only include if sufficient balance (if ticket_id provided)
                if not ticket_id or Decimal(str(balance_usd)) >= ticket_amount_usd:
                    result_deposits.append({
                        "currency": currency,
                        "balance": str(balance_crypto),
                        "balance_usd": balance_usd,
                        "wallet_address": deposit.wallet_address,
                        "held": deposit.held,
                        "fee_reserved": deposit.fee_reserved,
                        "available": str(deposit.get_available_decimal())
                    })
            except Exception as e:
                # Skip deposits where price fetch fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to get price for {currency}: {e}")
                continue

        return {
            "success": True,
            "deposits": result_deposits,
            "count": len(result_deposits)
        }

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get deposits with USD balances: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deposits: {str(e)}"
        )


@router.get("/deposits/{currency}")
async def get_deposit_balance(
    currency: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get deposit balance for specific currency
    Includes available, held, and fee_reserved amounts
    """
    try:
        # Sync balance (will raise ValueError if deposit doesn't exist)
        deposit = await ExchangerService.sync_deposit_balance(user_id, currency)

        # Get USD values
        from app.services.price_service import price_service
        price_usd = await price_service.get_price_usd(currency)

        balance_usd = None
        held_usd = None
        fee_reserved_usd = None
        available_usd = None

        if price_usd:
            balance_usd = str(Decimal(deposit.balance) * price_usd)
            held_usd = str(Decimal(deposit.held) * price_usd)
            fee_reserved_usd = str(Decimal(deposit.fee_reserved) * price_usd)
            available_usd = str(deposit.get_available_decimal() * price_usd)

        return {
            "success": True,
            "balance": {
                "currency": deposit.currency,
                "balance": deposit.balance,
                "unconfirmed_balance": deposit.unconfirmed_balance,
                "held": deposit.held,
                "fee_reserved": deposit.fee_reserved,
                "available": str(deposit.get_available_decimal()),
                "balance_usd": balance_usd,
                "held_usd": held_usd,
                "fee_reserved_usd": fee_reserved_usd,
                "available_usd": available_usd,
                "wallet_address": deposit.wallet_address
            }
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deposit balance: {str(e)}"
        )


@router.post("/deposits/{currency}/sync")
async def sync_deposit_balance(
    currency: str,
    user_id: str = Depends(get_current_user_id)
):
    """Sync deposit balance from blockchain"""
    try:
        deposit = await ExchangerService.sync_deposit_balance(user_id, currency)

        return {
            "success": True,
            "currency": deposit.currency,
            "balance": deposit.balance,
            "held": deposit.held,
            "fee_reserved": deposit.fee_reserved,
            "available": str(deposit.get_available_decimal()),
            "last_synced": deposit.last_synced.isoformat() if deposit.last_synced else None
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync deposit balance: {str(e)}"
        )


@router.get("/claim-limit")
async def get_claim_limit(
    user_id: str = Depends(get_current_user_id)
):
    """
    Get claim limit information
    Shows total deposits, held amount, and remaining claim capacity
    """
    try:
        info = await ExchangerService.get_claim_limit_info(user_id)

        return {
            "success": True,
            "claim_limit": ClaimLimitResponse(**info)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get claim limit: {str(e)}"
        )


@router.post("/holds/create")
async def hold_funds(
    request: HoldFundsRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Hold funds for ticket claim
    Locks funds proportionally across deposit wallets
    """
    try:
        ticket_amount_usd = Decimal(request.ticket_amount_usd)

        # Check if can claim
        can_claim, reason, available = await ExchangerService.can_claim_ticket(
            user_id,
            ticket_amount_usd
        )

        if not can_claim:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=reason
            )

        # Create hold
        hold = await ExchangerService.hold_funds_for_ticket(
            ticket_id=request.ticket_id,
            exchanger_id=user_id,
            ticket_amount_usd=ticket_amount_usd * Decimal(str(request.hold_multiplier))
        )

        return {
            "success": True,
            "hold_id": str(hold.id),
            "ticket_id": hold.ticket_id,
            "hold_usd": hold.hold_usd,
            "status": hold.status,
            "message": f"Held ${hold.hold_usd} for ticket {request.ticket_id}"
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to hold funds: {str(e)}"
        )


@router.post("/holds/release")
async def release_funds(
    request: ReleaseFundsRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Release held funds for ticket
    Called when ticket is completed or cancelled
    """
    try:
        success = await ExchangerService.release_funds_for_ticket(request.ticket_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active hold found for ticket {request.ticket_id}"
            )

        return {
            "success": True,
            "ticket_id": request.ticket_id,
            "message": f"Released funds for ticket {request.ticket_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to release funds: {str(e)}"
        )


@router.get("/supported-currencies")
async def get_supported_currencies():
    """Get list of supported currencies for exchanger deposits"""
    return {
        "success": True,
        "currencies": SUPPORTED_CURRENCIES,
        "count": len(SUPPORTED_CURRENCIES)
    }


# ====================
# Exchanger Preferences
# ====================

@router.get("/preferences")
async def get_preferences(
    user_id: str = Depends(get_current_user_id)
):
    """Get exchanger preferences"""
    try:
        prefs = await ExchangerService.get_preferences(user_id)

        # Convert ObjectId to string
        if prefs.get("_id"):
            prefs["_id"] = str(prefs["_id"])

        return {
            "success": True,
            "preferences": prefs
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get preferences: {str(e)}"
        )


@router.put("/preferences")
async def update_preferences(
    request: dict,
    user_id: str = Depends(get_current_user_id)
):
    """Update exchanger preferences"""
    try:
        prefs = await ExchangerService.update_preferences(user_id, request)

        # Convert ObjectId to string
        if prefs.get("_id"):
            prefs["_id"] = str(prefs["_id"])

        return {
            "success": True,
            "preferences": prefs
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update preferences: {str(e)}"
        )


# ====================
# Exchanger Questions
# ====================

@router.get("/questions/preset")
async def get_preset_questions():
    """Get list of preset questions"""
    from app.services.exchanger_constants import get_preset_questions

    questions = get_preset_questions()

    return {
        "success": True,
        "questions": questions,
        "count": len(questions)
    }


@router.get("/questions/tickets")
async def get_awaiting_claim_tickets(
    limit: int = 25,
    user_id: str = Depends(get_current_user_id)
):
    """Get tickets awaiting claim for asking questions"""
    try:
        tickets = await ExchangerService.get_awaiting_claim_tickets(limit=limit)

        # Convert ObjectIds to strings
        for ticket in tickets:
            if ticket.get("_id"):
                ticket["_id"] = str(ticket["_id"])

        return {
            "success": True,
            "tickets": tickets,
            "count": len(tickets)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tickets: {str(e)}"
        )


@router.post("/questions/ask")
async def ask_question(
    request: dict,
    user_id: str = Depends(get_current_user_id)
):
    """Ask anonymous question on ticket"""
    try:
        question = await ExchangerService.ask_question(
            exchanger_id=user_id,
            ticket_id=request.get("ticket_id"),
            question_text=request.get("question_text"),
            question_type=request.get("question_type", "preset"),
            alt_payment_method=request.get("alt_payment_method"),
            alt_amount_usd=request.get("alt_amount_usd")
        )

        # Convert ObjectId to string
        if question.get("_id"):
            question["_id"] = str(question["_id"])

        return {
            "success": True,
            "question": question,
            "message": "Question posted successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ask question: {str(e)}"
        )


@router.post("/withdraw")
async def withdraw_funds(
    request: WithdrawRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Withdraw exchanger funds - ONLY free funds allowed
    Network fee calculated at withdrawal time
    Server fees already reserved in fee_reserved field
    """
    try:
        result = await ExchangerService.withdraw_exchanger_funds(
            user_id=user_id,
            currency=request.currency,
            amount=request.amount,
            to_address=request.to_address
        )

        # Unpack result - handle both old and new formats
        if len(result) == 5:
            success, message, tx_hash, transaction, is_system_error = result
        else:
            success, message, tx_hash, transaction = result
            is_system_error = False

        if not success:
            # Use 500 for system errors (like decryption failure), 400 for user input errors
            status_code = (
                status.HTTP_500_INTERNAL_SERVER_ERROR if is_system_error
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(
                status_code=status_code,
                detail=message
            )

        return {
            "success": True,
            "tx_hash": tx_hash,
            "currency": request.currency,
            "amount": transaction["amount"],
            "network_fee": transaction["network_fee"],
            "message": f"Withdrawal initiated for {request.currency}"
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exchanger withdrawal error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process withdrawal: {str(e)}"
        )


@router.get("/history")
async def get_history(
    currency: Optional[str] = None,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id)
):
    """Get exchanger transaction history"""
    try:
        transactions = await ExchangerService.get_transaction_history(
            user_id=user_id,
            currency=currency,
            limit=min(limit, 100)  # Max 100
        )

        # Convert ObjectId to string
        for tx in transactions:
            tx["_id"] = str(tx["_id"])

        return {
            "success": True,
            "transactions": transactions,
            "count": len(transactions)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history: {str(e)}"
        )


# ====================
# Premade Messages
# ====================

@router.get("/premades")
async def get_premades(
    user_id: str = Depends(get_current_user_id)
):
    """Get all premade messages for exchanger"""
    try:
        premades = await ExchangerService.get_premades(user_id)

        return {
            "success": True,
            "premades": premades,
            "count": len(premades)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get premades: {str(e)}"
        )


@router.post("/premades")
async def create_premade(
    request: dict,
    user_id: str = Depends(get_current_user_id)
):
    """Create a new premade message"""
    try:
        name = request.get("name")
        content = request.get("content")

        if not name or not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name and content are required"
            )

        # Check for duplicates
        premades = await ExchangerService.get_premades(user_id)
        if any(p["name"] == name for p in premades):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Premade with name '{name}' already exists"
            )

        premade = await ExchangerService.create_premade(user_id, name, content)

        return {
            "success": True,
            "premade": premade,
            "message": f"Premade '{name}' created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create premade: {str(e)}"
        )


@router.delete("/premades/{name}")
async def delete_premade(
    name: str,
    user_id: str = Depends(get_current_user_id)
):
    """Delete a premade message by name"""
    try:
        success = await ExchangerService.delete_premade(user_id, name)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Premade '{name}' not found"
            )

        return {
            "success": True,
            "message": f"Premade '{name}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete premade: {str(e)}"
        )
