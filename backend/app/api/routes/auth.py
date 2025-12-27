"""
Authentication Routes - Discord OAuth2 & JWT
"""

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import RedirectResponse
import httpx
from datetime import timedelta

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.core.redis import SessionService
from app.services.user_service import UserService
from app.models.user import UserCreate

router = APIRouter(tags=["Authentication"])


@router.get("/discord/login")
async def discord_login():
    """Redirect to Discord OAuth2"""
    oauth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={settings.DISCORD_CLIENT_ID}"
        f"&redirect_uri={settings.DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email"
    )
    return {"url": oauth_url}


@router.get("/discord/callback")
async def discord_callback(code: str, request: Request):
    """Handle Discord OAuth2 callback"""

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": settings.DISCORD_CLIENT_ID,
                "client_secret": settings.DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Discord token")

        token_data = token_response.json()
        access_token = token_data["access_token"]

        # Get user info from Discord
        user_response = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Discord user")

        discord_user = user_response.json()

    # Create or update user
    discord_id = discord_user["id"]
    existing_user = await UserService.get_by_discord_id(discord_id)

    if existing_user:
        # Update login info and Discord profile data
        client_ip = request.client.host if request.client else "unknown"
        await UserService.update_login_info(
            discord_id,
            client_ip,
            username=discord_user["username"],
            discriminator=discord_user.get("discriminator", "0"),
            global_name=discord_user.get("global_name"),
            avatar_hash=discord_user.get("avatar")
        )
        user = existing_user
    else:
        # Create new user
        user_data = UserCreate(
            discord_id=discord_id,
            username=discord_user["username"],
            discriminator=discord_user.get("discriminator", "0"),
            global_name=discord_user.get("global_name"),
            avatar_hash=discord_user.get("avatar"),
            email=discord_user.get("email")
        )
        user = await UserService.create_user(user_data)

    # Generate JWT tokens
    token_data = {"discord_id": discord_id, "user_id": str(user["_id"])}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token in Redis
    await SessionService.store_refresh_token(
        refresh_token,
        discord_id,
        ttl=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "discord_id": user["discord_id"],
            "username": user["username"],
            "global_name": user.get("global_name"),
            "avatar_hash": user.get("avatar_hash"),
            "roles": user.get("roles", [])
        }
    }


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token"""

    try:
        payload = verify_token(refresh_token, token_type="refresh")
        discord_id = payload.get("discord_id")

        # Verify token exists in Redis
        is_valid = await SessionService.verify_refresh_token(refresh_token, discord_id)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Get user data
        user = await UserService.get_by_discord_id(discord_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Generate new tokens
        token_data = {"discord_id": discord_id, "user_id": payload.get("user_id")}
        new_access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)

        # Store new refresh token in Redis
        await SessionService.store_refresh_token(
            new_refresh_token,
            discord_id,
            ttl=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        )

        # Delete old refresh token
        await SessionService.delete_refresh_token(refresh_token)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user["_id"]),
                "discord_id": user["discord_id"],
                "username": user["username"],
                "global_name": user.get("global_name"),
                "avatar_hash": user.get("avatar_hash"),
                "discriminator": user.get("discriminator", "0"),
                "email": user.get("email"),
                "roles": user.get("roles", [])
            }
        }

    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/logout")
async def logout(refresh_token: str):
    """Logout and invalidate refresh token"""

    try:
        payload = verify_token(refresh_token, token_type="refresh")
        discord_id = payload.get("discord_id")

        # Delete refresh token from Redis
        await SessionService.delete_refresh_token(refresh_token)

        return {"message": "Logged out successfully"}

    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
