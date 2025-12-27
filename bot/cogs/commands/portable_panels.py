"""
Portable Panel Commands - Consolidated Ephemeral Panels

Three main commands that create invisible, portable panels:
- /user-panel - For all users (ticket management, wallet, etc.)
- /staff-panel - For staff (moderation, ticket oversight)
- /admin-panel - For admins (platform management, statistics)

These panels are ephemeral (only visible to the user) and provide
quick access to common actions without cluttering channels.
"""

import logging
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup

from config import config
from utils import (
    get_user_context,
    handle_api_errors,
    require_admin,
    require_staff,
    is_admin,
    is_staff,
    is_exchanger
)
from utils.embeds import create_embed
from utils.colors import (
    PURPLE_GRADIENT,
    SUCCESS_GREEN,
    ERROR_RED,
    INFO_BLUE
)

logger = logging.getLogger(__name__)


class PortablePanels(commands.Cog):
    """Portable ephemeral panels for user, staff, and admin"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.api = bot.api_client
        logger.info("✅ Portable Panels initialized")

    # =======================
    # USER PANEL
    # =======================

    @discord.slash_command(
        name="user-panel",
        description="Open your personal control panel"
    )
    @handle_api_errors(ephemeral=True)
    async def user_panel_command(self, ctx: discord.ApplicationContext):
        """
        Portable user panel - ephemeral, only visible to user

        Provides quick access to:
        - My Tickets
        - Wallet
        - Dashboard
        - Support
        - Swap
        """
        user_id, roles = get_user_context(ctx.interaction)

        embed = create_embed(
            title="👤 Your Control Panel",
            description=(
                "Quick access to all your account features.\n\n"
                "**Your Account**\n"
                f"• Discord ID: `{user_id}`\n"
                f"• Roles: {len(roles)} active roles"
            ),
            color=PURPLE_GRADIENT
        )

        embed.add_field(
            name="📋 Available Actions",
            value=(
                "• View your active tickets\n"
                "• Manage your wallets\n"
                "• Check your dashboard\n"
                "• Create support ticket\n"
                "• Quick swap"
            ),
            inline=False
        )

        embed.set_footer(text="This panel is only visible to you")

        view = UserPanelView(self.bot, user_id, roles)
        await ctx.respond(embed=embed, view=view, ephemeral=True)

    # =======================
    # STAFF PANEL
    # =======================

    @discord.slash_command(
        name="support-panel",
        description="[Staff] Open support management panel"
    )
    @require_staff(config)
    @handle_api_errors(ephemeral=True)
    async def staff_panel_command(self, ctx: discord.ApplicationContext):
        """
        Portable staff panel - ephemeral, only visible to staff

        Provides quick access to:
        - View all tickets
        - Manage support tickets
        - User management
        - Ticket moderation
        - View applications
        """
        user_id, roles = get_user_context(ctx.interaction)

        # Check if admin or staff
        admin = is_admin(ctx.interaction, self.config)
        staff = is_staff(ctx.interaction, self.config)

        embed = create_embed(
            title="👨‍💼 Staff Control Panel",
            description=(
                "Staff management tools and oversight.\n\n"
                f"**Your Permissions**\n"
                f"• Admin: {'✅' if admin else '❌'}\n"
                f"• Staff: {'✅' if staff else '❌'}"
            ),
            color=PURPLE_GRADIENT
        )

        embed.add_field(
            name="🛠️ Available Actions",
            value=(
                "• View all open tickets\n"
                "• Manage support tickets\n"
                "• Review applications\n"
                "• View platform stats\n"
                "• User lookup"
            ),
            inline=False
        )

        embed.set_footer(text="Staff Only • This panel is only visible to you")

        view = StaffPanelView(self.bot, user_id, roles)
        await ctx.respond(embed=embed, view=view, ephemeral=True)

    # =======================
    # ADMIN PANEL
    # =======================

    @discord.slash_command(
        name="admin-panel",
        description="[Admin] Open admin control panel"
    )
    @require_admin(config)
    @handle_api_errors(ephemeral=True)
    async def admin_panel_command(self, ctx: discord.ApplicationContext):
        """
        Portable admin panel - ephemeral, only visible to admins

        Provides quick access to:
        - Platform statistics
        - User management (freeze, unfreeze)
        - Application approval/rejection
        - Ticket oversight
        - System controls
        """
        user_id, roles = get_user_context(ctx.interaction)

        embed = create_embed(
            title="⚙️ Admin Control Panel",
            description=(
                "Complete platform administration tools.\n\n"
                "**⚠️ Admin Access Only**\n"
                "All actions are logged and audited."
            ),
            color=ERROR_RED
        )

        embed.add_field(
            name="🔧 Administrative Actions",
            value=(
                "• View platform statistics\n"
                "• Manage users (freeze/unfreeze)\n"
                "• Approve/reject applications\n"
                "• Force close tickets\n"
                "• View audit logs"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Quick Stats",
            value=(
                "Use the buttons below to view:\n"
                "• Active tickets\n"
                "• Pending applications\n"
                "• Platform metrics"
            ),
            inline=False
        )

        embed.set_footer(text="Admin Only • All actions are logged")

        view = AdminPanelView(self.bot, user_id, roles)
        await ctx.respond(embed=embed, view=view, ephemeral=True)


# =======================
# USER PANEL VIEW
# =======================

class UserPanelView(discord.ui.View):
    """Ephemeral view for user panel"""

    def __init__(self, bot, user_id: str, roles: list):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.api = bot.api_client

    @discord.ui.button(label="My Tickets", style=discord.ButtonStyle.primary, emoji="📋")
    async def my_tickets_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """View user's active tickets"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Fetch user's tickets from API
            tickets = await self.api.get(
                f"/api/v1/tickets/user/{self.user_id}",
                discord_user_id=self.user_id,
                discord_roles=self.roles
            )

            embed = create_embed(
                title="📋 Your Tickets",
                description=f"You have {len(tickets.get('items', []))} active tickets",
                color=INFO_BLUE
            )

            tickets_list = tickets.get('items', [])
            if tickets_list:
                for ticket in tickets_list[:5]:  # Show up to 5
                    status = ticket.get('status', 'unknown')
                    ticket_id = ticket.get('ticket_id', 'N/A')
                    embed.add_field(
                        name=f"Ticket #{ticket_id}",
                        value=f"Status: {status}\nType: {ticket.get('type', 'exchange')}",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="No Tickets",
                    value="You don't have any active tickets.",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to fetch tickets: {e}")
            await interaction.followup.send(
                "❌ Failed to fetch your tickets. Please try again.",
                ephemeral=True
            )

    @discord.ui.button(label="Dashboard", style=discord.ButtonStyle.success, emoji="📊")
    async def dashboard_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """View user dashboard"""
        await interaction.response.defer(ephemeral=True)

        try:
            dashboard = await self.api.get_user_dashboard(self.user_id, self.roles)

            embed = create_embed(
                title="📊 Your Dashboard",
                description="Your account statistics and information",
                color=SUCCESS_GREEN
            )

            stats = dashboard.get('stats', {})
            embed.add_field(
                name="Exchange Stats",
                value=f"Total Volume: ${stats.get('total_volume', 0):.2f}\nExchanges: {stats.get('total_exchanges', 0)}",
                inline=True
            )

            embed.add_field(
                name="Reputation",
                value=f"Score: {stats.get('reputation_score', 100)}/100\nReviews: {stats.get('total_reviews', 0)}",
                inline=True
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to fetch dashboard: {e}")
            await interaction.followup.send(
                "❌ Failed to load your dashboard. Please try again.",
                ephemeral=True
            )

    @discord.ui.button(label="Wallets", style=discord.ButtonStyle.secondary, emoji="💰")
    async def wallets_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """View user wallets"""
        await interaction.response.defer(ephemeral=True)

        try:
            wallets = await self.api.get_wallets(self.user_id, self.roles)

            embed = create_embed(
                title="💰 Your Wallets",
                description=f"You have {len(wallets)} active wallets",
                color=INFO_BLUE
            )

            for wallet in wallets[:6]:  # Show up to 6
                asset = wallet.get('asset', 'Unknown')
                balance = wallet.get('balance', 0)
                address = wallet.get('address', 'N/A')

                embed.add_field(
                    name=f"{asset}",
                    value=f"Balance: {balance}\nAddress: `{address[:10]}...`",
                    inline=True
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to fetch wallets: {e}")
            await interaction.followup.send(
                "❌ Failed to load your wallets. Please try again.",
                ephemeral=True
            )

    @discord.ui.button(label="Support", style=discord.ButtonStyle.secondary, emoji="💬")
    async def support_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Quick access to support"""
        await interaction.response.send_message(
            "💬 **Need Support?**\n\n"
            f"Visit <#{self.bot.config.channels.get('support_panel')}> to create a support ticket.\n\n"
            "**Available Support Types:**\n"
            "• Bug Report\n"
            "• Feature Request\n"
            "• General Support",
            ephemeral=True
        )


# =======================
# STAFF PANEL VIEW
# =======================

class StaffPanelView(discord.ui.View):
    """Ephemeral view for staff panel"""

    def __init__(self, bot, user_id: str, roles: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.api = bot.api_client

    @discord.ui.button(label="All Tickets", style=discord.ButtonStyle.primary, emoji="📋")
    async def all_tickets_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """View all open tickets"""
        await interaction.response.defer(ephemeral=True)

        try:
            tickets = await self.api.get_all_tickets(status="open", limit=10)

            embed = create_embed(
                title="📋 All Open Tickets",
                description=f"Currently {len(tickets)} open tickets",
                color=INFO_BLUE
            )

            for ticket in tickets[:10]:
                ticket_id = ticket.get('ticket_id', 'N/A')
                status = ticket.get('status', 'unknown')
                user = ticket.get('customer_id', 'Unknown')

                embed.add_field(
                    name=f"Ticket #{ticket_id}",
                    value=f"Status: {status}\nUser: <@{user}>",
                    inline=True
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to fetch tickets: {e}")
            await interaction.followup.send(
                "❌ Failed to fetch tickets.",
                ephemeral=True
            )

    @discord.ui.button(label="Applications", style=discord.ButtonStyle.success, emoji="📝")
    async def applications_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """View pending applications"""
        await interaction.response.send_message(
            "📝 **Pending Applications**\n\n"
            f"View pending applications in <#{self.bot.config.categories.get('exchanger_applications')}>",
            ephemeral=True
        )

    @discord.ui.button(label="Platform Stats", style=discord.ButtonStyle.secondary, emoji="📊")
    async def stats_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """View platform statistics"""
        await interaction.response.defer(ephemeral=True)

        try:
            stats = await self.api.get_platform_stats(self.user_id, self.roles)

            embed = create_embed(
                title="📊 Platform Statistics",
                description="Current platform metrics",
                color=INFO_BLUE
            )

            embed.add_field(
                name="Users",
                value=f"Total: {stats.get('total_users', 0)}\nActive: {stats.get('active_users', 0)}",
                inline=True
            )

            embed.add_field(
                name="Tickets",
                value=f"Open: {stats.get('open_tickets', 0)}\nCompleted: {stats.get('completed_tickets', 0)}",
                inline=True
            )

            embed.add_field(
                name="Volume",
                value=f"Total: ${stats.get('total_volume', 0):.2f}\nToday: ${stats.get('today_volume', 0):.2f}",
                inline=True
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to fetch stats: {e}")
            await interaction.followup.send(
                "❌ Failed to load statistics.",
                ephemeral=True
            )


# =======================
# ADMIN PANEL VIEW
# =======================

class AdminPanelView(discord.ui.View):
    """Ephemeral view for admin panel"""

    def __init__(self, bot, user_id: str, roles: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.api = bot.api_client

    @discord.ui.button(label="Platform Stats", style=discord.ButtonStyle.primary, emoji="📊")
    async def platform_stats_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """View detailed platform statistics"""
        await interaction.response.defer(ephemeral=True)

        try:
            stats = await self.api.get_platform_stats(self.user_id, self.roles)

            embed = create_embed(
                title="📊 Admin Platform Statistics",
                description="Comprehensive platform metrics",
                color=ERROR_RED
            )

            embed.add_field(
                name="📈 Users",
                value=f"Total: {stats.get('total_users', 0)}\nActive Today: {stats.get('active_today', 0)}\nNew This Week: {stats.get('new_this_week', 0)}",
                inline=True
            )

            embed.add_field(
                name="🎫 Tickets",
                value=f"Open: {stats.get('open_tickets', 0)}\nIn Progress: {stats.get('in_progress_tickets', 0)}\nCompleted: {stats.get('completed_tickets', 0)}",
                inline=True
            )

            embed.add_field(
                name="💰 Volume",
                value=f"Total: ${stats.get('total_volume', 0):.2f}\nThis Month: ${stats.get('month_volume', 0):.2f}\nToday: ${stats.get('today_volume', 0):.2f}",
                inline=True
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to fetch admin stats: {e}")
            await interaction.followup.send(
                "❌ Failed to load statistics.",
                ephemeral=True
            )

    @discord.ui.button(label="User Lookup", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def user_lookup_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Look up a user"""
        # Show a modal to get user ID
        modal = UserLookupModal(self.api, self.user_id, self.roles)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Applications", style=discord.ButtonStyle.success, emoji="📝")
    async def review_applications_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Review pending applications"""
        await interaction.response.send_message(
            "📝 **Application Review**\n\n"
            f"Review pending applications in <#{self.bot.config.categories.get('exchanger_applications')}>",
            ephemeral=True
        )

    @discord.ui.button(label="Freeze User", style=discord.ButtonStyle.danger, emoji="🔒")
    async def freeze_user_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Freeze a user account"""
        modal = FreezeUserModal(self.api, self.user_id, self.roles)
        await interaction.response.send_modal(modal)


# =======================
# MODALS
# =======================

class UserLookupModal(discord.ui.Modal):
    """Modal for looking up user information"""

    def __init__(self, api, admin_id: str, roles: list):
        super().__init__(title="User Lookup")
        self.api = api
        self.admin_id = admin_id
        self.roles = roles

        self.user_id_input = discord.ui.InputText(
            label="User Discord ID",
            placeholder="Enter Discord user ID...",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.user_id_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            lookup_user_id = self.user_id_input.value.strip()
            user = await self.api.get_user(lookup_user_id)

            embed = create_embed(
                title=f"🔍 User Lookup: {user.get('username', 'Unknown')}",
                description=f"User ID: `{lookup_user_id}`",
                color=INFO_BLUE
            )

            embed.add_field(
                name="Status",
                value=user.get('status', 'unknown'),
                inline=True
            )

            embed.add_field(
                name="Reputation",
                value=f"{user.get('reputation_score', 0)}/100",
                inline=True
            )

            stats = user.get('stats', {})
            embed.add_field(
                name="Exchange Stats",
                value=f"Volume: ${stats.get('total_volume', 0):.2f}\nCount: {stats.get('total_exchanges', 0)}",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"User lookup failed: {e}")
            await interaction.followup.send(
                "❌ User not found or lookup failed.",
                ephemeral=True
            )


class FreezeUserModal(discord.ui.Modal):
    """Modal for freezing a user account"""

    def __init__(self, api, admin_id: str, roles: list):
        super().__init__(title="Freeze User Account")
        self.api = api
        self.admin_id = admin_id
        self.roles = roles

        self.user_id_input = discord.ui.InputText(
            label="User Discord ID",
            placeholder="Enter Discord user ID...",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.user_id_input)

        self.reason_input = discord.ui.InputText(
            label="Reason",
            placeholder="Enter reason for freezing account...",
            style=discord.InputTextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            freeze_user_id = self.user_id_input.value.strip()
            reason = self.reason_input.value.strip()

            await self.api.freeze_user(freeze_user_id, reason)

            await interaction.followup.send(
                f"✅ User `{freeze_user_id}` has been frozen.\n**Reason:** {reason}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Freeze user failed: {e}")
            await interaction.followup.send(
                "❌ Failed to freeze user.",
                ephemeral=True
            )


def setup(bot: discord.Bot):
    bot.add_cog(PortablePanels(bot))
