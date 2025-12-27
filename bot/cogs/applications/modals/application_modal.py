"""
Application Modal for V4
Modal for exchanger application form
"""

import logging

import discord
from discord.ui import Modal, InputText

logger = logging.getLogger(__name__)


class ExchangerApplicationModal(Modal):
    """Modal for exchanger application"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="Exchanger Application")
        self.bot = bot

        self.payment_methods_input = InputText(
            label="What Payment methods do you have?",
            placeholder="e.g., PayPal, CashApp, Venmo, Zelle, etc.",
            required=True,
            min_length=10,
            max_length=500,
            style=discord.InputTextStyle.long
        )
        self.add_item(self.payment_methods_input)

        self.crypto_amount_input = InputText(
            label="How much crypto do you have?",
            placeholder="Approximate USD value of crypto you can deposit",
            required=True,
            min_length=5,
            max_length=200,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.crypto_amount_input)

        self.experience_input = InputText(
            label="Any Past experience or Vouches / REP?",
            placeholder="Describe your trading experience, vouches, or reputation",
            required=True,
            min_length=20,
            max_length=1000,
            style=discord.InputTextStyle.long
        )
        self.add_item(self.experience_input)

        self.availability_input = InputText(
            label="Availability (TimeZone)",
            placeholder="e.g., EST, 9am-11pm daily / PST, evenings and weekends",
            required=True,
            min_length=10,
            max_length=200,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.availability_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle application submission"""
        await interaction.response.defer(ephemeral=True)

        try:
            from cogs.applications.handlers.application_handler import create_application

            # Get account age
            import discord.utils
            account_age_days = (discord.utils.utcnow() - interaction.user.created_at).days

            await create_application(
                bot=self.bot,
                interaction=interaction,
                payment_methods=self.payment_methods_input.value.strip(),
                crypto_amount=self.crypto_amount_input.value.strip(),
                experience=self.experience_input.value.strip(),
                availability=self.availability_input.value.strip(),
                account_age_days=account_age_days
            )

        except Exception as e:
            logger.error(f"Error submitting application: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**\n\nFailed to submit application: {str(e)}",
                ephemeral=True
            )
