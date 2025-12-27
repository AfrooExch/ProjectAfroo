"""
User Management Endpoints
Handles user operations, profiles, and Discord integration
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from app.api.deps import (
    get_current_user,
    require_admin,
    require_staff,
    AuthContext
)
from app.services.user_service import user_service
from app.models.user import User, UserUpdate

router = APIRouter()


# ====================
# Request Models
# ====================

class SyncRolesRequest(BaseModel):
    """Request to sync Discord roles"""
    discord_id: str
    role_ids: List[int]
    username: str
    discriminator: str
    global_name: Optional[str] = None


class UserStatsResponse(BaseModel):
    """User statistics"""
    discord_id: str
    username: str
    total_volume: float
    total_trades: int
    reputation_score: int
    vouches_received: int
    success_rate: float
    tier: str


class ComprehensiveStatsResponse(BaseModel):
    """Comprehensive user statistics from stats_tracking_service"""
    # Client Exchange Stats
    client_total_exchanges: int = 0
    client_completed_exchanges: int = 0
    client_cancelled_exchanges: int = 0
    client_exchange_volume_usd: float = 0.0

    # Exchanger Stats
    exchanger_total_completed: int = 0
    exchanger_total_claimed: int = 0
    exchanger_total_fees_paid_usd: float = 0.0
    exchanger_total_profit_usd: float = 0.0
    exchanger_exchange_volume_usd: float = 0.0
    exchanger_tickets_completed: int = 0

    # Swap Stats
    swap_total_made: int = 0
    swap_total_completed: int = 0
    swap_total_failed: int = 0
    swap_total_volume_usd: float = 0.0

    # AutoMM Stats
    automm_total_created: int = 0
    automm_total_completed: int = 0
    automm_total_volume_usd: float = 0.0

    # Wallet Stats
    wallet_total_deposited_usd: float = 0.0
    wallet_total_withdrawn_usd: float = 0.0

    # User Info
    reputation_score: int = 100
    roles: List[str] = []


# ====================
# Public Endpoints
# ====================

@router.post("/sync-roles")
async def sync_discord_roles(
    request: SyncRolesRequest,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Sync Discord roles to database

    Called by bot when:
    - User roles change
    - User joins server
    - User interacts with bot
    - Bot starts up

    Headers:
        - Authorization: Bearer <BOT_SERVICE_TOKEN>
        - X-Discord-User-ID: <discord_user_id>
        - X-Discord-Roles: <comma_separated_role_ids>
    """
    # Get or create user
    user = await user_service.get_by_discord_id(request.discord_id)

    if not user:
        # Create new user
        user = await user_service.create_from_discord(
            discord_id=request.discord_id,
            username=request.username,
            discriminator=request.discriminator,
            global_name=request.global_name
        )
    else:
        # Update Discord info
        await user_service.update_discord_info(
            discord_id=request.discord_id,
            username=request.username,
            discriminator=request.discriminator,
            global_name=request.global_name
        )

    # Sync roles
    await user_service.sync_discord_roles(
        discord_id=request.discord_id,
        role_ids=request.role_ids
    )

    return {
        "success": True,
        "message": "Roles synced successfully",
        "user_id": request.discord_id,
        "role_count": len(request.role_ids)
    }


@router.get("/me")
async def get_current_user_profile(
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get current user's profile

    Works for both bot and web requests
    """
    user = auth.user

    return {
        "discord_id": user.get("discord_id"),
        "username": user.get("username"),
        "discriminator": user.get("discriminator"),
        "global_name": user.get("global_name"),
        "avatar_hash": user.get("avatar_hash"),
        "status": user.get("status"),
        "kyc_level": user.get("kyc_level"),
        "reputation_score": user.get("reputation_score"),
        "created_at": user.get("created_at"),
        "permissions": {
            "is_admin": auth.is_admin,
            "is_staff": auth.is_staff,
            "is_exchanger": auth.is_exchanger
        }
    }


@router.get("/{discord_id}/stats")
async def get_user_stats(
    discord_id: str,
    auth: AuthContext = Depends(get_current_user)
) -> UserStatsResponse:
    """
    Get user statistics

    Public endpoint - anyone can view user stats
    """
    from app.services.stats_service import stats_service

    user = await user_service.get_by_discord_id(discord_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    stats = await stats_service.get_user_stats(discord_id)

    return UserStatsResponse(
        discord_id=discord_id,
        username=user.get("username", "Unknown"),
        total_volume=stats.get("total_volume", 0),
        total_trades=stats.get("total_trades", 0),
        reputation_score=user.get("reputation_score", 100),
        vouches_received=stats.get("vouches_received", 0),
        success_rate=stats.get("success_rate", 0),
        tier=stats.get("tier", "bronze")
    )


@router.get("/{discord_id}/comprehensive-stats")
async def get_comprehensive_stats(
    discord_id: str
) -> ComprehensiveStatsResponse:
    """
    Get comprehensive user statistics from stats_tracking_service

    Public endpoint - anyone can view user stats (NO AUTH REQUIRED)
    """
    from app.services.stats_tracking_service import StatsTrackingService

    user = await user_service.get_by_discord_id(discord_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Get MongoDB user_id from user document
    user_id = str(user.get("_id"))

    # Get comprehensive stats from stats_tracking_service
    stats = await StatsTrackingService.get_user_stats(user_id)

    return ComprehensiveStatsResponse(
        # Client Exchange Stats
        client_total_exchanges=stats.get("client_total_exchanges", 0),
        client_completed_exchanges=stats.get("client_completed_exchanges", 0),
        client_cancelled_exchanges=stats.get("client_cancelled_exchanges", 0),
        client_exchange_volume_usd=stats.get("client_exchange_volume_usd", 0.0),

        # Exchanger Stats
        exchanger_total_completed=stats.get("exchanger_total_completed", 0),
        exchanger_total_claimed=stats.get("exchanger_total_claimed", 0),
        exchanger_total_fees_paid_usd=stats.get("exchanger_total_fees_paid_usd", 0.0),
        exchanger_total_profit_usd=stats.get("exchanger_total_profit_usd", 0.0),
        exchanger_exchange_volume_usd=stats.get("exchanger_exchange_volume_usd", 0.0),
        exchanger_tickets_completed=stats.get("exchanger_tickets_completed", 0),

        # Swap Stats
        swap_total_made=stats.get("swap_total_made", 0),
        swap_total_completed=stats.get("swap_total_completed", 0),
        swap_total_failed=stats.get("swap_total_failed", 0),
        swap_total_volume_usd=stats.get("swap_total_volume_usd", 0.0),

        # AutoMM Stats
        automm_total_created=stats.get("automm_total_created", 0),
        automm_total_completed=stats.get("automm_total_completed", 0),
        automm_total_volume_usd=stats.get("automm_total_volume_usd", 0.0),

        # Wallet Stats
        wallet_total_deposited_usd=stats.get("wallet_total_deposited_usd", 0.0),
        wallet_total_withdrawn_usd=stats.get("wallet_total_withdrawn_usd", 0.0),

        # User Info
        reputation_score=user.get("reputation_score", 100),
        roles=user.get("roles", [])
    )


@router.get("/{discord_id}")
async def get_user(
    discord_id: str,
    auth: AuthContext = Depends(get_current_user)
):
    """
    Get user by Discord ID

    Admins can view any user
    Users can only view their own profile
    """
    # Check permissions
    if not auth.is_admin and auth.user.get("discord_id") != discord_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to view this user"
        )

    user = await user_service.get_by_discord_id(discord_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "discord_id": user.get("discord_id"),
        "username": user.get("username"),
        "discriminator": user.get("discriminator"),
        "global_name": user.get("global_name"),
        "avatar_hash": user.get("avatar_hash"),
        "status": user.get("status"),
        "reputation_score": user.get("reputation_score"),
        "created_at": user.get("created_at")
    }


# ====================
# Admin Endpoints
# ====================

@router.get("/", dependencies=[Depends(require_admin)])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    auth: AuthContext = Depends(require_admin)
):
    """
    List all users (admin only)

    Query params:
        - skip: Number to skip (pagination)
        - limit: Max results (max 100)
        - status: Filter by status (active, suspended, banned)
    """
    from app.core.database import get_users_collection

    users_collection = get_users_collection()

    # Build query
    query = {}
    if status:
        query["status"] = status

    # Get users
    cursor = users_collection.find(query).skip(skip).limit(min(limit, 100))
    users = await cursor.to_list(length=limit)

    # Get total count
    total = await users_collection.count_documents(query)

    return {
        "users": [
            {
                "discord_id": u.get("discord_id"),
                "username": u.get("username"),
                "status": u.get("status"),
                "reputation_score": u.get("reputation_score"),
                "created_at": u.get("created_at")
            }
            for u in users
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/{discord_id}/freeze", dependencies=[Depends(require_admin)])
async def freeze_user(
    discord_id: str,
    reason: str,
    auth: AuthContext = Depends(require_admin)
):
    """
    Freeze user account (admin only)

    Prevents user from performing any operations
    """
    user = await user_service.get_by_discord_id(discord_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    await user_service.suspend_user(
        user_id=str(user["_id"]),
        reason=reason,
        admin_id=str(auth.user.get("_id"))
    )

    return {
        "success": True,
        "message": f"User {discord_id} frozen",
        "reason": reason
    }


@router.post("/{discord_id}/unfreeze", dependencies=[Depends(require_admin)])
async def unfreeze_user(
    discord_id: str,
    auth: AuthContext = Depends(require_admin)
):
    """
    Unfreeze user account (admin only)

    Restores user's ability to perform operations
    """
    from app.core.database import get_users_collection

    users_collection = get_users_collection()

    result = await users_collection.update_one(
        {"discord_id": discord_id},
        {
            "$set": {
                "status": "active"
            },
            "$unset": {
                "suspension_reason": "",
                "suspended_at": "",
                "suspended_by": ""
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "success": True,
        "message": f"User {discord_id} unfrozen"
    }


@router.delete("/{discord_id}/ban", dependencies=[Depends(require_admin)])
async def ban_user(
    discord_id: str,
    reason: str,
    auth: AuthContext = Depends(require_admin)
):
    """
    Ban user permanently (admin only)

    User will not be able to use the platform
    """
    user = await user_service.get_by_discord_id(discord_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    await user_service.ban_user(
        user_id=str(user["_id"]),
        reason=reason,
        admin_id=str(auth.user.get("_id"))
    )

    return {
        "success": True,
        "message": f"User {discord_id} banned",
        "reason": reason
    }
