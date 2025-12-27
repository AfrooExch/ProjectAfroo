"""
Admin Ticket Detail View
Shows ticket details and force action buttons based on ticket type
"""

import discord
from discord.ui import View, Button
import logging
from datetime import datetime
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED

logger = logging.getLogger(__name__)


class TicketDetailView(View):
    """Ticket detail view with type-specific force actions"""

    def __init__(self, bot, ticket_data: dict, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.ticket_data = ticket_data
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        # Add buttons based on ticket type
        self._add_action_buttons()

    def _add_action_buttons(self):
        """Add action buttons based on ticket type"""
        ticket_type = self.ticket_data.get("type", "")
        status = self.ticket_data.get("status", "")

        # Common actions for all types
        self.add_item(self.add_user_button)
        self.add_item(self.remove_user_button)

        # Type-specific actions
        if ticket_type == "exchange":
            self._add_exchange_actions(status)
        elif ticket_type == "swap":
            self._add_swap_actions(status)
        elif ticket_type == "automm":
            self._add_automm_actions(status)
        elif ticket_type == "support":
            self._add_support_actions(status)
        elif ticket_type == "application":
            self._add_application_actions(status)

        # Force close for all types (if not already closed)
        if status not in ["closed", "completed", "canceled"]:
            self.add_item(self.force_close_button)

    def _add_exchange_actions(self, status: str):
        """Add exchange-specific action buttons"""
        # Force Claim (if open)
        if status in ["open", "awaiting_tos"]:
            self.add_item(self.force_claim_button)

        # Force Unclaim (if claimed)
        if status in ["claimed", "client_sent", "payout_pending"]:
            self.add_item(self.force_unclaim_button)

        # Force Complete (if claimed or later)
        if status in ["claimed", "client_sent", "payout_pending"]:
            self.add_item(self.force_complete_button)

        # Repost
        self.add_item(self.repost_button)

    def _add_swap_actions(self, status: str):
        """Add swap-specific action buttons"""
        # Force Complete (if in progress)
        if status not in ["closed", "completed", "canceled"]:
            self.add_item(self.force_complete_button)

        # Repost
        self.add_item(self.repost_button)

    def _add_automm_actions(self, status: str):
        """Add AutoMM-specific action buttons"""
        # Force Complete (if in progress)
        if status not in ["closed", "completed", "canceled"]:
            self.add_item(self.force_complete_button)

        # Reveal Escrow Key (ephemeral)
        self.add_item(self.reveal_escrow_key_button)

        # Force Withdraw to Admin
        self.add_item(self.force_withdraw_admin_button)

        # Repost
        self.add_item(self.repost_button)

    def _add_support_actions(self, status: str):
        """Add support-specific action buttons"""
        # Support tickets only have force close and add/remove user
        pass

    def _add_application_actions(self, status: str):
        """Add application-specific action buttons"""
        # Accept Application
        if status == "open":
            self.add_item(self.accept_application_button)

        # Deny Application
        if status == "open":
            self.add_item(self.deny_application_button)

    def create_detail_embed(self) -> discord.Embed:
        """Create detailed ticket embed"""
        ticket_number = self.ticket_data.get("ticket_number", "N/A")
        ticket_type = self.ticket_data.get("type", "unknown")
        status = self.ticket_data.get("status", "unknown")

        # Type emoji
        type_emojis = {
            "exchange": "💱",
            "swap": "",
            "automm": "🤖",
            "support": "🎫",
            "application": "📝"
        }
        type_emoji = type_emojis.get(ticket_type, "📋")

        # Status emoji
        status_emojis = {
            "open": "🟢",
            "awaiting_tos": "⏳",
            "claimed": "🔵",
            "client_sent": "💸",
            "payout_pending": "⏰",
            "completed": "",
            "canceled": "",
            "closed": "🔒"
        }
        status_emoji = status_emojis.get(status, "⚪")

        description = f"## {type_emoji} Ticket #{ticket_number} Details\n\n"

        # Basic info
        description += f"**Type:** `{ticket_type.upper()}`\n"
        description += f"**Status:** {status_emoji} `{status.replace('_', ' ').title()}`\n\n"

        # User info
        discord_user_id = self.ticket_data.get("discord_user_id", self.ticket_data.get("user_id"))
        if discord_user_id:
            description += f"**Customer:** <@{discord_user_id}>\n"

        # Exchanger info (if claimed)
        exchanger_discord_id = self.ticket_data.get("exchanger_discord_id")
        if exchanger_discord_id:
            description += f"**Exchanger:** <@{exchanger_discord_id}>\n"

        # Channel link
        channel_id = self.ticket_data.get("channel_id")
        if channel_id:
            description += f"**Channel:** <#{channel_id}>\n"

        description += "\n"

        # Exchange-specific fields
        if ticket_type == "exchange":
            send_method = self.ticket_data.get("send_method", "N/A")
            receive_method = self.ticket_data.get("receive_method", "N/A")
            amount_usd = self.ticket_data.get("amount_usd", 0)
            fee_amount = self.ticket_data.get("fee_amount", 0)
            receiving_amount = self.ticket_data.get("receiving_amount", 0)

            description += "### Exchange Details\n\n"
            description += f"**Sending:** `{send_method}`\n"
            description += f"**Receiving:** `{receive_method}`\n"
            description += f"**Amount:** `${amount_usd:.2f}`\n"
            description += f"**Fee:** `${fee_amount:.2f}`\n"
            description += f"**Client Receives:** `${receiving_amount:.2f}`\n\n"

        # AutoMM-specific fields
        if ticket_type == "automm":
            amount_usd = self.ticket_data.get("amount_usd", 0)
            description += "### AutoMM Details\n\n"
            description += f"**Amount:** `${amount_usd:.2f}`\n\n"

        # Timestamps
        description += "### Timeline\n\n"

        created_at = self.ticket_data.get("created_at", "")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                timestamp = f"<t:{int(dt.timestamp())}:R>"
                description += f"**Created:** {timestamp}\n"
            except:
                pass

        claimed_at = self.ticket_data.get("claimed_at", "")
        if claimed_at:
            try:
                dt = datetime.fromisoformat(claimed_at.replace('Z', '+00:00'))
                timestamp = f"<t:{int(dt.timestamp())}:R>"
                description += f"**Claimed:** {timestamp}\n"
            except:
                pass

        closed_at = self.ticket_data.get("closed_at", "")
        if closed_at:
            try:
                dt = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                timestamp = f"<t:{int(dt.timestamp())}:R>"
                description += f"**Closed:** {timestamp}\n"
            except:
                pass

        embed = create_themed_embed(
            title="",
            description=description,
            color=PURPLE_GRADIENT
        )

        return embed

    # ============ COMMON ACTIONS ============

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕", row=0)
    async def add_user_button(self, button: Button, interaction: discord.Interaction):
        """Add user to ticket channel"""
        from cogs.admin.modals.ticket_modals import AddUserModal
        modal = AddUserModal(self.bot, self.ticket_data, self.user_id, self.roles, self.guild)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, emoji="➖", row=0)
    async def remove_user_button(self, button: Button, interaction: discord.Interaction):
        """Remove user from ticket channel"""
        from cogs.admin.modals.ticket_modals import RemoveUserModal
        modal = RemoveUserModal(self.bot, self.ticket_data, self.user_id, self.roles, self.guild)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Force Close", style=discord.ButtonStyle.danger, emoji="🔒", row=0)
    async def force_close_button(self, button: Button, interaction: discord.Interaction):
        """Force close ticket"""
        from cogs.admin.modals.ticket_modals import ForceCloseModal
        modal = ForceCloseModal(self.bot, self.ticket_data, self.user_id, self.roles, self.guild)
        await interaction.response.send_modal(modal)

    # ============ EXCHANGE ACTIONS ============

    @discord.ui.button(label="Force Claim", style=discord.ButtonStyle.primary, emoji="🔵", row=1)
    async def force_claim_button(self, button: Button, interaction: discord.Interaction):
        """Force claim ticket for an exchanger"""
        from cogs.admin.modals.ticket_modals import ForceClaimModal
        modal = ForceClaimModal(self.bot, self.ticket_data, self.user_id, self.roles, self.guild)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Force Unclaim", style=discord.ButtonStyle.secondary, emoji="🔓", row=1)
    async def force_unclaim_button(self, button: Button, interaction: discord.Interaction):
        """Force unclaim ticket and refund holds"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_id = self.ticket_data.get("_id")
            ticket_number = self.ticket_data.get("ticket_number")

            # Force unclaim via API
            result = await api.post(
                f"/api/v1/tickets/admin/{ticket_id}/force-unclaim",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"Ticket #{ticket_number} has been force unclaimed and reopened.\n\n"
                f"**Holds refunded (if any existed).**",
                ephemeral=True
            )

            # Notify in channel
            channel_id = self.ticket_data.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send("🔓 **Ticket Force Unclaimed by Admin**\n\nTicket reopened, holds refunded.")
                except Exception as e:
                    logger.warning(f"Could not send message to channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force unclaiming ticket: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Force Complete", style=discord.ButtonStyle.success, emoji="", row=1)
    async def force_complete_button(self, button: Button, interaction: discord.Interaction):
        """Force complete ticket"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_id = self.ticket_data.get("_id")
            ticket_number = self.ticket_data.get("ticket_number")

            # Force complete via API
            result = await api.post(
                f"/api/v1/admin/tickets/{ticket_id}/force-complete",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"Ticket #{ticket_number} has been force completed.\n\n"
                f"**Holds released and fees collected.**",
                ephemeral=True
            )

            # Notify in channel
            channel_id = self.ticket_data.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send("**Ticket Force Completed by Admin**\n\nHolds released, fees collected.")
                except Exception as e:
                    logger.warning(f"Could not send message to channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force completing ticket: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Repost", style=discord.ButtonStyle.secondary, emoji="🔁", row=1)
    async def repost_button(self, button: Button, interaction: discord.Interaction):
        """Repost ticket embed based on current state"""
        await interaction.response.defer(ephemeral=True)

        # This would need to recreate the appropriate embed based on ticket state
        # For now, just acknowledge
        await interaction.followup.send(
            "Repost feature needs custom embed logic per ticket type/state.\n\n"
            "This will be implemented to repost the correct embed based on ticket status.",
            ephemeral=True
        )

    # ============ AUTOMM ACTIONS ============

    @discord.ui.button(label="Reveal Escrow Key", style=discord.ButtonStyle.danger, emoji="🔑", row=2)
    async def reveal_escrow_key_button(self, button: Button, interaction: discord.Interaction):
        """Reveal escrow private key (ephemeral to admin only)"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get AutoMM escrow from ticket
            ticket_id = self.ticket_data.get("_id")

            # Query database for AutoMM escrow
            from app.core.database import get_database
            from app.core.security import get_decrypted_private_key
            from bson import ObjectId

            db = await get_database()
            automm_escrows = db["automm_escrows"]

            # Find escrow by ticket_id or channel_id
            channel_id = self.ticket_data.get("channel_id")
            escrow = await automm_escrows.find_one({"channel_id": channel_id})

            if not escrow:
                await interaction.followup.send(
                    "No AutoMM escrow found for this ticket.",
                    ephemeral=True
                )
                return

            # Decrypt the private key
            encrypted_key = escrow.get("encrypted_key")
            if not encrypted_key:
                await interaction.followup.send(
                    "No encrypted key found in escrow.",
                    ephemeral=True
                )
                return

            private_key = get_decrypted_private_key(encrypted_key)
            address = escrow.get("address", "N/A")
            currency = escrow.get("crypto", "N/A")

            await interaction.followup.send(
                f"🔑 **AutoMM Escrow Key (ADMIN ONLY)**\n\n"
                f"**Currency:** {currency}\n"
                f"**Address:** `{address}`\n"
                f"**Private Key:** ||`{private_key}`||\n\n"
                f"**Keep this secure!**",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error revealing escrow key: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Force Withdraw to Admin", style=discord.ButtonStyle.danger, emoji="", row=2)
    async def force_withdraw_admin_button(self, button: Button, interaction: discord.Interaction):
        """Force withdraw AutoMM funds to admin wallet"""
        await interaction.response.defer(ephemeral=True)

        await interaction.followup.send(
            "Force Withdraw to Admin requires implementing the withdrawal logic.\n\n"
            "This will send escrow funds to configured admin wallet.",
            ephemeral=True
        )

    # ============ APPLICATION ACTIONS ============

    @discord.ui.button(label="Accept Application", style=discord.ButtonStyle.success, emoji="", row=3)
    async def accept_application_button(self, button: Button, interaction: discord.Interaction):
        """Accept exchanger application"""
        await interaction.response.defer(ephemeral=True)

        try:
            ticket_id = self.ticket_data.get("_id")
            ticket_number = self.ticket_data.get("ticket_number")
            user_discord_id = self.ticket_data.get("discord_user_id", self.ticket_data.get("user_id"))
            channel_id = self.ticket_data.get("channel_id")

            if not channel_id:
                await interaction.followup.send("No channel found for this application.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send(f"Channel not found.", ephemeral=True)
                return

            # Call the application approval handler
            from cogs.applications.handlers.application_handler import admin_approve_application
            from datetime import datetime

            await admin_approve_application(
                bot=self.bot,
                app_id=ticket_id,
                app_number=ticket_number,
                channel=channel,
                user_id=int(user_discord_id),
                approved_by=interaction.user,
                opened_at=datetime.fromisoformat(self.ticket_data.get("created_at").replace('Z', '+00:00')) if self.ticket_data.get("created_at") else datetime.utcnow()
            )

            await interaction.followup.send(
                f"Application #{ticket_number} approved!\n\n"
                f"User <@{user_discord_id}> is now an exchanger.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error accepting application: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Deny Application", style=discord.ButtonStyle.danger, emoji="", row=3)
    async def deny_application_button(self, button: Button, interaction: discord.Interaction):
        """Deny exchanger application"""
        # Show modal for denial reason
        from cogs.admin.modals.ticket_modals import DenyApplicationModal
        await interaction.response.send_modal(DenyApplicationModal(self.bot, self.ticket_data, self.user_id, self.roles, self.guild))
