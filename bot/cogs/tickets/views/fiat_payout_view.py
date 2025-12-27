"""
Fiat-to-Fiat Payout Views
Handles exchanger confirmation of receiving funds and sending payment for fiat transactions
"""

import logging
import discord
from discord.ui import View, Button

from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN
from utils.auth import get_user_context
from config import config

logger = logging.getLogger(__name__)


class FiatExchangerConfirmationView(View):
    """View for exchanger to confirm they received customer's fiat payment"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel, ticket_data: dict):
        super().__init__(timeout=None)  # Persistent
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.ticket_data = ticket_data

    @discord.ui.button(
        label="I Received Payment",
        style=discord.ButtonStyle.primary,
        emoji="✅",
        custom_id="exchanger_confirm_received"
    )
    async def exchanger_confirm_button(self, button: Button, interaction: discord.Interaction):
        """Exchanger confirms they received customer's payment"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get user context for API authentication
            user_id, roles = get_user_context(interaction)

            # Verify it's the exchanger or admin with bypass
            exchanger_discord_id = self.ticket_data.get("exchanger_discord_id")

            # Check for admin bypass (Head Admin or Assistant Admin)
            from config import config
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            admin_bypass = is_head_admin or is_assistant_admin

            logger.info(f"Fiat confirm receipt: user={interaction.user.id}, exchanger={exchanger_discord_id}, admin_bypass={admin_bypass}, status={self.ticket_data.get('status')}")

            # Check permission (unless admin bypass)
            if not admin_bypass and (not exchanger_discord_id or str(interaction.user.id) != str(exchanger_discord_id)):
                await interaction.followup.send(
                    "❌ Only the assigned exchanger can confirm receiving payment.",
                    ephemeral=True
                )
                return

            # Mark exchanger confirmed
            await self.bot.api_client.post(
                f"/api/v1/tickets/{self.ticket_id}/exchanger-confirmed",
                data={},
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Disable button
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Get client Discord ID
            client_discord_id = self.ticket_data.get("discord_user_id") or str(self.ticket_data.get("user_id", ""))

            # Post confirmation that exchanger received payment
            confirmation_embed = create_themed_embed(
                title="",
                description=(
                    f"## ✅ Payment Received\n\n"
                    f"{interaction.user.mention} has confirmed receiving the customer's payment.\n\n"
                    f"**Next:** Send the payout to <@{client_discord_id}> now."
                ),
                color=SUCCESS_GREEN
            )

            await self.channel.send(embed=confirmation_embed)

            # Post payment sent instruction for exchanger
            from cogs.tickets.views.fiat_payout_view import FiatPaymentSentView

            sent_embed = create_themed_embed(
                title="",
                description=(
                    f"## 💸 Send Payment to Customer\n\n"
                    f"**Exchanger:** {interaction.user.mention}\n\n"
                    f"Send the **{self.ticket_data.get('receive_method', 'fiat')}** payment to <@{client_discord_id}> now.\n\n"
                    f"**Amount:** ${self.ticket_data.get('receiving_amount', 0):.2f} USD\n\n"
                    f"Once you've sent it, click the button below."
                ),
                color=PURPLE_GRADIENT
            )

            sent_view = FiatPaymentSentView(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=self.channel,
                ticket_data=self.ticket_data
            )

            await self.channel.send(content=f"<@{exchanger_discord_id}>", embed=sent_embed, view=sent_view)

            await interaction.followup.send(
                "✅ Confirmed! Now send the payment to the customer and click the next button.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in exchanger confirmation: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


class FiatPaymentSentView(View):
    """View for exchanger to confirm they sent payment to customer"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel, ticket_data: dict):
        super().__init__(timeout=None)  # Persistent
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.ticket_data = ticket_data

    @discord.ui.button(
        label="I Sent Payment",
        style=discord.ButtonStyle.success,
        emoji="💰",
        custom_id="exchanger_sent_payment"
    )
    async def exchanger_sent_button(self, button: Button, interaction: discord.Interaction):
        """Exchanger confirms they sent payment to customer"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get user context for API authentication
            user_id, roles = get_user_context(interaction)

            # Verify it's the exchanger or admin with bypass
            exchanger_discord_id = self.ticket_data.get("exchanger_discord_id")

            # Check for admin bypass (Head Admin or Assistant Admin)
            from config import config
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            admin_bypass = is_head_admin or is_assistant_admin

            logger.info(f"Fiat payment sent: user={interaction.user.id}, exchanger={exchanger_discord_id}, admin_bypass={admin_bypass}, status={self.ticket_data.get('status')}")

            # Check permission (unless admin bypass)
            if not admin_bypass and (not exchanger_discord_id or str(interaction.user.id) != str(exchanger_discord_id)):
                await interaction.followup.send(
                    "❌ Only the assigned exchanger can confirm sending payment.",
                    ephemeral=True
                )
                return

            # Mark payment sent
            await self.bot.api_client.post(
                f"/api/v1/tickets/{self.ticket_id}/payment-sent",
                data={},
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Disable button
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Get client Discord ID
            client_discord_id = self.ticket_data.get("discord_user_id") or str(self.ticket_data.get("user_id", ""))

            # Post client confirmation request
            from cogs.tickets.views.completion_views import ManualConfirmationView

            client_embed = create_themed_embed(
                title="",
                description=(
                    f"## 💰 Confirm Receipt\n\n"
                    f"<@{client_discord_id}> The exchanger has sent your payment.\n\n"
                    f"**Please confirm:**\n"
                    f"> Did you receive the **{self.ticket_data.get('receive_method', 'fiat')}** payment?\n\n"
                    f"Click **I Received Payment** once you've confirmed."
                ),
                color=PURPLE_GRADIENT
            )

            client_view = ManualConfirmationView(
                ticket_id=self.ticket_id,
                ticket_number=self.ticket_data.get("ticket_number", 0),
                api=self.bot.api_client
            )

            await self.channel.send(content=f"<@{client_discord_id}>", embed=client_embed, view=client_view)

            await interaction.followup.send(
                "✅ Confirmed! Waiting for customer to confirm receipt.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in payment sent confirmation: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
