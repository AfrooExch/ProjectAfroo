"""
Authentication and user context utilities for bot interactions

Provides helper functions and decorators to:
- Extract user context (Discord ID and roles) from interactions
- Handle API errors consistently
- Simplify secure API calls with user authentication
"""

import discord
import logging
from typing import Optional, List, Tuple, Dict, Any, Callable
from functools import wraps

from api.errors import (
    APIError, AuthenticationError, PermissionError,
    NotFoundError, RateLimitError, ValidationError, ServerError
)

logger = logging.getLogger(__name__)


# =======================
# User Context Extraction
# =======================

def get_user_context(interaction: discord.Interaction) -> Tuple[str, List[int]]:
    """
    Extract user context from Discord interaction

    Args:
        interaction: Discord interaction object

    Returns:
        Tuple of (discord_user_id, role_ids)

    Example:
        ```python
        user_id, roles = get_user_context(interaction)
        await api.get_wallet(user_id, roles, "BTC")
        ```
    """
    user_id = str(interaction.user.id)

    # Extract role IDs
    role_ids = []
    if hasattr(interaction.user, 'roles'):
        # Member has roles (in a guild)
        role_ids = [role.id for role in interaction.user.roles]

    return user_id, role_ids


def get_member_context(member: discord.Member) -> Tuple[str, List[int]]:
    """
    Extract user context from Discord member

    Args:
        member: Discord member object

    Returns:
        Tuple of (discord_user_id, role_ids)
    """
    user_id = str(member.id)
    role_ids = [role.id for role in member.roles]
    return user_id, role_ids


# =======================
# Error Handling Decorator
# =======================

def handle_api_errors(
    ephemeral: bool = True,
    show_details: bool = False
):
    """
    Decorator to handle API errors consistently across all cogs

    Catches API errors and sends user-friendly messages to Discord.
    Logs full error details for debugging.

    Args:
        ephemeral: Whether error messages should be ephemeral (default True)
        show_details: Whether to show technical details to user (default False)

    Usage:
        ```python
        @handle_api_errors(ephemeral=True)
        async def my_command(self, ctx: discord.ApplicationContext):
            user_id, roles = get_user_context(ctx.interaction)
            wallet = await self.api.get_wallet(user_id, roles, "BTC")
            # ... rest of command
        ```
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)

            except AuthenticationError as e:
                logger.error(f"Authentication error in {func.__name__}: {e}")
                error_msg = "❌ **Authentication Failed**\n\nYou are not authenticated. Please try again."
                if show_details:
                    error_msg += f"\n\n*Details: {e}*"

                # Try to get interaction from args
                ctx = _get_context_from_args(args)
                if ctx:
                    if ctx.response.is_done():
                        await ctx.followup.send(error_msg, ephemeral=ephemeral)
                    else:
                        await ctx.respond(error_msg, ephemeral=ephemeral)

            except PermissionError as e:
                logger.error(f"Permission error in {func.__name__}: {e}")
                error_msg = "❌ **Permission Denied**\n\nYou don't have permission to perform this action."
                if show_details:
                    error_msg += f"\n\n*Details: {e}*"

                ctx = _get_context_from_args(args)
                if ctx:
                    if ctx.response.is_done():
                        await ctx.followup.send(error_msg, ephemeral=ephemeral)
                    else:
                        await ctx.respond(error_msg, ephemeral=ephemeral)

            except NotFoundError as e:
                logger.error(f"Not found error in {func.__name__}: {e}")
                error_msg = "❌ **Not Found**\n\nThe requested resource could not be found."
                if show_details:
                    error_msg += f"\n\n*Details: {e}*"

                ctx = _get_context_from_args(args)
                if ctx:
                    if ctx.response.is_done():
                        await ctx.followup.send(error_msg, ephemeral=ephemeral)
                    else:
                        await ctx.respond(error_msg, ephemeral=ephemeral)

            except RateLimitError as e:
                logger.error(f"Rate limit error in {func.__name__}: {e}")
                retry_after = getattr(e, 'retry_after', 60)
                error_msg = f"❌ **Rate Limited**\n\nYou're making requests too quickly. Please wait {retry_after} seconds."

                ctx = _get_context_from_args(args)
                if ctx:
                    if ctx.response.is_done():
                        await ctx.followup.send(error_msg, ephemeral=ephemeral)
                    else:
                        await ctx.respond(error_msg, ephemeral=ephemeral)

            except ValidationError as e:
                logger.error(f"Validation error in {func.__name__}: {e}")
                error_msg = "❌ **Invalid Input**\n\nThe data you provided is invalid. Please check and try again."
                if show_details:
                    error_msg += f"\n\n*Details: {e}*"

                ctx = _get_context_from_args(args)
                if ctx:
                    if ctx.response.is_done():
                        await ctx.followup.send(error_msg, ephemeral=ephemeral)
                    else:
                        await ctx.respond(error_msg, ephemeral=ephemeral)

            except ServerError as e:
                logger.error(f"Server error in {func.__name__}: {e}")
                error_msg = "❌ **Server Error**\n\nThe API server encountered an error. Please try again later."
                if show_details:
                    error_msg += f"\n\n*Details: {e}*"

                ctx = _get_context_from_args(args)
                if ctx:
                    if ctx.response.is_done():
                        await ctx.followup.send(error_msg, ephemeral=ephemeral)
                    else:
                        await ctx.respond(error_msg, ephemeral=ephemeral)

            except APIError as e:
                logger.error(f"API error in {func.__name__}: {e}")
                error_msg = "❌ **API Error**\n\nAn error occurred while communicating with the API."
                if show_details:
                    error_msg += f"\n\n*Details: {e}*"

                ctx = _get_context_from_args(args)
                if ctx:
                    if ctx.response.is_done():
                        await ctx.followup.send(error_msg, ephemeral=ephemeral)
                    else:
                        await ctx.respond(error_msg, ephemeral=ephemeral)

            except Exception as e:
                logger.exception(f"Unexpected error in {func.__name__}: {e}")
                error_msg = "❌ **Unexpected Error**\n\nAn unexpected error occurred. Please contact an administrator."
                if show_details:
                    error_msg += f"\n\n*Details: {e}*"

                ctx = _get_context_from_args(args)
                if ctx:
                    try:
                        if ctx.response.is_done():
                            await ctx.followup.send(error_msg, ephemeral=ephemeral)
                        else:
                            await ctx.respond(error_msg, ephemeral=ephemeral)
                    except:
                        logger.error("Failed to send error message to user")

        return wrapper
    return decorator


def _get_context_from_args(args: tuple) -> Optional[discord.ApplicationContext]:
    """
    Helper to extract Discord context from function arguments

    Args:
        args: Function arguments tuple

    Returns:
        Discord ApplicationContext if found, None otherwise
    """
    for arg in args:
        if isinstance(arg, discord.ApplicationContext):
            return arg
        if hasattr(arg, 'interaction') and isinstance(arg.interaction, discord.Interaction):
            return arg
    return None


# =======================
# Permission Checkers
# =======================

def is_admin(interaction: discord.Interaction, config) -> bool:
    """
    Check if user has admin permissions

    Args:
        interaction: Discord interaction
        config: Bot config object

    Returns:
        True if user is admin
    """
    if not hasattr(interaction.user, 'roles'):
        return False

    admin_role_id = config.ROLE_HEAD_ADMIN
    role_ids = {role.id for role in interaction.user.roles}
    return admin_role_id in role_ids


def is_staff(interaction: discord.Interaction, config) -> bool:
    """
    Check if user has staff permissions

    Args:
        interaction: Discord interaction
        config: Bot config object

    Returns:
        True if user is staff or admin
    """
    if not hasattr(interaction.user, 'roles'):
        return False

    staff_role_id = config.ROLE_STAFF
    admin_role_id = config.ROLE_HEAD_ADMIN
    role_ids = {role.id for role in interaction.user.roles}

    return staff_role_id in role_ids or admin_role_id in role_ids


def is_exchanger(interaction: discord.Interaction, config) -> bool:
    """
    Check if user has exchanger permissions

    Args:
        interaction: Discord interaction
        config: Bot config object

    Returns:
        True if user is exchanger, staff, or admin
    """
    if not hasattr(interaction.user, 'roles'):
        return False

    exchanger_role_id = config.ROLE_EXCHANGER
    staff_role_id = config.ROLE_STAFF
    admin_role_id = config.ROLE_HEAD_ADMIN
    role_ids = {role.id for role in interaction.user.roles}

    return (exchanger_role_id in role_ids or
            staff_role_id in role_ids or
            admin_role_id in role_ids)


def require_admin(config):
    """
    Decorator to require admin permissions for a command

    Usage:
        ```python
        @require_admin(config)
        @handle_api_errors()
        async def admin_command(self, ctx: discord.ApplicationContext):
            # Only admins can reach here
            pass
        ```
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract context from args
            ctx = _get_context_from_args(args)
            if not ctx:
                logger.error(f"Could not find context in {func.__name__}")
                return

            # Check admin permission
            if not is_admin(ctx.interaction, config):
                await ctx.respond(
                    "❌ **Admin Only**\n\nThis command requires admin permissions.",
                    ephemeral=True
                )
                return

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_staff(config):
    """
    Decorator to require staff permissions for a command

    Usage:
        ```python
        @require_staff(config)
        @handle_api_errors()
        async def staff_command(self, ctx: discord.ApplicationContext):
            # Only staff/admins can reach here
            pass
        ```
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = _get_context_from_args(args)
            if not ctx:
                logger.error(f"Could not find context in {func.__name__}")
                return

            if not is_staff(ctx.interaction, config):
                await ctx.respond(
                    "❌ **Staff Only**\n\nThis command requires staff permissions.",
                    ephemeral=True
                )
                return

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_exchanger(config):
    """
    Decorator to require exchanger permissions for a command

    Usage:
        ```python
        @require_exchanger(config)
        @handle_api_errors()
        async def exchanger_command(self, ctx: discord.ApplicationContext):
            # Only exchangers/staff/admins can reach here
            pass
        ```
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = _get_context_from_args(args)
            if not ctx:
                logger.error(f"Could not find context in {func.__name__}")
                return

            if not is_exchanger(ctx.interaction, config):
                await ctx.respond(
                    "❌ **Exchanger Only**\n\nThis command requires exchanger permissions.",
                    ephemeral=True
                )
                return

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =======================
# API Call Wrapper
# =======================

class APIContext:
    """
    Context manager for API calls with automatic user context

    Usage:
        ```python
        async with APIContext(interaction, api) as (user_id, roles):
            wallet = await api.get_wallet(user_id, roles, "BTC")
            stats = await api.get_user_stats(user_id, roles)
        ```
    """

    def __init__(self, interaction: discord.Interaction, api):
        """
        Initialize API context

        Args:
            interaction: Discord interaction
            api: APIClient instance
        """
        self.interaction = interaction
        self.api = api
        self.user_id = None
        self.roles = None

    async def __aenter__(self):
        """Enter context - extract user info"""
        self.user_id, self.roles = get_user_context(self.interaction)
        return self.user_id, self.roles

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context"""
        pass
