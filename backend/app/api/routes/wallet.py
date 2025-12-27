"""
Wallet API Routes - Complete cryptocurrency wallet system
Handles wallet generation, deposits, withdrawals, transactions, and webhooks
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query
from typing import Optional
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field
import hmac
import hashlib
import logging

from app.core.config import settings
from app.services.wallet_service import get_wallet_service
from app.models.wallet import SUPPORTED_CURRENCIES, get_currency_name
from app.api.deps import get_current_user, AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet", tags=["Wallet"])


# =============================
# Request/Response Models
# =============================

class GenerateWalletRequest(BaseModel):
    """Request to generate wallet"""
    currency: str = Field(..., description="Currency code (BTC, ETH, USDC-SOL, etc.)")


class WithdrawRequest(BaseModel):
    """Request to withdraw funds"""
    to_address: str = Field(..., description="Destination address")
    amount: str = Field(..., description="Withdrawal amount")
    network_fee: Optional[str] = Field(None, description="Pre-calculated network fee (for max withdrawals)")
    server_fee: Optional[str] = Field(None, description="Pre-calculated server fee (for max withdrawals)")
    total_deducted: Optional[str] = Field(None, description="Pre-calculated total deducted (for max withdrawals)")


class TatumWebhookPayload(BaseModel):
    """Tatum webhook payload"""
    subscriptionType: str
    transactionId: str
    address: str
    amount: str
    currency: str
    blockNumber: Optional[int] = None
    txId: Optional[str] = None


# =============================
# Helper Functions
# =============================


def verify_tatum_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Tatum webhook HMAC signature

    Args:
        payload: Raw request body
        signature: Signature from header

    Returns:
        True if signature is valid
    """
    try:
        expected = hmac.new(
            settings.TATUM_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error(f"Failed to verify Tatum signature: {e}")
        return False


# =============================
# Wallet Endpoints
# =============================

@router.post("/{currency}/generate")
async def generate_wallet(
    currency: str,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Generate new wallet for user

    Creates wallet, balance record, and subscribes to deposit webhooks
    """
    try:
        user_id = auth.user.get("discord_id")
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported currency. Supported: {', '.join(SUPPORTED_CURRENCIES)}"
            )

        wallet_service = get_wallet_service()
        wallet_data = await wallet_service.create_wallet(user_id, currency)

        return {
            "success": True,
            "message": f"{get_currency_name(currency)} wallet created successfully",
            "data": wallet_data
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate wallet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate wallet")


@router.get("/portfolio")
async def get_portfolio(
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get all balances (portfolio view)

    Returns balances for all currencies the user holds
    """
    try:
        user_id = auth.user.get("discord_id")
        logger.info(f"Portfolio request for user: {user_id}")
        wallet_service = get_wallet_service()
        logger.info("Got wallet service instance")
        balances = await wallet_service.get_portfolio(user_id)
        logger.info(f"Got {len(balances)} balances")

        return {
            "success": True,
            "data": {
                "balances": balances,
                "currencies_held": len(balances)
            }
        }

    except ValueError as e:
        logger.error(f"ValueError in portfolio: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")


@router.get("/{currency}")
async def get_wallet(
    currency: str,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get wallet information for user

    Returns wallet address, balance, and status
    """
    try:
        user_id = auth.user.get("discord_id")
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")

        wallet_service = get_wallet_service()
        wallet_data = await wallet_service.get_wallet(user_id, currency)

        if not wallet_data:
            raise HTTPException(
                status_code=404,
                detail=f"No {currency} wallet found. Generate one first."
            )

        return {
            "success": True,
            "data": wallet_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get wallet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch wallet")


@router.get("/{currency}/balance")
async def get_balance(
    currency: str,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get balance for wallet

    Returns available, locked, and pending balances
    """
    try:
        user_id = auth.user.get("discord_id")
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")

        wallet_service = get_wallet_service()
        balance = await wallet_service.get_balance(user_id, currency)

        return {
            "success": True,
            "data": {
                "currency": currency,
                "balance": str(balance)
            }
        }

    except Exception as e:
        logger.error(f"Failed to get balance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch balance")


@router.post("/{currency}/sync")
async def sync_balance(
    currency: str,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Sync balance with blockchain

    Fetches latest balance from blockchain and updates database
    """
    try:
        user_id = auth.user.get("discord_id")
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")

        wallet_service = get_wallet_service()
        sync_data = await wallet_service.sync_balance(user_id, currency)

        return {
            "success": True,
            "message": "Balance synced successfully",
            "data": sync_data
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to sync balance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to sync balance")


@router.post("/{currency}/withdraw")
async def withdraw(
    currency: str,
    request_data: WithdrawRequest,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Withdraw funds from wallet

    Validates balance, calculates fees, and broadcasts transaction
    """
    try:
        user_id = auth.user.get("discord_id")
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")

        # Parse amount
        try:
            amount = Decimal(request_data.amount)
        except:
            raise HTTPException(status_code=400, detail="Invalid amount format")

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        wallet_service = get_wallet_service()

        # Parse precomputed fees if provided (for max withdrawals)
        precomputed_network_fee = None
        precomputed_server_fee = None
        precomputed_total = None

        if request_data.network_fee and request_data.server_fee and request_data.total_deducted:
            try:
                precomputed_network_fee = Decimal(request_data.network_fee)
                precomputed_server_fee = Decimal(request_data.server_fee)
                precomputed_total = Decimal(request_data.total_deducted)
                logger.info(f"Withdrawal with precomputed fees: network={precomputed_network_fee}, server={precomputed_server_fee}, total={precomputed_total}")
            except:
                logger.warning("Failed to parse precomputed fees, will recalculate")

        # Process withdrawal
        tx_data = await wallet_service.withdraw(
            user_id,
            currency,
            request_data.to_address,
            amount,
            precomputed_network_fee=precomputed_network_fee,
            precomputed_server_fee=precomputed_server_fee,
            precomputed_total=precomputed_total
        )

        return {
            "success": True,
            "message": "Withdrawal initiated successfully",
            "data": tx_data
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Withdrawal failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Withdrawal failed")


@router.post("/{currency}/withdraw/preview")
async def preview_withdrawal(
    currency: str,
    amount: str = Query(..., description="Withdrawal amount to preview or 'max'"),
    auth: AuthContext = Depends(get_current_user)
):
    """
    Preview withdrawal fees

    Calculates network and server fees without executing withdrawal
    Amount can be a number or 'max' for maximum withdrawal
    """
    try:
        user_id = auth.user.get("discord_id")
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")

        wallet_service = get_wallet_service()

        # Check for 'max' keyword
        if amount.lower() == "max":
            # Get current balance
            balance = await wallet_service.get_balance(user_id, currency)

            if balance <= 0:
                raise HTTPException(status_code=400, detail="Insufficient balance")

            # Calculate max withdrawal
            send_amount, network_fee, server_fee, total_deducted = await wallet_service.calculate_max_withdrawal(
                currency, balance
            )

            return {
                "success": True,
                "data": {
                    "amount": str(send_amount),
                    "network_fee": str(network_fee),
                    "server_fee": str(server_fee),
                    "total_deducted": str(total_deducted),
                    "available_balance": str(balance),
                    "is_max": True,
                    "you_will_send": str(send_amount),
                    "recipient_receives": str(send_amount)
                }
            }

        # Parse normal amount
        try:
            amount_dec = Decimal(amount)
        except:
            raise HTTPException(status_code=400, detail="Invalid amount format")

        if amount_dec <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        network_fee, server_fee, total_deducted = await wallet_service.calculate_fees(
            currency, amount_dec
        )

        return {
            "success": True,
            "data": {
                "amount": amount,
                "network_fee": str(network_fee),
                "server_fee": str(server_fee),
                "total_deducted": str(total_deducted),
                "is_max": False,
                "you_will_send": amount,
                "recipient_receives": amount
            }
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to preview withdrawal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to calculate fees")


@router.get("/{currency}/transactions")
async def get_transactions(
    currency: str,
    limit: int = 50,
    offset: int = 0,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get transaction history

    Returns deposits and withdrawals for the currency
    """
    try:
        user_id = auth.user.get("discord_id")
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")

        wallet_service = get_wallet_service()
        transactions = await wallet_service.get_transactions(
            user_id, currency, limit, offset
        )

        return {
            "success": True,
            "data": {
                "transactions": transactions,
                "count": len(transactions),
                "offset": offset,
                "limit": limit
            }
        }

    except Exception as e:
        logger.error(f"Failed to get transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")


# =============================
# Webhook Endpoints
# =============================

@router.post("/webhooks/tatum")
async def tatum_webhook(
    request: Request,
    x_payload_hash: Optional[str] = Header(None)
):
    """
    Tatum deposit webhook

    Receives notifications for incoming transactions to user wallets
    HMAC signature verification required
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify signature
        if not x_payload_hash:
            logger.warning("Tatum webhook received without signature")
            raise HTTPException(status_code=401, detail="Signature required")

        if not verify_tatum_signature(body, x_payload_hash):
            logger.error("Invalid Tatum webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse payload
        payload = await request.json()

        logger.info(f"Tatum webhook received: {payload}")

        # Extract data
        address = payload.get("address")
        amount = payload.get("amount")
        currency = payload.get("currency")
        tx_hash = payload.get("txId")

        if not all([address, amount, currency, tx_hash]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Find wallet by address
        from app.core.database import get_database
        db = get_database()

        wallet = await db.wallets.find_one({"address": address})

        if not wallet:
            logger.warning(f"Webhook for unknown wallet: {address}")
            return {"status": "ignored", "reason": "wallet_not_found"}

        # Process deposit
        wallet_service = get_wallet_service()
        await wallet_service.deposit_confirmed(
            wallet["user_id"],
            currency,
            amount,
            tx_hash
        )

        logger.info(f"Processed deposit: {amount} {currency} to {address[:10]}...")

        # Send Discord DM notification
        try:
            # Store notification in database for bot to process
            from app.core.database import get_database
            db = get_database()

            notification = {
                "user_id": wallet["user_id"],
                "type": "deposit_confirmed",
                "data": {
                    "currency": currency,
                    "amount": amount,
                    "tx_hash": tx_hash,
                    "address": address
                },
                "status": "pending",
                "created_at": datetime.utcnow()
            }

            await db.notifications.insert_one(notification)
            logger.info(f"Created deposit notification for user {wallet['user_id']}")

        except Exception as notif_err:
            logger.error(f"Failed to create deposit notification: {notif_err}")
            # Don't fail the webhook processing

        return {"status": "processed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


# =============================
# Admin Endpoints
# =============================

@router.post("/admin/profit/process")
async def process_profit_holds(
    currency: Optional[str] = None,
    admin_token: str = Header(..., alias="X-Admin-Token")
):
    """
    Process held profit fees

    Admin endpoint to batch process small fees
    Requires admin authentication
    """
    try:
        # Verify admin token
        if admin_token != settings.BOT_SERVICE_TOKEN:
            raise HTTPException(status_code=403, detail="Admin access required")

        # TODO: Implement batch profit processing
        # 1. Get all held profits for currency
        # 2. Sum amounts
        # 3. If sum >= threshold, send to admin wallet
        # 4. Update profit_holds as released

        logger.info(f"Processing profit holds for {currency or 'all currencies'}")

        return {
            "success": True,
            "message": "Profit processing initiated",
            "data": {
                "currency": currency,
                "status": "processing"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process profits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Profit processing failed")


@router.get("/admin/stats")
async def get_wallet_stats(
    admin_token: str = Header(..., alias="X-Admin-Token")
):
    """
    Get wallet system statistics

    Admin endpoint for monitoring
    """
    try:
        # Verify admin token
        if admin_token != settings.BOT_SERVICE_TOKEN:
            raise HTTPException(status_code=403, detail="Admin access required")

        from app.core.database import get_database
        db = get_database()

        # Count wallets
        wallet_count = await db.wallets.count_documents({})

        # Count transactions
        tx_count = await db.transactions.count_documents({})

        # Count held profits
        held_profits = await db.profit_holds.count_documents({"status": "held"})

        return {
            "success": True,
            "data": {
                "total_wallets": wallet_count,
                "total_transactions": tx_count,
                "held_profits": held_profits,
                "supported_currencies": len(SUPPORTED_CURRENCIES)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch stats")
