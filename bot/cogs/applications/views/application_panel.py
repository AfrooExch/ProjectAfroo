"""
Application Panel View for V4
Main panel with Apply button
"""

import logging

import discord
from discord.ui import View, Button

from config import Config

logger = logging.getLogger(__name__)


class ApplicationPanelView(View):
    """Main application panel with Apply button"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Apply to Become Exchanger",
        style=discord.ButtonStyle.primary,
        emoji="📋",
        custom_id="apply_exchanger_button"
    )
    async def apply_button(self, button: Button, interaction: discord.Interaction):
        """Handle apply button click"""

        # Check if user already has exchanger role
        if Config.is_exchanger(interaction.user):
            await interaction.response.send_message(
                "❌ You are already an exchanger!",
                ephemeral=True
            )
            return

        # Check if user already has pending application
        try:
            api = self.bot.api_client
            existing_app = await api.get(f"/api/v1/applications/user/{interaction.user.id}/pending")

            if existing_app:
                await interaction.response.send_message(
                    "⏳ **Application Pending**\n\n"
                    f"You already have a pending application.\n"
                    f"**Application ID:** `{existing_app.get('id', 'N/A')}`\n\n"
                    f"> Please wait for staff to review your application.\n"
                    f"> This typically takes 24-48 hours.",
                    ephemeral=True
                )
                return

        except Exception as e:
            # If no pending application found, continue
            logger.debug(f"No pending application found for user {interaction.user.id}: {e}")

        # Check account age
        import discord.utils
        account_age_days = (discord.utils.utcnow() - interaction.user.created_at).days

        if account_age_days < 30:
            await interaction.response.send_message(
                f"❌ **Account Too New**\n\n"
                f"Your Discord account must be at least 30 days old to apply.\n"
                f"**Your Account Age:** {account_age_days} days\n"
                f"**Required:** 30 days\n\n"
                f"> Please try again when your account is older.",
                ephemeral=True
            )
            return

        # Show application modal
        from cogs.applications.modals.application_modal import ExchangerApplicationModal

        modal = ExchangerApplicationModal(self.bot)
        await interaction.response.send_modal(modal)

        logger.info(f"User {interaction.user.id} opened application modal")
