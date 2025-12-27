"""
Create Ticket Modal - Form for creating exchange tickets
"""

import discord
import logging

from api.errors import APIError
from utils.embeds import create_ticket_embed, error_embed, success_embed
from config import config

logger = logging.getLogger(__name__)


class CreateTicketModal(discord.ui.Modal):
    """Modal for creating exchange tickets"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="Start Exchange")
        self.bot = bot

        # Input currency
        self.add_item(
            discord.ui.InputText(
                label="What are you sending?",
                placeholder="e.g., BTC, LTC, PayPal, Cash App, etc.",
                style=discord.InputTextStyle.short,
                max_length=50
            )
        )

        # Output currency
        self.add_item(
            discord.ui.InputText(
                label="What do you want to receive?",
                placeholder="e.g., BTC, LTC, PayPal, Cash App, etc.",
                style=discord.InputTextStyle.short,
                max_length=50
            )
        )

        # Amount
        self.add_item(
            discord.ui.InputText(
                label="Amount (USD value)",
                placeholder="e.g., 100.00",
                style=discord.InputTextStyle.short,
                max_length=20
            )
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get form values
            input_currency = self.children[0].value.strip()
            output_currency = self.children[1].value.strip()
            amount_str = self.children[2].value.strip()

            # Validate amount
            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError:
                await interaction.followup.send(
                    embed=error_embed(
                        description="❌ Invalid amount. Please enter a valid number."
                    ),
                    ephemeral=True
                )
                return

            # Create ticket via API
            api = self.bot.api_client
            ticket = await api.create_ticket(
                user_id=str(interaction.user.id),
                input_currency=input_currency,
                output_currency=output_currency,
                amount=amount
            )

            logger.info(
                f"Ticket created: {ticket.ticket_id} by {interaction.user.name} "
                f"({input_currency} -> {output_currency}, ${amount})"
            )

            # Create ticket channel
            guild = interaction.guild
            category = guild.get_channel(config.CATEGORY_TICKETS)

            if not category:
                await interaction.followup.send(
                    embed=error_embed(
                        description="❌ Tickets category not configured. Please contact an admin."
                    ),
                    ephemeral=True
                )
                return

            # Create channel
            channel = await category.create_text_channel(
                name=f"ticket-{ticket.ticket_id}",
                topic=f"{input_currency} → {output_currency} | ${amount}"
            )

            # Set permissions
            await channel.set_permissions(
                guild.default_role,
                view_channel=False
            )
            await channel.set_permissions(
                interaction.user,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

            # Update ticket with channel ID
            await api.update_ticket(
                ticket_id=ticket.ticket_id,
                channel_id=str(channel.id)
            )

            # Send ticket embed in channel
            ticket_embed = create_ticket_embed(ticket.dict())
            ticket_embed.description += (
                f"\n**Created by:** {interaction.user.mention}\n"
                f"\n📋 **Next Step:** Please agree to our Terms of Service below."
            )

            await channel.send(
                content=interaction.user.mention,
                embed=ticket_embed
            )

            # TODO: Send TOS view here

            # Confirm to user
            await interaction.followup.send(
                embed=success_embed(
                    description=(
                        f"✅ Ticket created successfully!\n\n"
                        f"**Ticket:** #{ticket.ticket_id}\n"
                        f"**Channel:** {channel.mention}\n\n"
                        f"Please head to {channel.mention} to continue."
                    )
                ),
                ephemeral=True
            )

        except APIError as e:
            logger.error(f"API error creating ticket: {e}")
            await interaction.followup.send(
                embed=error_embed(
                    description=f"❌ {e.user_message}"
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error creating ticket: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description="❌ An error occurred. Please try again or contact support."
                ),
                ephemeral=True
            )
