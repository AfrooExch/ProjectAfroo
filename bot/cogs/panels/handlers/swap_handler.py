"""
Swap Ticket Handler - Creates private swap channels with QR codes and management views
"""

import discord
import logging
import asyncio
import io
from typing import Dict, Any

from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED
from utils.auth import get_user_context
from cogs.panels.views.swap_management import SwapManagementView
from config import config

logger = logging.getLogger(__name__)


async def create_swap_ticket(
    bot: discord.Bot,
    user: discord.Member,
    guild: discord.Guild,
    session_data: Dict[str, Any]
):
    """
    Create private swap ticket channel with QR code and management controls

    Args:
        bot: Discord bot instance
        user: User creating the swap
        guild: Guild instance
        session_data: Session data with from_asset, to_asset, amount, quote
    """
    try:
        # Extract session data
        from_asset = session_data.get("from_asset")
        to_asset = session_data.get("to_asset")
        amount = session_data.get("amount")
        destination_address = session_data.get("destination_address")
        quote = session_data.get("quote", {})

        logger.info(
            f"Creating swap ticket for {user.name} ({user.id}): "
            f"{amount} {from_asset} → {to_asset}"
        )

        # Get API client
        api = bot.api_client
        user_context_id, roles = user.id, [r.id for r in user.roles]

        # Execute swap via API - creates ChangeNOW exchange order
        result = await api.afroo_swap_execute(
            from_asset=from_asset,
            to_asset=to_asset,
            amount=amount,
            destination_address=destination_address,
            user_id=str(user.id),
            discord_roles=roles
        )

        swap_data = result.get("swap", {})
        swap_id = str(swap_data.get("_id", ""))
        changenow_deposit_address = swap_data.get("changenow_deposit_address", "")
        estimated_output = swap_data.get("estimated_output", 0)
        exchange_rate = quote.get("exchange_rate", 0)

        # Truncate destination address for display
        dest_addr_display = destination_address if len(destination_address) <= 20 else f"{destination_address[:10]}...{destination_address[-6:]}"

        # Get swap category from config
        swap_category = None
        if config.swaps_category:
            swap_category = guild.get_channel(config.swaps_category)
            if swap_category:
                logger.info(f"Using swap category: {swap_category.name}")
            else:
                logger.warning(f"Swap category ID {config.swaps_category} not found")
        else:
            logger.warning("No swap category configured in config.json")

        # Create channel with permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Add staff role if configured
        if config.ROLE_STAFF:
            staff_role = guild.get_role(config.ROLE_STAFF)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )

        channel_name = f"swap-{user.name}-{swap_id[:8]}"
        swap_channel = await guild.create_text_channel(
            name=channel_name,
            category=swap_category,
            overwrites=overwrites,
            topic=f"Swap Ticket | {from_asset} → {to_asset} | User: {user.id}"
        )

        logger.info(f"Created swap channel: #{swap_channel.name} ({swap_channel.id})")

        # Build combined swap ticket embed
        ticket_embed = create_themed_embed(
            title="",
            description=(
                f"## Swap Ticket Created\n\n"
                f"{user.mention}, your swap order has been created.\n\n"
                f"**You Send:** `{amount} {from_asset}`\n"
                f"**You Receive:** `~{estimated_output:.8f} {to_asset}`\n"
                f"**Rate:** `1 {from_asset} = {exchange_rate:.8f} {to_asset}`\n"
                f"**Receiving Address:** `{dest_addr_display}`\n"
                f"**Status:** Pending Payment\n\n"
                f"### Payment Instructions\n\n"
                f"Send exactly **{amount} {from_asset}** to:\n"
                f"```\n{changenow_deposit_address}\n```\n\n"
                f"> **Important:** Only send {from_asset} to this address\n"
                f"> Send exactly {amount} {from_asset} within 2 hours\n\n"
                f"**What Happens Next:**\n"
                f"1. You send {amount} {from_asset} to the address above\n"
                f"2. Exchange processes your swap (5-30 minutes)\n"
                f"3. You receive ~{estimated_output:.8f} {to_asset} at `{dest_addr_display}`\n"
                f"4. Use buttons below to check status, view QR code, or copy address\n\n"
                f"**Swap ID:** `{swap_id}`"
            ),
            color=PURPLE_GRADIENT
        )

        # Create management view with QR and copy buttons
        management_view = SwapManagementView(
            bot=bot,
            swap_id=swap_id,
            user_id=user.id,
            from_asset=from_asset,
            to_asset=to_asset,
            deposit_address=changenow_deposit_address
        )

        # Send ticket embed with management buttons (no QR by default)
        await swap_channel.send(embed=ticket_embed, view=management_view)

        logger.info(f"Swap ticket created successfully for user {user.id}")

    except Exception as e:
        logger.error(f"Error creating swap ticket: {e}", exc_info=True)
        raise
