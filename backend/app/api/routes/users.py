"""
User Routes - Profile management
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional, List
from pydantic import BaseModel

from app.api.dependencies import get_current_active_user, require_admin, get_user_from_bot_request
from app.services.user_service import UserService
from app.models.user import UserUpdate

router = APIRouter(tags=["Users"])


class SyncRolesRequest(BaseModel):
    """Request to sync Discord roles"""
    discord_id: str
    role_ids: List[int]
    role_names: Optional[List[str]] = []
    username: str
    discriminator: str
    global_name: Optional[str] = None


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


@router.post("/sync-roles")
async def sync_discord_roles(
    request: SyncRolesRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Sync Discord roles to database

    Called by bot when:
    - User roles change
    - User joins server
    - User interacts with bot
    - Bot starts up
    """
    try:
        # Get or create user
        user = await UserService.get_by_discord_id(request.discord_id)

        if not user:
            # Create new user
            try:
                user_id = await UserService.create_user(request.discord_id)
                # Fetch the newly created user
                user = await UserService.get_by_discord_id(request.discord_id)
            except Exception as e:
                # If creation fails, user might already exist, try fetching again
                user = await UserService.get_by_discord_id(request.discord_id)
                if not user:
                    raise HTTPException(status_code=500, detail=f"Failed to create/fetch user: {str(e)}")

        # Update Discord info and roles
        from app.core.database import get_users_collection
        from bson import ObjectId

        users = get_users_collection()

        # Convert role IDs to strings for storage
        role_ids_str = [str(rid) for rid in request.role_ids]

        # Use discord_id to find user (more reliable)
        await users.update_one(
            {"discord_id": request.discord_id},
            {
                "$set": {
                    "username": request.username,
                    "discriminator": request.discriminator,
                    "global_name": request.global_name,
                    "discord_role_ids": role_ids_str,
                    "roles": request.role_names  # Store role names for display
                }
            }
        )

        return {
            "success": True,
            "message": "Roles synced successfully",
            "user_id": request.discord_id,
            "role_count": len(request.role_ids)
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error syncing roles for {request.discord_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync roles: {str(e)}")


@router.get("/me")
async def get_current_user_profile(
    user: dict = Depends(get_current_active_user)
):
    """Get current user's profile (JWT auth)"""

    # Remove sensitive fields
    user.pop("encrypted_private_key", None)
    user.pop("login_history", None)

    return {
        "id": str(user["_id"]),
        "discord_id": user["discord_id"],
        "username": user["username"],
        "global_name": user.get("global_name"),
        "avatar_hash": user.get("avatar_hash"),
        "status": user["status"],
        "kyc_level": user.get("kyc_level", 0),
        "reputation_score": user.get("reputation_score", 100),
        "roles": user.get("roles", []),
        "created_at": user["created_at"],
        "last_login_at": user.get("last_login_at")
    }


@router.get("/profile")
async def get_user_profile_by_bot(
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Get user's profile via bot token authentication"""
    from app.services.user_service import UserService

    user = await UserService.get_by_discord_id(discord_user_id)

    if not user:
        # Create user if doesn't exist
        user = await UserService.create_user(discord_user_id)

    # Remove sensitive fields
    user.pop("encrypted_private_key", None)
    user.pop("login_history", None)

    return {
        "id": str(user["_id"]),
        "discord_id": user["discord_id"],
        "username": user.get("username", "Unknown"),
        "global_name": user.get("global_name"),
        "avatar_hash": user.get("avatar_hash"),
        "status": user.get("status", "active"),
        "kyc_level": user.get("kyc_level", 0),
        "reputation_score": user.get("reputation_score", 100),
        "roles": user.get("roles", []),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at")
    }


@router.get("/{discord_id}/comprehensive-stats")
async def get_comprehensive_stats(
    discord_id: str
) -> ComprehensiveStatsResponse:
    """
    Get comprehensive user statistics from stats_tracking_service

    Public endpoint - anyone can view user stats (NO AUTH REQUIRED)
    """
    from app.services.stats_tracking_service import StatsTrackingService

    user = await UserService.get_by_discord_id(discord_id)
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
async def get_user_by_discord_id(
    discord_id: str,
    user: dict = Depends(get_current_active_user)
):
    """Get user by Discord ID (public profile)"""

    target_user = await UserService.get_by_discord_id(discord_id)

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Return only public fields
    return {
        "discord_id": target_user["discord_id"],
        "username": target_user["username"],
        "global_name": target_user.get("global_name"),
        "avatar_hash": target_user.get("avatar_hash"),
        "reputation_score": target_user.get("reputation_score", 100),
        "kyc_level": target_user.get("kyc_level", 0),
        "created_at": target_user["created_at"]
    }


@router.patch("/me")
async def update_current_user(
    update_data: UserUpdate,
    user: dict = Depends(get_current_active_user)
):
    """Update current user's profile"""

    user_id = str(user["_id"])
    updated_user = await UserService.update_user(user_id, update_data)

    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "Profile updated successfully",
        "user": {
            "id": str(updated_user["_id"]),
            "username": updated_user["username"],
            "global_name": updated_user.get("global_name"),
            "updated_at": updated_user["updated_at"]
        }
    }


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    reason: str,
    admin: dict = Depends(require_admin)
):
    """Suspend user (admin only)"""

    admin_id = str(admin["_id"])
    result = await UserService.suspend_user(user_id, reason, admin_id)

    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "User suspended successfully",
        "user_id": user_id,
        "reason": reason
    }


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: str,
    reason: str,
    admin: dict = Depends(require_admin)
):
    """Ban user permanently (admin only)"""

    admin_id = str(admin["_id"])
    result = await UserService.ban_user(user_id, reason, admin_id)

    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "User banned successfully",
        "user_id": user_id,
        "reason": reason
    }
