"""
Admin Audit Logs Handler
Complete audit log viewer with filtering, search, and details
"""

import discord
from discord.ui import View, Button, Select
import logging
from datetime import datetime
from utils.embeds import create_themed_embed, create_success_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


async def show_audit_logs(interaction, bot):
    """Show system audit logs with interactive filters"""
    await interaction.response.defer(ephemeral=True)

    try:
        from utils.auth import get_user_context
        api = bot.api_client
        user_context_id, roles = get_user_context(interaction)

        # Fetch initial logs
        logs_data = await api.get(
            "/api/v1/admin/audit-logs?limit=50",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        logs = logs_data.get("logs", [])

        if not logs:
            await interaction.followup.send("📋 No audit logs found.", ephemeral=True)
            return

        # Show logs with filters
        view = AuditLogsView(bot, logs, user_context_id, roles)
        embed = view.create_embed()

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}", exc_info=True)
        await interaction.followup.send(f"Error loading audit logs: {str(e)}", ephemeral=True)


class AuditLogsView(View):
    """Interactive audit logs viewer with filters"""

    def __init__(self, bot, logs: list, user_id: str, roles: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.logs = logs
        self.user_id = user_id
        self.roles = roles
        self.current_page = 0
        self.page_size = 10
        self.action_filter = None
        self.resource_filter = None

        # Add filter dropdowns
        self.add_item(self.create_action_filter())
        self.add_item(self.create_resource_filter())

    def create_action_filter(self) -> Select:
        """Create action type filter dropdown"""
        # Get unique actions from logs
        actions = set(log.get("action") for log in self.logs if log.get("action"))

        options = [
            discord.SelectOption(label="All Actions", value="all", emoji="📋", default=self.action_filter is None)
        ]

        # Common action types
        action_list = ["force_withdraw", "edit_stats", "edit_roles", "suspend_user", "ban_user",
                       "create_ticket", "close_ticket", "assign_ticket"]

        for action in action_list:
            if action in actions:
                is_default = self.action_filter == action
                options.append(discord.SelectOption(
                    label=action.replace("_", " ").title(),
                    value=action,
                    default=is_default
                ))

        select = Select(
            placeholder="Filter by Action...",
            options=options[:25]  # Max 25 options
        )
        select.callback = self.action_filter_callback
        return select

    def create_resource_filter(self) -> Select:
        """Create resource type filter dropdown"""
        options = [
            discord.SelectOption(label="All Resources", value="all", emoji="📦", default=self.resource_filter is None),
            discord.SelectOption(label="Users", value="user", emoji="👤", default=self.resource_filter == "user"),
            discord.SelectOption(label="Wallets", value="wallet", emoji="💼", default=self.resource_filter == "wallet"),
            discord.SelectOption(label="Client Wallets", value="client_wallet", emoji="💼", default=self.resource_filter == "client_wallet"),
            discord.SelectOption(label="Exchanger Wallets", value="exchanger_wallet", emoji="", default=self.resource_filter == "exchanger_wallet"),
            discord.SelectOption(label="Tickets", value="ticket", emoji="🎫", default=self.resource_filter == "ticket"),
            discord.SelectOption(label="Exchanges", value="exchange", emoji="💱", default=self.resource_filter == "exchange"),
            discord.SelectOption(label="System", value="system", emoji="⚙️", default=self.resource_filter == "system")
        ]

        select = Select(
            placeholder="Filter by Resource Type...",
            options=options
        )
        select.callback = self.resource_filter_callback
        return select

    async def action_filter_callback(self, interaction: discord.Interaction):
        """Handle action filter selection"""
        await interaction.response.defer()
        selected = interaction.data["values"][0]
        self.action_filter = None if selected == "all" else selected
        await self.refresh_logs(interaction)

    async def resource_filter_callback(self, interaction: discord.Interaction):
        """Handle resource filter selection"""
        await interaction.response.defer()
        selected = interaction.data["values"][0]
        self.resource_filter = None if selected == "all" else selected
        await self.refresh_logs(interaction)

    async def refresh_logs(self, interaction: discord.Interaction):
        """Refresh logs with current filters"""

        try:
            api = self.bot.api_client

            # Build query params
            params = "?limit=50"
            if self.action_filter:
                params += f"&action={self.action_filter}"
            if self.resource_filter:
                params += f"&resource_type={self.resource_filter}"

            # Fetch filtered logs
            logs_data = await api.get(
                f"/api/v1/admin/audit-logs{params}",
                discord_user_id=str(interaction.user.id),
                discord_roles=self.roles
            )

            self.logs = logs_data.get("logs", [])
            self.current_page = 0

            # Update view
            self.clear_items()
            self.add_item(self.create_action_filter())
            self.add_item(self.create_resource_filter())

            embed = self.create_embed()
            await interaction.edit_original_response(embed=embed, view=self)

        except Exception as e:
            logger.error(f"Error refreshing audit logs: {e}")
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    def create_embed(self) -> discord.Embed:
        """Create audit logs embed"""
        # Paginate logs
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_logs = self.logs[start:end]

        # Build description
        description = "## 📋 Audit Logs\n\n"

        if self.action_filter:
            description += f"**Action Filter:** {self.action_filter.replace('_', ' ').title()}\n"
        if self.resource_filter:
            description += f"**Resource Filter:** {self.resource_filter.replace('_', ' ').title()}\n"

        if self.action_filter or self.resource_filter:
            description += "\n"

        if not page_logs:
            description += "> No logs found with current filters."
        else:
            for log in page_logs:
                actor = log.get("actor_type", "unknown")
                action = log.get("action", "unknown")
                resource = log.get("resource_type", "unknown")
                created_at = log.get("created_at", "")

                # Format timestamp
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    timestamp = f"<t:{int(dt.timestamp())}:R>"
                except:
                    timestamp = "Unknown time"

                # Get details
                details = log.get("details", {})
                detail_text = ""

                if "user_discord_id" in details:
                    detail_text = f"User: <@{details['user_discord_id']}>"
                elif "discord_id" in details:
                    detail_text = f"User: <@{details['discord_id']}>"
                elif "currency" in details:
                    detail_text = f"{details.get('currency', '')}"

                description += f"**{action.replace('_', ' ').title()}**\n"
                description += f"> Actor: `{actor}` • Resource: `{resource}`\n"
                description += f"> {timestamp}"
                if detail_text:
                    description += f" • {detail_text}"
                description += "\n\n"

        # Add pagination info
        total_pages = (len(self.logs) + self.page_size - 1) // self.page_size
        if total_pages > 1:
            description += f"\n> Page {self.current_page + 1} of {total_pages} • {len(self.logs)} total logs"
        else:
            description += f"\n> {len(self.logs)} logs"

        embed = create_themed_embed(
            title="",
            description=description,
            color=PURPLE_GRADIENT
        )

        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="◀️", row=4)
    async def previous_button(self, button: Button, interaction: discord.Interaction):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Already on first page.", ephemeral=True)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="▶️", row=4)
    async def next_button(self, button: Button, interaction: discord.Interaction):
        """Go to next page"""
        total_pages = (len(self.logs) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Already on last page.", ephemeral=True)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary, emoji="", row=4)
    async def refresh_button(self, button: Button, interaction: discord.Interaction):
        """Refresh logs"""
        await self.refresh_logs(interaction)
