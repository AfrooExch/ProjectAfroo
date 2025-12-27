"""
Admin Profit Management Handler
Display comprehensive revenue, fees, and profit statistics
HEAD ADMIN & ASSISTANT ADMIN
"""

import logging
import discord
from discord.ui import View, Button

from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, WARNING
from config import Config

logger = logging.getLogger(__name__)


async def show_profit_management(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Display profit and revenue overview with pending fees awaiting collection

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get pending profits (fees waiting to be swept)
        pending_data = await api.get(
            "/api/v1/admin/profit/pending",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        pending = pending_data.get("data", {})
        exchange_fees = pending.get("exchange_fees", {})
        wallet_fees = pending.get("wallet_fees", {})
        by_currency = pending.get("by_currency", {})
        total_pending_usd = pending.get("total_usd", 0.0)

        # Build currency breakdown
        currency_lines = []
        for currency, amounts in by_currency.items():
            total_crypto = amounts.get("total", 0.0)
            exchange_crypto = amounts.get("exchange", 0.0)
            wallet_crypto = amounts.get("wallet", 0.0)

            sources = []
            if exchange_crypto > 0:
                sources.append(f"Exchange: {exchange_crypto:.8f}")
            if wallet_crypto > 0:
                sources.append(f"Wallet: {wallet_crypto:.8f}")

            if total_crypto > 0:
                currency_lines.append(
                    f"**{currency}:** `{total_crypto:.8f}`\n"
                    f"> {' | '.join(sources)}"
                )

        currency_breakdown = "\n".join(currency_lines) if currency_lines else "> No fees pending collection"

        # Calculate exchange fees total
        exchange_total_usd = sum(data.get("amount_usd", 0) for data in exchange_fees.values())

        # Calculate wallet fees total
        wallet_total_usd = sum(data.get("amount_usd", 0) for data in wallet_fees.values())

        embed = create_themed_embed(
            title="",
            description=(
                f"## Profit Management\n\n"
                f"### Pending Fee Collection\n\n"
                f"**Total Pending:** `${total_pending_usd:,.2f} USD`\n"
                f"**Exchange Fees:** `${exchange_total_usd:,.2f} USD`\n"
                f"**Wallet Fees:** `${wallet_total_usd:,.2f} USD`\n\n"
                f"### Breakdown by Currency\n\n"
                f"{currency_breakdown}\n\n"
                f"### Collection Info\n\n"
                f"**Auto-Sweep:** Runs twice daily at 6 AM and 6 PM\n"
                f"**Manual Sweep:** Use buttons below to collect now\n"
                f"**Minimum Amounts:** Small amounts held until threshold met\n\n"
                f"### Fee Rates\n\n"
                f"**Exchange:** 2% (min $0.50 per ticket)\n"
                f"**Wallet Withdrawals:** 0.3-0.4%\n"
                f"**Swap:** 0% (ChangeNOW partner commission external)\n"
                f"**AutoMM:** Free service\n\n"
                f"> 💡 Fees are locked and cannot be withdrawn by users\n"
                f"> 💡 Sweep sends accumulated fees to admin wallets"
            ),
            color=SUCCESS_GREEN
        )

        # Add buttons for Head Admin only
        view = None
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id == HEAD_ADMIN_ID:
            view = ProfitActionsView(bot)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed profit management to admin {interaction.user.id}: ${total_pending_usd:.2f} pending")

    except APIError as e:
        logger.error(f"API error loading profit data: {e}")
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error Loading Profit Data",
                description=f"{e.user_message}"
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing profit management: {e}", exc_info=True)
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error",
                description=f"Failed to load profit data: {str(e)}"
            ),
            ephemeral=True
        )


class ProfitActionsView(View):
    """View with buttons for profit management actions (HEAD ADMIN ONLY)"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(
        label="Sweep All Fees",
        style=discord.ButtonStyle.danger,
        emoji="💸"
    )
    async def sweep_all_button(self, button: Button, interaction: discord.Interaction):
        """Sweep all pending fees to admin wallets"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Call profit sweep endpoint
            result = await api.post(
                "/api/v1/admin/profit/sweep?sweep_type=all&force=false",
                {},
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            sweep_data = result.get("data", {})
            total_swept_usd = sweep_data.get("total_swept_usd", 0.0)
            exchange_fees = sweep_data.get("exchange_fees", {})
            wallet_fees = sweep_data.get("wallet_fees", {})
            errors = sweep_data.get("errors", [])

            # Build currency details
            swept_currencies = []
            for currency, data in exchange_fees.items():
                if data.get("status") == "success":
                    swept_currencies.append(
                        f"**{currency}:** {data.get('amount_crypto', 0):.8f} (${data.get('amount_usd', 0):.2f}) - Exchange"
                    )
            for currency, data in wallet_fees.items():
                if data.get("status") == "success":
                    swept_currencies.append(
                        f"**{currency}:** {data.get('amount_crypto', 0):.8f} (${data.get('amount_usd', 0):.2f}) - Wallet"
                    )

            currency_details = "\n".join(swept_currencies[:10]) if swept_currencies else "> No fees swept (all below minimum)"

            # Build error text
            error_text = ""
            if errors:
                error_text = f"\n\n### Errors\n\n"
                for error in errors[:3]:
                    error_text += f"> • {error}\n"

            embed = create_success_embed(
                title="Profit Sweep Complete",
                description=(
                    f"## Fees Swept to Admin Wallets\n\n"
                    f"**Total Swept:** `${total_swept_usd:,.2f} USD`\n\n"
                    f"### Currencies Swept\n\n"
                    f"{currency_details}\n\n"
                    f"### Details\n\n"
                    f"> • Fees sent to configured admin wallet addresses\n"
                    f"> • Transactions recorded on blockchain\n"
                    f"> • Small amounts below minimum threshold remain held\n"
                    f"{error_text}"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"Head Admin {interaction.user.id} triggered profit sweep: ${total_swept_usd:.2f}")

        except APIError as e:
            logger.error(f"API error during profit sweep: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Profit Sweep Failed",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during profit sweep: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to sweep fees: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Sweep Exchange Only",
        style=discord.ButtonStyle.primary,
        emoji="💱"
    )
    async def sweep_exchange_button(self, button: Button, interaction: discord.Interaction):
        """Sweep only exchange fees"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            result = await api.post(
                "/api/v1/admin/profit/sweep?sweep_type=exchange&force=false",
                {},
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            sweep_data = result.get("data", {})
            total_swept_usd = sweep_data.get("total_swept_usd", 0.0)
            exchange_fees = sweep_data.get("exchange_fees", {})

            swept_count = sum(1 for data in exchange_fees.values() if data.get("status") == "success")

            embed = create_success_embed(
                title="Exchange Fee Sweep Complete",
                description=(
                    f"## Exchange Fees Swept\n\n"
                    f"**Total Swept:** `${total_swept_usd:,.2f} USD`\n"
                    f"**Currencies Swept:** {swept_count}\n\n"
                    f"> Wallet fees not affected"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"Head Admin {interaction.user.id} swept exchange fees: ${total_swept_usd:.2f}")

        except Exception as e:
            logger.error(f"Error during exchange sweep: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to sweep exchange fees: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Sweep Wallet Only",
        style=discord.ButtonStyle.primary,
        emoji="💼"
    )
    async def sweep_wallet_button(self, button: Button, interaction: discord.Interaction):
        """Sweep only wallet fees"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            result = await api.post(
                "/api/v1/admin/profit/sweep?sweep_type=wallet&force=false",
                {},
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            sweep_data = result.get("data", {})
            total_swept_usd = sweep_data.get("total_swept_usd", 0.0)
            wallet_fees = sweep_data.get("wallet_fees", {})

            swept_count = sum(1 for data in wallet_fees.values() if data.get("status") == "success")

            embed = create_success_embed(
                title="Wallet Fee Sweep Complete",
                description=(
                    f"## Wallet Fees Swept\n\n"
                    f"**Total Swept:** `${total_swept_usd:,.2f} USD`\n"
                    f"**Currencies Swept:** {swept_count}\n\n"
                    f"> Exchange fees not affected"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"Head Admin {interaction.user.id} swept wallet fees: ${total_swept_usd:.2f}")

        except Exception as e:
            logger.error(f"Error during wallet sweep: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to sweep wallet fees: {str(e)}"
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Database Backup",
        style=discord.ButtonStyle.secondary,
        emoji="💾"
    )
    async def backup_button(self, button: Button, interaction: discord.Interaction):
        """Trigger database backup"""
        HEAD_ADMIN_ID = 1419744557054169128
        if interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Error**\n\nOnly Head Admin can perform this action.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Trigger backup
            result = await api.post(
                "/api/v1/admin/system/backup-database?backup_type=local",
                {},
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            backup_name = result.get("backup_name")
            backup_size_mb = result.get("backup_size_mb", 0)

            embed = create_success_embed(
                title="Database Backup Complete",
                description=(
                    f"## Backup Created Successfully\n\n"
                    f"**Backup Name:** `{backup_name}`\n"
                    f"**Size:** {backup_size_mb:.2f} MB\n"
                    f"**Type:** Local\n\n"
                    f"### Backup Location\n\n"
                    f"> • Stored in `/backups/` directory\n"
                    f"> • Accessible from backend container\n"
                    f"> • Contains full MongoDB dump\n\n"
                    f"### Next Steps\n\n"
                    f"> • Download backup from server if needed\n"
                    f"> • Store securely offsite\n"
                    f"> • Regular backups run automatically every 6 hours"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"Head Admin {interaction.user.id} triggered database backup: {backup_name}")

        except APIError as e:
            logger.error(f"API error during backup: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Backup Failed",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during backup: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to create backup: {str(e)}"
                ),
                ephemeral=True
            )
