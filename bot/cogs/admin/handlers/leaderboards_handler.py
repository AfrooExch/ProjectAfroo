"""Admin Leaderboards Handler - Display top users across all services"""
import logging
from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)

async def show_leaderboards(interaction, bot):
    """Display platform leaderboards"""
    api = bot.api_client
    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get leaderboards from endpoint
        leaderboards = await api.get(
            "/api/v1/admin/stats/leaderboards?limit=10",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        top_exchangers = leaderboards.get("top_exchangers", [])
        top_clients = leaderboards.get("top_clients", [])
        top_swappers = leaderboards.get("top_swappers", [])
        top_automm = leaderboards.get("top_automm", [])

        # Build leaderboard text
        description = "## 🏆 Platform Leaderboards\n\n"

        # Top Exchangers
        description += "### 💼 Top Exchangers (by volume)\n\n"
        if top_exchangers:
            for idx, user in enumerate(top_exchangers, 1):
                username = user.get("username", "Unknown")
                volume = user.get("volume_usd", 0)
                tickets = user.get("tickets_completed", 0)
                profit = user.get("profit_usd", 0)
                description += f"**{idx}.** {username}\n"
                description += f"   Volume: `${volume:,.2f}` | Tickets: `{tickets}` | Profit: `${profit:,.2f}`\n"
        else:
            description += "> No exchanger data yet\n"
        description += "\n"

        # Top Client Exchangers
        description += "### 💱 Top Client Exchangers (by volume)\n\n"
        if top_clients:
            for idx, user in enumerate(top_clients, 1):
                username = user.get("username", "Unknown")
                volume = user.get("volume_usd", 0)
                total = user.get("total_exchanges", 0)
                completed = user.get("completed_exchanges", 0)
                description += f"**{idx}.** {username}\n"
                description += f"   Volume: `${volume:,.2f}` | Exchanges: `{completed}/{total}`\n"
        else:
            description += "> No client data yet\n"
        description += "\n"

        # Top Swappers
        description += "### 🔁 Top Swappers (by volume)\n\n"
        if top_swappers:
            for idx, user in enumerate(top_swappers, 1):
                username = user.get("username", "Unknown")
                volume = user.get("volume_usd", 0)
                total = user.get("total_swaps", 0)
                completed = user.get("completed_swaps", 0)
                description += f"**{idx}.** {username}\n"
                description += f"   Volume: `${volume:,.2f}` | Swaps: `{completed}/{total}`\n"
        else:
            description += "> No swap data yet\n"
        description += "\n"

        # Top AutoMM Users
        description += "### 🤝 Top AutoMM Users (by volume)\n\n"
        if top_automm:
            for idx, user in enumerate(top_automm, 1):
                username = user.get("username", "Unknown")
                volume = user.get("volume_usd", 0)
                total = user.get("total_deals", 0)
                completed = user.get("completed_deals", 0)
                description += f"**{idx}.** {username}\n"
                description += f"   Volume: `${volume:,.2f}` | Deals: `{completed}/{total}`\n"
        else:
            description += "> No AutoMM data yet\n"
        description += "\n"

        description += "> Updated in real-time from user statistics"

        embed = create_themed_embed(
            title="",
            description=description,
            color=PURPLE_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        logger.info(f"Showed leaderboards to admin {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error loading leaderboards: {e}")
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error Loading Leaderboards",
                description=f"{e.user_message}"
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error loading leaderboards: {e}", exc_info=True)
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error",
                description=f"Failed to load leaderboards: {str(e)}"
            ),
            ephemeral=True
        )
