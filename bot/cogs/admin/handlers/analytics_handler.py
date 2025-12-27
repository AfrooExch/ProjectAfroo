"""Admin Analytics Handler - Platform statistics"""
import logging
from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)

async def show_analytics(interaction, bot):
    """Display comprehensive platform analytics"""
    api = bot.api_client
    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get analytics from overview endpoint
        analytics = await api.get(
            "/api/v1/admin/stats/overview",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        totals = analytics.get("totals", {})
        volumes = analytics.get("volumes", {})
        recent_24h = analytics.get("recent_24h", {})

        total_users = totals.get("users", 0)
        active_users = totals.get("active_users", 0)
        total_exchangers = totals.get("exchangers", 0)
        total_exchanges = totals.get("exchanges", 0)
        completed_exchanges = totals.get("completed_exchanges", 0)
        cancelled_exchanges = totals.get("cancelled_exchanges", 0)
        total_swaps = totals.get("swaps", 0)
        completed_swaps = totals.get("completed_swaps", 0)
        failed_swaps = totals.get("failed_swaps", 0)
        total_automm = totals.get("automm_deals", 0)
        completed_automm = totals.get("completed_automm", 0)
        total_wallets = totals.get("wallets", 0)
        open_tickets = totals.get("open_tickets", 0)
        total_partners = totals.get("partners", 0)

        # Volume stats
        client_exchange_vol = volumes.get("client_exchange_volume_usd", 0)
        exchanger_vol = volumes.get("exchanger_volume_usd", 0)
        exchanger_profit = volumes.get("exchanger_profit_usd", 0)
        exchanger_fees = volumes.get("exchanger_fees_paid_usd", 0)
        swap_vol = volumes.get("swap_volume_usd", 0)
        automm_vol = volumes.get("automm_volume_usd", 0)
        deposits = volumes.get("deposits_usd", 0)
        withdrawals = volumes.get("withdrawals_usd", 0)

        new_users_24h = recent_24h.get("new_users", 0)
        new_exchanges_24h = recent_24h.get("new_exchanges", 0)
        new_swaps_24h = recent_24h.get("new_swaps", 0)

        # Calculate success rates
        exchange_success_rate = (completed_exchanges / total_exchanges * 100) if total_exchanges > 0 else 0
        swap_success_rate = (completed_swaps / total_swaps * 100) if total_swaps > 0 else 0

        # Calculate total platform volume
        total_platform_volume = client_exchange_vol + swap_vol + automm_vol

        embed = create_themed_embed(
            title="",
            description=(
                f"## Platform Analytics\n\n"
                f"### 👥 Users\n\n"
                f"**Total Users:** {total_users:,}\n"
                f"**Active Users:** {active_users:,}\n"
                f"**Exchangers:** {total_exchangers:,}\n"
                f"**Partners:** {total_partners:,}\n\n"
                f"### 💱 Exchange Activity\n\n"
                f"**Total Exchanges:** `{total_exchanges:,}` ({completed_exchanges:,} | {cancelled_exchanges:,})\n"
                f"**Success Rate:** `{exchange_success_rate:.1f}%`\n"
                f"**Client Volume:** `${client_exchange_vol:,.2f} USD`\n"
                f"**Exchanger Volume:** `${exchanger_vol:,.2f} USD`\n"
                f"**Exchanger Profit:** `${exchanger_profit:,.2f} USD`\n"
                f"**Exchanger Fees Paid:** `${exchanger_fees:,.2f} USD`\n\n"
                f"### 🔁 Swap Activity\n\n"
                f"**Total Swaps:** `{total_swaps:,}` ({completed_swaps:,} | {failed_swaps:,})\n"
                f"**Success Rate:** `{swap_success_rate:.1f}%`\n"
                f"**Swap Volume:** `${swap_vol:,.2f} USD`\n\n"
                f"### 🤝 AutoMM (P2P Escrow)\n\n"
                f"**Total Deals:** `{total_automm:,}` ({completed_automm:,} completed)\n"
                f"**AutoMM Volume:** `${automm_vol:,.2f} USD`\n\n"
                f"### 💼 Wallet Activity\n\n"
                f"**Total Wallets:** {total_wallets:,}\n"
                f"**Total Deposited:** `${deposits:,.2f} USD`\n"
                f"**Total Withdrawn:** `${withdrawals:,.2f} USD`\n\n"
                f"### 📈 Platform Totals\n\n"
                f"**Total Platform Volume:** `${total_platform_volume:,.2f} USD`\n"
                f"**Open Tickets:** {open_tickets:,}\n\n"
                f"### ⏰ Last 24 Hours\n\n"
                f"> • New Users: {new_users_24h:,}\n"
                f"> • New Exchanges: {new_exchanges_24h:,}\n"
                f"> • New Swaps: {new_swaps_24h:,}\n\n"
                f"> All stats tracked automatically from user transactions"
            ),
            color=PURPLE_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        logger.info(f"Showed comprehensive analytics to admin {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error loading analytics: {e}")
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error Loading Analytics",
                description=f"{e.user_message}"
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error loading analytics: {e}", exc_info=True)
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error",
                description=f"Failed to load analytics: {str(e)}"
            ),
            ephemeral=True
        )
