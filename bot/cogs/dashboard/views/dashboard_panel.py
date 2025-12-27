"""
Dashboard Panel View for V4
Main panel with dropdown for dashboard options
"""

import logging

import discord
from discord.ui import View, Select

logger = logging.getLogger(__name__)


class DashboardPanelView(View):
    """Main dashboard panel with dropdown menu"""

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=None)
        self.bot = bot

        # Create dropdown
        self.add_item(DashboardDropdown(bot))


class DashboardDropdown(Select):
    """Dropdown for dashboard options"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot

        options = [
            discord.SelectOption(
                label="View Stats",
                value="view_stats",
                description="See your trading volume, tier, and statistics",
                emoji="📈"
            ),
            discord.SelectOption(
                label="Recovery Codes",
                value="recovery_codes",
                description="Generate or view account recovery codes",
                emoji="🔑"
            ),
            discord.SelectOption(
                label="Redeem Code",
                value="redeem_code",
                description="Transfer account using recovery code",
                emoji="🎁"
            ),
            discord.SelectOption(
                label="Active Tickets",
                value="active_tickets",
                description="View all your open tickets",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Wallet Access",
                value="wallet_access",
                description="Quick access to your Afroo wallet",
                emoji="💼"
            ),
            discord.SelectOption(
                label="Settings",
                value="settings",
                description="Manage your profile and preferences",
                emoji="⚙️"
            )
        ]

        super().__init__(
            placeholder="Select a dashboard option...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="dashboard_panel_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection"""
        selected = self.values[0]

        logger.info(f"User {interaction.user.id} selected dashboard option: {selected}")

        await interaction.response.defer(ephemeral=True)

        try:
            if selected == "view_stats":
                from cogs.dashboard.handlers.stats_handler import show_user_stats
                await show_user_stats(interaction, self.bot)

            elif selected == "recovery_codes":
                from cogs.dashboard.handlers.recovery_handler import show_recovery_codes
                await show_recovery_codes(interaction, self.bot)

            elif selected == "redeem_code":
                from cogs.dashboard.handlers.transfer_handler import show_transfer_info
                await show_transfer_info(interaction, self.bot)

            elif selected == "active_tickets":
                from cogs.dashboard.handlers.tickets_handler import show_active_tickets
                await show_active_tickets(interaction, self.bot)

            elif selected == "wallet_access":
                from cogs.dashboard.handlers.wallet_handler import show_wallet_access
                await show_wallet_access(interaction, self.bot)

            elif selected == "settings":
                from cogs.dashboard.handlers.settings_handler import show_settings
                await show_settings(interaction, self.bot)

            else:
                await interaction.followup.send(
                    "❌ Invalid selection. Please try again.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error handling dashboard selection: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**\n\nFailed to process request: {str(e)}",
                ephemeral=True
            )
