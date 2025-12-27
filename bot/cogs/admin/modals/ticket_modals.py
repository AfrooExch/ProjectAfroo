"""
Admin Ticket Modals
Input modals for ticket management actions
"""

import discord
from discord.ui import InputText, Modal
import logging

logger = logging.getLogger(__name__)


class TicketNumberModal(Modal):
    """Modal to enter ticket ID (MongoDB _id) to view details"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title="View Ticket Details")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.ticket_id = InputText(
            label="Ticket ID (from list)",
            placeholder="Enter ticket ID (e.g., 6913feec2e1167e3c06ad3bc)",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client

            ticket_id = self.ticket_id.value.strip()

            # Fetch ticket by ID from the list
            # Search through the existing tickets list instead of API call
            # Find ticket in cache by ID
            ticket_data = None
            if hasattr(interaction.client, '_ticket_cache'):
                tickets = interaction.client._ticket_cache
                for t in tickets:
                    if t.get('id') == ticket_id or str(t.get('_id')) == ticket_id:
                        ticket_data = t
                        break

            if not ticket_data:
                await interaction.followup.send(
                    f"Ticket not found. Please copy the ticket ID from the list.",
                    ephemeral=True
                )
                return

            # Show ticket detail view
            from cogs.admin.views.ticket_detail_view import TicketDetailView
            view = TicketDetailView(self.bot, ticket_data, self.user_id, self.roles, self.guild)
            embed = view.create_detail_embed()

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error fetching ticket: {e}", exc_info=True)
            await interaction.followup.send(f"Error loading ticket: {str(e)}", ephemeral=True)


class ForceCloseModal(Modal):
    """Modal to force close a ticket"""

    def __init__(self, bot, ticket_data: dict, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title=f"Force Close Ticket #{ticket_data.get('ticket_number')}")
        self.bot = bot
        self.ticket_data = ticket_data
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.reason = InputText(
            label="Reason for Force Close",
            placeholder="Enter reason (required for audit log)",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_id = self.ticket_data.get("_id")
            ticket_number = self.ticket_data.get("ticket_number")
            reason = self.reason.value

            # Force close via API
            result = await api.post(
                f"/api/v1/admin/tickets/{ticket_id}/force-close",
                data={"reason": reason},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"Ticket #{ticket_number} has been force closed.\n\n**Reason:** {reason}",
                ephemeral=True
            )

            # Close Discord channel if exists
            channel_id = self.ticket_data.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send(f"🔒 **Ticket Force Closed by Admin**\n\nReason: {reason}")
                        await channel.edit(archived=True)
                except Exception as e:
                    logger.warning(f"Could not archive channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force closing ticket: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class AddUserModal(Modal):
    """Modal to add user to ticket channel"""

    def __init__(self, bot, ticket_data: dict, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title=f"Add User to Ticket #{ticket_data.get('ticket_number')}")
        self.bot = bot
        self.ticket_data = ticket_data
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.user_id_input = InputText(
            label="User Discord ID",
            placeholder="Enter Discord user ID (e.g., 123456789)",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.user_id_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            channel_id = self.ticket_data.get("channel_id")
            if not channel_id:
                await interaction.followup.send("Ticket has no Discord channel.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send(f"Channel <#{channel_id}> not found.", ephemeral=True)
                return

            # Get user
            target_user_id = int(self.user_id_input.value.strip())
            target_user = self.guild.get_member(target_user_id)

            if not target_user:
                await interaction.followup.send(f"User with ID {target_user_id} not found in server.", ephemeral=True)
                return

            # Add permissions: View, Speak, Read history
            await channel.set_permissions(
                target_user,
                read_messages=True,
                send_messages=True,
                read_message_history=True
            )

            await interaction.followup.send(
                f"Added {target_user.mention} to <#{channel_id}>",
                ephemeral=True
            )

            # Notify in channel
            await channel.send(f"➕ **Admin added {target_user.mention} to this ticket**")

        except ValueError:
            await interaction.followup.send("Invalid user ID format.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error adding user to ticket: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class RemoveUserModal(Modal):
    """Modal to remove user from ticket channel"""

    def __init__(self, bot, ticket_data: dict, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title=f"Remove User from Ticket #{ticket_data.get('ticket_number')}")
        self.bot = bot
        self.ticket_data = ticket_data
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.user_id_input = InputText(
            label="User Discord ID",
            placeholder="Enter Discord user ID (e.g., 123456789)",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.user_id_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            channel_id = self.ticket_data.get("channel_id")
            if not channel_id:
                await interaction.followup.send("Ticket has no Discord channel.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send(f"Channel <#{channel_id}> not found.", ephemeral=True)
                return

            # Get user
            target_user_id = int(self.user_id_input.value.strip())
            target_user = self.guild.get_member(target_user_id)

            if not target_user:
                await interaction.followup.send(f"User with ID {target_user_id} not found in server.", ephemeral=True)
                return

            # Remove permissions
            await channel.set_permissions(
                target_user,
                read_messages=False,
                send_messages=False,
                read_message_history=False
            )

            await interaction.followup.send(
                f"Removed {target_user.mention} from <#{channel_id}>",
                ephemeral=True
            )

            # Notify in channel
            await channel.send(f"➖ **Admin removed {target_user.mention} from this ticket**")

        except ValueError:
            await interaction.followup.send("Invalid user ID format.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing user from ticket: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class ForceClaimModal(Modal):
    """Modal to force claim ticket for an exchanger"""

    def __init__(self, bot, ticket_data: dict, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title=f"Force Claim Ticket #{ticket_data.get('ticket_number')}")
        self.bot = bot
        self.ticket_data = ticket_data
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.exchanger_id_input = InputText(
            label="Exchanger Discord ID",
            placeholder="Enter exchanger's Discord ID",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.exchanger_id_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_id = self.ticket_data.get("_id")
            ticket_number = self.ticket_data.get("ticket_number")
            exchanger_discord_id = self.exchanger_id_input.value.strip()

            # Force claim via API
            result = await api.post(
                f"/api/v1/tickets/admin/{ticket_id}/force-claim",
                data={"exchanger_discord_id": exchanger_discord_id},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"Ticket #{ticket_number} has been force claimed for <@{exchanger_discord_id}>.\n\n"
                f"**Holds bypassed - no deposit required.**",
                ephemeral=True
            )

            # Notify in channel
            channel_id = self.ticket_data.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send(
                            f"🔵 **Ticket Force Claimed by Admin**\n\n"
                            f"Exchanger: <@{exchanger_discord_id}>\n"
                            f"**Holds bypassed** - No deposit required"
                        )
                except Exception as e:
                    logger.warning(f"Could not send message to channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force claiming ticket: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class DenyApplicationModal(Modal):
    """Modal to deny exchanger application"""

    def __init__(self, bot, ticket_data: dict, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title=f"Deny Application #{ticket_data.get('ticket_number')}")
        self.bot = bot
        self.ticket_data = ticket_data
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.reason = InputText(
            label="Reason for Denial",
            placeholder="Enter reason (required for audit log)",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            ticket_id = self.ticket_data.get("_id")
            ticket_number = self.ticket_data.get("ticket_number")
            user_discord_id = self.ticket_data.get("discord_user_id", self.ticket_data.get("user_id"))
            channel_id = self.ticket_data.get("channel_id")
            reason = self.reason.value

            if not channel_id:
                await interaction.followup.send("No channel found for this application.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send(f"Channel not found.", ephemeral=True)
                return

            # Call the application denial handler
            from cogs.applications.handlers.application_handler import admin_deny_application
            from datetime import datetime

            await admin_deny_application(
                bot=self.bot,
                app_id=ticket_id,
                app_number=ticket_number,
                channel=channel,
                user_id=int(user_discord_id),
                denied_by=interaction.user,
                reason=reason,
                opened_at=datetime.fromisoformat(self.ticket_data.get("created_at").replace('Z', '+00:00')) if self.ticket_data.get("created_at") else datetime.utcnow()
            )

            await interaction.followup.send(
                f"Application #{ticket_number} denied.\n\n**Reason:** {reason}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error denying application: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
