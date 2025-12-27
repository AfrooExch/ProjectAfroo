"""
Stats & Leaderboard API Routes
Platform statistics, leaderboards, user dashboards
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta

from app.api.deps import get_current_user_bot, AuthContext
from app.core.database import get_database

router = APIRouter()


@router.get("/stats/leaderboard")
async def get_leaderboard(
    leaderboard_type: str = Query("customer", description="customer, exchanger, trader, or automm"),
    limit: int = Query(10, ge=1, le=50),
    db = Depends(get_database)
):
    """Get leaderboard - public endpoint"""

    # Determine collection and sort field based on type
    if leaderboard_type == "customer":
        # Top customers by transaction volume
        pipeline = [
            {"$match": {"role": "customer"}},
            {"$lookup": {
                "from": "transactions",
                "localField": "discord_id",
                "foreignField": "user_id",
                "as": "transactions"
            }},
            {"$addFields": {
                "total_volume": {"$sum": "$transactions.amount_usd"},
                "transaction_count": {"$size": "$transactions"}
            }},
            {"$sort": {"total_volume": -1}},
            {"$limit": limit},
            {"$project": {
                "discord_id": 1,
                "username": 1,
                "avatar_hash": 1,
                "discriminator": 1,
                "global_name": 1,
                "total_volume": 1,
                "transaction_count": 1,
                "rank": 1
            }}
        ]
        results = await db.users.aggregate(pipeline).to_list(length=limit)

    elif leaderboard_type == "exchanger":
        # Top exchangers by volume from user_statistics
        pipeline = [
            {"$match": {"roles": "Exchanger"}},
            {"$lookup": {
                "from": "user_statistics",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "stats"
            }},
            {"$unwind": {"path": "$stats", "preserveNullAndEmptyArrays": True}},
            {"$addFields": {
                "exchanger_exchange_volume_usd": {"$toDouble": {"$ifNull": ["$stats.exchanger_exchange_volume_usd", "0"]}},
                "exchanger_total_completed": {"$ifNull": ["$stats.exchanger_total_completed", 0]},
                "vouch_count": {"$ifNull": ["$stats.vouch_count", 0]}
            }},
            {"$match": {"exchanger_exchange_volume_usd": {"$gt": 0}}},
            {"$sort": {"exchanger_exchange_volume_usd": -1}},
            {"$limit": limit},
            {"$project": {
                "discord_id": 1,
                "username": 1,
                "avatar_hash": 1,
                "discriminator": 1,
                "global_name": 1,
                "completed_exchanges": "$exchanger_total_completed",
                "total_volume": "$exchanger_exchange_volume_usd",
                "vouch_count": 1,
                "rating": {"$ifNull": ["$stats.exchanger_rating", 0]}
            }}
        ]
        results = await db.users.aggregate(pipeline).to_list(length=limit)

    elif leaderboard_type == "trader":
        # Top traders by swap volume
        pipeline = [
            {"$group": {
                "_id": "$user_id",
                "total_swaps": {"$sum": 1},
                "total_volume": {"$sum": "$from_amount_usd"}
            }},
            {"$sort": {"total_volume": -1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "discord_id",
                "as": "user"
            }},
            {"$unwind": "$user"},
            {"$project": {
                "discord_id": "$_id",
                "username": "$user.username",
                "avatar_hash": "$user.avatar_hash",
                "discriminator": "$user.discriminator",
                "global_name": "$user.global_name",
                "total_swaps": 1,
                "total_volume": 1
            }}
        ]
        results = await db.swaps.aggregate(pipeline).to_list(length=limit)

    elif leaderboard_type == "automm":
        # Top AutoMM users by volume
        pipeline = [
            {"$group": {
                "_id": "$user_id",
                "total_automm": {"$sum": 1},
                "total_volume": {"$sum": "$volume_usd"}
            }},
            {"$sort": {"total_volume": -1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "discord_id",
                "as": "user"
            }},
            {"$unwind": "$user"},
            {"$project": {
                "discord_id": "$_id",
                "username": "$user.username",
                "avatar_hash": "$user.avatar_hash",
                "discriminator": "$user.discriminator",
                "global_name": "$user.global_name",
                "total_automm": 1,
                "total_volume": 1
            }}
        ]
        results = await db.automm_swaps.aggregate(pipeline).to_list(length=limit)

    else:
        raise HTTPException(400, f"Invalid leaderboard type: {leaderboard_type}")

    # Add rank to results
    for idx, entry in enumerate(results, 1):
        entry["rank"] = idx
        entry["_id"] = str(entry.get("_id", ""))

    return {
        "success": True,
        "leaderboard_type": leaderboard_type,
        "entries": results
    }


@router.get("/stats/platform")
async def get_platform_stats(
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Get platform-wide statistics - admin only"""
    if not auth.is_admin:
        raise HTTPException(403, "Admin only")

    # Get various platform stats
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    stats = {
        "users": {
            "total": await db.users.count_documents({}),
            "customers": await db.users.count_documents({"role": "customer"}),
            "exchangers": await db.users.count_documents({"role": "exchanger"}),
            "approved_exchangers": await db.users.count_documents({"role": "exchanger", "status": "approved"}),
            "new_24h": await db.users.count_documents({"created_at": {"$gte": day_ago}}),
            "new_7d": await db.users.count_documents({"created_at": {"$gte": week_ago}}),
            "new_30d": await db.users.count_documents({"created_at": {"$gte": month_ago}})
        },
        "transactions": {
            "total": await db.transactions.count_documents({}),
            "deposits": await db.transactions.count_documents({"type": "deposit"}),
            "withdrawals": await db.transactions.count_documents({"type": "withdrawal"}),
            "completed": await db.transactions.count_documents({"status": "completed"}),
            "pending": await db.transactions.count_documents({"status": "pending"}),
            "failed": await db.transactions.count_documents({"status": "failed"}),
            "last_24h": await db.transactions.count_documents({"created_at": {"$gte": day_ago}}),
            "last_7d": await db.transactions.count_documents({"created_at": {"$gte": week_ago}})
        },
        "exchanges": {
            "total": await db.exchange_requests.count_documents({}),
            "completed": await db.exchange_requests.count_documents({"status": "completed"}),
            "active": await db.exchange_requests.count_documents({"status": {"$in": ["pending", "in_progress"]}}),
            "cancelled": await db.exchange_requests.count_documents({"status": "cancelled"}),
            "last_24h": await db.exchange_requests.count_documents({"created_at": {"$gte": day_ago}})
        },
        "swaps": {
            "total": await db.swaps.count_documents({}),
            "completed": await db.swaps.count_documents({"status": "completed"}),
            "pending": await db.swaps.count_documents({"status": "pending"}),
            "failed": await db.swaps.count_documents({"status": "failed"}),
            "last_24h": await db.swaps.count_documents({"created_at": {"$gte": day_ago}})
        },
        "escrow": {
            "total": await db.escrow.count_documents({}),
            "active": await db.escrow.count_documents({"status": "active"}),
            "completed": await db.escrow.count_documents({"status": "completed"}),
            "disputed": await db.escrow.count_documents({"status": "disputed"})
        },
        "tickets": {
            "total": await db.tickets.count_documents({}),
            "open": await db.tickets.count_documents({"status": "open"}),
            "in_progress": await db.tickets.count_documents({"status": "in_progress"}),
            "closed": await db.tickets.count_documents({"status": "closed"}),
            "last_24h": await db.tickets.count_documents({"created_at": {"$gte": day_ago}})
        },
        "support_tickets": {
            "total": await db.support_tickets.count_documents({}),
            "open": await db.support_tickets.count_documents({"status": "open"}),
            "closed": await db.support_tickets.count_documents({"status": "closed"})
        },
        "applications": {
            "total": await db.applications.count_documents({}),
            "pending": await db.applications.count_documents({"status": "pending"}),
            "approved": await db.applications.count_documents({"status": "approved"}),
            "rejected": await db.applications.count_documents({"status": "rejected"})
        }
    }

    # Calculate volume stats
    volume_pipeline = [
        {"$group": {
            "_id": None,
            "total_volume_usd": {"$sum": "$amount_usd"}
        }}
    ]

    tx_volume = await db.transactions.aggregate(volume_pipeline).to_list(length=1)
    stats["volume"] = {
        "total_usd": tx_volume[0]["total_volume_usd"] if tx_volume else 0
    }

    return {"success": True, "stats": stats}


@router.get("/users/{user_id}/dashboard")
async def get_user_dashboard(
    user_id: str,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Get user dashboard with their stats"""

    # Check authorization - user can only see their own dashboard unless admin
    if auth.user["discord_id"] != user_id and not auth.is_admin:
        raise HTTPException(403, "Not authorized")

    # Get user data
    user = await db.users.find_one({"discord_id": user_id})
    if not user:
        raise HTTPException(404, "User not found")

    # Get user's transaction stats
    tx_count = await db.transactions.count_documents({"user_id": user_id})
    tx_completed = await db.transactions.count_documents({"user_id": user_id, "status": "completed"})

    # Calculate total volume
    volume_pipeline = [
        {"$match": {"user_id": user_id, "status": "completed"}},
        {"$group": {
            "_id": None,
            "total_volume_usd": {"$sum": "$amount_usd"}
        }}
    ]
    volume_result = await db.transactions.aggregate(volume_pipeline).to_list(length=1)
    total_volume = volume_result[0]["total_volume_usd"] if volume_result else 0

    # Get recent transactions
    recent_tx = await db.transactions.find(
        {"user_id": user_id}
    ).sort("created_at", -1).limit(10).to_list(length=10)

    # Convert ObjectIds to strings
    for tx in recent_tx:
        tx["_id"] = str(tx["_id"])

    # Get balances (from wallets)
    balances = []
    wallets = await db.wallets.find({"user_id": user_id}).to_list(length=100)
    for wallet in wallets:
        balances.append({
            "asset": wallet["asset"],
            "balance": wallet["balance"],
            "available": wallet.get("available", wallet["balance"]),
            "locked": wallet.get("locked", 0)
        })

    # Get exchanger-specific stats if applicable
    exchanger_stats = None
    if user.get("role") == "exchanger":
        exchange_count = await db.exchange_requests.count_documents({"exchanger_id": user_id})
        exchange_completed = await db.exchange_requests.count_documents({
            "exchanger_id": user_id,
            "status": "completed"
        })

        exchanger_stats = {
            "total_exchanges": exchange_count,
            "completed_exchanges": exchange_completed,
            "rating": user.get("rating", 0),
            "reviews_count": user.get("reviews_count", 0),
            "status": user.get("status", "pending")
        }

    dashboard = {
        "user": {
            "discord_id": user["discord_id"],
            "username": user.get("username", "Unknown"),
            "role": user.get("role", "customer"),
            "created_at": user.get("created_at")
        },
        "stats": {
            "total_transactions": tx_count,
            "completed_transactions": tx_completed,
            "total_volume_usd": total_volume
        },
        "balances": balances,
        "recent_transactions": recent_tx,
        "exchanger_stats": exchanger_stats
    }

    return {"success": True, "dashboard": dashboard}
