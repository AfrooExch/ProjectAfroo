"""
API Dependencies - Authentication and common dependencies
Keeps route files clean and focused
"""

from fastapi import Depends, HTTPException, Header, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.core.security import verify_token
from app.core.config import settings
from app.core.database import get_users_collection

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Dependency to get current authenticated user from JWT
    Usage: user = Depends(get_current_user)
    """
    token = credentials.credentials

    try:
        payload = verify_token(token, token_type="access")
        discord_id = payload.get("discord_id")

        if not discord_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_active_user(
    user: dict = Depends(get_current_user)
):
    """
    Dependency to ensure user is active
    Usage: user = Depends(get_current_active_user)
    """
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="User account is not active")
    return user


async def require_admin(
    user: dict = Depends(get_current_active_user)
):
    """
    Dependency to require admin role
    Usage: admin_user = Depends(require_admin)
    """
    if "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_exchanger(
    user: dict = Depends(get_current_active_user)
):
    """
    Dependency to require exchanger role
    Usage: exchanger_user = Depends(require_exchanger)
    """
    if "exchanger" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Exchanger role required")
    return user


async def require_staff(
    user: dict = Depends(get_current_active_user)
):
    """
    Dependency to require staff/mod role (includes admin)
    Usage: staff_user = Depends(require_staff)
    """
    roles = user.get("roles", [])
    if not any(role in roles for role in ["admin", "mod", "staff"]):
        raise HTTPException(status_code=403, detail="Staff access required")
    return user


async def require_partner(
    user: dict = Depends(get_current_active_user)
):
    """
    Dependency to require partner role
    Usage: partner_user = Depends(require_partner)
    """
    if "partner" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Partner access required")
    return user


async def verify_bot_token(
    x_bot_token: str = Header(...),
    x_discord_id: str = Header(...)
):
    """
    Dependency to verify Discord bot requests
    Usage: discord_id = Depends(verify_bot_token)
    """
    if x_bot_token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid bot token")

    users = get_users_collection()
    user = await users.find_one({"discord_id": x_discord_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


async def get_user_from_bot_request(
    request: Request,
    x_bot_token: Optional[str] = Header(None, alias="x-bot-token"),
    x_discord_user_id: Optional[str] = Header(None, alias="x-discord-user-id"),
    x_discord_id: Optional[str] = Header(None, alias="x-discord-id"),
    x_user_id: Optional[str] = Header(None, alias="x-user-id")
):
    """
    Dependency to get user from bot-authenticated requests
    Accepts bot service token + Discord user ID via headers
    Usage: user_id = Depends(get_user_from_bot_request)
    """
    # Check bot token
    if not x_bot_token or x_bot_token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Authentication failed. Please contact support.")

    # Get Discord user ID from any available header
    discord_user_id = x_discord_user_id or x_discord_id or x_user_id
    if not discord_user_id:
        raise HTTPException(status_code=401, detail="Missing Discord user ID")

    # Return the Discord user ID (not the user document, since they may not be in users collection yet)
    return discord_user_id


async def get_optional_user(
    request: Request
):
    """
    Optional authentication - returns user if authenticated, None otherwise
    Usage: user = Depends(get_optional_user)
    """
    # Try to get authorization header
    authorization: str = request.headers.get("Authorization")
    if not authorization:
        return None

    try:
        # Parse Bearer token
        scheme, credentials_str = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            return None

        # Create credentials object and verify
        credentials = HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials_str)
        return await get_current_user(credentials)
    except (ValueError, HTTPException, AttributeError):
        return None


async def require_head_admin(
    user: dict = Depends(get_current_active_user)
):
    """
    Dependency to require Head Admin only (full access)
    Usage: head_admin = Depends(require_head_admin)
    """
    if user.get("discord_id") != str(settings.DISCORD_HEAD_ADMIN_USER_ID):
        raise HTTPException(
            status_code=403,
            detail="Head Admin access required"
        )
    return user


async def require_assistant_admin_or_higher(
    user: dict = Depends(get_current_active_user)
):
    """
    Dependency to require Assistant Admin or Head Admin (tickets, basic stats)
    Usage: admin = Depends(require_assistant_admin_or_higher)
    """
    discord_id = user.get("discord_id")
    if discord_id not in [str(settings.DISCORD_HEAD_ADMIN_USER_ID), str(settings.DISCORD_ASSISTANT_ADMIN_USER_ID)]:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user


# ===========================
# Bot-Compatible Admin Dependencies
# ===========================

async def require_head_admin_bot(request: Request) -> str:
    """
    Dependency for bot-initiated admin requests (HEAD ADMIN ONLY)
    Verifies bot service token + Discord user ID is Head Admin

    Usage: discord_id = Depends(require_head_admin_bot)
    """
    # Head Admin User ID (NOT role ID)
    # Get admin IDs from settings

    # Verify bot token
    x_bot_token = request.headers.get("X-Bot-Token")
    if not x_bot_token or x_bot_token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

    # Check Discord user ID
    x_discord_user_id = request.headers.get("X-Discord-User-ID")
    if not x_discord_user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing Discord user ID"
        )

    # Verify Head Admin
    if x_discord_user_id != str(settings.DISCORD_HEAD_ADMIN_USER_ID):
        raise HTTPException(
            status_code=403,
            detail="Head Admin access required"
        )

    return x_discord_user_id


async def require_assistant_admin_or_higher_bot(request: Request) -> str:
    """
    Dependency for bot-initiated admin requests (ASSISTANT ADMIN OR HIGHER)
    Verifies bot service token + Discord user has Head Admin or Assistant Admin ROLE

    Usage: discord_id = Depends(require_assistant_admin_or_higher_bot)
    """
    # Verify bot token
    x_bot_token = request.headers.get("X-Bot-Token")
    if not x_bot_token or x_bot_token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

    # Check Discord user ID
    x_discord_user_id = request.headers.get("X-Discord-User-ID")
    if not x_discord_user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing Discord user ID"
        )

    # Allow "SYSTEM" for automated background tasks (bot-initiated)
    if x_discord_user_id == "SYSTEM":
        return x_discord_user_id

    # Get roles from request headers (passed by bot)
    x_discord_roles = request.headers.get("X-Discord-Roles", "")
    user_role_ids = []
    if x_discord_roles:
        try:
            user_role_ids = [int(role_id.strip()) for role_id in x_discord_roles.split(",") if role_id.strip()]
        except ValueError:
            pass

    # Verify admin role (check if user has Head Admin or Assistant Admin ROLE in their current roles)
    has_admin_role = (
        settings.ROLE_HEAD_ADMIN in user_role_ids or
        settings.ROLE_ASSISTANT_ADMIN in user_role_ids
    )

    if not has_admin_role:
        # Also check legacy user IDs as fallback
        if x_discord_user_id not in [str(settings.DISCORD_HEAD_ADMIN_USER_ID), str(settings.DISCORD_ASSISTANT_ADMIN_USER_ID)]:
            raise HTTPException(
                status_code=403,
                detail="Admin access required: Only Head Admin or Assistant Admin roles can perform this action"
            )

    return x_discord_user_id
