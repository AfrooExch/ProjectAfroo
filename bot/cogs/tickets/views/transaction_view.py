"""
Transaction Panel View for V4
Main control panel during active exchanges with all action buttons
"""

import logging
from typing import Optional

import discord
from discord.ui import View, Button, Modal, InputText, Select

from api.errors import APIError
from utils.embeds import create_themed_embed, create_success_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS, ERROR
from config import config

logger = logging.getLogger(__name__)


class TransactionPanelView(View):
    """
    Main transaction panel with buttons:
    - I Sent My Funds (customer)
    - Change Amount (both)
    - Change Fee (staff)
    - Unclaim (both)
    - Close (staff)
    """

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

    @discord.ui.button(
        label="I Sent My Funds",
        style=discord.ButtonStyle.primary,
        emoji="💸",
        custom_id="i_sent_funds",
        row=0
    )
    async def i_sent_funds_button(self, button: Button, interaction: discord.Interaction):
        """Customer confirms they sent funds"""
        await interaction.response.defer(ephemeral=True)

        # Get ticket to verify customer or admin
        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket with authentication
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket = result.get("ticket") if isinstance(result, dict) else result

            # Get customer Discord ID (can be either discord_user_id or user_id string)
            customer_discord_id = ticket.get("discord_user_id") or str(ticket.get("user_id", ""))

            # Check if user is customer or admin
            is_customer = str(interaction.user.id) == str(customer_discord_id)
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False

            if not (is_customer or is_head_admin or is_assistant_admin):
                await interaction.followup.send(
                    "❌ Only the customer or admins can confirm sending funds.",
                    ephemeral=True
                )
                return

            # Log who pressed it
            if is_head_admin or is_assistant_admin:
                logger.info(f"Admin {interaction.user.name} ({interaction.user.id}) confirmed funds sent for ticket {self.ticket_id}")

            # Call API to mark client sent
            await self.bot.api_client.post(
                f"/api/v1/tickets/{self.ticket_id}/client-sent",
                data={},
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Get exchanger Discord ID
            exchanger_discord_id = ticket.get("exchanger_discord_id")

            # Post confirmation with proper mention handling
            if exchanger_discord_id:
                exchanger_mention = f"<@{exchanger_discord_id}>"
                description_text = (
                    f"## 💰 Customer Sent Funds\n\n"
                    f"{interaction.user.mention} has confirmed sending their funds.\n\n"
                    f"**Exchanger:** {exchanger_mention} should now verify the payment and process the payout."
                )
            else:
                # Ticket not claimed yet - shouldn't happen but handle gracefully
                description_text = (
                    f"## 💰 Customer Sent Funds\n\n"
                    f"{interaction.user.mention} has confirmed sending their funds.\n\n"
                    f"**Waiting for an exchanger to claim this ticket.**"
                )

            embed = create_themed_embed(
                title="",
                description=description_text,
                color=PURPLE_GRADIENT
            )

            mention = f"<@{exchanger_discord_id}>" if exchanger_discord_id else None

            await self.channel.send(content=mention, embed=embed)

            # Show payout options to exchanger
            await self.post_payout_panel(ticket, user_id, roles)

            await interaction.followup.send(
                "✅ You've confirmed sending funds. Waiting for exchanger to process payout.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error handling funds sent: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="Change Amount",
        style=discord.ButtonStyle.secondary,
        emoji="💰",
        custom_id="change_amount",
        row=0
    )
    async def change_amount_button(self, button: Button, interaction: discord.Interaction):
        """Change exchange amount"""
        # Show modal
        modal = ChangeAmountModal(self.bot, self.ticket_id, self.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Change Fee",
        style=discord.ButtonStyle.secondary,
        emoji="🏷️",
        custom_id="change_fee",
        row=0
    )
    async def change_fee_button(self, button: Button, interaction: discord.Interaction):
        """Change service fee (admins can force, others need approval)"""
        # Show modal (modal handles admin bypass logic)
        modal = ChangeFeeModal(self.bot, self.ticket_id, self.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Unclaim",
        style=discord.ButtonStyle.secondary,
        emoji="🔙",
        custom_id="unclaim_ticket",
        row=1
    )
    async def unclaim_button(self, button: Button, interaction: discord.Interaction):
        """Request to unclaim ticket"""
        # Show reason modal
        from cogs.tickets.views.claim_view import UnclaimReasonModal
        modal = UnclaimReasonModal(self.bot, self.ticket_id, self.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="close_ticket",
        row=1
    )
    async def close_button(self, button: Button, interaction: discord.Interaction):
        """Close ticket (admins can close, others can request to close)"""
        # Check if user is admin
        is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        is_admin = is_head_admin or is_assistant_admin

        if is_admin:
            # Admin can directly close
            modal = CloseTicketModal(self.bot, self.ticket_id, self.channel)
            await interaction.response.send_modal(modal)
        else:
            # Client/Exchanger can request to close
            modal = RequestCloseTicketModal(self.bot, self.ticket_id, self.channel)
            await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Currency Converter",
        style=discord.ButtonStyle.secondary,
        emoji="💱",
        custom_id="currency_converter",
        row=2
    )
    async def currency_converter_button(self, button: Button, interaction: discord.Interaction):
        """Show currency converter modal"""
        modal = CurrencyConverterModal(self.bot)
        await interaction.response.send_modal(modal)

    async def post_payout_panel(self, ticket: dict, user_id: str = None, roles: list = None):
        """Post payout options panel for exchanger"""
        try:
            # Get Discord IDs (not ObjectIDs)
            exchanger_discord_id = ticket.get("exchanger_discord_id")
            client_discord_id = ticket.get("discord_user_id") or str(ticket.get("user_id", ""))
            receive_method = ticket.get("receive_method", "")
            receive_crypto = ticket.get("receive_crypto", "")

            # Check if customer is receiving crypto
            is_crypto_payout = receive_method == "crypto" or receive_crypto

            if not is_crypto_payout:
                # FIAT PAYOUT - Two-step confirmation: exchanger confirms receipt, then sends payment, then client confirms
                from cogs.tickets.views.fiat_payout_view import FiatExchangerConfirmationView

                # Build description with proper mentions
                if exchanger_discord_id:
                    exchanger_text = f"<@{exchanger_discord_id}>"
                else:
                    exchanger_text = "The exchanger"

                embed = create_themed_embed(
                    title="",
                    description=(
                        f"## ⏳ Waiting for Exchanger Confirmation\n\n"
                        f"**Exchanger:** {exchanger_text}\n\n"
                        f"**Step 1:** Confirm you received the customer's **{ticket.get('send_method', 'fiat')}** payment.\n\n"
                        f"Once confirmed, you'll be prompted to send the payout to the customer."
                    ),
                    color=PURPLE_GRADIENT
                )

                # Show exchanger confirmation view
                view = FiatExchangerConfirmationView(
                    bot=self.bot,
                    ticket_id=self.ticket_id,
                    channel=self.channel,
                    ticket_data=ticket
                )

                await self.channel.send(content=exchanger_text if exchanger_discord_id else None, embed=embed, view=view)
                return

            # CRYPTO PAYOUT - Show wallet options
            # Import payout view
            from cogs.tickets.views.payout_view import PayoutMethodView

            # Create payout embed with proper mention
            if exchanger_discord_id:
                mention_text = f"<@{exchanger_discord_id}> Choose how you want to send crypto to the customer:"
            else:
                mention_text = "**Exchanger:** Choose how you want to send crypto to the customer:"

            embed = create_themed_embed(
                title="",
                description=(
                    f"## Select Payout Method\n\n"
                    f"{mention_text}\n\n"
                    f"**Internal Wallet:**\n"
                    f"> Use your locked deposit funds\n"
                    f"> Automatic blockchain transaction\n"
                    f"> Funds released immediately\n\n"
                    f"**External Wallet:**\n"
                    f"> Use your own wallet\n"
                    f"> Paste transaction hash for verification\n"
                    f"> Keeps your deposit balance"
                ),
                color=PURPLE_GRADIENT
            )

            # Create payout view
            view = PayoutMethodView(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=self.channel
            )

            await self.channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error posting payout panel: {e}")


class ChangeAmountModal(Modal):
    """Modal for changing exchange amount"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(title="Change Amount")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

        self.new_amount_input = InputText(
            label="New Amount (USD)",
            placeholder="Enter new amount in USD (e.g., 75.00)",
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.new_amount_input)

        self.reason_input = InputText(
            label="Reason for change",
            placeholder="Explain why the amount is being changed...",
            required=True,
            max_length=200,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.reason_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle amount change"""
        await interaction.response.defer(ephemeral=True)

        # Parse new amount
        try:
            new_amount = float(self.new_amount_input.value.replace("$", "").replace(",", "").strip())
        except ValueError:
            await interaction.followup.send(
                "❌ Invalid amount format.",
                ephemeral=True
            )
            return

        # Validate amount
        if new_amount < 4.00:
            await interaction.followup.send(
                "❌ Minimum exchange amount is **$4.00 USD**.",
                ephemeral=True
            )
            return

        if new_amount > 100000.00:
            await interaction.followup.send(
                "❌ Maximum exchange amount is **$100,000 USD**.",
                ephemeral=True
            )
            return

        reason = self.reason_input.value.strip()

        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get current ticket
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket = result.get("ticket") if isinstance(result, dict) else result
            old_amount = ticket.get("amount_usd", 0)

            # Check if user is admin
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_admin = is_head_admin or is_assistant_admin

            # Calculate new fees for display
            is_crypto = ticket.get("send_method") == "crypto" or ticket.get("send_crypto")
            is_receive_crypto = ticket.get("receive_method") == "crypto" or ticket.get("receive_crypto")

            if is_crypto and is_receive_crypto:
                fee_percent = 5.0
                new_fee = new_amount * 0.05
            elif new_amount >= 40.0:
                fee_percent = 10.0
                new_fee = new_amount * 0.10
            else:
                fee_percent = (4.0 / new_amount) * 100
                new_fee = 4.0

            new_receiving = new_amount - new_fee

            if is_admin:
                # Admin bypass - force change without approval
                logger.info(f"Admin {interaction.user.name} force-changing amount for ticket {self.ticket_id}")

                await self.bot.api_client.post(
                    f"/api/v1/admin/tickets/admin/{self.ticket_id}/force-change-amount",
                    data={
                        "new_amount": new_amount,
                        "reason": reason
                    },
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Post update message
                embed = create_success_embed(
                    title="✅ Amount Changed (Admin)",
                    description=(
                        f"**Changed by:** {interaction.user.mention} (Admin)\n"
                        f"**Reason:** {reason}\n\n"
                        f"**Old Amount:** `${old_amount:,.2f}`\n"
                        f"**New Amount:** `${new_amount:,.2f}`\n"
                        f"**New Fee:** `${new_fee:.2f} ({fee_percent:.0f}%)`\n"
                        f"**Customer Receives:** `${new_receiving:.2f}`\n\n"
                        f"*Admin bypass: No approval required*"
                    )
                )

                await self.channel.send(embed=embed)

                await interaction.followup.send(
                    "✅ Amount changed (admin bypass)",
                    ephemeral=True
                )

            else:
                # Regular flow - requires approval from other party
                await self.bot.api_client.post(
                    f"/api/v1/tickets/{self.ticket_id}/request-amount-change",
                    data={
                        "new_amount": new_amount,
                        "reason": reason
                    },
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Post approval request message
                embed = create_themed_embed(
                    title="",
                    description=(
                        f"## 💰 Amount Change Requested\n\n"
                        f"**Requested by:** {interaction.user.mention}\n"
                        f"**Reason:** {reason}\n\n"
                        f"**Current Amount:** `${old_amount:,.2f}`\n"
                        f"**Proposed Amount:** `${new_amount:,.2f}`\n"
                        f"**New Fee:** `${new_fee:.2f} ({fee_percent:.0f}%)`\n"
                        f"**New Customer Receives:** `${new_receiving:.2f}`\n\n"
                        f"⚠️ **Both parties must approve this change.**"
                    ),
                    color=PURPLE_GRADIENT
                )

                # Add approval button
                from cogs.tickets.views.approval_views import AmountChangeApprovalView
                view = AmountChangeApprovalView(
                    bot=self.bot,
                    ticket_id=self.ticket_id,
                    channel=self.channel
                )

                await self.channel.send(embed=embed, view=view)

                await interaction.followup.send(
                    "✅ Amount change requested. Waiting for approval from other party.",
                    ephemeral=True
                )

            logger.info(f"Amount change for ticket #{self.ticket_id}: ${old_amount} -> ${new_amount}")

        except Exception as e:
            logger.error(f"Error changing amount: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error changing amount: {str(e)}",
                ephemeral=True
            )


class ChangeFeeModal(Modal):
    """Modal for changing service fee (staff only)"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(title="Change Fee")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

        self.new_fee_input = InputText(
            label="New Fee Percentage",
            placeholder="Enter new fee percentage (e.g., 5 for 5%)",
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.new_fee_input)

        self.reason_input = InputText(
            label="Reason for change",
            placeholder="Explain why the fee is being changed...",
            required=True,
            max_length=200,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.reason_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle fee change"""
        await interaction.response.defer(ephemeral=True)

        # Parse new fee
        try:
            new_fee_percent = float(self.new_fee_input.value.replace("%", "").strip())
        except ValueError:
            await interaction.followup.send(
                "❌ Invalid fee format.",
                ephemeral=True
            )
            return

        # Validate fee
        if new_fee_percent < 0 or new_fee_percent > 50:
            await interaction.followup.send(
                "❌ Fee must be between 0% and 50%.",
                ephemeral=True
            )
            return

        reason = self.reason_input.value.strip()

        try:
            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get current ticket
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket = result.get("ticket") if isinstance(result, dict) else result
            amount_usd = ticket.get("amount_usd", 0)
            old_fee = ticket.get("fee_amount", 0)
            old_fee_percent = ticket.get("fee_percentage", 0)

            # Check if user is admin
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_admin = is_head_admin or is_assistant_admin

            # Calculate new fee
            new_fee = amount_usd * (new_fee_percent / 100)
            new_receiving = amount_usd - new_fee

            if is_admin:
                # Admin bypass - force change without approval
                logger.info(f"Admin {interaction.user.name} force-changing fee for ticket {self.ticket_id}")

                await self.bot.api_client.post(
                    f"/api/v1/admin/tickets/admin/{self.ticket_id}/force-change-fee",
                    data={
                        "new_fee_percentage": new_fee_percent,
                        "reason": reason
                    },
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Post update message
                embed = create_success_embed(
                    title="✅ Fee Changed (Admin)",
                    description=(
                        f"**Changed by:** {interaction.user.mention} (Admin)\n"
                        f"**Reason:** {reason}\n\n"
                        f"**Old Fee:** `${old_fee:.2f} ({old_fee_percent:.0f}%)`\n"
                        f"**New Fee:** `${new_fee:.2f} ({new_fee_percent:.0f}%)`\n"
                        f"**Customer Receives:** `${new_receiving:.2f}`\n\n"
                        f"*Admin bypass: No approval required*"
                    )
                )

                await self.channel.send(embed=embed)

                await interaction.followup.send(
                    "✅ Fee changed (admin bypass)",
                    ephemeral=True
                )

            else:
                # Regular flow - requires approval from other party
                await self.bot.api_client.post(
                    f"/api/v1/tickets/{self.ticket_id}/request-fee-change",
                    data={
                        "new_fee_percentage": new_fee_percent,
                        "reason": reason
                    },
                    discord_user_id=user_id,
                    discord_roles=roles
                )

                # Post approval request message
                embed = create_themed_embed(
                    title="",
                    description=(
                        f"## 🏷️ Fee Change Requested\n\n"
                        f"**Requested by:** {interaction.user.mention}\n"
                        f"**Reason:** {reason}\n\n"
                        f"**Current Fee:** `${old_fee:.2f} ({old_fee_percent:.0f}%)`\n"
                        f"**Proposed Fee:** `${new_fee:.2f} ({new_fee_percent:.0f}%)`\n"
                        f"**New Customer Receives:** `${new_receiving:.2f}`\n\n"
                        f"⚠️ **Both parties must approve this change.**"
                    ),
                    color=PURPLE_GRADIENT
                )

                # Add approval button
                from cogs.tickets.views.approval_views import FeeChangeApprovalView
                view = FeeChangeApprovalView(
                    bot=self.bot,
                    ticket_id=self.ticket_id,
                    channel=self.channel
                )

                await self.channel.send(embed=embed, view=view)

                await interaction.followup.send(
                    "✅ Fee change requested. Waiting for approval from other party.",
                    ephemeral=True
                )

            logger.info(f"Fee change for ticket #{self.ticket_id}: {old_fee_percent}% -> {new_fee_percent}%")

        except Exception as e:
            logger.error(f"Error changing fee: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error changing fee: {str(e)}",
                ephemeral=True
            )


class CloseTicketModal(Modal):
    """Modal for closing ticket (staff only)"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(title="Close Ticket")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

        self.reason_input = InputText(
            label="Close Reason",
            placeholder="Enter reason for closing this ticket...",
            required=True,
            max_length=500,
            style=discord.InputTextStyle.paragraph
        )
        self.add_item(self.reason_input)

    async def generate_and_send_transcripts(self, interaction: discord.Interaction, ticket: dict, reason: str):
        """Generate transcript and send to both parties and transcript channel"""
        try:
            from datetime import datetime
            import aiohttp

            # Get ticket details
            ticket_number = ticket.get("ticket_number", "Unknown")
            client_discord_id = ticket.get("discord_user_id")
            exchanger_discord_id = ticket.get("exchanger_discord_id")
            guild = interaction.guild

            # Generate HTML transcript using chat_exporter
            try:
                import chat_exporter

                messages = []
                async for message in self.channel.history(limit=500, oldest_first=True):
                    messages.append(message)

                transcript_html = await chat_exporter.export(self.channel)

                if transcript_html:
                    logger.info(f"Generated transcript for ticket #{ticket_number}")

                    # Upload to backend
                    from config import config
                    api_base = config.API_BASE_URL
                    upload_url = f"{api_base}/api/v1/transcripts/upload"

                    upload_data = {
                        "ticket_id": str(self.ticket_id),
                        "ticket_type": "ticket",  # Valid types: ticket, swap, automm, application, support
                        "ticket_number": ticket_number,
                        "user_id": str(client_discord_id) if client_discord_id else "unknown",
                        "participants": [str(client_discord_id), str(exchanger_discord_id)] if client_discord_id and exchanger_discord_id else [],
                        "html_content": transcript_html,
                        "message_count": len(messages)
                    }

                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            upload_url,
                            json=upload_data,
                            headers={
                                'X-Bot-Token': config.BOT_SERVICE_TOKEN,
                                'Content-Type': 'application/json'
                            }
                        ) as response:
                            if response.status in [200, 201]:
                                result = await response.json()
                                transcript_url = result.get("public_url")
                                logger.info(f"Uploaded transcript: {transcript_url}")

                                # DM Client
                                if client_discord_id:
                                    try:
                                        client_user = await self.bot.fetch_user(int(client_discord_id))
                                        client_embed = create_themed_embed(
                                            title="📄 Ticket Closed - Transcript",
                                            description=(
                                                f"Your ticket **#{ticket_number}** has been closed by staff.\n\n"
                                                f"**Reason:** {reason}\n\n"
                                                f"**Transcript:** [View Transcript]({transcript_url})\n\n"
                                                f"Thank you for using our service."
                                            ),
                                            color=PURPLE_GRADIENT
                                        )
                                        await client_user.send(embed=client_embed)
                                        logger.info(f"Sent transcript to client {client_discord_id}")
                                    except Exception as e:
                                        logger.warning(f"Failed to DM client {client_discord_id}: {e}")

                                # DM Exchanger
                                if exchanger_discord_id:
                                    try:
                                        exchanger_user = await self.bot.fetch_user(int(exchanger_discord_id))
                                        exchanger_embed = create_themed_embed(
                                            title="📄 Ticket Closed - Transcript",
                                            description=(
                                                f"Ticket **#{ticket_number}** has been closed by staff.\n\n"
                                                f"**Reason:** {reason}\n\n"
                                                f"**Transcript:** [View Transcript]({transcript_url})\n\n"
                                                f"Thank you for your service."
                                            ),
                                            color=PURPLE_GRADIENT
                                        )
                                        await exchanger_user.send(embed=exchanger_embed)
                                        logger.info(f"Sent transcript to exchanger {exchanger_discord_id}")
                                    except Exception as e:
                                        logger.warning(f"Failed to DM exchanger {exchanger_discord_id}: {e}")

                                # Post to transcript channel
                                from config import config
                                transcript_channel_id = config.transcript_channel
                                if transcript_channel_id:
                                    transcript_channel = guild.get_channel(transcript_channel_id)
                                    if transcript_channel:
                                        public_embed = create_themed_embed(
                                            title="📄 Ticket Closed",
                                            description=(
                                                f"**Ticket:** #{ticket_number}\n"
                                                f"**Status:** Closed by Staff\n"
                                                f"**Reason:** {reason}\n"
                                                f"**Transcript:** [View Transcript]({transcript_url})\n"
                                                f"**Closed at:** <t:{int(datetime.utcnow().timestamp())}:F>"
                                            ),
                                            color=ERROR_RED
                                        )
                                        await transcript_channel.send(embed=public_embed)
                                        logger.info(f"Posted transcript to transcript channel")

                            else:
                                error_text = await response.text()
                                logger.error(f"Failed to upload transcript: {response.status} - {error_text}")

            except ImportError:
                logger.warning("chat_exporter not installed, skipping transcript")
            except Exception as e:
                logger.error(f"Error generating transcript: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in generate_and_send_transcripts: {e}", exc_info=True)

    async def callback(self, interaction: discord.Interaction):
        """Handle ticket close"""
        await interaction.response.defer(ephemeral=True)

        reason = self.reason_input.value.strip()

        try:
            # Get user context for authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket info first to find exchanger channel
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket = result.get("ticket") if isinstance(result, dict) and "ticket" in result else result
            exchanger_channel_id = ticket.get("exchanger_channel_id")

            # Close ticket via API (releases holds properly)
            await self.bot.api_client.post(
                f"/api/v1/tickets/{self.ticket_id}/close",
                data={"reason": reason},
                discord_user_id=user_id,
                discord_roles=roles
            )

            # Post close message
            embed = create_error_embed(
                title="Ticket Closed",
                description=(
                    f"**Closed by:** {interaction.user.mention}\n"
                    f"**Reason:** {reason}\n\n"
                    f"This ticket has been closed by staff.\n"
                    f"Any holds have been released (refunded).\n\n"
                    f"The channel will be deleted in 30 seconds."
                )
            )

            await self.channel.send(embed=embed)

            await interaction.followup.send(
                "✅ Ticket closed successfully! Holds released.",
                ephemeral=True
            )

            logger.info(f"Ticket #{self.ticket_id} closed by staff: {reason}")

            # Generate and send transcripts
            await self.generate_and_send_transcripts(interaction, ticket, reason)

            # Delete channel after delay
            import asyncio
            await asyncio.sleep(30)

            # Delete main client channel
            try:
                await self.channel.delete(reason=f"Ticket closed by staff: {reason}")
            except Exception as e:
                logger.error(f"Error deleting client channel: {e}")

            # Also delete exchanger channel if it exists
            if exchanger_channel_id:
                try:
                    guild = interaction.guild
                    exchanger_channel = guild.get_channel(int(exchanger_channel_id))
                    if exchanger_channel:
                        await exchanger_channel.delete(reason=f"Ticket closed by staff: {reason}")
                        logger.info(f"Deleted exchanger channel {exchanger_channel_id}")
                except Exception as e:
                    logger.error(f"Error deleting exchanger channel: {e}")

        except Exception as e:
            logger.error(f"Error closing ticket: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error closing ticket: {str(e)}",
                ephemeral=True
            )


class RequestCloseTicketModal(Modal):
    """Modal for requesting to close ticket (client/exchanger)"""

    def __init__(self, bot: discord.Bot, ticket_id: str, channel: discord.TextChannel):
        super().__init__(title="Request to Close Ticket")
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel

        self.reason_input = InputText(
            label="Reason for Close Request",
            placeholder="Explain why you want to close this ticket...",
            required=True,
            max_length=500,
            style=discord.InputTextStyle.paragraph
        )
        self.add_item(self.reason_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle close request"""
        await interaction.response.defer(ephemeral=True)

        reason = self.reason_input.value.strip()

        try:
            # Get user context
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Get ticket to determine requester role
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/{self.ticket_id}",
                discord_user_id=user_id,
                discord_roles=roles
            )
            ticket = result.get("ticket") if isinstance(result, dict) else result

            # Determine who is requesting
            customer_discord_id = ticket.get("discord_user_id") or str(ticket.get("user_id", ""))
            exchanger_discord_id = ticket.get("exchanger_discord_id")

            if str(interaction.user.id) == str(customer_discord_id):
                requester = "Customer"
            elif str(interaction.user.id) == str(exchanger_discord_id):
                requester = "Exchanger"
            else:
                requester = "User"

            # Post close request to channel
            embed = create_themed_embed(
                title="🔔 Close Ticket Request",
                description=(
                    f"**Requested by:** {interaction.user.mention} ({requester})\n"
                    f"**Reason:** {reason}\n\n"
                    f"**⚠️ Staff:** Please review this request and close the ticket if appropriate."
                ),
                color=0xFFA500  # Orange
            )

            # Mention admins
            admin_role = self.channel.guild.get_role(config.head_admin_role)
            mention = admin_role.mention if admin_role else "@Admin"

            await self.channel.send(content=mention, embed=embed)

            await interaction.followup.send(
                "✅ Close request sent! Staff has been notified.",
                ephemeral=True
            )

            logger.info(f"Ticket #{self.ticket_id}: Close requested by {interaction.user.name} ({requester})")

        except Exception as e:
            logger.error(f"Error requesting close: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


class CurrencyConverterModal(Modal):
    """Modal for currency converter"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="Currency Converter")
        self.bot = bot

        self.amount_input = InputText(
            label="Amount in USD",
            placeholder="100.00",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.amount_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            amount_usd = float(self.amount_input.value)

            if amount_usd <= 0:
                await interaction.followup.send("❌ Amount must be positive", ephemeral=True)
                return

            # Get user context for API authentication
            from utils.auth import get_user_context
            user_id, roles = get_user_context(interaction)

            # Call backend to get conversions
            result = await self.bot.api_client.get(
                f"/api/v1/tickets/exchange-rates?amount={amount_usd}",
                discord_user_id=user_id,
                discord_roles=roles
            )

            conversions = result.get("conversions", {})

            # Currency symbols/flags mapping
            currency_flags = {
                "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "CAD": "🇨🇦",
                "AUD": "🇦🇺", "CHF": "🇨🇭", "CNY": "🇨🇳", "INR": "🇮🇳",
                "MXN": "🇲🇽", "BRL": "🇧🇷"
            }
            currency_symbols = {
                "EUR": "€", "GBP": "£", "JPY": "¥", "CAD": "$",
                "AUD": "$", "CHF": "CHF", "CNY": "¥", "INR": "₹",
                "MXN": "$", "BRL": "R$"
            }

            # Build embed
            description = f"## 💱 ${amount_usd:.2f} USD\n\n"

            for code, data in conversions.items():
                flag = currency_flags.get(code, "")
                name = data.get("name", code)
                converted = data.get("amount", 0)
                symbol = currency_symbols.get(code, "")

                description += f"{flag} **{code}** ({name}): {symbol}{converted:,.2f}\n"

            embed = create_themed_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )
            embed.set_footer(text="Rates are approximate and may vary")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.followup.send("❌ Invalid amount", ephemeral=True)
        except Exception as e:
            logger.error(f"Currency conversion error: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
