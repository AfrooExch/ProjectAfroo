"""
Admin Ticket Management Handler - Force actions on tickets
HEAD ADMIN & ASSISTANT ADMIN
"""

import logging
import discord
from discord.ui import View, Button, Select, Modal, InputText

from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT, WARNING, ERROR_RED
from config import Config

logger = logging.getLogger(__name__)


async def show_ticket_management(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show ticket management interface with filters and actions

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    try:
        from utils.auth import get_user_context
        api = bot.api_client
        user_context_id, roles = get_user_context(interaction)

        # Get all open tickets
        tickets_response = await api.get(
            "/api/v1/admin/tickets/all?status=pending&limit=50",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        tickets = tickets_response.get("tickets", [])

        embed = create_themed_embed(
            title="",
            description=(
                f"## 🎫 Ticket Management\n\n"
                f"### Active Tickets\n\n"
                f"**Total Open:** {len(tickets)}\n\n"
                f"### Actions Available\n\n"
                f"> • **Search Ticket** - Find ticket by ID or number\n"
                f"> • **Force Claim** - Assign exchanger to ticket\n"
                f"> • **Force Unclaim** - Remove exchanger, release holds\n"
                f"> • **Force Close** - Close ticket immediately\n"
                f"> • **Add/Remove Users** - Manage ticket participants\n\n"
                f"### Quick Stats\n\n"
            ),
            color=PURPLE_GRADIENT
        )

        # Show some recent tickets
        if tickets:
            embed.description += f"**Recent Tickets:**\n\n"
            for ticket in tickets[:5]:
                ticket_num = ticket.get("ticket_number", "N/A")
                status = ticket.get("status", "unknown")
                amount = ticket.get("amount_usd", 0)
                embed.description += f"> • `#{ticket_num}` - {status} - ${amount:.2f}\n"

            if len(tickets) > 5:
                embed.description += f"\n> *+{len(tickets) - 5} more tickets*\n"

        embed.description += "\n> Use the buttons below to manage tickets"

        view = TicketManagementView(bot)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed ticket management to admin {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error loading tickets: {e}")
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error Loading Tickets",
                description=f"{e.user_message}"
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing ticket management: {e}", exc_info=True)
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error",
                description=f"Failed to load ticket management: {str(e)}"
            ),
            ephemeral=True
        )


class TicketManagementView(View):
    """View with buttons for ticket management actions"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(
        label="Search Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🔍"
    )
    async def search_ticket_button(self, button: Button, interaction: discord.Interaction):
        """Open search ticket modal"""
        modal = SearchTicketModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Force Claim",
        style=discord.ButtonStyle.secondary,
        emoji="👤"
    )
    async def force_claim_button(self, button: Button, interaction: discord.Interaction):
        """Open force claim modal"""
        modal = ForceClaimModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Force Unclaim",
        style=discord.ButtonStyle.secondary,
        emoji="🔓"
    )
    async def force_unclaim_button(self, button: Button, interaction: discord.Interaction):
        """Open force unclaim modal"""
        modal = ForceUnclaimModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Force Close",
        style=discord.ButtonStyle.danger,
        emoji="🚫"
    )
    async def force_close_button(self, button: Button, interaction: discord.Interaction):
        """Open force close modal"""
        modal = ForceCloseModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Manage Users",
        style=discord.ButtonStyle.secondary,
        emoji="👥"
    )
    async def manage_users_button(self, button: Button, interaction: discord.Interaction):
        """Open manage users modal"""
        modal = ManageTicketUsersModal(self.bot)
        await interaction.response.send_modal(modal)


class SearchTicketModal(Modal):
    """Modal for searching and viewing ticket details"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🔍 Search Ticket")
        self.bot = bot

        self.ticket_input = InputText(
            label="Ticket ID or Number",
            placeholder="Enter ticket MongoDB ID or ticket number",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            ticket_query = self.ticket_input.value.strip()

            # Get all tickets and search
            tickets_response = await api.get(
                "/api/v1/admin/tickets/all?limit=1000",
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            tickets = tickets_response.get("tickets", [])

            # Search by ID or number
            found_ticket = None
            for ticket in tickets:
                if ticket["id"] == ticket_query or str(ticket.get("ticket_number")) == ticket_query:
                    found_ticket = ticket
                    break

            if not found_ticket:
                await interaction.followup.send(
                    embed=create_error_embed(
                        title="Ticket Not Found",
                        description=f"No ticket found with ID or number: `{ticket_query}`"
                    ),
                    ephemeral=True
                )
                return

            # Display ticket details
            status_emoji = {
                "pending": "⏳",
                "active": "",
                "completed": "",
                "cancelled": ""
            }.get(found_ticket.get("status"), "❓")

            embed = create_themed_embed(
                title="",
                description=(
                    f"## 🎫 Ticket Details\n\n"
                    f"**Ticket Number:** `#{found_ticket.get('ticket_number')}`\n"
                    f"**ID:** `{found_ticket['id']}`\n"
                    f"**Status:** {status_emoji} {found_ticket['status'].title()}\n"
                    f"**Type:** {found_ticket.get('type', 'unknown').title()}\n\n"
                    f"### Transaction Details\n\n"
                    f"**Amount:** ${found_ticket.get('amount_usd', 0):.2f} USD\n"
                    f"**Send Method:** {found_ticket.get('send_method', 'N/A')}\n"
                    f"**Receive Method:** {found_ticket.get('receive_method', 'N/A')}\n\n"
                    f"### Parties\n\n"
                    f"**User ID:** {found_ticket.get('user_id', 'N/A')}\n"
                    f"**Exchanger ID:** {found_ticket.get('exchanger_id') or 'Not claimed'}\n\n"
                    f"### Discord\n\n"
                    f"**Channel:** <#{found_ticket.get('channel_id')}>\n\n"
                    f"### Timestamps\n\n"
                    f"**Created:** {found_ticket.get('created_at', 'N/A')}\n"
                    f"**Updated:** {found_ticket.get('updated_at', 'N/A')}"
                ),
                color=PURPLE_GRADIENT
            )

            view = TicketActionsView(self.bot, found_ticket['id'])
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error searching ticket: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Search Failed",
                    description=f"Error: {str(e)}"
                ),
                ephemeral=True
            )


class TicketActionsView(View):
    """Quick actions for a specific ticket"""

    def __init__(self, bot: discord.Bot, ticket_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="Force Close",
        style=discord.ButtonStyle.danger,
        emoji="🚫"
    )
    async def quick_force_close(self, button: Button, interaction: discord.Interaction):
        """Quick force close this ticket"""
        modal = QuickForceCloseModal(self.bot, self.ticket_id)
        await interaction.response.send_modal(modal)


class QuickForceCloseModal(Modal):
    """Quick force close modal with pre-filled ticket ID"""

    def __init__(self, bot: discord.Bot, ticket_id: str):
        super().__init__(title="🚫 Force Close Ticket")
        self.bot = bot
        self.ticket_id = ticket_id

        self.reason = InputText(
            label="Reason for Closing",
            placeholder="Why is this ticket being force closed?",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Force close ticket
            result = await api.post(
                "/api/v1/admin/tickets/force-close",
                {
                    "ticket_id": self.ticket_id,
                    "reason": self.reason.value,
                    "release_holds": True
                },
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            embed = create_success_embed(
                title="Ticket Force Closed",
                description=(
                    f"## Ticket Closed Successfully\n\n"
                    f"**Ticket ID:** `{self.ticket_id}`\n"
                    f"**Reason:** {self.reason.value}\n\n"
                    f"### Actions Taken\n\n"
                    f"> • Ticket status changed to cancelled\n"
                    f"> • All holds released\n"
                    f"> • Exchanger can claim new tickets\n"
                    f"> • Logged in audit trail"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(f"Admin {interaction.user.id} force closed ticket {self.ticket_id}: {self.reason.value}")

        except APIError as e:
            logger.error(f"API error force closing ticket: {e}")
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Force Close Failed",
                    description=f"{e.user_message}"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error force closing ticket: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_error_embed(
                    title="Error",
                    description=f"Failed to close ticket: {str(e)}"
                ),
                ephemeral=True
            )


class ForceClaimModal(Modal):
    """Modal for force claiming ticket"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="👤 Force Claim Ticket")
        self.bot = bot

        self.ticket_id = InputText(
            label="Ticket ID",
            placeholder="Ticket MongoDB ID",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.exchanger_id = InputText(
            label="Exchanger Discord ID",
            placeholder="Discord ID of exchanger to assign",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_id)
        self.add_item(self.exchanger_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            result = await api.post(
                "/api/v1/admin/tickets/force-claim",
                {
                    "ticket_id": self.ticket_id.value,
                    "exchanger_discord_id": self.exchanger_id.value
                },
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            embed = create_success_embed(
                title="Ticket Force Claimed",
                description=(
                    f"## Ticket Claimed Successfully\n\n"
                    f"**Ticket ID:** `{self.ticket_id.value}`\n"
                    f"**Exchanger:** <@{self.exchanger_id.value}>\n\n"
                    f"### Bypass Applied\n\n"
                    f"> • Balance checks skipped\n"
                    f"> • No holds created\n"
                    f"> • Ticket moved to active\n"
                    f"> • Logged as force claim"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            await interaction.followup.send(
                embed=create_error_embed(title="Force Claim Failed", description=f"{e.user_message}"),
                ephemeral=True
            )


class ForceUnclaimModal(Modal):
    """Modal for force unclaiming ticket"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🔓 Force Unclaim Ticket")
        self.bot = bot

        self.ticket_id = InputText(
            label="Ticket ID",
            placeholder="Ticket MongoDB ID",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            result = await api.post(
                f"/api/v1/admin/tickets/force-unclaim?ticket_id={self.ticket_id.value}&release_holds=true",
                {},
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            embed = create_success_embed(
                title="Ticket Force Unclaimed",
                description=(
                    f"## Ticket Unclaimed Successfully\n\n"
                    f"**Ticket ID:** `{self.ticket_id.value}`\n\n"
                    f"### Actions Taken\n\n"
                    f"> • Exchanger removed from ticket\n"
                    f"> • All holds released\n"
                    f"> • Ticket moved to pending\n"
                    f"> • Available for new claims"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            await interaction.followup.send(
                embed=create_error_embed(title="Force Unclaim Failed", description=f"{e.user_message}"),
                ephemeral=True
            )


class ForceCloseModal(Modal):
    """Modal for force closing ticket"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🚫 Force Close Ticket")
        self.bot = bot

        self.ticket_id = InputText(
            label="Ticket ID",
            placeholder="Ticket MongoDB ID",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.reason = InputText(
            label="Reason",
            placeholder="Why is this ticket being closed?",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.ticket_id)
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            result = await api.post(
                "/api/v1/admin/tickets/force-close",
                {
                    "ticket_id": self.ticket_id.value,
                    "reason": self.reason.value,
                    "release_holds": True
                },
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            embed = create_success_embed(
                title="Ticket Force Closed",
                description=(
                    f"## Ticket Closed\n\n"
                    f"**Ticket ID:** `{self.ticket_id.value}`\n"
                    f"**Reason:** {self.reason.value}\n\n"
                    f"> • All holds released\n"
                    f"> • Ticket cancelled\n"
                    f"> • Logged in audit"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            await interaction.followup.send(
                embed=create_error_embed(title="Force Close Failed", description=f"{e.user_message}"),
                ephemeral=True
            )


class ManageTicketUsersModal(Modal):
    """Modal for adding/removing users from ticket"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="👥 Manage Ticket Users")
        self.bot = bot

        self.ticket_id = InputText(
            label="Ticket ID",
            placeholder="Ticket MongoDB ID",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.user_discord_id = InputText(
            label="User Discord ID",
            placeholder="Discord ID to add/remove",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.action = InputText(
            label="Action (add or remove)",
            placeholder="Type: add or remove",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.ticket_id)
        self.add_item(self.user_discord_id)
        self.add_item(self.action)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            action = self.action.value.strip().lower()
            endpoint = f"/api/v1/admin/tickets/{'add-user' if action == 'add' else 'remove-user'}"

            result = await api.post(
                endpoint,
                {
                    "ticket_id": self.ticket_id.value,
                    "discord_id": self.user_discord_id.value
                },
                discord_user_id=str(interaction.user.id),
                discord_roles=roles
            )

            action_text = "Added to" if action == "add" else "Removed from"
            embed = create_success_embed(
                title=f"User {action_text} Ticket",
                description=(
                    f"## Success\n\n"
                    f"**User:** <@{self.user_discord_id.value}>\n"
                    f"**Ticket ID:** `{self.ticket_id.value}`\n"
                    f"**Action:** {action_text.title()}\n\n"
                    f"> User can now {'view and participate' if action == 'add' else 'no longer see'} in this ticket"
                )
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            await interaction.followup.send(
                embed=create_error_embed(title="Action Failed", description=f"{e.user_message}"),
                ephemeral=True
            )
