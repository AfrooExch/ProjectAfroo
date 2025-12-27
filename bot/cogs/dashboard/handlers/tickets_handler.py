"""
Active Tickets Handler for V4
Displays user's active tickets
"""

import logging

import discord

from api.errors import APIError
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


async def show_active_tickets(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show user's active tickets

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get active tickets from API
        tickets_response = await api.get(
            f"/api/v1/tickets/active",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        tickets = tickets_response.get("tickets", []) if isinstance(tickets_response, dict) else tickets_response

        if not tickets:
            embed = create_themed_embed(
                title="",
                description=(
                    f"## 🎫 Active Tickets\n\n"
                    f"You don't have any active tickets right now.\n\n"
                    f"> Use the Exchange Panel to create a new exchange ticket!"
                ),
                color=PURPLE_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Build tickets list
        tickets_text = ""

        for ticket in tickets[:15]:  # Max 15 tickets
            ticket_id = ticket.get("id", "")
            ticket_type = ticket.get("type", "exchange")
            status = ticket.get("status", "open")
            channel_id = ticket.get("channel_id")
            created_at = ticket.get("created_at", "")

            # Get status emoji
            status_emojis = {
                "open": "🟢",
                "pending_tos": "⏳",
                "claimed": "🔵",
                "funds_sent": "💸",
                "completed": "✅",
                "cancelled": "❌"
            }
            status_emoji = status_emojis.get(status, "⚪")

            # Get type emoji
            type_emojis = {
                "exchange": "💱",
                "support": "🎫",
                "application": "📋",
                "swap": "🔄"
            }
            type_emoji = type_emojis.get(ticket_type, "🎫")

            # Format channel link
            channel_link = f"<#{channel_id}>" if channel_id else "N/A"

            tickets_text += (
                f"{status_emoji} {type_emoji} **Ticket #{ticket_id[:8]}**\n"
                f"> Type: {ticket_type.title()}\n"
                f"> Status: {status.replace('_', ' ').title()}\n"
                f"> Channel: {channel_link}\n\n"
            )

        embed = create_themed_embed(
            title="",
            description=(
                f"## 🎫 Active Tickets\n\n"
                f"**Total Active:** {len(tickets)}\n\n"
                f"{tickets_text}"
                f"> Click on a channel to view the ticket."
            ),
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text="💡 Tip: Complete tickets to improve your stats and tier")

        await interaction.followup.send(embed=embed, ephemeral=True)

        logger.info(f"Showed active tickets for user {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error fetching active tickets: {e}")
        await interaction.followup.send(
            f"❌ **Error Loading Tickets**\n\n{e.user_message}",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing active tickets: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ **Error**\n\nFailed to load tickets: {str(e)}",
            ephemeral=True
        )
