"""
Tickets Cog - Exchange ticket management
Handles ticket creation, claiming, completion
"""

import discord
from discord.ext import commands
import logging

from api.client import APIClient
from api.errors import APIError
from utils.embeds import create_ticket_embed, error_embed
from utils.decorators import require_staff, defer_response
from config import config
from cogs.tickets.views.exchange_flow import ExchangePanelView, send_exchange_panel
from cogs.tickets.views.tos_view import TOSAcceptanceView
from cogs.tickets.views.claim_view import ClaimTicketView, UnclaimApprovalView
from cogs.tickets.views.transaction_view import TransactionPanelView
from cogs.tickets.views.payout_view import PayoutMethodView, CustomerConfirmationView

logger = logging.getLogger(__name__)


class TicketsCog(commands.Cog):
    """
    Tickets Cog - Manages exchange tickets

    Commands:
        /panel exchange - Deploy exchange panel
        /ticket info <ticket_id> - View ticket information
        /ticket claim <ticket_id> - Claim a ticket (exchanger)
        /ticket complete <ticket_id> - Complete a ticket (exchanger)
    """

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.api: APIClient = bot.api_client

        # Register persistent views for automatic restoration on bot restart
        # These views need to persist across bot restarts
        self.register_persistent_views()

    def register_persistent_views(self):
        """Register all persistent views"""
        # Main panel - must persist
        self.bot.add_view(ExchangePanelView(self.bot))

        # Transaction panels - should persist
        # These will be recreated on bot restart if messages still exist
        # We can't easily reconstruct these without storing message IDs,
        # so they'll timeout naturally if bot restarts

        logger.info("Registered persistent views for tickets cog")

    def cog_load(self):
        """Called when cog is loaded"""
        logger.info(f"{self.__class__.__name__} loaded")

    def cog_unload(self):
        """Called when cog is unloaded"""
        logger.info(f"{self.__class__.__name__} unloaded")

    # =======================
    # Ticket Commands (DISABLED - User request)
    # =======================

    # ticket = discord.SlashCommandGroup(
    #     name="ticket",
    #     description="Ticket management commands"
    # )

    # @ticket.command(
    #     name="info",
    #     description="View ticket information"
    # )
    @defer_response(ephemeral=True)
    async def ticket_info(
        self,
        ctx: discord.ApplicationContext,
        ticket_id: discord.Option(
            str,
        #     description="Ticket ID (e.g., 0042)",
            required=True
        )
    ):
        """View ticket information"""
        try:
            # Get ticket from API
            ticket = await self.api.get_ticket(ticket_id)

            # Create embed
            embed = create_ticket_embed(ticket.dict())

            # Add additional info
            if ticket.exchanger_username:
                embed.add_field(
                    name="**Exchanger**",
                    value=f"`{ticket.exchanger_username}`",
                    inline=True
                )

            if ticket.channel_id:
                embed.add_field(
                    name="**Channel**",
                    value=f"<#{ticket.channel_id}>",
                    inline=True
                )

            await ctx.respond(embed=embed)

        except APIError as e:
            logger.error(f"Error fetching ticket {ticket_id}: {e}")
            await ctx.respond(
                embed=error_embed(description=f"❌ {e.user_message}")
            )

    # @ticket.command(
    #     name="claim",
    #     description="Claim a ticket (Exchanger only)"
    # )
    @defer_response()
    async def claim_ticket(
        self,
        ctx: discord.ApplicationContext,
        ticket_id: discord.Option(
            str,
        #     description="Ticket ID to claim",
            required=True
        )
    ):
        """Claim a ticket"""
        # Check if user is exchanger
        if not config.is_exchanger(ctx.author) and not config.is_admin(ctx.author):
            await ctx.respond(
                embed=error_embed(
                #     description="⛔ You need the Exchanger role to claim tickets."
                )
            )
            return

        try:
            # Claim ticket via API
            ticket = await self.api.claim_ticket(
                ticket_id=ticket_id,
                exchanger_id=str(ctx.author.id)
            )

            logger.info(f"Ticket {ticket_id} claimed by {ctx.author.name}")

            # Create success embed
            embed = create_ticket_embed(ticket.dict())
            embed.title = "✅ Ticket Claimed"
            embed.description += f"\n\n**Claimed by:** {ctx.author.mention}"

            await ctx.respond(embed=embed)

            # Update ticket channel if it exists
            if ticket.channel_id:
                try:
                    channel = ctx.guild.get_channel(int(ticket.channel_id))
                    if channel:
                        await channel.send(
                            f"✅ This ticket has been claimed by {ctx.author.mention}!"
                        )
                except:
                    pass

        except APIError as e:
            logger.error(f"Error claiming ticket {ticket_id}: {e}")
            await ctx.respond(
                embed=error_embed(description=f"❌ {e.user_message}")
            )

    # @ticket.command(
    #     name="complete",
    #     description="Complete a ticket (Exchanger only)"
    # )
    @defer_response()
    async def complete_ticket(
        self,
        ctx: discord.ApplicationContext,
        ticket_id: discord.Option(
            str,
        #     description="Ticket ID to complete",
            required=True
        )
    ):
        """Complete a ticket"""
        try:
            # Complete ticket via API
            ticket = await self.api.complete_ticket(ticket_id)

            logger.info(f"Ticket {ticket_id} completed by {ctx.author.name}")

            # Create success embed
            embed = create_ticket_embed(ticket.dict())
            embed.title = "✅ Ticket Completed"
            embed.color = discord.Color.green()

            await ctx.respond(embed=embed)

            # Update ticket channel
            if ticket.channel_id:
                try:
                    channel = ctx.guild.get_channel(int(ticket.channel_id))
                    if channel:
                        await channel.send(
                            "🎉 This ticket has been completed! Thank you for using Afroo Exchange."
                        )
                        # TODO: Archive channel after delay
                except:
                    pass

        except APIError as e:
            logger.error(f"Error completing ticket {ticket_id}: {e}")
            await ctx.respond(
                embed=error_embed(description=f"❌ {e.user_message}")
            )


def setup(bot: discord.Bot):
    """Required function to load cog"""
    bot.add_cog(TicketsCog(bot))
