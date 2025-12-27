"""
Afroo Swap API Routes
V4 instant swap system
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.afroo_swap_service import AfrooSwapService
from app.api.deps import get_current_user, AuthContext
from app.core.database import get_users_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/afroo-swaps", tags=["afroo_swaps"])


class SwapQuoteRequest(BaseModel):
    from_asset: str
    to_asset: str
    amount: float = Field(gt=0, le=1000000, description="Amount must be greater than 0 and less than 1,000,000")


class SwapExecuteRequest(BaseModel):
    from_asset: str
    to_asset: str
    amount: float = Field(gt=0, le=1000000, description="Amount must be greater than 0 and less than 1,000,000")
    destination_address: str = Field(description="Destination wallet address to receive swapped crypto")
    refund_address: str = Field(default=None, description="Refund address if swap fails (optional)")
    slippage_tolerance: float = Field(ge=0.001, le=0.5, default=0.01, description="Slippage tolerance between 0.1% and 50%")


@router.post("/quote")
async def get_swap_quote(
    data: SwapQuoteRequest,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get swap quote with estimated rate and fees.
    Quote is valid for 30 seconds.
    Accepts both bot token and web JWT authentication.
    """
    try:
        quote = await AfrooSwapService.get_swap_quote(
            from_asset=data.from_asset,
            to_asset=data.to_asset,
            amount=data.amount
        )

        return {
            "success": True,
            "quote": quote
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quote: {str(e)}"
        )


@router.post("/execute")
async def execute_swap(
    data: SwapExecuteRequest,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Execute instant swap.
    Debits from_asset, credits to_asset, collects fees.
    Accepts both bot token and web JWT authentication.
    """
    try:
        # Get user document from auth context
        discord_user_id = auth.user.get("discord_id")
        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_user_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        result = await AfrooSwapService.execute_swap(
            user_id=str(user["_id"]),
            from_asset=data.from_asset,
            to_asset=data.to_asset,
            amount=data.amount,
            destination_address=data.destination_address,
            refund_address=data.refund_address,
            slippage_tolerance=data.slippage_tolerance
        )

        return {
            "success": True,
            "swap": result,
            "message": f"Swapped {data.amount} {data.from_asset} → {result.get('estimated_output', 'N/A')} {data.to_asset}"
        }

    except ValueError as e:
        logger.error(f"Swap validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Swap execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute swap: {str(e)}"
        )


@router.get("/history")
async def get_swap_history(
    limit: int = Query(50, le=100),
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get user swap history.
    Accepts both bot token and web JWT authentication.
    """
    try:
        # Get user document from auth context
        discord_user_id = auth.user.get("discord_id")
        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_user_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        swaps = await AfrooSwapService.get_swap_history(
            user_id=str(user["_id"]),
            limit=limit
        )

        return {
            "success": True,
            "swaps": swaps,
            "count": len(swaps)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history: {str(e)}"
        )


@router.get("/supported-assets")
async def get_supported_assets():
    """Get list of assets supported for swaps from ChangeNOW"""
    try:
        from app.services.changenow_service import ChangeNowService

        # Get all available currencies from ChangeNOW
        currencies = await ChangeNowService.get_available_currencies()

        if not currencies:
            # Fallback to basic list if API fails
            currencies = [
                {"ticker": "btc", "name": "Bitcoin"},
                {"ticker": "eth", "name": "Ethereum"},
                {"ticker": "ltc", "name": "Litecoin"},
                {"ticker": "sol", "name": "Solana"},
                {"ticker": "usdt", "name": "Tether"},
                {"ticker": "usdc", "name": "USD Coin"},
            ]

        # Format currencies for frontend
        # Group by ticker and select preferred networks
        ticker_groups = {}

        for currency in currencies:
            ticker = currency.get("ticker", "").upper()
            network = currency.get("network", "").lower()

            # Skip invalid entries
            if not ticker:
                continue

            # Group by ticker
            if ticker not in ticker_groups:
                ticker_groups[ticker] = []
            ticker_groups[ticker].append(currency)

        # Network priority (prefer these networks for multi-chain tokens)
        network_priority = {
            "USDT": ["eth", "bsc", "tron", "sol"],
            "USDC": ["eth", "sol", "polygon"],
            "BUSD": ["bsc", "eth"],
            "DAI": ["eth"],
            "LTC": ["ltc", "bsc"],  # Prefer native Litecoin chain
            "SOL": ["sol", "eth"],   # Prefer native Solana chain
        }

        assets = []
        for ticker, currencies_list in ticker_groups.items():
            # For single-network currencies, just use it
            if len(currencies_list) == 1:
                currency = currencies_list[0]
            else:
                # For multi-chain, prefer based on priority
                preferred_networks = network_priority.get(ticker, ["eth", "bsc"])

                # Try to find preferred network
                currency = None
                for pref_net in preferred_networks:
                    for curr in currencies_list:
                        if curr.get("network", "").lower() == pref_net:
                            currency = curr
                            break
                    if currency:
                        break

                # Fallback to first if no preferred found
                if not currency:
                    currency = currencies_list[0]

            network = currency.get("network", "")

            # Detect stablecoins
            is_stable = ticker in ["USDT", "USDC", "BUSD", "DAI", "TUSD", "USDD", "USDP"]

            # Mark featured coins
            is_featured = ticker in ["BTC", "ETH", "SOL", "LTC", "USDT", "USDC"]

            # Create display code with network suffix for multi-chain tokens
            display_code = ticker
            if network and ticker in ["USDT", "USDC", "BUSD", "DAI"]:
                display_code = f"{ticker}-{network.upper()}"

            assets.append({
                "code": display_code,
                "ticker": ticker.lower(),  # ChangeNow ticker
                "name": currency.get("name", "Unknown"),
                "network": network,
                "hasExternalId": currency.get("hasExternalId", False),
                "isFiat": currency.get("isFiat", False),
                "featured": is_featured,
                "isStable": is_stable
            })

        return {
            "success": True,
            "assets": assets,
            "count": len(assets)
        }

    except Exception as e:
        logger.error(f"Failed to get supported assets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get supported assets: {str(e)}"
        )


@router.get("/pending-notifications")
async def get_pending_notifications(
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get swaps with pending completion notifications.
    Used by bot's completion notifier task.
    Accepts both bot token and web JWT authentication.
    """
    try:
        from app.core.database import get_db_collection
        from app.utils.helpers import serialize_objectids

        swaps_db = await get_db_collection("afroo_swaps")

        # Find all swaps with notification_pending = true
        cursor = swaps_db.find({
            "notification_pending": True,
            "status": "completed"
        }).limit(50)

        swaps = await cursor.to_list(length=50)

        # Recursively convert all ObjectIds to strings for JSON serialization
        swaps = serialize_objectids(swaps)

        return {
            "success": True,
            "swaps": swaps,
            "count": len(swaps)
        }

    except Exception as e:
        logger.error(f"Failed to get pending swap notifications: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending notifications: {str(e)}"
        )


@router.get("/{swap_id}")
async def get_swap_details(
    swap_id: str,
    auth: AuthContext = Depends(get_current_user),
    refresh: bool = Query(False, description="Refresh status from ChangeNOW before returning")
):
    """
    Get swap details by ID.
    Accepts both bot token and web JWT authentication.
    Optionally refresh status from ChangeNOW with ?refresh=true
    """
    try:
        # Get user document from auth context
        discord_user_id = auth.user.get("discord_id")
        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_user_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Refresh status from ChangeNOW if requested
        if refresh:
            await AfrooSwapService.update_swap_status(swap_id)

        swap = await AfrooSwapService.get_swap_details(
            swap_id=swap_id,
            user_id=str(user["_id"])
        )

        if not swap:
            raise HTTPException(status_code=404, detail="Swap not found")

        return swap

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get swap details: {str(e)}"
        )


@router.post("/{swap_id}/mark-notification-processed")
async def mark_notification_processed(
    swap_id: str,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Mark swap notification as processed.
    Called by bot after sending completion notifications.
    Accepts both bot token and web JWT authentication.
    """
    try:
        from app.core.database import get_db_collection
        from bson import ObjectId

        swaps_db = await get_db_collection("afroo_swaps")

        result = await swaps_db.update_one(
            {"_id": ObjectId(swap_id)},
            {
                "$set": {
                    "notification_pending": False,
                    "notification_processed_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Swap not found")

        return {
            "success": True,
            "message": "Notification marked as processed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification as processed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notification as processed: {str(e)}"
        )
