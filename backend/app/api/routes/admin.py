"""
Admin Routes - Platform administration
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timedelta

from app.api.dependencies import require_admin, require_head_admin, require_assistant_admin_or_higher, require_head_admin_bot, require_assistant_admin_or_higher_bot
from app.core.database import (
    get_users_collection,
    get_exchanges_collection,
    get_wallets_collection,
    get_tickets_collection,
    get_partners_collection,
    get_audit_logs_collection,
    get_swaps_collection,
    get_transactions_collection,
    get_db_collection
)
from bson import ObjectId
from pydantic import BaseModel

router = APIRouter(tags=["Admin"])
logger = logging.getLogger(__name__)


@router.get("/stats/overview")
async def get_platform_overview(
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get comprehensive platform statistics overview from stats_tracking_service"""

    users = get_users_collection()
    exchanges = get_exchanges_collection()
    wallets = get_wallets_collection()
    tickets = get_tickets_collection()
    partners = get_partners_collection()
    swaps = get_swaps_collection()
    transactions = get_transactions_collection()
    user_statistics = await get_db_collection("user_statistics")
    automm_deals = await get_db_collection("automm_deals")

    # Count totals
    total_users = await users.count_documents({})
    active_users = await users.count_documents({"status": "active"})
    total_exchanges = await exchanges.count_documents({})
    completed_exchanges = await exchanges.count_documents({"status": "completed"})
    cancelled_exchanges = await exchanges.count_documents({"status": "cancelled"})
    total_wallets = await wallets.count_documents({})
    open_tickets = await tickets.count_documents({"status": {"$nin": ["closed", "completed", "cancelled"]}})
    total_partners = await partners.count_documents({})
    total_swaps = await swaps.count_documents({})
    completed_swaps = await swaps.count_documents({"status": "completed"})
    failed_swaps = await swaps.count_documents({"status": "failed"})
    total_automm = await automm_deals.count_documents({})
    completed_automm = await automm_deals.count_documents({"status": "completed"})

    # Count exchangers (users with "Exchanger" role)
    total_exchangers = await users.count_documents({"roles": "Exchanger"})

    # Aggregate stats from user_statistics collection
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_client_exchange_volume": {"$sum": "$client_exchange_volume_usd"},
                "total_exchanger_volume": {"$sum": "$exchanger_exchange_volume_usd"},
                "total_exchanger_profit": {"$sum": "$exchanger_total_profit_usd"},
                "total_exchanger_fees": {"$sum": "$exchanger_total_fees_paid_usd"},
                "total_swap_volume": {"$sum": "$swap_total_volume_usd"},
                "total_automm_volume": {"$sum": "$automm_total_volume_usd"},
                "total_deposits": {"$sum": "$wallet_total_deposited_usd"},
                "total_withdrawals": {"$sum": "$wallet_total_withdrawn_usd"}
            }
        }
    ]

    aggregated_stats = await user_statistics.aggregate(pipeline).to_list(1)
    stats_summary = aggregated_stats[0] if aggregated_stats else {}

    # Calculate total volume
    total_volume = 0.0
    exchange_cursor = exchanges.find({"status": "completed"})
    async for ex in exchange_cursor:
        receive_amount = float(ex.get("receive_amount", 0))
        total_volume += receive_amount

    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    new_users_24h = await users.count_documents({"created_at": {"$gte": yesterday}})
    new_exchanges_24h = await exchanges.count_documents({"created_at": {"$gte": yesterday}})
    new_swaps_24h = await swaps.count_documents({"created_at": {"$gte": yesterday}})

    return {
        "total_users": total_users,
        "total_exchangers": total_exchangers,
        "total_tickets": await tickets.count_documents({}),
        "active_tickets": open_tickets,
        "total_volume_usd": round(total_volume, 2),
        "total_swaps": total_swaps,
        "total_deposits_usd": round(stats_summary.get("total_deposits", 0), 2),
        "totals": {
            "users": total_users,
            "active_users": active_users,
            "exchangers": total_exchangers,
            "exchanges": total_exchanges,
            "completed_exchanges": completed_exchanges,
            "cancelled_exchanges": cancelled_exchanges,
            "swaps": total_swaps,
            "completed_swaps": completed_swaps,
            "failed_swaps": failed_swaps,
            "automm_deals": total_automm,
            "completed_automm": completed_automm,
            "wallets": total_wallets,
            "open_tickets": open_tickets,
            "partners": total_partners
        },
        "volumes": {
            "client_exchange_volume_usd": round(stats_summary.get("total_client_exchange_volume", 0), 2),
            "exchanger_volume_usd": round(stats_summary.get("total_exchanger_volume", 0), 2),
            "exchanger_profit_usd": round(stats_summary.get("total_exchanger_profit", 0), 2),
            "exchanger_fees_paid_usd": round(stats_summary.get("total_exchanger_fees", 0), 2),
            "swap_volume_usd": round(stats_summary.get("total_swap_volume", 0), 2),
            "automm_volume_usd": round(stats_summary.get("total_automm_volume", 0), 2),
            "deposits_usd": round(stats_summary.get("total_deposits", 0), 2),
            "withdrawals_usd": round(stats_summary.get("total_withdrawals", 0), 2)
        },
        "recent_24h": {
            "new_users": new_users_24h,
            "new_exchanges": new_exchanges_24h,
            "new_swaps": new_swaps_24h
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/stats/leaderboards")
async def get_leaderboards(
    limit: int = 10
):
    """Get platform leaderboards for top users - public endpoint"""

    user_statistics = await get_db_collection("user_statistics")
    users = get_users_collection()

    # Top Exchangers by volume
    top_exchangers_cursor = user_statistics.find(
        {"exchanger_exchange_volume_usd": {"$gt": 0}}
    ).sort("exchanger_exchange_volume_usd", -1).limit(limit)

    top_exchangers = []
    async for stat in top_exchangers_cursor:
        user = await users.find_one({"_id": stat["user_id"]})
        if user:
            top_exchangers.append({
                "discord_id": user.get("discord_id"),
                "username": user.get("username", "Unknown"),
                "avatar_hash": user.get("avatar_hash"),
                "discriminator": user.get("discriminator", "0"),
                "volume_usd": round(stat.get("exchanger_exchange_volume_usd", 0), 2),
                "tickets_completed": stat.get("exchanger_total_completed", 0),
                "profit_usd": round(stat.get("exchanger_total_profit_usd", 0), 2)
            })

    # Top Client Exchangers by volume
    top_clients_cursor = user_statistics.find(
        {"client_exchange_volume_usd": {"$gt": 0}}
    ).sort("client_exchange_volume_usd", -1).limit(limit)

    top_clients = []
    async for stat in top_clients_cursor:
        user = await users.find_one({"_id": stat["user_id"]})
        if user:
            top_clients.append({
                "discord_id": user.get("discord_id"),
                "username": user.get("username", "Unknown"),
                "avatar_hash": user.get("avatar_hash"),
                "discriminator": user.get("discriminator", "0"),
                "volume_usd": round(stat.get("client_exchange_volume_usd", 0), 2),
                "total_exchanges": stat.get("client_total_exchanges", 0),
                "completed_exchanges": stat.get("client_completed_exchanges", 0)
            })

    # Top Swappers by volume
    top_swappers_cursor = user_statistics.find(
        {"swap_total_volume_usd": {"$gt": 0}}
    ).sort("swap_total_volume_usd", -1).limit(limit)

    top_swappers = []
    async for stat in top_swappers_cursor:
        user = await users.find_one({"_id": stat["user_id"]})
        if user:
            top_swappers.append({
                "discord_id": user.get("discord_id"),
                "username": user.get("username", "Unknown"),
                "avatar_hash": user.get("avatar_hash"),
                "discriminator": user.get("discriminator", "0"),
                "volume_usd": round(stat.get("swap_total_volume_usd", 0), 2),
                "total_swaps": stat.get("swap_total_made", 0),
                "completed_swaps": stat.get("swap_total_completed", 0)
            })

    # Top AutoMM Users by volume
    top_automm_cursor = user_statistics.find(
        {"automm_total_volume_usd": {"$gt": 0}}
    ).sort("automm_total_volume_usd", -1).limit(limit)

    top_automm = []
    async for stat in top_automm_cursor:
        user = await users.find_one({"_id": stat["user_id"]})
        if user:
            top_automm.append({
                "discord_id": user.get("discord_id"),
                "username": user.get("username", "Unknown"),
                "avatar_hash": user.get("avatar_hash"),
                "discriminator": user.get("discriminator", "0"),
                "volume_usd": round(stat.get("automm_total_volume_usd", 0), 2),
                "total_deals": stat.get("automm_total_created", 0),
                "completed_deals": stat.get("automm_total_completed", 0)
            })

    return {
        "top_exchangers": top_exchangers,
        "top_clients": top_clients,
        "top_swappers": top_swappers,
        "top_automm": top_automm,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/stats/exchanges")
async def get_exchange_stats(
    admin: dict = Depends(require_admin)
):
    """Get exchange statistics"""

    exchanges = get_exchanges_collection()

    # Count by status
    pending = await exchanges.count_documents({"status": "pending"})
    active = await exchanges.count_documents({"status": "active"})
    completed = await exchanges.count_documents({"status": "completed"})
    cancelled = await exchanges.count_documents({"status": "cancelled"})

    # Volume calculation (would need actual blockchain data)
    # Placeholder for now
    total_volume = 0.0
    total_fees = 0.0

    return {
        "counts": {
            "pending": pending,
            "active": active,
            "completed": completed,
            "cancelled": cancelled,
            "total": pending + active + completed + cancelled
        },
        "volume": {
            "total": total_volume,
            "fees_collected": total_fees
        }
    }


@router.get("/stats/tickets")
async def get_ticket_stats(
    admin: dict = Depends(require_admin)
):
    """Get ticket statistics"""

    tickets = get_tickets_collection()

    # Count by status
    open_count = await tickets.count_documents({"status": "open"})
    in_progress = await tickets.count_documents({"status": "in_progress"})
    resolved = await tickets.count_documents({"status": "resolved"})
    closed = await tickets.count_documents({"status": "closed"})

    # Count by type
    general = await tickets.count_documents({"type": "general"})
    exchange_support = await tickets.count_documents({"type": "exchange"})
    wallet_support = await tickets.count_documents({"type": "wallet"})
    kyc = await tickets.count_documents({"type": "kyc"})
    technical = await tickets.count_documents({"type": "technical"})

    return {
        "status": {
            "open": open_count,
            "in_progress": in_progress,
            "resolved": resolved,
            "closed": closed
        },
        "type": {
            "general": general,
            "exchange": exchange_support,
            "wallet": wallet_support,
            "kyc": kyc,
            "technical": technical
        }
    }


@router.get("/audit-logs")
async def get_audit_logs(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = 100,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get audit logs"""

    audit_logs = get_audit_logs_collection()

    query = {}
    if action:
        query["action"] = action
    if resource_type:
        query["resource_type"] = resource_type

    cursor = audit_logs.find(query).sort("created_at", -1).limit(limit)
    logs = await cursor.to_list(length=limit)

    return {
        "logs": [
            {
                "id": str(log["_id"]),
                "user_id": str(log["user_id"]) if log.get("user_id") else None,
                "actor_type": log["actor_type"],
                "action": log["action"],
                "resource_type": log["resource_type"],
                "resource_id": str(log["resource_id"]),
                "details": log.get("details", {}),
                "created_at": log["created_at"].isoformat() if log.get("created_at") else None
            }
            for log in logs
        ],
        "count": len(logs)
    }


@router.get("/holds/all")
async def get_all_holds(
    limit: int = 100,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get all active holds in the system (ADMIN)"""

    holds = await get_db_collection("holds")

    # Get all active holds
    active_holds = await holds.find({"status": "active"}).limit(limit).to_list(length=limit)

    # Serialize ObjectId fields
    holds_list = []
    for hold in active_holds:
        holds_list.append({
            "id": str(hold["_id"]),
            "user_id": str(hold.get("user_id", "")),
            "ticket_id": str(hold.get("ticket_id", "")),
            "asset": hold.get("asset", ""),
            "amount_units": float(hold.get("amount_units", 0)),
            "amount_usd": float(hold.get("amount_usd", 0)),
            "status": hold.get("status", ""),
            "created_at": hold.get("created_at").isoformat() if hold.get("created_at") else None
        })

    return holds_list


@router.get("/users/search")
async def search_users(
    query: str,
    limit: int = 20,
    admin: dict = Depends(require_admin)
):
    """Search users by username or Discord ID"""

    users = get_users_collection()

    # Search by username or discord_id
    cursor = users.find({
        "$or": [
            {"username": {"$regex": query, "$options": "i"}},
            {"discord_id": query}
        ]
    }).limit(limit)

    found_users = await cursor.to_list(length=limit)

    return {
        "users": [
            {
                "id": str(u["_id"]),
                "discord_id": u["discord_id"],
                "username": u["username"],
                "global_name": u.get("global_name"),
                "status": u["status"],
                "reputation_score": u.get("reputation_score", 100),
                "roles": u.get("roles", []),
                "created_at": u["created_at"]
            }
            for u in found_users
        ],
        "count": len(found_users)
    }


@router.post("/system/maintenance-mode")
async def toggle_maintenance_mode(
    enabled: bool,
    message: Optional[str] = None,
    admin: dict = Depends(require_admin)
):
    """Toggle maintenance mode"""

    # TODO: Implement maintenance mode using Redis flag
    # This would be checked in middleware to block requests

    return {
        "message": "Maintenance mode toggled",
        "enabled": enabled,
        "maintenance_message": message
    }


@router.post("/system/backup-database")
async def backup_database(
    backup_type: str = "local",  # "local" or "cloud"
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Force backup database (HEAD ADMIN ONLY)
    Creates MongoDB dump and optionally uploads to cloud storage
    """
    import subprocess
    import os
    from datetime import datetime

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"afroo_backup_{timestamp}"

    try:
        if backup_type == "local":
            # Local backup using mongodump
            backup_dir = f"/backups/{backup_name}"
            os.makedirs(backup_dir, exist_ok=True)

            # Run mongodump
            result = subprocess.run(
                [
                    "mongodump",
                    "--uri", os.getenv("MONGODB_URL"),
                    "--out", backup_dir
                ],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                raise Exception(f"Mongodump failed: {result.stderr}")

            # Get backup size
            backup_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, _, filenames in os.walk(backup_dir)
                for filename in filenames
            )

            return {
                "success": True,
                "data": {
                    "backup_type": "local",
                    "backup_name": backup_name,
                    "backup_path": backup_dir,
                    "backup_size_mb": round(backup_size / (1024 * 1024), 2),
                    "timestamp": timestamp
                }
            }

        elif backup_type == "cloud":
            # Cloud backup (would integrate with S3/Google Cloud Storage)
            # For now, just create local backup
            backup_dir = f"/backups/{backup_name}"
            os.makedirs(backup_dir, exist_ok=True)

            result = subprocess.run(
                [
                    "mongodump",
                    "--uri", os.getenv("MONGODB_URL"),
                    "--out", backup_dir
                ],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                raise Exception(f"Mongodump failed: {result.stderr}")

            # TODO: Upload to cloud storage (S3, Google Cloud, etc.)

            backup_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, _, filenames in os.walk(backup_dir)
                for filename in filenames
            )

            return {
                "success": True,
                "data": {
                    "backup_type": "cloud",
                    "backup_name": backup_name,
                    "backup_path": backup_dir,
                    "backup_size_mb": round(backup_size / (1024 * 1024), 2),
                    "cloud_url": "TODO - integrate cloud storage",
                    "timestamp": timestamp
                }
            }

        else:
            raise HTTPException(status_code=400, detail="Invalid backup_type. Use 'local' or 'cloud'")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Backup timeout - database too large")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.get("/profit/overview")
async def get_profit_overview(
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get comprehensive profit and revenue overview (HEAD ADMIN & ASSISTANT ADMIN)"""

    # Exchange fees: 2% min $0.50 per completed exchange
    server_fees = await get_db_collection("server_fees")
    platform_fees = await get_db_collection("platform_fees")
    tickets = get_tickets_collection()
    swaps = get_swaps_collection()
    transactions = get_transactions_collection()

    # === EXCHANGE FEES ===
    # 2% min $0.50 from each completed exchange
    completed_exchanges = await tickets.find({"status": "completed", "type": "exchange"}).to_list(length=100000)

    exchange_fees_collected = 0.0
    exchange_fees_to_collect = 0.0

    for ticket in completed_exchanges:
        amount_usd = float(ticket.get("amount_usd", 0))
        fee = max(amount_usd * 0.02, 0.50)
        exchange_fees_collected += fee

    # Fees pending collection from server_fees
    pending_server_fees = await server_fees.find({"status": "pending_collection"}).to_list(length=10000)
    for fee_record in pending_server_fees:
        exchange_fees_to_collect += float(fee_record.get("amount_usd", 0))

    # Uncollected platform fees
    pending_platform_fees = await platform_fees.find({"collected": False}).to_list(length=10000)
    for fee_record in pending_platform_fees:
        exchange_fees_to_collect += float(fee_record.get("amount_usd", 0))

    # === SWAP FEES ===
    # 0.4% collected by ChangeNow (external)
    completed_swaps = await swaps.find({"status": "completed"}).to_list(length=100000)

    swap_fees_estimate = 0.0
    total_swap_volume = 0.0

    for swap in completed_swaps:
        from_amount_usd = float(swap.get("from_amount_usd", 0))
        total_swap_volume += from_amount_usd
        swap_fees_estimate += from_amount_usd * 0.004  # 0.4%

    # === WALLET TRANSACTION FEES ===
    # 0.4-0.5% from wallet transactions
    wallet_txns = await transactions.find({
        "transaction_type": {"$in": ["send", "swap"]},
        "status": "completed"
    }).to_list(length=100000)

    wallet_fees_collected = 0.0
    wallet_fees_to_collect = 0.0

    for txn in wallet_txns:
        amount_usd = float(txn.get("amount_usd", 0))
        fee = amount_usd * 0.0045  # 0.45% average

        # Check if fee was collected
        if txn.get("fee_collected"):
            wallet_fees_collected += fee
        else:
            wallet_fees_to_collect += fee

    # === TOTALS ===
    total_collected = exchange_fees_collected + wallet_fees_collected
    total_to_collect = exchange_fees_to_collect + wallet_fees_to_collect
    total_fees = total_collected + total_to_collect + swap_fees_estimate

    return {
        "exchange_fees": {
            "collected": round(exchange_fees_collected, 2),
            "to_collect": round(exchange_fees_to_collect, 2),
            "total": round(exchange_fees_collected + exchange_fees_to_collect, 2),
            "rate": "2% (min $0.50)",
            "completed_count": len(completed_exchanges)
        },
        "swap_fees": {
            "estimate": round(swap_fees_estimate, 2),
            "rate": "0.4% (ChangeNow)",
            "min_withdrawal": 200.00,
            "note": "External - withdraw on ChangeNow site",
            "completed_count": len(completed_swaps),
            "total_volume": round(total_swap_volume, 2)
        },
        "wallet_fees": {
            "collected": round(wallet_fees_collected, 2),
            "to_collect": round(wallet_fees_to_collect, 2),
            "total": round(wallet_fees_collected + wallet_fees_to_collect, 2),
            "rate": "0.4-0.5%",
            "transaction_count": len(wallet_txns)
        },
        "automm_fees": {
            "total": 0.00,
            "note": "Free service - no fees collected"
        },
        "totals": {
            "collected": round(total_collected, 2),
            "to_collect": round(total_to_collect, 2),
            "total_all_time": round(total_fees, 2)
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/profit/mass-collect")
async def mass_collect_fees(
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Mass collect all pending fees from exchangers and wallet transactions (HEAD ADMIN ONLY)
    Sends all collected fees to admin wallets
    """
    from app.core.config import settings

    server_fees = await get_db_collection("server_fees")
    platform_fees = await get_db_collection("platform_fees")
    exchanger_deposits = await get_db_collection("exchanger_deposits")

    collected_count = 0
    collected_total_usd = 0.0
    errors = []

    # Collect from server_fees (exchange fees)
    pending_server_fees = await server_fees.find({"status": "pending_collection"}).to_list(length=10000)

    for fee_record in pending_server_fees:
        try:
            exchanger_id = fee_record.get("exchanger_id")
            amount_usd = float(fee_record.get("amount_usd", 0))
            currency = fee_record.get("asset", "USDT")

            # Get exchanger deposit
            deposit = await exchanger_deposits.find_one({
                "user_id": exchanger_id,
                "currency": currency
            })

            if not deposit:
                errors.append(f"No deposit found for exchanger {exchanger_id} in {currency}")
                continue

            # Deduct fee from fee_reserved
            fee_reserved = float(deposit.get("fee_reserved", 0))
            if fee_reserved < amount_usd:
                errors.append(f"Insufficient fee_reserved for exchanger {exchanger_id}")
                continue

            # Update deposit
            await exchanger_deposits.update_one(
                {"_id": deposit["_id"]},
                {
                    "$inc": {"fee_reserved": -amount_usd},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            # Mark fee as collected
            await server_fees.update_one(
                {"_id": fee_record["_id"]},
                {
                    "$set": {
                        "status": "collected",
                        "collected_at": datetime.utcnow(),
                        "collected_by": head_admin.get("discord_id")
                    }
                }
            )

            collected_count += 1
            collected_total_usd += amount_usd

        except Exception as e:
            errors.append(f"Error collecting fee {fee_record['_id']}: {str(e)}")

    # Collect from platform_fees
    pending_platform_fees = await platform_fees.find({"collected": False}).to_list(length=10000)

    for fee_record in pending_platform_fees:
        try:
            # Mark as collected
            await platform_fees.update_one(
                {"_id": fee_record["_id"]},
                {
                    "$set": {
                        "collected": True,
                        "collected_at": datetime.utcnow(),
                        "collected_by": head_admin.get("discord_id")
                    }
                }
            )

            collected_count += 1
            collected_total_usd += float(fee_record.get("amount_usd", 0))

        except Exception as e:
            errors.append(f"Error collecting platform fee {fee_record['_id']}: {str(e)}")

    return {
        "success": True,
        "collected_count": collected_count,
        "collected_total_usd": round(collected_total_usd, 2),
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat()
    }


class ForceWithdrawRequest(BaseModel):
    """Force withdraw user funds to admin wallet"""
    discord_id: str
    wallet_type: str  # "client" or "exchanger"
    currency: str
    amount_crypto: float  # Amount in crypto (e.g., 0.5 BTC)
    reason: str


@router.post("/users/force-withdraw")
async def force_withdraw_to_admin(
    request: ForceWithdrawRequest,
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Force withdraw user funds to admin wallet (HEAD ADMIN ONLY)
    Supports client and exchanger wallets, amount specified in crypto
    """
    from app.core.config import settings

    users = get_users_collection()
    wallets = get_wallets_collection()
    audit_logs = get_audit_logs_collection()

    # Get user
    user = await users.find_one({"discord_id": request.discord_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get wallet based on type
    if request.wallet_type == "client":
        # Client wallet: user_id is discord_id string
        wallet = await wallets.find_one({
            "user_id": request.discord_id,
            "currency": request.currency
        })
    elif request.wallet_type == "exchanger":
        # Exchanger wallet: from exchanger_deposits collection
        exchanger_deposits = await get_db_collection("exchanger_deposits")
        wallet = await exchanger_deposits.find_one({
            "user_id": request.discord_id,
            "currency": request.currency
        })
    else:
        raise HTTPException(status_code=400, detail="Invalid wallet_type. Must be 'client' or 'exchanger'")

    if not wallet:
        raise HTTPException(status_code=404, detail=f"{request.wallet_type.capitalize()} wallet not found for currency {request.currency}")

    # Get balance
    # Client wallets use "balance", exchanger wallets use "balance_units"
    if request.wallet_type == "client":
        balance_crypto = float(wallet.get("balance", "0"))
    else:  # exchanger
        balance_crypto = float(wallet.get("balance_units", 0))

    balance_usd = float(wallet.get("balance_usd", 0.0))

    # Validate amount
    if request.amount_crypto > balance_crypto:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Requested: {request.amount_crypto} {request.currency}, Available: {balance_crypto} {request.currency}"
        )

    # Get admin wallet address from .env
    try:
        admin_wallet_address = settings.get_admin_wallet(request.currency)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # TODO: Implement actual blockchain transaction using wallet service
    # For now, just update balances

    # Calculate new balances
    new_balance_crypto = balance_crypto - request.amount_crypto

    # Calculate proportional USD decrease (if balance_usd exists)
    if balance_crypto > 0 and balance_usd > 0:
        new_balance_usd = (new_balance_crypto / balance_crypto) * balance_usd
    else:
        new_balance_usd = 0.0

    # Update wallet balance
    if request.wallet_type == "client":
        await wallets.update_one(
            {"_id": wallet["_id"]},
            {
                "$set": {
                    "balance": str(new_balance_crypto),
                    "balance_usd": new_balance_usd,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    else:  # exchanger
        exchanger_deposits = await get_db_collection("exchanger_deposits")
        await exchanger_deposits.update_one(
            {"_id": wallet["_id"]},
            {
                "$set": {
                    "balance_units": new_balance_crypto,
                    "balance_usd": new_balance_usd,
                    "updated_at": datetime.utcnow()
                }
            }
        )

    # Log audit trail
    await audit_logs.insert_one({
        "actor_type": "admin",
        "actor_id": admin_id,
        "action": "force_withdraw",
        "resource_type": f"{request.wallet_type}_wallet",
        "resource_id": str(wallet["_id"]),
        "details": {
            "user_discord_id": request.discord_id,
            "wallet_type": request.wallet_type,
            "currency": request.currency,
            "amount_crypto": request.amount_crypto,
            "admin_wallet": admin_wallet_address,
            "reason": request.reason,
            "previous_balance_crypto": balance_crypto,
            "new_balance_crypto": new_balance_crypto,
            "previous_balance_usd": balance_usd,
            "new_balance_usd": new_balance_usd
        },
        "created_at": datetime.utcnow()
    })

    logger.warning(f"HEAD ADMIN {admin_id} force withdrew {request.amount_crypto} {request.currency} from {request.wallet_type} wallet of user {request.discord_id}")

    return {
        "success": True,
        "message": "Funds transferred to admin wallet",
        "amount_crypto": request.amount_crypto,
        "currency": request.currency,
        "admin_wallet": admin_wallet_address,
        "user_new_balance_crypto": new_balance_crypto,
        "user_new_balance_usd": new_balance_usd,
        "tx_hash": "Pending"  # TODO: Return actual tx hash when blockchain integration is complete
    }


@router.get("/users/{discord_id}/details")
async def get_user_details(
    discord_id: str,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get comprehensive user details including wallets and private keys (ADMIN)"""

    users = get_users_collection()
    wallets = get_wallets_collection()
    exchanges = get_exchanges_collection()
    swaps = get_swaps_collection()
    transactions = get_transactions_collection()

    # Get user
    user = await users.find_one({"discord_id": discord_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_oid = user["_id"]

    # Get encryption service for decrypting private keys
    from app.core.encryption import get_encryption_service
    encryption_service = get_encryption_service()

    # Get user client wallets with private keys (user_id is Discord ID string)
    user_wallets = await wallets.find({"user_id": discord_id}).to_list(length=1000)
    logger.info(f"Found {len(user_wallets)} client wallets for discord_id={discord_id}")

    # Get balances collection
    balances_collection = await get_db_collection("balances")

    client_wallet_list = []
    for wallet in user_wallets:
        encrypted_key = wallet.get("encrypted_private_key")
        decrypted_key = None
        if encrypted_key:
            try:
                decrypted_key = encryption_service.decrypt_private_key(encrypted_key)
            except Exception as e:
                logger.error(f"Failed to decrypt client wallet key for {wallet['currency']}: {e}")
                decrypted_key = "DECRYPTION_FAILED"

        # Get balance from balances collection
        balance_doc = await balances_collection.find_one({
            "user_id": discord_id,
            "currency": wallet["currency"]
        })

        if balance_doc:
            # Calculate total balance (available + locked + pending)
            from decimal import Decimal
            available = Decimal(balance_doc.get("available", "0"))
            locked = Decimal(balance_doc.get("locked", "0"))
            pending = Decimal(balance_doc.get("pending", "0"))
            total_balance = str(available + locked + pending)
        else:
            total_balance = "0"

        client_wallet_list.append({
            "currency": wallet["currency"],
            "address": wallet["address"],
            "balance": total_balance,
            "balance_usd": 0.0,  # TODO: Calculate USD value using price service
            "encrypted_private_key": encrypted_key,
            "private_key": decrypted_key,  # Decrypted for admin access
            "created_at": wallet["created_at"].isoformat() if wallet.get("created_at") else None
        })

    # Get exchanger deposit wallets with private keys
    exchanger_deposits_collection = await get_db_collection("exchanger_deposits")
    exchanger_deposits_cursor = exchanger_deposits_collection.find({"user_id": discord_id})
    exchanger_deposit_list = []
    async for deposit in exchanger_deposits_cursor:
        encrypted_key = deposit.get("encrypted_private_key")
        decrypted_key = None
        if encrypted_key and encrypted_key != "N/A":
            try:
                decrypted_key = encryption_service.decrypt_private_key(encrypted_key)
            except Exception as e:
                logger.error(f"Failed to decrypt exchanger wallet key for {deposit.get('currency')}: {e}")
                decrypted_key = "DECRYPTION_FAILED"

        exchanger_deposit_list.append({
            "currency": deposit.get("currency", deposit.get("asset", "UNKNOWN")),
            "address": deposit.get("wallet_address", deposit.get("address", "N/A")),
            "balance": str(deposit.get("balance_units", 0)),
            "balance_usd": deposit.get("balance_usd", 0.0),
            "encrypted_private_key": encrypted_key,
            "private_key": decrypted_key,  # Decrypted for admin access
            "created_at": deposit["created_at"].isoformat() if deposit.get("created_at") else None
        })

    # Get user statistics
    total_exchanges = await exchanges.count_documents({
        "$or": [
            {"client_id": user_oid},
            {"exchanger_id": user_oid}
        ]
    })

    completed_exchanges = await exchanges.count_documents({
        "$or": [
            {"client_id": user_oid},
            {"exchanger_id": user_oid}
        ],
        "status": "completed"
    })

    total_swaps = await swaps.count_documents({"user_id": user_oid})
    completed_swaps = await swaps.count_documents({
        "user_id": user_oid,
        "status": "completed"
    })

    total_withdrawals = await transactions.count_documents({
        "user_id": user_oid,
        "transaction_type": "withdrawal"
    })

    # Calculate volume
    exchange_cursor = exchanges.find({
        "$or": [
            {"client_id": user_oid},
            {"exchanger_id": user_oid}
        ],
        "status": "completed"
    })

    total_volume = 0.0
    async for ex in exchange_cursor:
        receive_amount = float(ex.get("receive_amount", 0))
        total_volume += receive_amount

    return {
        "user_info": {
            "id": str(user["_id"]),
            "discord_id": user["discord_id"],
            "username": user["username"],
            "global_name": user.get("global_name"),
            "avatar_hash": user.get("avatar_hash"),
            "status": user["status"],
            "roles": user.get("roles", []),
            "kyc_level": user.get("kyc_level", 0),
            "reputation_score": user.get("reputation_score", 100),
            "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
            "last_login_at": user.get("last_login_at").isoformat() if user.get("last_login_at") else None
        },
        "client_wallets": client_wallet_list,
        "exchanger_wallets": exchanger_deposit_list,
        "wallets": client_wallet_list,  # Backward compatibility
        "statistics": {
            "total_exchanges": total_exchanges,
            "completed_exchanges": completed_exchanges,
            "total_swaps": total_swaps,
            "completed_swaps": completed_swaps,
            "total_withdrawals": total_withdrawals,
            "total_volume_usd": round(total_volume, 2)
        }
    }


@router.post("/users/edit-stats")
async def edit_user_stats(
    request: dict,
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Edit user statistics (HEAD ADMIN ONLY)

    Updates user_statistics collection and user reputation
    """
    try:
        discord_id = request.get("discord_id")
        if not discord_id:
            raise HTTPException(status_code=400, detail="discord_id required")

        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_oid = user["_id"]

        # Get user_statistics collection
        user_statistics = await get_db_collection("user_statistics")

        # Build update operations
        stats_update = {}
        user_update = {}
        changes = {}

        # Client Exchange Stats
        if "client_total_exchanges" in request:
            stats_update["client_total_exchanges"] = int(request["client_total_exchanges"])
            changes["Client Total Exchanges"] = int(request["client_total_exchanges"])
        if "client_completed_exchanges" in request:
            stats_update["client_completed_exchanges"] = int(request["client_completed_exchanges"])
            changes["Client Completed Exchanges"] = int(request["client_completed_exchanges"])
        if "client_cancelled_exchanges" in request:
            stats_update["client_cancelled_exchanges"] = int(request["client_cancelled_exchanges"])
            changes["Client Cancelled Exchanges"] = int(request["client_cancelled_exchanges"])
        if "client_exchange_volume_usd" in request:
            stats_update["client_exchange_volume_usd"] = float(request["client_exchange_volume_usd"])
            changes["Client Exchange Volume USD"] = float(request["client_exchange_volume_usd"])

        # Exchanger Stats
        if "exchanger_total_completed" in request:
            stats_update["exchanger_total_completed"] = int(request["exchanger_total_completed"])
            changes["Exchanger Total Completed"] = int(request["exchanger_total_completed"])
        if "exchanger_total_claimed" in request:
            stats_update["exchanger_total_claimed"] = int(request["exchanger_total_claimed"])
            changes["Exchanger Total Claimed"] = int(request["exchanger_total_claimed"])
        if "exchanger_total_fees_paid_usd" in request:
            stats_update["exchanger_total_fees_paid_usd"] = float(request["exchanger_total_fees_paid_usd"])
            changes["Exchanger Total Fees Paid USD"] = float(request["exchanger_total_fees_paid_usd"])
        if "exchanger_total_profit_usd" in request:
            stats_update["exchanger_total_profit_usd"] = float(request["exchanger_total_profit_usd"])
            changes["Exchanger Total Profit USD"] = float(request["exchanger_total_profit_usd"])
        if "exchanger_exchange_volume_usd" in request:
            stats_update["exchanger_exchange_volume_usd"] = float(request["exchanger_exchange_volume_usd"])
            changes["Exchanger Exchange Volume USD"] = float(request["exchanger_exchange_volume_usd"])
        if "exchanger_tickets_completed" in request:
            stats_update["exchanger_tickets_completed"] = int(request["exchanger_tickets_completed"])
            changes["Exchanger Tickets Completed"] = int(request["exchanger_tickets_completed"])

        # Swap Stats
        if "swap_total_made" in request:
            stats_update["swap_total_made"] = int(request["swap_total_made"])
            changes["Swap Total Made"] = int(request["swap_total_made"])
        if "swap_total_completed" in request:
            stats_update["swap_total_completed"] = int(request["swap_total_completed"])
            changes["Swap Total Completed"] = int(request["swap_total_completed"])
        if "swap_total_failed" in request:
            stats_update["swap_total_failed"] = int(request["swap_total_failed"])
            changes["Swap Total Failed"] = int(request["swap_total_failed"])
        if "swap_total_volume_usd" in request:
            stats_update["swap_total_volume_usd"] = float(request["swap_total_volume_usd"])
            changes["Swap Total Volume USD"] = float(request["swap_total_volume_usd"])

        # AutoMM Stats
        if "automm_total_created" in request:
            stats_update["automm_total_created"] = int(request["automm_total_created"])
            changes["AutoMM Total Created"] = int(request["automm_total_created"])
        if "automm_total_completed" in request:
            stats_update["automm_total_completed"] = int(request["automm_total_completed"])
            changes["AutoMM Total Completed"] = int(request["automm_total_completed"])
        if "automm_total_volume_usd" in request:
            stats_update["automm_total_volume_usd"] = float(request["automm_total_volume_usd"])
            changes["AutoMM Total Volume USD"] = float(request["automm_total_volume_usd"])

        # Wallet Stats
        if "wallet_total_deposited_usd" in request:
            stats_update["wallet_total_deposited_usd"] = float(request["wallet_total_deposited_usd"])
            changes["Wallet Total Deposited USD"] = float(request["wallet_total_deposited_usd"])
        if "wallet_total_withdrawn_usd" in request:
            stats_update["wallet_total_withdrawn_usd"] = float(request["wallet_total_withdrawn_usd"])
            changes["Wallet Total Withdrawn USD"] = float(request["wallet_total_withdrawn_usd"])

        # Reputation (stored in users collection)
        if "reputation_score" in request:
            rep = int(request["reputation_score"])
            # Cap at 1000, min at 100
            rep = max(100, min(1000, rep))
            user_update["reputation_score"] = rep
            changes["Reputation Score"] = rep

        if not stats_update and not user_update:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        # Update user_statistics
        if stats_update:
            stats_update["updated_at"] = datetime.utcnow()
            await user_statistics.update_one(
                {"user_id": user_oid},
                {"$set": stats_update},
                upsert=True
            )

        # Update users collection (reputation)
        if user_update:
            await users.update_one(
                {"_id": user_oid},
                {"$set": user_update}
            )

        logger.warning(f"HEAD ADMIN {admin_id} edited stats for user {discord_id}: {changes}")

        return {
            "success": True,
            "message": "Stats updated successfully",
            "changes": changes
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid value: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to edit user stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update stats")


@router.post("/users/edit-roles")
async def edit_user_roles(
    request: dict,
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Edit user roles (HEAD ADMIN ONLY)

    Updates user roles in database
    """
    try:
        discord_id = request.get("discord_id")
        role_names = request.get("roles", [])

        if not discord_id:
            raise HTTPException(status_code=400, detail="discord_id required")

        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        old_roles = user.get("roles", [])

        # Update user roles
        await users.update_one(
            {"discord_id": discord_id},
            {"$set": {"roles": role_names}}
        )

        logger.warning(f"HEAD ADMIN {admin_id} edited roles for user {discord_id}: {old_roles} -> {role_names}")

        return {
            "success": True,
            "message": "Roles updated successfully",
            "old_roles": old_roles,
            "new_roles": role_names
        }

    except Exception as e:
        logger.error(f"Failed to edit user roles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update roles")


# ==================== PROFIT COLLECTION ENDPOINTS ====================

@router.get("/profit/pending")
async def get_pending_profit(
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """
    Get summary of profits pending collection.
    Shows accumulated fees from exchange and wallet operations.
    """
    try:
        from app.services.profit_sweep_service import ProfitSweepService

        summary = await ProfitSweepService.get_pending_profits()

        logger.info(f"Admin {admin_id} viewed pending profits: ${summary.get('total_usd', 0):.2f}")

        return {
            "success": True,
            "data": summary
        }

    except Exception as e:
        logger.error(f"Failed to get pending profits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve pending profits")


@router.post("/profit/sweep")
async def trigger_profit_sweep_endpoint(
    sweep_type: Optional[str] = "all",
    force: Optional[bool] = False,
    dry_run: Optional[bool] = False,
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Manually trigger profit sweep.

    Args:
        sweep_type: "exchange", "wallet", or "all" (default: "all")
        force: Skip minimum amount checks (default: False)
        dry_run: Preview without executing (default: False)

    Permissions:
        HEAD_ADMIN only
    """
    try:
        from app.services.profit_sweep_service import ProfitSweepService

        logger.info(
            f"HEAD ADMIN {admin_id} triggered profit sweep: "
            f"type={sweep_type} force={force} dry_run={dry_run}"
        )

        result = await ProfitSweepService.sweep_all_fees(
            sweep_type=sweep_type,
            force=force,
            dry_run=dry_run
        )

        return {
            "success": True,
            "message": f"Profit sweep {'preview' if dry_run else 'completed'}",
            "data": result
        }

    except Exception as e:
        logger.error(f"Failed to trigger profit sweep: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to execute profit sweep")


@router.get("/profit/history")
async def get_profit_sweep_history(
    limit: Optional[int] = 50,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """
    Get recent profit sweep transaction history.

    Args:
        limit: Maximum number of records to return (default: 50, max: 200)
    """
    try:
        from app.services.profit_sweep_service import ProfitSweepService

        # Cap limit at 200
        limit = min(limit, 200)

        history = await ProfitSweepService.get_sweep_history(limit=limit)

        logger.info(f"Admin {admin_id} viewed profit sweep history")

        return {
            "success": True,
            "data": history,
            "count": len(history)
        }

    except Exception as e:
        logger.error(f"Failed to get profit sweep history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve sweep history")


@router.get("/system/info")
async def get_system_info(
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """
    Get system information and status (HEAD ADMIN & ASSISTANT ADMIN)
    Returns version, uptime, database stats, scheduled tasks status
    """
    import os
    from datetime import datetime
    import time

    try:
        # Database size - skip for now to avoid ObjectId serialization issues
        # TODO: Implement proper database size monitoring
        database_size_mb = 0.0

        # Get uptime - use app start time if available
        try:
            # Try to get process uptime
            import psutil
            process = psutil.Process(os.getpid())
            uptime_seconds = datetime.utcnow().timestamp() - process.create_time()
            uptime_hours = round(uptime_seconds / 3600, 2)
        except ImportError:
            # psutil not available, estimate from file modification time
            uptime_hours = 0.0

        # Get last backup info
        backup_dir = "/backups"
        last_backup = "Never"
        if os.path.exists(backup_dir):
            backups = [
                d for d in os.listdir(backup_dir)
                if os.path.isdir(os.path.join(backup_dir, d)) and d.startswith("afroo_backup_")
            ]
            if backups:
                backups.sort(reverse=True)
                last_backup_name = backups[0]
                # Extract timestamp from backup name (afroo_backup_YYYYMMDD_HHMMSS)
                timestamp_str = last_backup_name.replace("afroo_backup_", "")
                try:
                    backup_dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    last_backup = backup_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except:
                    last_backup = last_backup_name

        # Get scheduled tasks status
        from app.services.background_tasks import scheduler
        scheduled_tasks = []

        try:
            if scheduler and scheduler.running:
                for job in scheduler.get_jobs():
                    # Ensure all values are JSON serializable
                    task_info = {
                        "name": str(job.name) if job.name else str(job.id),
                        "schedule": str(job.trigger),
                        "status": "running" if job.next_run_time else "paused"
                    }

                    # Only add next_run if it exists and is serializable
                    if job.next_run_time:
                        try:
                            task_info["next_run"] = job.next_run_time.isoformat()
                        except:
                            task_info["next_run"] = str(job.next_run_time)

                    scheduled_tasks.append(task_info)
        except Exception as sched_error:
            logger.warning(f"Could not get scheduler tasks: {sched_error}")
            scheduled_tasks = []

        return {
            "success": True,
            "data": {
                "version": str(os.getenv("VERSION", "4.0.0")),
                "environment": str(os.getenv("ENVIRONMENT", "development")),
                "uptime_hours": float(uptime_hours),
                "database_size_mb": float(database_size_mb),
                "last_backup": str(last_backup),
                "scheduled_tasks": scheduled_tasks
            }
        }

    except Exception as e:
        logger.error(f"Failed to get system info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve system information")


@router.get("/system/backup-history")
async def get_backup_history(
    limit: Optional[int] = 10,
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Get database backup history (HEAD ADMIN ONLY)
    Returns list of recent backups with metadata
    """
    import os
    from datetime import datetime

    try:
        backup_dir = "/backups"
        backups = []

        if os.path.exists(backup_dir):
            # Get all backup directories
            backup_folders = [
                d for d in os.listdir(backup_dir)
                if os.path.isdir(os.path.join(backup_dir, d)) and d.startswith("afroo_backup_")
            ]

            # Sort by timestamp (newest first)
            backup_folders.sort(reverse=True)

            # Limit results
            backup_folders = backup_folders[:limit]

            for backup_name in backup_folders:
                backup_path = os.path.join(backup_dir, backup_name)

                # Extract timestamp from name
                timestamp_str = backup_name.replace("afroo_backup_", "")
                try:
                    backup_dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    created_at = backup_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except:
                    created_at = "Unknown"

                # Calculate backup size
                try:
                    backup_size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, _, filenames in os.walk(backup_path)
                        for filename in filenames
                    )
                    size_mb = round(backup_size / (1024 * 1024), 2)
                except:
                    size_mb = 0

                # Determine backup type (could be enhanced with metadata file)
                backup_type = "local"  # Default assumption

                backups.append({
                    "backup_name": backup_name,
                    "backup_type": backup_type,
                    "size_mb": size_mb,
                    "created_at": created_at,
                    "status": "success"  # If exists, assume success
                })

        logger.info(f"Admin {admin_id} viewed backup history: {len(backups)} backups")

        return {
            "success": True,
            "data": backups,
            "count": len(backups)
        }

    except Exception as e:
        logger.error(f"Failed to get backup history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve backup history")


# ============================================================================
# TIER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/tiers/sync")
async def get_tier_sync_data(
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """
    Get all customer tier role assignments for Discord sync.
    Returns list of users with their assigned tiers + role IDs.
    """
    try:
        from app.services.tier_role_service import TierRoleService
        from app.core.config import settings

        result = await TierRoleService.sync_all_tier_roles()

        # Add tier role IDs from settings
        if result.get("success"):
            result["tier_role_ids"] = settings.get_tier_role_ids()

        logger.info(f"Tier sync data requested by {admin_id}")

        return result

    except Exception as e:
        logger.error(f"Failed to get tier sync data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tiers/user/{discord_id}")
async def get_user_tier(
    discord_id: str,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get customer tier for a specific user"""
    try:
        from app.services.tier_role_service import TierRoleService

        tier_info = await TierRoleService.get_user_tier(discord_id)

        if not tier_info:
            return {
                "success": False,
                "error": "User has no tier"
            }

        return {
            "success": True,
            **tier_info
        }

    except Exception as e:
        logger.error(f"Failed to get user tier: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tiers/user/{discord_id}/update")
async def update_user_tier(
    discord_id: str,
    tier: str,
    volume: float,
    admin_id: str = Depends(require_head_admin_bot)
):
    """
    Manually update a user's tier (HEAD ADMIN only).
    Used for overrides and manual adjustments.
    """
    try:
        from app.services.tier_role_service import TierRoleService

        result = await TierRoleService.update_tier_for_user(discord_id, tier, volume)

        logger.info(f"Admin {admin_id} updated tier for {discord_id}: {tier} (${volume:,.2f})")

        return result

    except Exception as e:
        logger.error(f"Failed to update user tier: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tiers/user/{discord_id}")
async def remove_user_tier(
    discord_id: str,
    admin_id: str = Depends(require_head_admin_bot)
):
    """Remove tier from a user (HEAD ADMIN only)"""
    try:
        from app.services.tier_role_service import TierRoleService

        result = await TierRoleService.remove_tier_from_user(discord_id)

        logger.info(f"Admin {admin_id} removed tier from {discord_id}")

        return result

    except Exception as e:
        logger.error(f"Failed to remove user tier: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tiers/distribution")
async def get_tier_distribution(
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get distribution of users across tiers"""
    try:
        from app.services.tier_role_service import TierRoleService

        result = await TierRoleService.get_tier_distribution()

        logger.info(f"Admin {admin_id} viewed tier distribution")

        return result

    except Exception as e:
        logger.error(f"Failed to get tier distribution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
