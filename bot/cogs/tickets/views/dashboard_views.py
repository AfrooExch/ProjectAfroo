"""
Exchange Dashboard Views
7-button dashboard for managing exchange tickets after claim
"""

import discord
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from cogs.tickets.constants import get_payment_method, CRYPTO_ASSETS
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED, BLUE_PRIMARY
from utils.auth import get_user_context
from api.client import APIClient
from config import config

logger = logging.getLogger(__name__)


def create_dashboard_embed(ticket_data: Dict[str, Any], exchanger: discord.Member) -> discord.Embed:
    """
    Create exchange dashboard embed (V3 Style)

    Args:
        ticket_data: Ticket data from API
        exchanger: Discord member who claimed the ticket

    Returns:
        Discord embed with dashboard
    """
    ticket_number = ticket_data.get("ticket_number")
    amount_usd = ticket_data.get("amount_usd", 0)
    fee_amount = ticket_data.get("fee_amount", 0)
    fee_percentage = ticket_data.get("fee_percentage", 10.0)
    receiving_amount = ticket_data.get("receiving_amount", 0)

    send_method_id = ticket_data.get("send_method")
    receive_method_id = ticket_data.get("receive_method")
    send_crypto = ticket_data.get("send_crypto")
    receive_crypto = ticket_data.get("receive_crypto")

    # Get payment method details
    send_method = get_payment_method(send_method_id)
    receive_method = get_payment_method(receive_method_id)

    # Build display names (V3 style - no emojis) with fallbacks
    if send_crypto:
        crypto_asset = CRYPTO_ASSETS.get(send_crypto)
        if crypto_asset:
            send_display = f"{crypto_asset.name} ({send_crypto})"
        else:
            send_display = send_crypto.upper()
    else:
        send_display = send_method.name if send_method else (send_method_id or "Payment Method")

    if receive_crypto:
        crypto_asset = CRYPTO_ASSETS.get(receive_crypto)
        if crypto_asset:
            receive_display = f"{crypto_asset.name} ({receive_crypto})"
        else:
            receive_display = receive_crypto.upper()
    else:
        receive_display = receive_method.name if receive_method else (receive_method_id or "Payment Method")

    # Calculate server fee (2% or min $0.50)
    server_fee = max(amount_usd * 0.02, 0.50)

    # Format fee display
    if amount_usd < 40.0:
        fee_display = f"`${fee_amount:.2f}` (Min Fee)"
    else:
        fee_display = f"`${fee_amount:.2f}` ({fee_percentage:.0f}%)"

    # Clean embed with purple gradient and full breakdown
    embed = create_themed_embed(
        title="",
        description=(
            f"## Exchanger Dashboard\n\n"
            f"**Ticket:** #{ticket_number}\n"
            f"**Claimed By:** {exchanger.mention}\n\n"
            f"**Exchange Breakdown:**\n"
            f"> **Customer Amount:** `${amount_usd:,.2f}`\n"
            f"> **Service Fee:** {fee_display}\n"
            f"> **You Send to Client:** `${receiving_amount:.2f}`\n"
            f"> **Server Fee (2% min $0.50):** `${server_fee:.2f}`\n\n"
            f"**Payment Methods:**\n"
            f"> **Receiving from Client:** {send_display}\n"
            f"> **Sending to Client:** {receive_display}\n\n"
            f"**Instructions:**\n"
            f"> **Client:** Click 'I Sent' after sending payment\n"
            f"> **Exchanger:** Use buttons below to manage ticket"
        ),
        color=PURPLE_GRADIENT
    )

    return embed


class ExchangeDashboardView(discord.ui.View):
    """
    7-button Exchange Dashboard for managing tickets
    """

    def __init__(
        self,
        ticket_id: str,
        ticket_number: int,
        api: APIClient,
        timeout: float = None  # No timeout - persistent
    ):
        super().__init__(timeout=timeout)
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.api = api

    @discord.ui.button(label="I Sent My Funds", style=discord.ButtonStyle.primary, emoji="💸", row=0)
    async def sent_funds_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Client confirms they sent payment"""
        try:
            await interaction.response.defer()

            # Get user context
            user_id, roles = get_user_context(interaction)

            # Check for admin bypass (Head Admin or Assistant Admin can mark on behalf of client)
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            admin_bypass = is_head_admin or is_assistant_admin

            # Call API to mark funds as sent (client or admin can do this)
            result = await self.api.post(
                f"/api/v1/tickets/{self.ticket_id}/client-sent",
                data={},
                discord_user_id=user_id,
                discord_roles=roles
            )

            ticket_data = result.get("ticket", {})
            receiving_amount = ticket_data.get("receiving_amount", 0)
            receive_method = ticket_data.get("receive_method", "")
            receive_crypto = ticket_data.get("receive_crypto", "")
            exchanger_discord_id = ticket_data.get("exchanger_discord_id")

            # Check if customer is receiving crypto
            is_crypto_payout = receive_method == "crypto" or receive_crypto

            # Update embed
            embed = create_themed_embed(
                title="Client Sent Funds",
                description=f"{interaction.user.mention} has confirmed they sent the payment!",
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=embed)

            if not is_crypto_payout:
                # FIAT PAYOUT - Ask EXCHANGER to confirm they received client's payment first
                guild = interaction.guild
                exchanger_member = guild.get_member(int(exchanger_discord_id)) if exchanger_discord_id else None

                confirm_embed = create_themed_embed(
                    title="",
                    description=(
                        f"## Step 1: Confirm Receipt\n\n"
                        f"**Exchanger**: {exchanger_member.mention if exchanger_member else '@Exchanger'}\n\n"
                        f"Did you receive the client's payment?\n\n"
                        f"Click the button below to confirm you received it, then send **${receiving_amount:,.2f}** to the client."
                    ),
                    color=PURPLE_GRADIENT
                )

                # Create a simple confirmation view for exchanger
                from cogs.tickets.views.completion_views import ExchangerReceivedConfirmView

                confirm_view = ExchangerReceivedConfirmView(
                    ticket_id=self.ticket_id,
                    ticket_number=self.ticket_number,
                    api=self.api,
                    receiving_amount=receiving_amount
                )

                await interaction.channel.send(embed=confirm_embed, view=confirm_view)
            else:
                # CRYPTO PAYOUT - Show wallet options
                from cogs.tickets.views.payout_views import PayoutMethodView

                payout_view = PayoutMethodView(
                    ticket_id=self.ticket_id,
                    ticket_number=self.ticket_number,
                    api=self.api
                )

                payout_embed = create_themed_embed(
                    title="Select Payout Method",
                    description=f"How will you pay the client **${receiving_amount:,.2f}** in crypto?",
                    color=PURPLE_GRADIENT
                )

                await interaction.channel.send(embed=payout_embed, view=payout_view)

        except ValueError as e:
            embed = create_themed_embed(
                title="Permission Denied",
                description=str(e),
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error marking funds sent for ticket {self.ticket_id}: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Change Amount", style=discord.ButtonStyle.secondary, emoji="💵", row=0)
    async def change_amount_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Request amount change - requires both parties to agree"""
        try:
            # Show modal for new amount
            modal = ChangeAmountModal(self.ticket_id, self.api)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error showing change amount modal: {e}", exc_info=True)

    @discord.ui.button(label="Change Fee", style=discord.ButtonStyle.secondary, emoji="💰", row=0)
    async def change_fee_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Request fee change - requires both parties to agree"""
        try:
            # Show modal for new fee
            modal = ChangeFeeModal(self.ticket_id, self.api)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error showing change fee modal: {e}", exc_info=True)

    @discord.ui.button(label="Request Unclaim", style=discord.ButtonStyle.secondary, emoji="🔓", row=1)
    async def unclaim_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Request to unclaim ticket - requires both parties to agree"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get user context
            user_id, roles = get_user_context(interaction)

            # Get ticket data to check if requester is both client and exchanger
            ticket_result = await self.api.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket_data = ticket_result.get("ticket", {})

            # Check if requester is both client and exchanger
            client_discord_id = ticket_data.get("discord_user_id")
            exchanger_discord_id = ticket_data.get("exchanger_discord_id")  # If available

            # For now, check if user_id matches client (more complex check would require looking up assigned_to)
            is_only_party = (client_discord_id == user_id and not ticket_data.get("assigned_to"))

            # If requester is the only party, execute immediately without confirmation
            if is_only_party or (client_discord_id == user_id and exchanger_discord_id == user_id):
                # Call API to approve unclaim directly
                result = await self.api.post(
                    f"/api/v1/tickets/{self.ticket_id}/approve-unclaim",
                    data={},
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Get updated ticket data
                updated_ticket_data = result.get("ticket", {})

                embed = create_themed_embed(
                    title="Ticket Unclaimed",
                    description=f"Ticket **#{self.ticket_number}** has been unclaimed.\n\nFunds have been released and the ticket is available for claim again.",
                    color=PURPLE_GRADIENT
                )
                await interaction.channel.send(embed=embed)
                await interaction.followup.send("Ticket unclaimed successfully!", ephemeral=True)

                # Move back to unclaimed category
                guild = interaction.guild
                tickets_category = guild.get_channel(config.CATEGORY_TICKETS)
                if tickets_category:
                    await interaction.channel.edit(category=tickets_category)

                # IMPORTANT: Remove specific exchanger's permissions first
                exchanger_discord_id = ticket_data.get("exchanger_discord_id")
                if exchanger_discord_id:
                    try:
                        exchanger_member = guild.get_member(int(exchanger_discord_id))
                        if exchanger_member:
                            # Remove their specific permissions (resets to role-based)
                            await interaction.channel.set_permissions(exchanger_member, overwrite=None)
                            logger.info(f"Removed specific permissions for exchanger {exchanger_discord_id} on ticket {self.ticket_id}")
                    except Exception as e:
                        logger.error(f"Failed to remove exchanger permissions: {e}")

                # Reset main exchanger role to VIEW ONLY permissions
                main_exchanger_role_id = config.ROLE_EXCHANGER
                main_exchanger_role = guild.get_role(main_exchanger_role_id)

                if main_exchanger_role:
                    await interaction.channel.set_permissions(
                        main_exchanger_role,
                        view_channel=True,
                        read_messages=True,
                        send_messages=False,  # VIEW ONLY - cannot speak until they claim
                        read_message_history=True
                    )
                    logger.info(f"Reset VIEW ONLY permissions for main exchanger role on ticket {self.ticket_id}")

                # Repost the exchange ticket embed so new exchangers can claim it
                from cogs.tickets.views.claim_views import create_exchange_details_embed, ClaimView

                # Get bot instance for custom emojis
                bot = interaction.client

                # Create fresh exchange details embed with claim button
                exchange_embed = create_exchange_details_embed(updated_ticket_data, bot=bot)
                claim_view = ClaimView(
                    ticket_id=self.ticket_id,
                    ticket_number=self.ticket_number,
                    api=self.api
                )

                # Get payment methods from ticket data for exchanger role pings
                send_method = updated_ticket_data.get("send_method", "")
                receive_method = updated_ticket_data.get("receive_method", "")

                logger.info(f"Ticket methods after unclaim: send={send_method}, receive={receive_method}")

                # Get appropriate exchanger roles for these payment methods
                exchanger_role_ids = config.get_exchanger_roles_for_methods(send_method, receive_method)

                logger.info(f"Got exchanger role IDs after unclaim: {exchanger_role_ids}")

                # Build role mentions
                role_mentions = []
                for role_id in exchanger_role_ids:
                    role = guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                        logger.info(f"Found role for repost: {role.name} ({role_id})")

                # If no valid roles, use generic exchanger role
                if not role_mentions:
                    exchanger_role = guild.get_role(config.ROLE_EXCHANGER)
                    role_mentions = [exchanger_role.mention if exchanger_role else "@Exchanger"]
                    logger.warning(f"No specific roles found for repost, using generic exchanger role")

                # Send the exchange ticket embed again with claim button
                await interaction.channel.send(
                    content=f"{' '.join(role_mentions)} Ticket available for claim again!",
                    embed=exchange_embed,
                    view=claim_view
                )
            else:
                # Call API to request unclaim
                result = await self.api.post(
                    f"/api/v1/tickets/{self.ticket_id}/request-unclaim",
                    data={},
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Show confirmation view (requester pre-confirmed)
                embed = create_themed_embed(
                    title="Unclaim Request",
                    description=f"{interaction.user.mention} has requested to unclaim this ticket.\n\nWaiting for the other party to agree.",
                    color=PURPLE_GRADIENT
                )

                view = UnclaimConfirmView(self.ticket_id, self.ticket_number, self.api, interaction.user.id)
                await interaction.channel.send(embed=embed, view=view)

                await interaction.followup.send("Unclaim request sent!", ephemeral=True)

        except Exception as e:
            logger.error(f"Error requesting unclaim: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Request Close", style=discord.ButtonStyle.danger, emoji="🔒", row=1)
    async def close_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Request to close ticket - releases holds and closes ticket"""
        try:
            # Show confirmation modal (don't defer first!)
            modal = CloseTicketModal(self.ticket_id, self.ticket_number, self.api)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error requesting close: {e}", exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Convert Currency", style=discord.ButtonStyle.secondary, emoji="💱", row=1)
    async def convert_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show live conversion rates for top 10 global currencies"""
        try:
            # Show modal for amount to convert
            modal = CurrencyConversionModal(self.api)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error showing conversion modal: {e}", exc_info=True)

    @discord.ui.button(label="Remind Client", style=discord.ButtonStyle.secondary, emoji="🔔", row=2)
    async def remind_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Bot DMs client about open ticket (exchanger only)"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get user context
            user_id, roles = get_user_context(interaction)

            # Check if user is exchanger
            if config.ROLE_EXCHANGER not in roles:
                embed = create_themed_embed(
                    title="Permission Denied",
                    description="Only exchangers can send reminders.",
                    color=ERROR_RED
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Get ticket data to find client
            result = await self.api.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )

            ticket_data = result.get("ticket", {})
            client_discord_id = ticket_data.get("discord_user_id")

            # Get client member
            guild = interaction.guild
            client_member = guild.get_member(int(client_discord_id)) if client_discord_id else None

            if not client_member:
                embed = create_themed_embed(
                    title="Error",
                    description="Could not find client member.",
                    color=ERROR_RED
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Send DM to client
            try:
                dm_embed = create_themed_embed(
                    title="🔔 Exchange Ticket Reminder",
                    description=f"You have an open exchange ticket **#{self.ticket_number}** that needs your attention!\n\nPlease check {interaction.channel.mention} to continue with your exchange.",
                    color=BLUE_PRIMARY
                )

                await client_member.send(embed=dm_embed)

                # Notify in channel
                embed = create_themed_embed(
                    title="Reminder Sent",
                    description=f"A reminder has been sent to {client_member.mention} via DM.",
                    color=PURPLE_GRADIENT
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

            except discord.Forbidden:
                embed = create_themed_embed(
                    title="Cannot Send DM",
                    description=f"Could not send DM to {client_member.mention} (DMs disabled). Pinging them in channel instead...",
                    color=PURPLE_GRADIENT
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

                # Ping in channel
                await interaction.channel.send(
                    f"{client_member.mention} You have an open exchange ticket that needs your attention!"
                )

        except Exception as e:
            logger.error(f"Error sending reminder: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class ChangeAmountModal(discord.ui.Modal):
    """Modal for requesting amount change"""

    def __init__(self, ticket_id: str, api: APIClient):
        super().__init__(title="Request Amount Change")
        self.ticket_id = ticket_id
        self.api = api

        self.new_amount = discord.ui.InputText(
            label="New Amount (USD)",
            placeholder="Enter new amount in USD",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.new_amount)

        self.reason = discord.ui.InputText(
            label="Reason for Change",
            placeholder="Why are you requesting this change?",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        """Handle amount change request"""
        try:
            await interaction.response.defer()

            user_id, roles = get_user_context(interaction)
            new_amount = float(self.new_amount.value.strip().replace("$", "").replace(",", ""))

            # Request change via API
            result = await self.api.post(
                f"/api/v1/tickets/{self.ticket_id}/request-amount-change",
                data={"new_amount": new_amount, "reason": self.reason.value},
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Show confirmation request
            embed = create_themed_embed(
                title="Amount Change Request",
                description=f"{interaction.user.mention} requests to change the amount to **${new_amount:,.2f}**.\n\n**Reason:** {self.reason.value}\n\nWaiting for the other party to agree.",
                color=PURPLE_GRADIENT
            )

            view = AmountChangeConfirmView(self.ticket_id, new_amount, self.api, interaction.user.id)
            await interaction.channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error requesting amount change: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class ChangeFeeModal(discord.ui.Modal):
    """Modal for requesting fee change"""

    def __init__(self, ticket_id: str, api: APIClient):
        super().__init__(title="Request Fee Change")
        self.ticket_id = ticket_id
        self.api = api

        self.new_fee = discord.ui.InputText(
            label="New Fee Percentage",
            placeholder="Enter new fee percentage (e.g., 5.0 for 5%)",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.new_fee)

        self.reason = discord.ui.InputText(
            label="Reason for Change",
            placeholder="Why are you requesting this change?",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        """Handle fee change request"""
        try:
            await interaction.response.defer()

            user_id, roles = get_user_context(interaction)
            new_fee_percentage = float(self.new_fee.value.strip().replace("%", ""))

            # Request change via API
            result = await self.api.post(
                f"/api/v1/tickets/{self.ticket_id}/request-fee-change",
                data={"new_fee_percentage": new_fee_percentage, "reason": self.reason.value},
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Show confirmation request
            embed = create_themed_embed(
                title="Fee Change Request",
                description=f"{interaction.user.mention} requests to change the fee to **{new_fee_percentage}%**.\n\n**Reason:** {self.reason.value}\n\nWaiting for the other party to agree.",
                color=PURPLE_GRADIENT
            )

            view = FeeChangeConfirmView(self.ticket_id, new_fee_percentage, self.api, interaction.user.id)
            await interaction.channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error requesting fee change: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class CloseTicketModal(discord.ui.Modal):
    """Modal for requesting ticket close"""

    def __init__(self, ticket_id: str, ticket_number: int, api: APIClient):
        super().__init__(title=f"Close Ticket #{ticket_number}")
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.api = api

        self.reason = discord.ui.InputText(
            label="Reason for Closing",
            placeholder="Why are you closing this ticket?",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        """Handle close ticket - staff closes immediately, others request close with approval"""
        try:
            await interaction.response.defer()

            user_id, roles = get_user_context(interaction)

            # Check if user is staff
            is_staff = config.ROLE_STAFF in roles or config.ROLE_ADMIN in roles

            if is_staff:
                # STAFF: Close immediately, refund holds, no transcripts
                result = await self.api.post(
                    f"/api/v1/tickets/{self.ticket_id}/cancel",
                    data={"reason": self.reason.value},
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Show close confirmation
                embed = create_themed_embed(
                    title="Ticket Closed",
                    description=f"Ticket **#{self.ticket_number}** has been closed by {interaction.user.mention}.\n\n**Reason:** {self.reason.value}\n\n✅ Holds have been released (refunded)\n\nThis channel will be deleted in 30 seconds.",
                    color=ERROR_RED
                )

                await interaction.channel.send(embed=embed)

                # Delete channel after delay
                import asyncio
                await asyncio.sleep(30)
                try:
                    await interaction.channel.delete(reason=f"Ticket closed: {self.reason.value}")
                except:
                    pass
            else:
                # NON-STAFF: Request close with approval needed
                result = await self.api.post(
                    f"/api/v1/tickets/{self.ticket_id}/request-close",
                    data={"reason": self.reason.value},
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Show request confirmation
                embed = create_themed_embed(
                    title="Close Request Sent",
                    description=f"{interaction.user.mention} has requested to close this ticket.\n\n**Reason:** {self.reason.value}\n\nWaiting for the other party to approve. If approved, transcripts will be generated and sent to both parties.",
                    color=PURPLE_GRADIENT
                )

                # Show approval view
                from cogs.tickets.views.dashboard_views import CloseConfirmView
                view = CloseConfirmView(self.ticket_id, self.ticket_number, self.api, user_id)

                await interaction.channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error closing ticket: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class CurrencyConversionModal(discord.ui.Modal):
    """Modal for currency conversion"""

    def __init__(self, api: APIClient):
        super().__init__(title="Currency Converter")
        self.api = api

        self.amount = discord.ui.InputText(
            label="Amount in USD",
            placeholder="Enter amount to convert (e.g., 100)",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.amount)

    async def callback(self, interaction: discord.Interaction):
        """Show currency conversions"""
        try:
            await interaction.response.defer(ephemeral=True)

            amount_usd = float(self.amount.value.strip().replace("$", "").replace(",", ""))

            # Call API to get live rates
            result = await self.api.get(
                f"/api/v1/tickets/exchange-rates?amount={amount_usd}",
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
            )

            rates = result.get("conversions", {})

            # Build embed with top 10 global currencies
            embed = create_themed_embed(
                title=f"${amount_usd:,.2f} USD Conversion Rates",
                description="Live conversion rates for global currencies:",
                color=PURPLE_GRADIENT
            )

            # Display rates
            for currency_code, currency_data in list(rates.items())[:10]:
                name = currency_data.get("name", currency_code)
                formatted = currency_data.get("formatted", f"{currency_data['amount']:,.2f} {currency_code}")
                embed.add_field(
                    name=name,
                    value=formatted,
                    inline=True
                )

            embed.set_footer(text="Rates are approximate and may vary")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error converting currency: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


# Confirmation Views for Change Requests

class UnclaimConfirmView(discord.ui.View):
    """Confirmation view for unclaim request"""

    def __init__(self, ticket_id: str, ticket_number: int, api: APIClient, requester_id: int):
        super().__init__(timeout=300)  # 5 minutes
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.api = api
        self.requester_id = requester_id
        # Requester automatically agrees by initiating the action
        self.confirmed_users = {requester_id}

    @discord.ui.button(label="Agree to Unclaim", style=discord.ButtonStyle.primary, emoji="✅")
    async def agree_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Agree to unclaim - only OTHER party can click"""
        try:
            # Prevent requester from clicking Agree (they already agreed by requesting)
            if interaction.user.id == self.requester_id:
                await interaction.response.send_message(
                    "You already initiated this request. Waiting for the other party to agree.",
                    ephemeral=True
                )
                return

            await interaction.response.defer()

            # Other party agreed - execute immediately
            result = await self.api.post(
                f"/api/v1/tickets/{self.ticket_id}/approve-unclaim",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
            )

            # Get updated ticket data
            ticket_data = result.get("ticket", {})

            embed = create_themed_embed(
                title="Ticket Unclaimed",
                description=f"Ticket **#{self.ticket_number}** has been unclaimed.\n\nFunds have been released and the ticket is available for claim again.",
                color=PURPLE_GRADIENT
            )

            # Disable buttons
            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

            # Move back to unclaimed category
            guild = interaction.guild
            tickets_category = guild.get_channel(config.CATEGORY_TICKETS)
            if tickets_category:
                await interaction.channel.edit(category=tickets_category)

            # IMPORTANT: Remove specific exchanger's permissions first
            exchanger_discord_id = ticket_data.get("exchanger_discord_id")
            if exchanger_discord_id:
                try:
                    exchanger_member = guild.get_member(int(exchanger_discord_id))
                    if exchanger_member:
                        # Remove their specific permissions (resets to role-based)
                        await interaction.channel.set_permissions(exchanger_member, overwrite=None)
                        logger.info(f"Removed specific permissions for exchanger {exchanger_discord_id} on ticket {self.ticket_id}")
                except Exception as e:
                    logger.error(f"Failed to remove exchanger permissions: {e}")

            # Remove exchanger permissions (reset channel permissions)
            # Get main exchanger role for VIEW ONLY permissions
            main_exchanger_role_id = config.ROLE_EXCHANGER
            main_exchanger_role = guild.get_role(main_exchanger_role_id)

            if main_exchanger_role:
                await interaction.channel.set_permissions(
                    main_exchanger_role,
                    view_channel=True,
                    read_messages=True,
                    send_messages=False,  # VIEW ONLY - cannot speak until they claim
                    read_message_history=True
                )
                logger.info(f"Reset VIEW ONLY permissions for main exchanger role on ticket {self.ticket_id}")

            # Repost the exchange ticket embed so new exchangers can claim it
            from cogs.tickets.views.claim_views import create_exchange_details_embed, ClaimView

            # Get bot instance for custom emojis
            bot = interaction.client

            # Create fresh exchange details embed with claim button
            exchange_embed = create_exchange_details_embed(ticket_data, bot=bot)
            claim_view = ClaimView(
                ticket_id=self.ticket_id,
                ticket_number=self.ticket_number,
                api=self.api
            )

            # Get payment methods from ticket data for exchanger role pings
            send_method = ticket_data.get("send_method", "")
            receive_method = ticket_data.get("receive_method", "")

            logger.info(f"Ticket methods after unclaim: send={send_method}, receive={receive_method}")

            # Get appropriate exchanger roles for these payment methods
            exchanger_role_ids = config.get_exchanger_roles_for_methods(send_method, receive_method)

            logger.info(f"Got exchanger role IDs after unclaim: {exchanger_role_ids}")

            # Build role mentions
            role_mentions = []
            for role_id in exchanger_role_ids:
                role = guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
                    logger.info(f"Found role for repost: {role.name} ({role_id})")

            # If no valid roles, use generic exchanger role
            if not role_mentions:
                exchanger_role = guild.get_role(config.ROLE_EXCHANGER)
                role_mentions = [exchanger_role.mention if exchanger_role else "@Exchanger"]
                logger.warning(f"No specific roles found for repost, using generic exchanger role")

            # Send the exchange ticket embed again with claim button
            await interaction.channel.send(
                content=f"{' '.join(role_mentions)} Ticket available for claim again!",
                embed=exchange_embed,
                view=claim_view
            )

        except Exception as e:
            logger.error(f"Error agreeing to unclaim: {e}", exc_info=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="❌")
    async def deny_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Deny unclaim - only OTHER party can deny"""
        # Prevent requester from denying their own request
        if interaction.user.id == self.requester_id:
            await interaction.response.send_message(
                "You cannot deny your own request. Cancel it by clicking the button again.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        embed = create_themed_embed(
            title="Unclaim Denied",
            description=f"{interaction.user.mention} has denied the unclaim request.",
            color=ERROR_RED
        )

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)


class AmountChangeConfirmView(discord.ui.View):
    """Confirmation view for amount change"""

    def __init__(self, ticket_id: str, new_amount: float, api: APIClient, requester_id: int):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.new_amount = new_amount
        self.api = api
        self.requester_id = requester_id
        # Requester automatically agrees by initiating the action
        self.confirmed_users = {requester_id}

    async def refresh_dashboard(self, channel: discord.TextChannel):
        """Refresh the dashboard embed with updated ticket data"""
        try:
            # Fetch updated ticket data via API
            ticket_result = await self.api.get_ticket(self.ticket_id)

            # Get exchanger member
            exchanger_id = int(ticket_result.get("exchanger_discord_id", 0))
            exchanger = channel.guild.get_member(exchanger_id) if exchanger_id else None

            # Find and update the dashboard message
            async for message in channel.history(limit=50):
                if message.embeds and message.author.bot:
                    embed = message.embeds[0]
                    if "Exchange Dashboard" in (embed.title or "") or "Step by Step Guide" in (embed.description or ""):
                        # Recreate the dashboard embed with updated data
                        new_embed = create_dashboard_embed(ticket_result, exchanger)
                        await message.edit(embed=new_embed)
                        logger.info(f"Refreshed dashboard embed for ticket #{self.ticket_id}")
                        break
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}", exc_info=True)

    @discord.ui.button(label="Agree", style=discord.ButtonStyle.primary, emoji="✅")
    async def agree_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Agree to amount change - only OTHER party can click"""
        try:
            # Prevent requester from clicking Agree
            if interaction.user.id == self.requester_id:
                await interaction.response.send_message(
                    "You already initiated this request. Waiting for the other party to agree.",
                    ephemeral=True
                )
                return

            await interaction.response.defer()

            # Other party agreed - execute immediately
            result = await self.api.post(
                f"/api/v1/tickets/{self.ticket_id}/approve-amount-change",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
            )

            embed = create_themed_embed(
                title="Amount Changed",
                description=f"The exchange amount has been changed to **${self.new_amount:,.2f}**.",
                color=PURPLE_GRADIENT
            )

            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

            # Refresh the dashboard embed with updated values
            await self.refresh_dashboard(interaction.channel)

        except Exception as e:
            logger.error(f"Error changing amount: {e}", exc_info=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="❌")
    async def deny_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Deny amount change - only OTHER party can deny"""
        # Prevent requester from denying their own request
        if interaction.user.id == self.requester_id:
            await interaction.response.send_message(
                "You cannot deny your own request. Cancel it by clicking the button again.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        embed = create_themed_embed(
            title="Amount Change Denied",
            description=f"{interaction.user.mention} has denied the amount change request.",
            color=ERROR_RED
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)


class FeeChangeConfirmView(discord.ui.View):
    """Confirmation view for fee change"""

    def __init__(self, ticket_id: str, new_fee_percentage: float, api: APIClient, requester_id: int):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.new_fee_percentage = new_fee_percentage
        self.api = api
        self.requester_id = requester_id
        # Requester automatically agrees by initiating the action
        self.confirmed_users = {requester_id}

    async def refresh_dashboard(self, channel: discord.TextChannel):
        """Refresh the dashboard embed with updated ticket data"""
        try:
            # Fetch updated ticket data via API
            ticket_result = await self.api.get_ticket(self.ticket_id)

            # Get exchanger member
            exchanger_id = int(ticket_result.get("exchanger_discord_id", 0))
            exchanger = channel.guild.get_member(exchanger_id) if exchanger_id else None

            # Find and update the dashboard message
            async for message in channel.history(limit=50):
                if message.embeds and message.author.bot:
                    embed = message.embeds[0]
                    if "Exchange Dashboard" in (embed.title or "") or "Step by Step Guide" in (embed.description or ""):
                        # Recreate the dashboard embed with updated data
                        new_embed = create_dashboard_embed(ticket_result, exchanger)
                        await message.edit(embed=new_embed)
                        logger.info(f"Refreshed dashboard embed for ticket #{self.ticket_id}")
                        break
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}", exc_info=True)

    @discord.ui.button(label="Agree", style=discord.ButtonStyle.primary, emoji="✅")
    async def agree_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Agree to fee change - only OTHER party can click"""
        try:
            # Prevent requester from clicking Agree
            if interaction.user.id == self.requester_id:
                await interaction.response.send_message(
                    "You already initiated this request. Waiting for the other party to agree.",
                    ephemeral=True
                )
                return

            await interaction.response.defer()

            # Other party agreed - execute immediately
            result = await self.api.post(
                f"/api/v1/tickets/{self.ticket_id}/approve-fee-change",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
            )

            embed = create_themed_embed(
                title="Fee Changed",
                description=f"The service fee has been changed to **{self.new_fee_percentage}%**.",
                color=PURPLE_GRADIENT
            )

            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

            # Refresh the dashboard embed with updated values
            await self.refresh_dashboard(interaction.channel)

        except Exception as e:
            logger.error(f"Error changing fee: {e}", exc_info=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="❌")
    async def deny_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Deny fee change - only OTHER party can deny"""
        # Prevent requester from denying their own request
        if interaction.user.id == self.requester_id:
            await interaction.response.send_message(
                "You cannot deny your own request. Cancel it by clicking the button again.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        embed = create_themed_embed(
            title="Fee Change Denied",
            description=f"{interaction.user.mention} has denied the fee change request.",
            color=ERROR_RED
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)


class CloseConfirmView(discord.ui.View):
    """Confirmation view for close request"""

    def __init__(self, ticket_id: str, ticket_number: int, api: APIClient, requester_id: int):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.api = api
        self.requester_id = requester_id
        # Requester automatically agrees by initiating the action
        self.confirmed_users = {requester_id}

    @discord.ui.button(label="Agree to Close", style=discord.ButtonStyle.danger, emoji="✅")
    async def agree_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Agree to close ticket - only OTHER party can click"""
        try:
            # Prevent requester from clicking Agree
            if interaction.user.id == self.requester_id:
                await interaction.response.send_message(
                    "You already initiated this request. Waiting for the other party to agree.",
                    ephemeral=True
                )
                return

            await interaction.response.defer()

            # Other party agreed - execute immediately
            result = await self.api.post(
                f"/api/v1/tickets/{self.ticket_id}/approve-close",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=[role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
            )

            ticket_data = result.get("ticket", {})

            embed = create_themed_embed(
                title="Exchange Completed",
                description=f"Ticket **#{self.ticket_number}** has been completed successfully!\n\n**Transcripts generated** - Check your DMs for the exchange transcript and vouch template.\n\n**Server fee collected** from exchanger.\n\nThis channel will be deleted in 15 seconds.",
                color=PURPLE_GRADIENT
            )

            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

            # TODO: Bot should listen for completed tickets and DM transcripts + vouch templates

            # Delete channel after 15 seconds
            import asyncio
            await asyncio.sleep(15)
            await interaction.channel.delete(reason="Ticket closed by mutual agreement")

        except Exception as e:
            logger.error(f"Error closing ticket: {e}", exc_info=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.success, emoji="❌")
    async def deny_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Deny close - only OTHER party can deny"""
        # Prevent requester from denying their own request
        if interaction.user.id == self.requester_id:
            await interaction.response.send_message(
                "You cannot deny your own request. Cancel it by clicking the button again.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        embed = create_themed_embed(
            title="Close Denied",
            description=f"{interaction.user.mention} has denied the close request. The ticket will remain open.",
            color=PURPLE_GRADIENT
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)
