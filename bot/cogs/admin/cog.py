"""
Admin Panel Cog for V4
Comprehensive admin controls for platform management
"""

import logging
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup, Option
from config import config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, RED_GRADIENT

logger = logging.getLogger(__name__)


def is_admin_or_assistant():
    """Check if user has Head Admin or Assistant Admin role"""
    async def predicate(ctx):
        if not ctx.guild:
            return False

        member = ctx.guild.get_member(ctx.author.id)
        if not member:
            return False

        role_ids = [role.id for role in member.roles]
        head_admin_role = config.head_admin_role
        assistant_admin_role = config.assistant_admin_role

        has_permission = head_admin_role in role_ids or assistant_admin_role in role_ids

        if not has_permission:
            embed = create_themed_embed(
                title="Permission Denied",
                description="This command requires Head Admin or Assistant Admin role.",
                color=RED_GRADIENT
            )
            await ctx.respond(embed=embed, ephemeral=True)

        return has_permission

    return commands.check(predicate)


class AdminCog(commands.Cog):
    """Admin Panel - Platform management controls"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        logger.info("Admin cog loaded")

    @commands.Cog.listener()
    async def on_ready(self):
        from cogs.admin.views.admin_panel import AdminPanelView
        self.bot.add_view(AdminPanelView(self.bot))
        logger.info("Admin persistent views registered")

    # ========================================
    # EXCHANGE TICKET FORCE COMMANDS
    # ========================================

    admin = SlashCommandGroup(
        name="admin",
        description="Admin commands for ticket management",
        default_member_permissions=discord.Permissions(administrator=True)
    )

    @admin.command(
        name="claim",
        description="[ADMIN] Claim a ticket for yourself (bypasses deposit/balance checks)"
    )
    @is_admin_or_assistant()
    async def admin_claim(
        self,
        ctx: discord.ApplicationContext,
        ticket_number: Option(str, "Ticket number (e.g., 12345)", required=True)
    ):
        """Admin claims ticket for themselves"""
        from cogs.admin.handlers.admin_commands_handler import admin_claim_ticket
        await admin_claim_ticket(self.bot, ctx.interaction, ticket_number)

    @discord.slash_command(
        name="force-close",
        description="[ADMIN] Force close an exchange ticket (bypasses approvals)"
    )
    @is_admin_or_assistant()
    async def force_close(
        self,
        ctx: discord.ApplicationContext,
        ticket_number: Option(str, "Ticket number (e.g., 12345)", required=True),
        reason: Option(str, "Reason for force closing", required=True)
    ):
        """Force close an exchange ticket"""
        from cogs.admin.handlers.admin_commands_handler import force_close_ticket
        await force_close_ticket(self.bot, ctx.interaction, ticket_number, reason)

    @discord.slash_command(
        name="force-claim",
        description="[ADMIN] Force claim a ticket for an exchanger (bypasses balance checks)"
    )
    @is_admin_or_assistant()
    async def force_claim(
        self,
        ctx: discord.ApplicationContext,
        ticket_number: Option(str, "Ticket number (e.g., 12345)", required=True),
        exchanger_id: Option(str, "Discord ID of exchanger", required=True)
    ):
        """Force claim a ticket for an exchanger"""
        from cogs.admin.handlers.admin_commands_handler import force_claim_ticket
        await force_claim_ticket(self.bot, ctx.interaction, ticket_number, exchanger_id)

    @discord.slash_command(
        name="force-unclaim",
        description="[ADMIN] Force unclaim a ticket (releases holds and moves to pending)"
    )
    @is_admin_or_assistant()
    async def force_unclaim(
        self,
        ctx: discord.ApplicationContext,
        ticket_number: Option(str, "Ticket number (e.g., 12345)", required=True)
    ):
        """Force unclaim a ticket"""
        from cogs.admin.handlers.admin_commands_handler import force_unclaim_ticket
        await force_unclaim_ticket(self.bot, ctx.interaction, ticket_number)

    @discord.slash_command(
        name="force-complete",
        description="[ADMIN] Force complete a ticket with full workflow (transcript, fees, holds)"
    )
    @is_admin_or_assistant()
    async def force_complete(
        self,
        ctx: discord.ApplicationContext,
        ticket_number: Option(str, "Ticket number (e.g., 12345)", required=True)
    ):
        """Force complete a ticket with full workflow"""
        from cogs.admin.handlers.admin_commands_handler import force_complete_ticket
        await force_complete_ticket(self.bot, ctx.interaction, ticket_number)

    # ========================================
    # AUTOMM COMMAND
    # ========================================

    @discord.slash_command(
        name="reveal-automm-key",
        description="[ADMIN] Reveal AutoMM escrow private key (for dispute resolution)"
    )
    @is_admin_or_assistant()
    async def reveal_automm_key(
        self,
        ctx: discord.ApplicationContext,
        mm_id: Option(str, "AutoMM ID (e.g., A1B2C3D4)", required=True)
    ):
        """Reveal AutoMM escrow private key"""
        from cogs.admin.handlers.admin_commands_handler import reveal_automm_key
        await reveal_automm_key(self.bot, ctx.interaction, mm_id)

    # ========================================
    # SWAP INFO COMMAND
    # ========================================

    @discord.slash_command(
        name="swap-info",
        description="[ADMIN] Get comprehensive swap information (internal + external)"
    )
    @is_admin_or_assistant()
    async def swap_info(
        self,
        ctx: discord.ApplicationContext,
        swap_id: Option(str, "Swap ID", required=True)
    ):
        """Get comprehensive swap information"""
        from cogs.admin.handlers.admin_commands_handler import get_swap_info
        await get_swap_info(self.bot, ctx.interaction, swap_id)

    # ========================================
    # PANEL MANAGEMENT COMMANDS
    # ========================================

    @discord.slash_command(
        name="send-exchange-panel",
        description="[ADMIN] Send the new exchange panel (V2) to a channel"
    )
    @is_admin_or_assistant()
    async def send_exchange_panel(
        self,
        ctx: discord.ApplicationContext,
        channel: Option(discord.TextChannel, "Channel to send panel to", required=True)
    ):
        """Send the new exchange panel V2"""
        try:
            await ctx.defer(ephemeral=True)

            from cogs.tickets.views.exchange_panel_v2 import send_exchange_panel_v2

            await send_exchange_panel_v2(channel, self.bot)

            embed = create_themed_embed(
                title="Panel Sent",
                description=f"Exchange Panel V2 has been sent to {channel.mention}!",
                color=PURPLE_GRADIENT
            )
            await ctx.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Admin {ctx.author.name} sent exchange panel V2 to {channel.name}")

        except Exception as e:
            logger.error(f"Error sending exchange panel: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"Failed to send panel: {str(e)}",
                color=RED_GRADIENT
            )
            await ctx.followup.send(embed=embed, ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(AdminCog(bot))
