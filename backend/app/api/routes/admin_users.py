"""
Admin User Management Routes - Edit stats, roles, manage users
HEAD ADMIN ONLY
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel

from app.api.dependencies import require_head_admin, require_head_admin_bot
from app.core.database import get_users_collection, get_db_collection, get_audit_logs_collection

router = APIRouter(tags=["Admin - Users"])


class EditUserStatsRequest(BaseModel):
    """Edit user statistics"""
    discord_id: str
    total_exchanges: Optional[int] = None
    completed_exchanges: Optional[int] = None
    total_swaps: Optional[int] = None
    completed_swaps: Optional[int] = None
    total_volume_usd: Optional[float] = None
    reputation_score: Optional[int] = None


class EditUserRolesRequest(BaseModel):
    """Edit user roles"""
    discord_id: str
    roles: List[str]


class UpdateUserStatusRequest(BaseModel):
    """Update user status"""
    discord_id: str
    status: str  # active, suspended, banned
    reason: Optional[str] = None


@router.post("/users/edit-stats")
async def edit_user_stats(
    request: EditUserStatsRequest,
    admin_id: str = Depends(require_head_admin_bot)
):
    """Edit user statistics (HEAD ADMIN ONLY)"""
    users = get_users_collection()
    user_statistics = await get_db_collection("user_statistics")
    audit_logs = get_audit_logs_collection()

    # Get user
    user = await users.find_one({"discord_id": request.discord_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prepare update
    update_fields = {}
    changes = {}

    if request.reputation_score is not None:
        update_fields["reputation_score"] = request.reputation_score
        changes["reputation_score"] = request.reputation_score

    if update_fields:
        await users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    **update_fields,
                    "updated_at": datetime.utcnow()
                }
            }
        )

    # Update user_statistics
    stats_update = {}
    if request.total_exchanges is not None:
        stats_update["total_exchanges"] = request.total_exchanges
        changes["total_exchanges"] = request.total_exchanges
    if request.completed_exchanges is not None:
        stats_update["completed_exchanges"] = request.completed_exchanges
        changes["completed_exchanges"] = request.completed_exchanges
    if request.total_swaps is not None:
        stats_update["total_swaps"] = request.total_swaps
        changes["total_swaps"] = request.total_swaps
    if request.completed_swaps is not None:
        stats_update["completed_swaps"] = request.completed_swaps
        changes["completed_swaps"] = request.completed_swaps
    if request.total_volume_usd is not None:
        stats_update["total_volume_usd"] = request.total_volume_usd
        changes["total_volume_usd"] = request.total_volume_usd

    if stats_update:
        await user_statistics.update_one(
            {"user_id": user["_id"]},
            {
                "$set": {
                    **stats_update,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )

    # Log action
    await audit_logs.insert_one({
        "actor_type": "admin",
        "actor_id": head_admin["_id"],
        "action": "user_edit_stats",
        "resource_type": "user",
        "resource_id": user["_id"],
        "details": {
            "user_discord_id": request.discord_id,
            "changes": changes
        },
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "message": "User stats updated",
        "discord_id": request.discord_id,
        "changes": changes
    }


@router.post("/users/edit-roles")
async def edit_user_roles(
    request: EditUserRolesRequest,
    admin_id: str = Depends(require_head_admin_bot)
):
    """Edit user roles (HEAD ADMIN ONLY)"""
    users = get_users_collection()
    audit_logs = get_audit_logs_collection()

    # Get user
    user = await users.find_one({"discord_id": request.discord_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_roles = user.get("roles", [])

    # Update roles
    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "roles": request.roles,
                "updated_at": datetime.utcnow()
            }
        }
    )

    # Log action
    await audit_logs.insert_one({
        "actor_type": "admin",
        "actor_id": head_admin["_id"],
        "action": "user_edit_roles",
        "resource_type": "user",
        "resource_id": user["_id"],
        "details": {
            "user_discord_id": request.discord_id,
            "old_roles": old_roles,
            "new_roles": request.roles
        },
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "message": "User roles updated",
        "discord_id": request.discord_id,
        "old_roles": old_roles,
        "new_roles": request.roles
    }


@router.post("/users/update-status")
async def update_user_status(
    request: UpdateUserStatusRequest,
    admin_id: str = Depends(require_head_admin_bot)
):
    """Update user status (active/suspended/banned) (HEAD ADMIN ONLY)"""
    users = get_users_collection()
    audit_logs = get_audit_logs_collection()

    valid_statuses = ["active", "suspended", "banned"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    # Get user
    user = await users.find_one({"discord_id": request.discord_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_status = user.get("status", "active")

    # Update status
    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "status": request.status,
                "status_reason": request.reason,
                "status_updated_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        }
    )

    # Log action
    await audit_logs.insert_one({
        "actor_type": "admin",
        "actor_id": head_admin["_id"],
        "action": "user_status_change",
        "resource_type": "user",
        "resource_id": user["_id"],
        "details": {
            "user_discord_id": request.discord_id,
            "old_status": old_status,
            "new_status": request.status,
            "reason": request.reason
        },
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "message": f"User status changed to {request.status}",
        "discord_id": request.discord_id,
        "old_status": old_status,
        "new_status": request.status
    }


@router.get("/users/exchangers")
async def get_all_exchangers(
    limit: int = 100,
    admin_id: str = Depends(require_head_admin_bot)
):
    """Get all exchangers with deposits and stats (HEAD ADMIN ONLY)"""
    users = get_users_collection()
    exchanger_deposits = await get_db_collection("exchanger_deposits")

    # Find all users with "Exchanger" role (capital E)
    exchangers = await users.find({"roles": "Exchanger"}).limit(limit).to_list(length=limit)

    exchanger_list = []
    for exchanger in exchangers:
        # Get deposits
        deposits = await exchanger_deposits.find({"user_id": exchanger["_id"]}).to_list(length=100)

        total_balance_usd = sum(float(d.get("balance_usd", 0)) for d in deposits)
        total_held_usd = sum(float(d.get("held_usd", 0)) for d in deposits)
        total_fee_reserved_usd = sum(float(d.get("fee_reserved_usd", 0)) for d in deposits)

        exchanger_list.append({
            "discord_id": exchanger["discord_id"],
            "username": exchanger.get("username"),
            "status": exchanger.get("status"),
            "reputation_score": exchanger.get("reputation_score", 100),
            "total_balance_usd": round(total_balance_usd, 2),
            "total_held_usd": round(total_held_usd, 2),
            "total_fee_reserved_usd": round(total_fee_reserved_usd, 2),
            "deposit_count": len(deposits),
            "created_at": exchanger["created_at"].isoformat() if exchanger.get("created_at") else None
        })

    return {
        "exchangers": exchanger_list,
        "count": len(exchanger_list)
    }
