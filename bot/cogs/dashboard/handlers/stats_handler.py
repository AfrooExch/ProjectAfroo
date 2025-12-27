"""
Stats Handler for V4
Displays user statistics and trading information
"""

import logging

import discord

from api.errors import APIError
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


async def show_user_stats(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show user comprehensive statistics

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get user profile
        user_data = await api.get(
            "/api/v1/users/profile",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        # Get comprehensive stats from new endpoint
        stats = await api.get(
            f"/api/v1/users/{interaction.user.id}/comprehensive-stats",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        # Calculate account age
        joined_date = user_data.get("created_at", "Unknown")
        account_age_days = 0
        try:
            from datetime import datetime
            if isinstance(joined_date, str):
                created = datetime.fromisoformat(joined_date.replace('Z', '+00:00'))
                account_age_days = (datetime.utcnow() - created.replace(tzinfo=None)).days
        except:
            account_age_days = 0

        # Client Exchange Stats
        client_exchanges = stats.get("client_total_exchanges", 0)
        client_completed = stats.get("client_completed_exchanges", 0)
        client_cancelled = stats.get("client_cancelled_exchanges", 0)
        client_volume = stats.get("client_exchange_volume_usd", 0.0)
        client_success_rate = (client_completed / client_exchanges * 100) if client_exchanges > 0 else 0

        # Exchanger Stats
        exchanger_claimed = stats.get("exchanger_total_claimed", 0)
        exchanger_completed = stats.get("exchanger_total_completed", 0)
        exchanger_tickets_completed = stats.get("exchanger_tickets_completed", 0)
        exchanger_profit = stats.get("exchanger_total_profit_usd", 0.0)
        exchanger_fees_paid = stats.get("exchanger_total_fees_paid_usd", 0.0)
        exchanger_volume = stats.get("exchanger_exchange_volume_usd", 0.0)

        # Swap Stats
        swap_total = stats.get("swap_total_made", 0)
        swap_completed = stats.get("swap_total_completed", 0)
        swap_failed = stats.get("swap_total_failed", 0)
        swap_volume = stats.get("swap_total_volume_usd", 0.0)
        swap_success_rate = (swap_completed / swap_total * 100) if swap_total > 0 else 0

        # AutoMM Stats
        automm_total = stats.get("automm_total_created", 0)
        automm_completed = stats.get("automm_total_completed", 0)
        automm_volume = stats.get("automm_total_volume_usd", 0.0)

        # Wallet Stats
        wallet_deposited = stats.get("wallet_total_deposited_usd", 0.0)
        wallet_withdrawn = stats.get("wallet_total_withdrawn_usd", 0.0)

        # Calculate tier based on client exchange volume
        if client_volume >= 50000:
            tier, tier_emoji, next_tier, next_req = "Elite Trader", "💠", "Max", 0
        elif client_volume >= 25000:
            tier, tier_emoji, next_tier, next_req = "Diamond Trader", "💎", "Elite", 50000
        elif client_volume >= 10000:
            tier, tier_emoji, next_tier, next_req = "Platinum Trader", "🔷", "Diamond", 25000
        elif client_volume >= 5000:
            tier, tier_emoji, next_tier, next_req = "Gold Trader", "🥇", "Platinum", 10000
        elif client_volume >= 2500:
            tier, tier_emoji, next_tier, next_req = "Silver Trader", "🥈", "Gold", 5000
        elif client_volume >= 500:
            tier, tier_emoji, next_tier, next_req = "Bronze Trader", "🥉", "Silver", 2500
        else:
            tier, tier_emoji, next_tier, next_req = "Beginner", "⭐", "Bronze", 500

        # Reputation score
        reputation = stats.get("reputation_score", 100)

        # Build embed description
        description = (
            f"## 📊 Your Complete Dashboard\n\n"
            f"**User:** {interaction.user.mention}\n"
            f"**Account Age:** {account_age_days} days\n"
            f"**Reputation:** `{reputation}`\n"
            f"**Tier:** {tier_emoji} {tier}\n\n"
        )

        # Client Exchange Stats - ALWAYS SHOW
        description += (
            f"### 💱 Exchange Activity (As Client)\n\n"
            f"**Total Exchanges:** `{client_exchanges}` (✅ {client_completed} | ❌ {client_cancelled})\n"
            f"**Success Rate:** `{client_success_rate:.1f}%`\n"
            f"**Total Volume:** `${client_volume:,.2f} USD`\n"
        )

        # Show milestone progress
        if next_req > 0:
            description += f"**Progress to {next_tier}:** `${client_volume:,.2f} / ${next_req:,.2f}`\n"
        description += "\n"

        # Exchanger Stats - ALWAYS SHOW
        description += (
            f"### 🔄 Exchanger Activity\n\n"
        )
        if exchanger_completed > 0 or exchanger_claimed > 0:
            description += (
                f"**Tickets Claimed:** `{exchanger_claimed}`\n"
                f"**Tickets Completed:** `{exchanger_completed}`\n"
                f"**Volume Exchanged:** `${exchanger_volume:,.2f} USD`\n"
                f"**Total Profit:** `${exchanger_profit:,.2f} USD`\n"
                f"**Fees Paid:** `${exchanger_fees_paid:,.2f} USD`\n\n"
            )
        else:
            description += f"> No exchanger activity yet\n\n"

        # Swap Stats - ALWAYS SHOW
        description += (
            f"### 🔁 Swap Statistics\n\n"
        )
        if swap_total > 0:
            description += (
                f"**Total Swaps:** `{swap_total}` (✅ {swap_completed} | ❌ {swap_failed})\n"
                f"**Success Rate:** `{swap_success_rate:.1f}%`\n"
                f"**Total Volume:** `${swap_volume:,.2f} USD`\n\n"
            )
        else:
            description += f"> No swaps yet\n\n"

        # AutoMM Stats - ALWAYS SHOW
        description += (
            f"### 🤝 AutoMM (P2P Escrow)\n\n"
        )
        if automm_total > 0:
            description += (
                f"**Total Deals:** `{automm_total}` (✅ {automm_completed} completed)\n"
                f"**Total Volume:** `${automm_volume:,.2f} USD`\n\n"
            )
        else:
            description += f"> No AutoMM deals yet\n\n"

        # Wallet Stats - ALWAYS SHOW
        description += (
            f"### 💼 Wallet Activity\n\n"
        )
        if wallet_deposited > 0 or wallet_withdrawn > 0:
            description += (
                f"**Total Deposited:** `${wallet_deposited:,.2f} USD`\n"
                f"**Total Withdrawn:** `${wallet_withdrawn:,.2f} USD`\n\n"
            )
        else:
            description += f"> No wallet transactions tracked yet\n\n"

        # Calculate total platform activity
        total_platform_volume = client_volume + exchanger_volume + swap_volume + automm_volume

        # Leaderboard Placement
        description += f"### 🏆 Your Rankings\n\n"
        try:
            # Get leaderboards to find user's placement
            leaderboards = await api.get(
                "/api/v1/admin/stats/leaderboards?limit=100",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            # Find user's rank in each category
            user_discord_id = str(interaction.user.id)

            # Client Exchange Rank
            client_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_clients", [])) if u.get("discord_id") == user_discord_id), None)
            if client_rank:
                description += f"**Client Exchange:** Rank #{client_rank} 🥇\n"
            else:
                description += f"**Client Exchange:** Not ranked yet\n"

            # Exchanger Rank
            exchanger_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_exchangers", [])) if u.get("discord_id") == user_discord_id), None)
            if exchanger_rank:
                description += f"**Exchanger:** Rank #{exchanger_rank} 🥇\n"
            else:
                description += f"**Exchanger:** Not ranked yet\n"

            # Swap Rank
            swap_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_swappers", [])) if u.get("discord_id") == user_discord_id), None)
            if swap_rank:
                description += f"**Swapper:** Rank #{swap_rank} 🥇\n"
            else:
                description += f"**Swapper:** Not ranked yet\n"

            # AutoMM Rank
            automm_rank = next((idx + 1 for idx, u in enumerate(leaderboards.get("top_automm", [])) if u.get("discord_id") == user_discord_id), None)
            if automm_rank:
                description += f"**AutoMM:** Rank #{automm_rank} 🥇\n"
            else:
                description += f"**AutoMM:** Not ranked yet\n"

            description += f"\n"
        except:
            description += "> Rankings will appear once you start trading\n\n"

        description += f"**Total Platform Volume:** `${total_platform_volume:,.2f} USD`\n\n"
        description += f"> 💡 Keep trading to unlock higher tiers and climb the leaderboards!"

        # Create stats embed
        embed = create_themed_embed(
            title="",
            description=description,
            color=PURPLE_GRADIENT
        )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="📈 All stats are tracked automatically after each transaction")

        await interaction.followup.send(embed=embed, ephemeral=True)

        logger.info(f"Showed comprehensive stats for user {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error fetching stats: {e}")
        await interaction.followup.send(
            f"❌ **Error Loading Stats**\n\n{e.user_message}",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing stats: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ **Error**\n\nFailed to load stats: {str(e)}",
            ephemeral=True
        )
