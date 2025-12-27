"""
Exchange Routes - Crypto exchange operations
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from app.api.dependencies import get_current_active_user
from app.services.exchange_service import ExchangeService
from app.models.exchange import ExchangeCreate

router = APIRouter(tags=["Exchanges"])


@router.post("/create")
async def create_exchange(
    exchange_data: ExchangeCreate,
    user: dict = Depends(get_current_active_user)
):
    """Create new exchange offer"""

    creator_id = str(user["_id"])

    try:
        exchange = await ExchangeService.create_exchange(creator_id, exchange_data)

        return {
            "message": "Exchange created successfully",
            "exchange": {
                "id": str(exchange["_id"]),
                "send_currency": exchange["send_currency"],
                "send_amount": exchange["send_amount"],
                "receive_currency": exchange["receive_currency"],
                "receive_amount": exchange["receive_amount"],
                "exchange_rate": exchange["exchange_rate"],
                "platform_fee": exchange["platform_fee_amount"],
                "status": exchange["status"],
                "expires_at": exchange["expires_at"],
                "created_at": exchange["created_at"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
async def list_exchanges(
    status: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_active_user)
):
    """List available exchanges"""

    exchanges = await ExchangeService.list_exchanges(
        status=status,
        limit=limit
    )

    return {
        "exchanges": [
            {
                "id": str(ex["_id"]),
                "send_currency": ex["send_currency"],
                "send_amount": ex["send_amount"],
                "receive_currency": ex["receive_currency"],
                "receive_amount": ex["receive_amount"],
                "exchange_rate": ex["exchange_rate"],
                "status": ex["status"],
                "created_at": ex["created_at"],
                "expires_at": ex["expires_at"]
            }
            for ex in exchanges
        ],
        "count": len(exchanges)
    }


@router.get("/my-exchanges")
async def my_exchanges(
    status: Optional[str] = None,
    user: dict = Depends(get_current_active_user)
):
    """List user's exchanges"""

    user_id = str(user["_id"])
    exchanges = await ExchangeService.list_exchanges(
        user_id=user_id,
        status=status
    )

    return {
        "exchanges": [
            {
                "id": str(ex["_id"]),
                "type": "creator" if str(ex["creator_id"]) == user_id else "exchanger",
                "send_currency": ex["send_currency"],
                "send_amount": ex["send_amount"],
                "receive_currency": ex["receive_currency"],
                "receive_amount": ex["receive_amount"],
                "status": ex["status"],
                "created_at": ex["created_at"],
                "expires_at": ex.get("expires_at")
            }
            for ex in exchanges
        ],
        "count": len(exchanges)
    }


@router.post("/{exchange_id}/accept")
async def accept_exchange(
    exchange_id: str,
    user: dict = Depends(get_current_active_user)
):
    """Accept an exchange offer"""

    exchanger_id = str(user["_id"])

    try:
        exchange = await ExchangeService.accept_exchange(exchange_id, exchanger_id)

        return {
            "message": "Exchange accepted successfully",
            "exchange": {
                "id": str(exchange["_id"]),
                "status": exchange["status"],
                "accepted_at": exchange.get("accepted_at")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{exchange_id}/cancel")
async def cancel_exchange(
    exchange_id: str,
    user: dict = Depends(get_current_active_user)
):
    """Cancel an exchange"""

    user_id = str(user["_id"])

    try:
        exchange = await ExchangeService.cancel_exchange(exchange_id, user_id)

        return {
            "message": "Exchange cancelled successfully",
            "exchange": {
                "id": str(exchange["_id"]),
                "status": exchange["status"],
                "cancelled_at": exchange.get("cancelled_at")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{exchange_id}")
async def get_exchange(
    exchange_id: str,
    user: dict = Depends(get_current_active_user)
):
    """Get exchange details"""

    from bson import ObjectId
    from app.core.database import get_exchanges_collection

    exchanges = get_exchanges_collection()
    exchange = await exchanges.find_one({"_id": ObjectId(exchange_id)})

    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not found")

    return {
        "id": str(exchange["_id"]),
        "creator_id": str(exchange["creator_id"]),
        "exchanger_id": str(exchange["exchanger_id"]) if exchange.get("exchanger_id") else None,
        "send_currency": exchange["send_currency"],
        "send_amount": exchange["send_amount"],
        "receive_currency": exchange["receive_currency"],
        "receive_amount": exchange["receive_amount"],
        "exchange_rate": exchange["exchange_rate"],
        "platform_fee": exchange["platform_fee_amount"],
        "status": exchange["status"],
        "notes": exchange.get("notes"),
        "created_at": exchange["created_at"],
        "expires_at": exchange.get("expires_at"),
        "accepted_at": exchange.get("accepted_at"),
        "completed_at": exchange.get("completed_at")
    }
