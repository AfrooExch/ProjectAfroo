"""
Ticket Creation Handler for V4
Creates exchange tickets via API and sets up Discord channels
"""

import logging
from typing import Dict, Any
import discord

from api.client import APIClient
from api.errors import APIError
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT
from utils.payment_methods import format_payment_method_display, get_tos_for_method
from config import config

logger = logging.getLogger(__name__)


async def create_exchange_ticket(
    bot: discord.Bot,
    user: discord.User,
    guild: discord.Guild,
    session_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create exchange ticket via API and setup Discord channel

    Args:
        bot: Discord bot instance
        user: User creating the ticket
        guild: Discord guild
        session_data: Exchange session data

    Returns:
        Ticket data from API
    """
    api: APIClient = bot.api_client

    # Extract session data
    send_method = session_data["send_method"]
    receive_method = session_data["receive_method"]
    amount_usd = session_data["amount_usd"]
    send_crypto = session_data.get("send_crypto")
    receive_crypto = session_data.get("receive_crypto")

    logger.info(
        f"Creating exchange ticket for user {user.id}: "
        f"{send_method} -> {receive_method}, ${amount_usd:.2f}"
    )

    # Format displays
    send_display = format_payment_method_display(send_method, send_crypto)
    receive_display = format_payment_method_display(receive_method, receive_crypto)

    # Calculate fees (simplified - API will do full calculation)
    is_send_crypto = send_method == "crypto" or send_crypto
    is_receive_crypto = receive_method == "crypto" or receive_crypto

    if is_send_crypto and is_receive_crypto:
        fee_percent = 5.0
        fee_amount = amount_usd * 0.05
    elif amount_usd >= 40.0:
        fee_percent = 10.0
        fee_amount = amount_usd * 0.10
    else:
        fee_percent = (4.0 / amount_usd) * 100
        fee_amount = 4.0

    receiving_amount = amount_usd - fee_amount

    try:
        # Create ticket via API
        ticket_data = await api.create_exchange_ticket(
            user_id=str(user.id),
            username=user.name,
            send_method=send_method,
            receive_method=receive_method,
            amount_usd=amount_usd,
            fee_amount=fee_amount,
            fee_percentage=fee_percent,
            receiving_amount=receiving_amount,
            send_crypto=send_crypto,
            receive_crypto=receive_crypto
        )

        ticket_id = ticket_data.get("ticket_number") or ticket_data.get("id")
        logger.info(f"Ticket created via API: #{ticket_id}")

        # Create Discord channel
        channel = await create_ticket_channel(
            guild=guild,
            user=user,
            ticket_id=ticket_id,
            send_display=send_display,
            receive_display=receive_display,
            amount_usd=amount_usd
        )

        logger.info(f"Ticket channel created: {channel.id}")

        # Update ticket with channel ID via API
        await api.update_ticket(ticket_id, channel_id=str(channel.id))

        # Post TOS in channel
        await post_ticket_tos(
            channel=channel,
            bot=bot,
            user=user,
            ticket_id=ticket_id,
            ticket_data=ticket_data,
            send_method=send_method,
            receive_method=receive_method,
            send_crypto=send_crypto,
            receive_crypto=receive_crypto,
            send_display=send_display,
            receive_display=receive_display,
            amount_usd=amount_usd,
            fee_amount=fee_amount,
            fee_percentage=fee_percent,
            receiving_amount=receiving_amount
        )

        return ticket_data

    except APIError as e:
        logger.error(f"API error creating ticket: {e}")
        raise Exception(f"API error: {e.user_message}")
    except Exception as e:
        logger.error(f"Error creating ticket: {e}", exc_info=True)
        raise


async def create_ticket_channel(
    guild: discord.Guild,
    user: discord.User,
    ticket_id: str,
    send_display: str,
    receive_display: str,
    amount_usd: float
) -> discord.TextChannel:
    """
    Create private ticket channel with proper permissions

    Initially only admin and staff can see it (customer can see too)
    After TOS accept, exchangers can VIEW (but not speak)
    """
    # Get category
    tickets_category_id = config.TICKETS_CATEGORY_ID
    tickets_category = guild.get_channel(tickets_category_id)

    if not tickets_category:
        logger.warning(f"Tickets category not found: {tickets_category_id}")
        tickets_category = None

    # Clean username for channel name
    username_clean = user.name.lower().replace(" ", "-")[:20]
    channel_name = f"ticket-{username_clean}-{ticket_id}"

    # Set up permissions (PRIVATE initially)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_messages=True,
            embed_links=True
        )
    }

    # Add staff roles
    admin_role = guild.get_role(config.HEAD_ADMIN_ROLE_ID)
    if admin_role:
        overwrites[admin_role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_messages=True
        )

    staff_role = guild.get_role(config.STAFF_ROLE_ID)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True
        )

    # Create channel
    channel = await guild.create_text_channel(
        name=channel_name,
        category=tickets_category,
        overwrites=overwrites,
        topic=f"Exchange Ticket #{ticket_id} | {send_display} → {receive_display} | ${amount_usd:.2f}",
        reason=f"Exchange ticket #{ticket_id} for {user.name}"
    )

    logger.info(f"Created ticket channel: {channel.name} ({channel.id})")
    return channel


async def post_ticket_tos(
    channel: discord.TextChannel,
    bot: discord.Bot,
    user: discord.User,
    ticket_id: str,
    ticket_data: Dict[str, Any],
    send_method: str,
    receive_method: str,
    send_crypto: str,
    receive_crypto: str,
    send_display: str,
    receive_display: str,
    amount_usd: float,
    fee_amount: float,
    fee_percentage: float,
    receiving_amount: float
):
    """Post TOS embed in ticket channel"""
    # Get TOS text for send method
    tos_text = get_tos_for_method(send_method, send_crypto)

    # Get TOS channel mention
    tos_channel_id = config.TOS_CHANNEL_ID
    tos_channel_mention = f"<#{tos_channel_id}>" if tos_channel_id else "our Terms of Service channel"

    # Determine fee display (show "Min Fee" if it's the minimum fee)
    MIN_FEE = 4.00
    if fee_amount <= MIN_FEE:
        fee_display = f"`${fee_amount:.2f}` **(Min Fee)**"
    else:
        fee_display = f"`${fee_amount:.2f}` **({fee_percentage:.0f}%)**"

    # Create TOS embed
    embed = create_themed_embed(
        title="",
        description=(
            f"## Exchange Ticket #{ticket_id}\n\n"
            f"**Customer:** {user.mention}\n"
            f"**Status:** Awaiting TOS Acceptance\n\n"
            f"### Exchange Details\n\n"
            f"**Sending:** {send_display}\n"
            f"**Receiving:** {receive_display}\n"
            f"**Customer Sends:** `${amount_usd:,.2f} USD`\n"
            f"**Service Fee:** {fee_display}\n"
            f"**Customer Receives:** `${receiving_amount:.2f} USD`\n\n"
            f"### Terms of Service\n\n"
            f"{tos_text}\n\n"
            f"**Read our full Terms of Service in {tos_channel_mention}**\n\n"
            f"---\n\n"
            f"{user.mention} **You must accept these terms to proceed.**\n\n"
            f"By clicking **I Agree**, you acknowledge that you have read and agree to these terms.\n\n"
            f"⚠️ **Violation of these terms will result in permanent ban and forfeiture of funds.**\n\n"
            f"> You have **10 minutes** to accept. The ticket will auto-close if you don't respond."
        ),
        color=PURPLE_GRADIENT
    )

    # Import TOS view
    from cogs.tickets.views.tos_view import TOSAcceptanceView

    # Create TOS view with timer
    tos_view = TOSAcceptanceView(
        bot=bot,
        ticket_id=ticket_id,
        channel=channel,
        customer_id=user.id
    )

    # Send TOS message
    message = await channel.send(embed=embed, view=tos_view)

    # Start TOS timer in background
    tos_view.start_timer(message)

    logger.info(f"Posted TOS for ticket #{ticket_id}")
