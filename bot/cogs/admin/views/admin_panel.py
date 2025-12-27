"""Admin Panel View - Main admin dropdown interface"""
import logging
import discord
from discord.ui import View, Select
from config import config

logger = logging.getLogger(__name__)


class AdminPanelView(View):
    """Main admin panel with dropdown"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(AdminDropdown(bot))


class AdminDropdown(Select):
    """Dropdown for admin actions"""
    def __init__(self, bot):
        self.bot = bot

        # Show all options (role checks happen at callback time)
        options = [
            # Available to HEAD ADMIN and ASSISTANT ADMIN
            discord.SelectOption(label="Profit Management", value="profit_management", description="View revenue, fees, and profit stats", emoji=""),
            discord.SelectOption(label="User Lookup", value="user_lookup", description="View user info, stats, and private keys", emoji="🔍"),
            discord.SelectOption(label="Analytics", value="analytics", description="View platform statistics", emoji=""),
            discord.SelectOption(label="Leaderboards", value="leaderboards", description="View top users across all services", emoji="🏆"),
            discord.SelectOption(label="Audit Logs", value="audit_logs", description="View system audit logs", emoji="📋"),
            # HEAD ADMIN ONLY options
            discord.SelectOption(label="System Settings", value="settings", description="[HEAD ADMIN] Database backups & system info", emoji="⚙️")
        ]

        super().__init__(placeholder="Select admin action...", min_values=1, max_values=1, options=options, custom_id="admin_panel_dropdown")

    async def callback(self, interaction: discord.Interaction):
        if not config.is_admin(interaction.user) and not config.is_staff(interaction.user):
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return

        selected = self.values[0]

        # Define admin user IDs (NOT role IDs)
        HEAD_ADMIN_ID = 1419744557054169128
        ASSISTANT_ADMIN_ID = 537080477631119360

        # Check HEAD ADMIN only actions
        head_admin_only_actions = ["settings"]
        if selected in head_admin_only_actions and interaction.user.id != HEAD_ADMIN_ID:
            await interaction.response.send_message(
                "**Access Denied**\n\nThis action is restricted to Head Admin only.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if selected == "profit_management":
                from cogs.admin.handlers.profit_handler import show_profit_management
                await show_profit_management(interaction, self.bot)
            elif selected == "user_lookup":
                from cogs.admin.handlers.users_handler import show_user_lookup
                await show_user_lookup(interaction, self.bot)
            elif selected == "analytics":
                from cogs.admin.handlers.analytics_handler import show_analytics
                await show_analytics(interaction, self.bot)
            elif selected == "leaderboards":
                from cogs.admin.handlers.leaderboards_handler import show_leaderboards
                await show_leaderboards(interaction, self.bot)
            elif selected == "audit_logs":
                from cogs.admin.handlers.audit_handler import show_audit_logs
                await show_audit_logs(interaction, self.bot)
            elif selected == "settings":
                from cogs.admin.handlers.system_settings_handler import show_system_settings
                await show_system_settings(interaction, self.bot)
        except Exception as e:
            logger.error(f"Admin panel error: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
