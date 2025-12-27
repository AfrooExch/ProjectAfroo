"""
Decorators - Permission checks and utilities
"""

import functools
import logging
from typing import Callable, List
import discord
from discord.ext import commands

from config import config
from api.errors import PermissionError
from utils.embeds import create_permission_error_embed

logger = logging.getLogger(__name__)


def require_role(*role_names: str):
    """
    Decorator to require specific roles

    Args:
        *role_names: Role names (owner, admin, staff, exchanger, customer)

    Example:
        @require_role("admin")
        async def admin_command(ctx):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(self, ctx: discord.ApplicationContext, *args, **kwargs):
            # Check if user has required role
            user = ctx.author

            has_permission = False

            for role_name in role_names:
                if role_name == "owner" and config.is_admin(user):
                    has_permission = True
                    break
                elif role_name == "admin" and config.is_admin(user):
                    has_permission = True
                    break
                elif role_name == "staff" and (config.is_staff(user) or config.is_admin(user)):
                    has_permission = True
                    break
                elif role_name == "exchanger" and (config.is_exchanger(user) or config.is_admin(user)):
                    has_permission = True
                    break
                elif role_name == "customer":
                    # Everyone can be a customer
                    has_permission = True
                    break

            if not has_permission:
                logger.warning(
                    f"Permission denied: {user.name} tried to use {func.__name__} "
                    f"(requires: {', '.join(role_names)})"
                )
                await ctx.respond(
                    embed=create_permission_error_embed(),
                    ephemeral=True
                )
                return

            # User has permission, execute command
            return await func(self, ctx, *args, **kwargs)

        return wrapper
    return decorator


def require_admin():
    """Decorator to require admin role"""
    return require_role("admin")


def require_staff():
    """Decorator to require staff role"""
    return require_role("staff")


def require_exchanger():
    """Decorator to require exchanger role"""
    return require_role("exchanger")


def defer_response(ephemeral: bool = False):
    """
    Decorator to automatically defer response

    Args:
        ephemeral: Whether to defer with ephemeral flag

    Example:
        @defer_response(ephemeral=True)
        async def slow_command(ctx):
            # Response is automatically deferred
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(self, ctx: discord.ApplicationContext, *args, **kwargs):
            # Defer response
            await ctx.defer(ephemeral=ephemeral)

            # Execute command
            return await func(self, ctx, *args, **kwargs)

        return wrapper
    return decorator
