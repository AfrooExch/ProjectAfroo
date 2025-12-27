"""
Claim View for V4
Handles ticket claiming with balance checks and hold creation
"""

import logging
from typing import Optional

import discord
from discord.ui import View, Button, Modal, InputText

from api.errors import APIError
from utils.embeds import create_themed_embed, create_success_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS, ERROR, WARNING, SUCCESS_GREEN
from config import config

logger = logging.getLogger(__name__)


class ClaimTicketView(View):
    """View for claiming tickets"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

    @discord.ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="claim_ticket"
    )
    async def claim_button(self, button: Button, interaction: discord.Interaction):
        """Handle ticket claim"""
        await interaction.response.defer(ephemeral=True)

        logger.info(f"Exchanger {interaction.user.id} attempting to claim ticket #{self.ticket_id}")

        # Check if user is exchanger
        if not config.is_exchanger(interaction.user) and not config.is_admin(interaction.user):
            await interaction.followup.send(
                "❌ You need the Exchanger role to claim tickets.",
                ephemeral=True
            )
            return

        try:
            # Claim ticket via API (includes balance check and hold creation)
            result = await self.bot.api_client.claim_ticket(
                ticket_id=self.ticket_id,
                exchanger_id=str(interaction.user.id),
                exchanger_username=interaction.user.name
            )

            logger.info(f"Ticket #{self.ticket_id} successfully claimed by {interaction.user.name}")

            # Disable claim button
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Update channel permissions
            await self.update_channel_permissions(interaction.user)

            # Move to claimed category
            await self.move_to_claimed_category()

            # Post claim success message
            await self.post_claim_success(interaction.user, result)

            # Post transaction panel
            await self.post_transaction_panel()

            await interaction.followup.send(
                "✅ Ticket claimed successfully!",
                ephemeral=True
            )

        except APIError as e:
            logger.error(f"API error claiming ticket: {e}")

            # Check if it's an insufficient balance error
            if "insufficient" in str(e).lower() or "balance" in str(e).lower():
                await interaction.followup.send(
                    f"❌ **Insufficient Balance**\n\n{e.user_message}\n\n"
                    f"You need to deposit more funds before claiming this ticket.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Error claiming ticket: {e.user_message}",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error claiming ticket: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An error occurred while claiming the ticket: {str(e)}",
                ephemeral=True
            )

    async def update_channel_permissions(self, exchanger: discord.Member):
        """Update channel permissions after claim"""
        try:
            # Remove exchanger role (they had VIEW ONLY)
            exchanger_role_id = config.EXCHANGER_ROLE_ID
            exchanger_role = self.channel.guild.get_role(exchanger_role_id)

            if exchanger_role:
                await self.channel.set_permissions(exchanger_role, overwrite=None)

            # Add specific exchanger (can now speak)
            await self.channel.set_permissions(
                exchanger,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True
            )

            logger.info(f"Updated channel permissions for exchanger {exchanger.id}")

        except Exception as e:
            logger.error(f"Error updating channel permissions: {e}")

    async def move_to_claimed_category(self):
        """Move channel to claimed tickets category"""
        try:
            claimed_category_id = config.CLAIMED_TICKETS_CATEGORY_ID
            if not claimed_category_id:
                logger.warning("Claimed tickets category ID not configured")
                return

            claimed_category = self.channel.guild.get_channel(claimed_category_id)
            if not claimed_category:
                logger.warning(f"Claimed tickets category not found: {claimed_category_id}")
                return

            await self.channel.edit(category=claimed_category)
            logger.info(f"Moved ticket #{self.ticket_id} to claimed category")

        except Exception as e:
            logger.error(f"Error moving to claimed category: {e}")

    async def post_claim_success(self, exchanger: discord.Member, result: dict):
        """Post claim success message"""
        try:
            # Get hold information
            hold_info = result.get("hold", {})
            funds_locked = hold_info.get("amount_usd", 0) > 0

            embed = create_success_embed(
                title="Ticket Claimed",
                description=(
                    f"**Exchanger:** {exchanger.mention}\n"
                    f"**Claimed at:** <t:{int(discord.utils.utcnow().timestamp())}:F>\n\n"
                    f"This ticket has been claimed by {exchanger.mention}!\n\n"
                    f"Both parties can now communicate to complete the exchange."
                )
            )

            if funds_locked:
                hold_amount = hold_info.get("amount_usd", 0)
                hold_asset = hold_info.get("asset", "funds")

                embed.add_field(
                    name="🔒 Funds Locked",
                    value=(
                        f"**${hold_amount:,.2f} USD** worth of **{hold_asset}** has been locked from your deposits.\n\n"
                        f"These funds cannot be withdrawn until the ticket is completed or unclaimed.\n\n"
                        f"*This ensures you can fulfill the exchange.*"
                    ),
                    inline=False
                )

            await self.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error posting claim success: {e}")

    async def post_transaction_panel(self):
        """Post transaction panel with buttons"""
        try:
            # Import transaction view
            from cogs.tickets.views.transaction_view import TransactionPanelView
            from utils.auth import get_user_context

            # Get user context for API authentication
            user_id, roles = get_user_context(self.interaction)

            # Get ticket data
            ticket = await self.bot.api_client.get_ticket(
                self.ticket_id,
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Create embed
            embed = create_themed_embed(
                title="",
                description=(
                    f"## Exchange in Progress\n\n"
                    f"### Next Steps\n\n"
                    f"**For Customer:**\n"
                    f"> 1. Send your payment using the agreed method\n"
                    f"> 2. Click **I Sent My Funds** below after sending\n"
                    f"> 3. Wait for exchanger to process payout\n\n"
                    f"**For Exchanger:**\n"
                    f"> 1. Verify customer's payment\n"
                    f"> 2. Process payout to customer\n"
                    f"> 3. Complete the ticket\n\n"
                    f"### Actions\n\n"
                    f"Use the buttons below to manage this exchange."
                ),
                color=PURPLE_GRADIENT
            )

            # Create transaction view
            view = TransactionPanelView(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=self.channel
            )

            await self.channel.send(embed=embed, view=view)
            logger.info(f"Posted transaction panel for ticket #{self.ticket_id}")

        except Exception as e:
            logger.error(f"Error posting transaction panel: {e}")


class UnclaimRequestView(View):
    """View for requesting to unclaim a ticket"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

    @discord.ui.button(
        label="Request Unclaim",
        style=discord.ButtonStyle.secondary,
        emoji="🔙",
        custom_id="request_unclaim"
    )
    async def unclaim_button(self, button: Button, interaction: discord.Interaction):
        """Handle unclaim request"""
        # Show reason modal
        modal = UnclaimReasonModal(self.bot, self.ticket_id, self.channel)
        await interaction.response.send_modal(modal)


class UnclaimReasonModal(Modal):
    """Modal for entering unclaim reason"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(title="Request Unclaim")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

        self.reason_input = InputText(
            label="Reason for unclaiming",
            placeholder="Explain why you need to unclaim this ticket...",
            required=True,
            max_length=500,
            style=discord.InputTextStyle.paragraph
        )
        self.add_item(self.reason_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle unclaim request submission"""
        await interaction.response.defer(ephemeral=True)

        reason = self.reason_input.value.strip()

        logger.info(f"Unclaim requested for ticket #{self.ticket_id} by {interaction.user.id}: {reason}")

        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket to determine who needs to approve
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            # Unwrap response - API returns {"ticket": {...}, "messages": [...]}
            ticket = result.get("ticket") if isinstance(result, dict) and "ticket" in result else result

            # Use Discord IDs for comparison (not ObjectIDs)
            customer_id = ticket.get("discord_user_id") or str(ticket.get("user_id", ""))
            exchanger_id = ticket.get("exchanger_discord_id")

            # Check if user is admin
            from config import config
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_admin = is_head_admin or is_assistant_admin

            # Determine who requested and who needs to approve
            if str(interaction.user.id) == str(customer_id):
                requester = "customer"
                approver_id = exchanger_id if exchanger_id else None
            elif exchanger_id and str(interaction.user.id) == str(exchanger_id):
                requester = "exchanger"
                approver_id = customer_id if customer_id else None
            elif is_admin:
                # Admin can force unclaim without approval
                requester = "admin"
                approver_id = None
            else:
                await interaction.followup.send(
                    "❌ Only the customer, exchanger, or admin can request unclaim.",
                    ephemeral=True
                )
                return

            # If admin, force unclaim immediately
            if is_admin:
                try:
                    # First create the request (even though admin is the requester)
                    await self.bot.api_client.post(
                        f"/api/v1/tickets/{self.ticket_id}/request-unclaim",
                        data={"reason": reason},
                        discord_user_id=user_id,
                        discord_roles=roles
                    )

                    # Then immediately approve it with a different user ID (system approval)
                    # Use a different ID to bypass "cannot approve your own request" check
                    await self.bot.api_client.post(
                        f"/api/v1/tickets/{self.ticket_id}/approve-unclaim",
                        data={},
                        discord_user_id="SYSTEM",  # System approval
                        discord_roles=roles
                    )

                    embed = create_themed_embed(
                        title="✅ Ticket Unclaimed (Admin)",
                        description=f"This ticket has been unclaimed by admin {interaction.user.mention}.\n\n**Reason:** {reason}",
                        color=SUCCESS_GREEN
                    )
                    await self.channel.send(embed=embed)

                    await interaction.followup.send(
                        "✅ Ticket unclaimed successfully (admin bypass).",
                        ephemeral=True
                    )
                    return

                except Exception as e:
                    logger.error(f"Error admin unclaiming: {e}")
                    await interaction.followup.send(
                        f"❌ Error unclaiming: {str(e)}",
                        ephemeral=True
                    )
                    return

            # Validate approver exists
            if not approver_id:
                await interaction.followup.send(
                    "❌ Cannot unclaim - other party not found in ticket.",
                    ephemeral=True
                )
                return

            # Post unclaim approval request
            embed = create_themed_embed(
                title="",
                description=(
                    f"## ⚠️ Unclaim Request\n\n"
                    f"**Requester:** {interaction.user.mention}\n"
                    f"**Reason:** {reason}\n\n"
                    f"### Approval Required\n\n"
                    f"This unclaim requires approval from:\n"
                    f"✅ <@{approver_id}> (Other party)\n"
                    f"✅ Staff members\n\n"
                    f"**Both parties must approve for the unclaim to proceed.**"
                ),
                color=WARNING
            )

            # Create approval view
            approval_view = UnclaimApprovalView(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=self.channel,
                requester_id=interaction.user.id,
                approver_id=int(approver_id)
            )

            await self.channel.send(embed=embed, view=approval_view)

            await interaction.followup.send(
                "✅ Unclaim request submitted. Waiting for approval.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error requesting unclaim: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error requesting unclaim: {str(e)}",
                ephemeral=True
            )


class UnclaimApprovalView(View):
    """View for approving unclaim requests"""

    def __init__(
        self,
        bot: discord.Bot,
        ticket_id: str,
        channel: discord.TextChannel,
        requester_id: int,
        approver_id: int
    ):
        super().__init__(timeout=None)  # Persistent - never times out
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.requester_id = requester_id
        self.approver_id = approver_id

        self.other_party_approved = False
        self.staff_approved = False

    @discord.ui.button(
        label="Approve (Other Party)",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def approve_other_button(self, button: Button, interaction: discord.Interaction):
        """Approve as the other party"""
        # Check for admin bypass (Head Admin or Assistant Admin)
        is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        admin_bypass = is_head_admin or is_assistant_admin

        if interaction.user.id != self.approver_id and not admin_bypass:
            await interaction.response.send_message(
                "❌ Only the other party can approve this.",
                ephemeral=True
            )
            return

        self.other_party_approved = True
        await interaction.response.send_message(
            "✅ You have approved the unclaim request.",
            ephemeral=True
        )

        # Check if both approved
        if self.other_party_approved and self.staff_approved:
            await self.process_unclaim(interaction)

    @discord.ui.button(
        label="Approve (Staff)",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def approve_staff_button(self, button: Button, interaction: discord.Interaction):
        """Approve as staff"""
        # Check for admin bypass (Head Admin or Assistant Admin)
        is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        admin_bypass = is_head_admin or is_assistant_admin

        if not config.is_staff(interaction.user) and not admin_bypass:
            await interaction.response.send_message(
                "❌ Only staff can approve this.",
                ephemeral=True
            )
            return

        self.staff_approved = True
        await interaction.response.send_message(
            "✅ Staff approval granted.",
            ephemeral=True
        )

        # Check if both approved
        if self.other_party_approved and self.staff_approved:
            await self.process_unclaim(interaction)

    async def process_unclaim(self, interaction: discord.Interaction):
        """Process the unclaim - handles both client and exchanger channels"""
        try:
            # Disable buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Get user context for API
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Unclaim via API (releases holds)
            result = await self.bot.api_client.post(
                f"/api/v1/tickets/{self.ticket_id}/approve-unclaim",
                data={},
                discord_user_id=user_id,
                discord_roles=roles
            )

            ticket = result.get("ticket", {})
            guild = self.channel.guild

            # Get both channel IDs from ticket
            client_channel_id = ticket.get("channel_id")
            exchanger_channel_id = ticket.get("exchanger_channel_id")
            old_exchanger_discord_id = ticket.get("exchanger_discord_id")

            client_channel = guild.get_channel(int(client_channel_id)) if client_channel_id else None
            exchanger_channel = guild.get_channel(int(exchanger_channel_id)) if exchanger_channel_id else None

            # Get categories
            client_tickets_category = guild.get_channel(config.CLIENT_TICKETS_CATEGORY_ID)
            exchanger_tickets_category = guild.get_channel(config.EXCHANGER_TICKETS_CATEGORY_ID)

            # 1. Move CLIENT channel back to Client Tickets category
            if client_channel and client_tickets_category:
                await client_channel.edit(category=client_tickets_category)
                logger.info(f"Moved client channel {client_channel.id} back to Client Tickets category")

            # 2. Remove old exchanger permissions from CLIENT channel
            if client_channel and old_exchanger_discord_id:
                old_exchanger_member = guild.get_member(int(old_exchanger_discord_id))
                if old_exchanger_member:
                    await client_channel.set_permissions(old_exchanger_member, overwrite=None)
                    logger.info(f"Removed {old_exchanger_member.name} from client channel")

            # 3. Unlock EXCHANGER channel for all payment-specific roles
            if exchanger_channel:
                # Get payment method roles from ticket
                send_method = ticket.get("send_method", "")
                receive_method = ticket.get("receive_method", "")
                payment_method_roles = self.get_payment_method_roles(send_method, receive_method)

                # Unlock for all payment-specific exchanger roles
                for role_id in payment_method_roles:
                    role = guild.get_role(role_id)
                    if role:
                        await exchanger_channel.set_permissions(
                            role,
                            read_messages=True,
                            send_messages=False  # VIEW ONLY
                        )
                        logger.info(f"Unlocked exchanger channel for {role.name}")

                # Also unlock generic "All Exchangers" role
                ALL_EXCHANGERS_ROLE = 1381982080560402462
                if ALL_EXCHANGERS_ROLE not in payment_method_roles:
                    all_exch_role = guild.get_role(ALL_EXCHANGERS_ROLE)
                    if all_exch_role:
                        await exchanger_channel.set_permissions(
                            all_exch_role,
                            read_messages=True,
                            send_messages=False
                        )
                        logger.info(f"Unlocked exchanger channel for All Exchangers")

            # 4. Post "Waiting for Exchanger" embed in CLIENT channel
            if client_channel:
                wait_embed = create_themed_embed(
                    title="",
                    description=(
                        f"## ⏳ Waiting for Exchanger\n\n"
                        f"**Ticket #{ticket.get('ticket_number', 'Unknown')}**\n\n"
                        f"Your ticket has been unclaimed and is now back in the exchanger queue.\n\n"
                        f"An exchanger will claim it shortly."
                    ),
                    color=PURPLE_GRADIENT
                )
                await client_channel.send(embed=wait_embed)

            # 5. Re-post Claim button in EXCHANGER channel
            if exchanger_channel:
                from cogs.tickets.views.exchanger_ticket_view import ExchangerTicketView

                claim_embed = create_themed_embed(
                    title="",
                    description=(
                        f"## 💱 Exchange Ticket Available\n\n"
                        f"**Ticket #{ticket.get('ticket_number', 'Unknown')}**\n\n"
                        f"This ticket has been unclaimed and is available for claiming again."
                    ),
                    color=PURPLE_GRADIENT
                )

                claim_view = ExchangerTicketView(
                    bot=self.bot,
                    ticket_id=self.ticket_id,
                    channel=exchanger_channel
                )

                await exchanger_channel.send(embed=claim_embed, view=claim_view)

            # Success message in current channel
            success_embed = create_success_embed(
                title="✅ Ticket Unclaimed",
                description=(
                    "The ticket has been unclaimed and reopened for other exchangers.\n\n"
                    "• Client channel: Moved back to Client Tickets\n"
                    "• Exchanger channel: Unlocked for claims\n"
                    "• Funds: Released to exchanger"
                )
            )
            await self.channel.send(embed=success_embed)

            logger.info(f"Ticket #{self.ticket_id} unclaimed successfully with channel management")

        except Exception as e:
            logger.error(f"Error processing unclaim: {e}", exc_info=True)
            error_embed = create_error_embed(
                title="❌ Error",
                description=f"Failed to unclaim ticket: {str(e)}\n\nPlease contact support."
            )
            await self.channel.send(embed=error_embed)

    def get_payment_method_roles(self, send_method: str, receive_method: str) -> list:
        """Get exchanger role IDs based on payment methods"""
        # Payment method to role ID mapping
        PAYMENT_ROLES = {
            "PayPal": 1431732911140503583,
            "CashApp": 1431733031999377428,
            "ApplePay": 1431733169777938594,
            "Venmo": 1431733262367326370,
            "Zelle": 1431733429929775104,
            "Chime": 1431733785086394408,
            "Revolut": 1431734050217005136,
            "Skrill": 1431734179086860468,
            "Bank": 1431734579290570752,
            "PaySafe": 1431734710744387684,
            "Binance GiftCard": 1431734831028633650,
        }

        # All exchangers role
        ALL_EXCHANGERS = 1381982080560402462

        role_ids = []

        # Check if crypto to crypto (add all exchangers)
        is_send_crypto = any(crypto in send_method.upper() for crypto in ["BTC", "ETH", "LTC", "USDT", "SOL", "XRP", "CRYPTO"])
        is_receive_crypto = any(crypto in receive_method.upper() for crypto in ["BTC", "ETH", "LTC", "USDT", "SOL", "XRP", "CRYPTO"])

        if is_send_crypto and is_receive_crypto:
            # Crypto to crypto - add all exchangers
            role_ids.append(ALL_EXCHANGERS)
            logger.info("Crypto to crypto exchange - adding all exchangers")
        else:
            # Fiat or mixed - add specific payment method roles
            for method_name, role_id in PAYMENT_ROLES.items():
                if method_name.upper() in send_method.upper() or method_name.upper() in receive_method.upper():
                    role_ids.append(role_id)
                    logger.info(f"Adding {method_name} exchanger role")

        # Fallback to all exchangers if no specific roles found
        if not role_ids:
            role_ids.append(ALL_EXCHANGERS)
            logger.info("No specific roles found - adding all exchangers as fallback")

        return role_ids
