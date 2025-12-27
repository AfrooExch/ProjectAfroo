"""
Account Transfer Handler for V4
Allows users to transfer their account using recovery codes
"""

import logging

import discord
from discord.ui import Modal, InputText

from api.errors import APIError
from utils.embeds import create_themed_embed, create_success_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED

logger = logging.getLogger(__name__)


class TransferAccountModal(Modal):
    """Modal for account transfer"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🔑 Transfer Account with Recovery Code")
        self.bot = bot

        self.recovery_code = InputText(
            label="Recovery Code",
            placeholder="AFRO-XXXXX-XXXXX-XXXXX",
            style=discord.InputTextStyle.short,
            required=True,
            max_length=24  # AFRO- + 15 chars + 3 dashes
        )

        self.add_item(self.recovery_code)

    async def callback(self, interaction: discord.Interaction):
        """Handle transfer submission"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            recovery_code = self.recovery_code.value.strip().upper()

            # Validate format (AFRO-XXXXX-XXXXX-XXXXX)
            if not recovery_code.startswith("AFRO-"):
                await interaction.followup.send(
                    embed=create_error_embed(
                        title="Invalid Recovery Code",
                        description="Recovery codes must start with `AFRO-` (format: AFRO-XXXXX-XXXXX-XXXXX)."
                    ),
                    ephemeral=True
                )
                return

            # Check length (should be 19 chars with dashes: AFRO-XXXXX-XXXXX-XXXXX)
            if len(recovery_code) != 24 or recovery_code.count('-') != 4:
                await interaction.followup.send(
                    embed=create_error_embed(
                        title="Invalid Recovery Code",
                        description="Recovery codes should be in format: `AFRO-XXXXX-XXXXX-XXXXX`"
                    ),
                    ephemeral=True
                )
                return

            # Call API to transfer account
            # This endpoint does NOT require authentication since user may have lost Discord access
            result = await api.post(
                "/api/v1/recovery/transfer",
                {
                    "recovery_code": recovery_code,
                    "new_discord_id": str(interaction.user.id)
                }
            )

            transfer_data = result.get("transfer", {})
            wallets_transferred = transfer_data.get("wallets_transferred", 0)
            stats = transfer_data.get("stats", {})

            # Success
            embed = create_success_embed(
                title="Account Transfer Successful",
                description=(
                    f"## ✅ Your account has been transferred!\n\n"
                    f"**Previous Discord ID:** `{transfer_data.get('previous_discord_id', 'Unknown')}`\n"
                    f"**New Discord ID:** `{transfer_data.get('new_discord_id', 'Unknown')}`\n\n"
                    f"### Transferred Data\n\n"
                    f"**Wallets:** {wallets_transferred} wallet(s) transferred\n"
                    f"**Volume:** ${stats.get('total_volume_usd', 0):,.2f} USD\n"
                    f"**Trades:** {stats.get('completed_trades', 0)} completed\n"
                    f"**Swaps:** {stats.get('total_swaps', 0)} completed\n\n"
                    f"### What's Next?\n\n"
                    f"> • Your wallets, stats, and reputation are now linked to this Discord account\n"
                    f"> • Your recovery code has been marked as used\n"
                    f"> • Generate new recovery codes in your dashboard\n"
                    f"> • You can now use all Afroo services normally\n\n"
                    f"Welcome back! 🎉"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Account transfer successful: {transfer_data.get('previous_discord_id')} → {interaction.user.id}"
            )

        except APIError as e:
            logger.error(f"API error during account transfer: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Transfer Failed",
                    description=f"{e.user_message}\n\nPlease verify your recovery code and try again."
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during account transfer: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Transfer Failed",
                    description=f"An unexpected error occurred: {str(e)}\n\nPlease contact support if this persists."
                ),
                ephemeral=True
            )


async def show_transfer_info(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show account transfer information and modal.

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    try:
        embed = create_themed_embed(
            title="",
            description=(
                f"## 🔑 Account Recovery Transfer\n\n"
                f"### Lost Access to Your Discord?\n\n"
                f"If you previously generated recovery codes and lost access to your Discord account, "
                f"you can transfer your Afroo account to your new Discord account.\n\n"
                f"### What Gets Transferred?\n\n"
                f"> • **All Wallets** - Your crypto wallets with private keys\n"
                f"> • **Statistics** - Trading volume, swap history, completed trades\n"
                f"> • **Reputation** - Your reputation score and ratings\n"
                f"> • **Roles** - Your Afroo roles (Exchanger, VIP, etc.)\n\n"
                f"### Requirements\n\n"
                f"> • You must have generated recovery codes on your old account\n"
                f"> • You need one of your recovery codes\n"
                f"> • This Discord account must NOT already have an Afroo account\n"
                f"> • Each recovery code can only be used once\n\n"
                f"### Ready to Transfer?\n\n"
                f"> Click the button below to enter your recovery code."
            ),
            color=PURPLE_GRADIENT
        )

        view = TransferAccountView(bot)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed transfer info to user {interaction.user.id}")

    except Exception as e:
        logger.error(f"Error showing transfer info: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ **Error**\n\nFailed to show transfer info: {str(e)}",
            ephemeral=True
        )


class TransferAccountView(discord.ui.View):
    """View with button to open transfer modal"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(
        label="Transfer Account",
        style=discord.ButtonStyle.primary,
        emoji="🔑"
    )
    async def transfer_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Open transfer modal"""
        modal = TransferAccountModal(self.bot)
        await interaction.response.send_modal(modal)
