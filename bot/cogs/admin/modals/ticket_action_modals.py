"""
Admin Ticket Action Modals
Simplified modals that accept ticket ID + required params
"""

import discord
from discord.ui import InputText, Modal
import logging

logger = logging.getLogger(__name__)


async def get_ticket_by_number_and_type(api, ticket_number: str, ticket_type: str, user_id: str, roles: list) -> dict:
    """Fetch ticket by ticket number and type to get MongoDB _id"""
    try:
        # Fetch tickets with filters
        tickets_data = await api.get(
            f"/api/v1/admin/tickets/all?ticket_type={ticket_type}&limit=100",
            discord_user_id=user_id,
            discord_roles=roles
        )

        tickets = tickets_data.get("tickets", [])

        # DEBUG: Log what we received
        logger.info(f"Searching for {ticket_type} ticket #{ticket_number}")
        logger.info(f"API returned {len(tickets)} tickets")
        if tickets:
            logger.info(f"Sample ticket structure: {tickets[0].keys() if tickets else 'none'}")
            logger.info(f"First 3 ticket numbers: {[t.get('ticket_number') for t in tickets[:3]]}")

        # Find ticket by number
        for ticket in tickets:
            if str(ticket.get("ticket_number")) == str(ticket_number):
                logger.info(f"Found ticket: {ticket.get('id')}")
                return ticket

        logger.warning(f"{ticket_type.title()} ticket #{ticket_number} not found in {len(tickets)} tickets")
        return None
    except Exception as e:
        logger.error(f"Error fetching ticket: {e}", exc_info=True)
        return None


class ForceClaimActionModal(Modal):
    """Modal to force claim with ticket ID"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild, ticket_type: str):
        super().__init__(title="Force Claim Ticket")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild
        self.ticket_type = ticket_type

        self.ticket_number = InputText(
            label="Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

        self.exchanger_id = InputText(
            label="Exchanger Discord ID",
            placeholder="Enter exchanger's Discord ID",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.exchanger_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()
            exchanger_id = self.exchanger_id.value.strip()

            # Fetch ticket by number and type
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, self.ticket_type, str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"{self.ticket_type.title()} ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            ticket_id = ticket.get("id")

            result = await api.post(
                f"/api/v1/tickets/admin/{ticket_id}/force-claim",
                data={"exchanger_discord_id": exchanger_id},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"{self.ticket_type.title()} ticket #{ticket_number} force claimed for <@{exchanger_id}>.\n\n**Holds bypassed.**",
                ephemeral=True
            )

            # Notify in ticket channel if it exists
            channel_id = ticket.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send(
                            f"🔵 **Ticket Force Claimed by Admin**\n\n"
                            f"**Exchanger:** <@{exchanger_id}>\n"
                            f"**Admin:** {interaction.user.mention}\n"
                            f"**Status:** Database updated to `claimed`\n"
                            f"**Holds bypassed** - No deposit required\n\n"
                            f"📌 **Note:** The exchanger can now use the dashboard to manage this ticket."
                        )
                except Exception as e:
                    logger.warning(f"Could not notify channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force claiming: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class ForceUnclaimActionModal(Modal):
    """Modal to force unclaim with ticket ID"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild, ticket_type: str):
        super().__init__(title="Force Unclaim Ticket")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild
        self.ticket_type = ticket_type

        self.ticket_number = InputText(
            label="Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()

            # Fetch ticket by number and type
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, self.ticket_type, str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"{self.ticket_type.title()} ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            ticket_id = ticket.get("id")

            result = await api.post(
                f"/api/v1/tickets/admin/{ticket_id}/force-unclaim",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"{self.ticket_type.title()} ticket #{ticket_number} force unclaimed and reopened.",
                ephemeral=True
            )

            # Notify in ticket channel if it exists
            channel_id = ticket.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send(
                            f"🔓 **Admin Force Unclaimed Ticket**\n\n"
                            f"By: {interaction.user.mention}\n"
                            f"Holds refunded, ticket reopened"
                        )
                except Exception as e:
                    logger.warning(f"Could not notify channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force unclaiming: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class ForceCompleteActionModal(Modal):
    """Modal to force complete with ticket ID"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild, ticket_type: str):
        super().__init__(title="Force Complete Ticket")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild
        self.ticket_type = ticket_type

        self.ticket_number = InputText(
            label="Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()

            # Fetch ticket by number and type
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, self.ticket_type, str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"{self.ticket_type.title()} ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            ticket_id = ticket.get("id")

            result = await api.post(
                f"/api/v1/tickets/admin/{ticket_id}/force-complete",
                data={},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"{self.ticket_type.title()} ticket #{ticket_number} force completed.\n\n**Holds released, fees collected.**",
                ephemeral=True
            )

            # Notify in ticket channel if it exists
            channel_id = ticket.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send(
                            f"**Admin Force Completed Ticket**\n\n"
                            f"By: {interaction.user.mention}\n"
                            f"Funds deducted, fees collected\n"
                            f"Exchange complete!"
                        )
                except Exception as e:
                    logger.warning(f"Could not notify channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force completing: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class ForceCloseActionModal(Modal):
    """Modal to force close with ticket ID"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild, ticket_type: str):
        super().__init__(title="Force Close Ticket")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild
        self.ticket_type = ticket_type

        self.ticket_number = InputText(
            label="Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

        self.reason = InputText(
            label="Reason for Force Close",
            placeholder="Enter reason (for audit log)",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()
            reason = self.reason.value

            # Fetch ticket by number and type
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, self.ticket_type, str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"{self.ticket_type.title()} ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            ticket_id = ticket.get("id")

            result = await api.post(
                f"/api/v1/tickets/admin/{ticket_id}/force-close",
                data={"reason": reason},
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            await interaction.followup.send(
                f"{self.ticket_type.title()} ticket #{ticket_number} force closed.\n\n**Reason:** {reason}",
                ephemeral=True
            )

            # Notify in ticket channel if it exists
            channel_id = ticket.get("channel_id")
            if channel_id:
                try:
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send(
                            f"🔒 **Admin Force Closed Ticket**\n\n"
                            f"By: {interaction.user.mention}\n"
                            f"**Reason:** {reason}\n"
                            f"All holds refunded"
                        )
                        # Archive the channel
                        if hasattr(channel, 'edit'):
                            try:
                                await channel.edit(archived=True)
                            except:
                                pass
                except Exception as e:
                    logger.warning(f"Could not notify channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error force closing: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class AddUserActionModal(Modal):
    """Modal to add user to ticket channel"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild, ticket_type: str):
        super().__init__(title="Add User to Ticket")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild
        self.ticket_type = ticket_type

        self.ticket_number = InputText(
            label="Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

        self.target_user_id = InputText(
            label="User Discord ID",
            placeholder="Enter Discord ID of user to add",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.target_user_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            # Get ticket to find channel
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()
            target_user_id = int(self.target_user_id.value.strip())

            # Fetch ticket by number and type
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, self.ticket_type, str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"{self.ticket_type.title()} ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            channel_id = ticket.get("channel_id")
            if not channel_id:
                await interaction.followup.send("Ticket has no Discord channel.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send(f"Channel not found.", ephemeral=True)
                return

            target_user = self.guild.get_member(target_user_id)
            if not target_user:
                await interaction.followup.send(f"User <@{target_user_id}> not found in server.", ephemeral=True)
                return

            # Add permissions
            await channel.set_permissions(
                target_user,
                read_messages=True,
                send_messages=True,
                read_message_history=True
            )

            await interaction.followup.send(
                f"Added {target_user.mention} to {self.ticket_type.title()} ticket #{ticket_number}.",
                ephemeral=True
            )

            await channel.send(f"➕ **Admin added {target_user.mention} to this ticket**")

        except ValueError:
            await interaction.followup.send("Invalid user ID format.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error adding user: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class RemoveUserActionModal(Modal):
    """Modal to remove user from ticket channel"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild, ticket_type: str):
        super().__init__(title="Remove User from Ticket")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild
        self.ticket_type = ticket_type

        self.ticket_number = InputText(
            label="Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

        self.target_user_id = InputText(
            label="User Discord ID",
            placeholder="Enter Discord ID of user to remove",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.target_user_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            # Get ticket to find channel
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()
            target_user_id = int(self.target_user_id.value.strip())

            # Fetch ticket by number and type
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, self.ticket_type, str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"{self.ticket_type.title()} ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            channel_id = ticket.get("channel_id")
            if not channel_id:
                await interaction.followup.send("Ticket has no Discord channel.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send(f"Channel not found.", ephemeral=True)
                return

            target_user = self.guild.get_member(target_user_id)
            if not target_user:
                await interaction.followup.send(f"User <@{target_user_id}> not found in server.", ephemeral=True)
                return

            # Remove permissions
            await channel.set_permissions(
                target_user,
                read_messages=False,
                send_messages=False,
                read_message_history=False
            )

            await interaction.followup.send(
                f"Removed {target_user.mention} from {self.ticket_type.title()} ticket #{ticket_number}.",
                ephemeral=True
            )

            await channel.send(f"➖ **Admin removed {target_user.mention} from this ticket**")

        except ValueError:
            await interaction.followup.send("Invalid user ID format.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing user: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class RevealEscrowKeyModal(Modal):
    """Modal to reveal AutoMM escrow key"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title="Reveal Escrow Key")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.ticket_number = InputText(
            label="AutoMM Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()

            # Fetch AutoMM ticket
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, "automm", str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"AutoMM ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            ticket_id = ticket.get("id")

            # Call backend to get escrow private key
            try:
                escrow_data = await api.get(
                    f"/api/v1/admin/automm/{ticket_id}/escrow-key",
                    discord_user_id=str(interaction.user.id),
                    discord_roles=self.roles
                )

                private_key = escrow_data.get("private_key")
                address = escrow_data.get("address")
                currency = escrow_data.get("currency")

                await interaction.followup.send(
                    f"🔑 **AutoMM Escrow Key (ADMIN ONLY)**\n\n"
                    f"**Ticket:** #{ticket_number}\n"
                    f"**Currency:** {currency}\n"
                    f"**Address:** `{address}`\n"
                    f"**Private Key:** ||`{private_key}`||\n\n"
                    f"**Keep this secure!**",
                    ephemeral=True
                )

            except Exception as e:
                # Endpoint doesn't exist yet
                await interaction.followup.send(
                    f"Reveal Escrow Key requires a backend endpoint.\n\n"
                    f"**Ticket:** AutoMM #{ticket_number}\n"
                    f"**Channel:** <#{ticket.get('channel_id')}>\n\n"
                    f"Contact developer to implement `/api/v1/admin/automm/{{ticket_id}}/escrow-key` endpoint.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error revealing escrow key: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class ForceWithdrawAdminModal(Modal):
    """Modal to force withdraw AutoMM to admin"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title="Force Withdraw to Admin")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.ticket_number = InputText(
            label="AutoMM Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()

            # Fetch AutoMM ticket
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, "automm", str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"AutoMM ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            await interaction.followup.send(
                f"Force Withdraw to Admin is not yet implemented.\n\n"
                f"**Ticket:** AutoMM #{ticket_number}\n"
                f"**Channel:** <#{ticket.get('channel_id')}>\n\n"
                f"This will withdraw AutoMM escrow funds to configured admin wallet.\n"
                f"Contact developer to implement `/api/v1/admin/automm/{{ticket_id}}/force-withdraw` endpoint.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in force withdraw: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class AcceptApplicationModal(Modal):
    """Modal to accept application"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title="Accept Application")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.ticket_number = InputText(
            label="Application Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            # Fetch ticket to get details
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()

            # Fetch application tickets
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, "application", str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"Application ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            ticket_id = ticket.get("id")
            user_discord_id = ticket.get("discord_user_id", ticket.get("user_id"))
            channel_id = ticket.get("channel_id")

            if not channel_id:
                await interaction.followup.send("No channel found for this application.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send("Channel not found.", ephemeral=True)
                return

            # Call approval handler
            from cogs.applications.handlers.application_handler import admin_approve_application
            from datetime import datetime

            await admin_approve_application(
                bot=self.bot,
                app_id=ticket_id,
                app_number=ticket.get("ticket_number", 0),
                channel=channel,
                user_id=int(user_discord_id),
                approved_by=interaction.user,
                opened_at=datetime.fromisoformat(ticket.get("created_at").replace('Z', '+00:00')) if ticket.get("created_at") else datetime.utcnow()
            )

            await interaction.followup.send(
                f"Application #{ticket_number} accepted!\n\nUser <@{user_discord_id}> is now an exchanger.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error accepting application: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class DenyApplicationActionModal(Modal):
    """Modal to deny application"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(title="Deny Application")
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

        self.ticket_number = InputText(
            label="Application Ticket Number",
            placeholder="e.g., 1, 2, 3",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_number)

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
            # Fetch ticket to get details
            api = self.bot.api_client
            ticket_number = self.ticket_number.value.strip()
            reason = self.reason.value

            # Fetch application ticket
            ticket = await get_ticket_by_number_and_type(
                api, ticket_number, "application", str(interaction.user.id), self.roles
            )

            if not ticket:
                await interaction.followup.send(
                    f"Application ticket #{ticket_number} not found.",
                    ephemeral=True
                )
                return

            ticket_id = ticket.get("id")
            user_discord_id = ticket.get("discord_user_id", ticket.get("user_id"))
            channel_id = ticket.get("channel_id")

            if not channel_id:
                await interaction.followup.send("No channel found for this application.", ephemeral=True)
                return

            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.followup.send("Channel not found.", ephemeral=True)
                return

            # Call denial handler
            from cogs.applications.handlers.application_handler import admin_deny_application
            from datetime import datetime

            await admin_deny_application(
                bot=self.bot,
                app_id=ticket_id,
                app_number=ticket.get("ticket_number", 0),
                channel=channel,
                user_id=int(user_discord_id),
                denied_by=interaction.user,
                reason=reason,
                opened_at=datetime.fromisoformat(ticket.get("created_at").replace('Z', '+00:00')) if ticket.get("created_at") else datetime.utcnow()
            )

            await interaction.followup.send(
                f"Application #{ticket_number} denied.\n\n**Reason:** {reason}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error denying application: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
