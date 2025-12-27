"""
API Dependencies - Authentication and Authorization
Secure bot and web authentication with permission validation
"""

from typing import Optional
from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from jose.exceptions import JWTError as PyJWTError

from app.core.config import settings
from app.models.user import User
from app.services.user_service import user_service

security = HTTPBearer()


class AuthContext:
    """Authentication context"""
    def __init__(
        self,
        user: User,
        auth_type: str,  # "bot" or "web"
        is_admin: bool = False,
        is_staff: bool = False,
        is_exchanger: bool = False
    ):
        self.user = user
        self.auth_type = auth_type
        self.is_admin = is_admin
        self.is_staff = is_staff
        self.is_exchanger = is_exchanger


async def verify_bot_service_token(
    authorization: str = Header(None)
) -> bool:
    """
    Verify bot service token

    Returns True if valid, raises exception otherwise
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )

    token = authorization.replace("Bearer ", "")

    # Verify service token matches
    if token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid bot service token"
        )

    return True


async def get_current_user_bot(
    x_discord_user_id: Optional[str] = Header(None, alias="X-Discord-User-ID"),
    x_discord_roles: Optional[str] = Header(None, alias="X-Discord-Roles"),
    is_bot: bool = Depends(verify_bot_service_token)
) -> AuthContext:
    """
    Get current user from bot request

    Headers required:
        - Authorization: Bearer <BOT_SERVICE_TOKEN>
        - X-Discord-User-ID: <discord_user_id>
        - X-Discord-Roles: <comma_separated_role_ids>

    Returns AuthContext with user and permissions
    """
    if not x_discord_user_id:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Discord-User-ID header"
        )

    # Get or create user
    user = await user_service.get_by_discord_id(x_discord_user_id)
    if not user:
        # Auto-create user on first interaction
        user = await user_service.create_from_discord(
            discord_id=x_discord_user_id,
            username="Unknown",  # Bot should update this
            discriminator="0000"
        )

    # Parse roles
    role_ids = []
    if x_discord_roles:
        try:
            role_ids = [int(r) for r in x_discord_roles.split(",") if r.strip()]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid X-Discord-Roles format"
            )

    # Sync roles to user
    await user_service.sync_discord_roles(x_discord_user_id, role_ids)

    # Check permissions
    is_admin = await user_service.is_admin(x_discord_user_id)
    is_staff = await user_service.is_staff(x_discord_user_id)
    is_exchanger = await user_service.is_exchanger(x_discord_user_id)

    return AuthContext(
        user=user,
        auth_type="bot",
        is_admin=is_admin,
        is_staff=is_staff,
        is_exchanger=is_exchanger
    )


async def get_current_user_web(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthContext:
    """
    Get current user from web JWT token

    Headers required:
        - Authorization: Bearer <USER_JWT>

    Returns AuthContext with user and permissions
    """
    token = credentials.credentials

    # Check if it's bot service token (shouldn't be used here)
    if token == settings.BOT_SERVICE_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Bot service token not valid for web endpoints"
        )

    # Decode JWT
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        discord_id = payload.get("discord_id")
        if not discord_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload"
            )
    except PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    # Get user
    user = await user_service.get_by_discord_id(discord_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Check permissions
    is_admin = await user_service.is_admin(discord_id)
    is_staff = await user_service.is_staff(discord_id)
    is_exchanger = await user_service.is_exchanger(discord_id)

    return AuthContext(
        user=user,
        auth_type="web",
        is_admin=is_admin,
        is_staff=is_staff,
        is_exchanger=is_exchanger
    )


async def get_current_user(
    authorization: str = Header(None),
    x_discord_user_id: Optional[str] = Header(None, alias="X-Discord-User-ID"),
    x_discord_roles: Optional[str] = Header(None, alias="X-Discord-Roles")
) -> AuthContext:
    """
    Get current user from either bot or web authentication

    Bot requests:
        - Authorization: Bearer <BOT_SERVICE_TOKEN>
        - X-Discord-User-ID: <discord_user_id>
        - X-Discord-Roles: <comma_separated_role_ids>

    Web requests:
        - Authorization: Bearer <USER_JWT>

    Returns AuthContext with user and permissions
    """
    import logging
    logger = logging.getLogger(__name__)

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )

    token = authorization.replace("Bearer ", "")
    logger.info(f"[AUTH] Token received (first 20 chars): {token[:20]}...")
    logger.info(f"[AUTH] Expected bot token (first 20 chars): {settings.BOT_SERVICE_TOKEN[:20]}...")
    logger.info(f"[AUTH] Token matches bot token: {token == settings.BOT_SERVICE_TOKEN}")
    logger.info(f"[AUTH] X-Discord-User-ID header: {x_discord_user_id}")

    # Check if it's bot service token
    if token == settings.BOT_SERVICE_TOKEN:
        # Bot authentication
        if not x_discord_user_id:
            raise HTTPException(
                status_code=400,
                detail="Bot requests require X-Discord-User-ID header"
            )

        # Verify and get user
        await verify_bot_service_token(authorization)
        return await get_current_user_bot(x_discord_user_id, x_discord_roles, True)

    # Otherwise, web JWT authentication
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        discord_id = payload.get("discord_id")
        if not discord_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload"
            )
    except PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    # Get user
    user = await user_service.get_by_discord_id(discord_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Check permissions
    is_admin = await user_service.is_admin(discord_id)
    is_staff = await user_service.is_staff(discord_id)
    is_exchanger = await user_service.is_exchanger(discord_id)

    return AuthContext(
        user=user,
        auth_type="web",
        is_admin=is_admin,
        is_staff=is_staff,
        is_exchanger=is_exchanger
    )


# Permission-specific dependencies

async def require_admin(
    auth: AuthContext = Depends(get_current_user)
) -> AuthContext:
    """Require admin permissions"""
    if not auth.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin permissions required"
        )
    return auth


async def require_staff(
    auth: AuthContext = Depends(get_current_user)
) -> AuthContext:
    """Require staff permissions (staff or admin)"""
    if not auth.is_staff and not auth.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Staff permissions required"
        )
    return auth


async def require_exchanger(
    auth: AuthContext = Depends(get_current_user)
) -> AuthContext:
    """Require exchanger permissions"""
    if not auth.is_exchanger and not auth.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Exchanger permissions required"
        )
    return auth


# Resource ownership validation

async def validate_wallet_ownership(
    wallet_id: str,
    auth: AuthContext = Depends(get_current_user)
) -> AuthContext:
    """Validate user owns the wallet"""
    from app.services.wallet_service import wallet_service

    wallet = await wallet_service.get_wallet_by_id(wallet_id)
    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    # Admin can access any wallet
    if auth.is_admin:
        return auth

    # Otherwise, must be owner
    if wallet.owner_discord_id != auth.user.discord_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this wallet"
        )

    return auth


async def validate_ticket_access(
    ticket_id: str,
    auth: AuthContext = Depends(get_current_user)
) -> AuthContext:
    """Validate user can access the ticket"""
    from app.services.ticket_service import ticket_service

    ticket = await ticket_service.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    # Admin/staff can access any ticket
    if auth.is_admin or auth.is_staff:
        return auth

    # Customer can access their own tickets
    if ticket.customer_id == auth.user.discord_id:
        return auth

    # Exchanger can access tickets they claimed
    if ticket.exchanger_id == auth.user.discord_id:
        return auth

    raise HTTPException(
        status_code=403,
        detail="You don't have permission to access this ticket"
    )


async def validate_deposit_access(
    auth: AuthContext = Depends(get_current_user)
) -> AuthContext:
    """Validate user can access exchanger deposits"""
    # Only exchangers and admins can access deposit system
    if not auth.is_exchanger and not auth.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Exchanger permissions required to access deposits"
        )
    return auth
