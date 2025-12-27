"""
COMPLETE PANEL SYSTEM - ALL PANELS AUTO-POST ON STARTUP
Production-ready, consolidated, clean implementation

This file deploys ALL panels when bot starts:
- TOS
- Fees
- Support
- Application
- Leaderboard
- Exchange
- Swap
- AutoMM
- Wallet
- User Dashboard
- Exchanger Panel
- Exchanger FAQ
- Exchanger Rules
- Admin Panel

Strategy:
- Clears channels first for clean deployment
- Uses existing views where they exist
- Creates simple views for static content
- All panels persistent and production-ready
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone

from config import Config
from utils.embeds import create_embed
from utils.colors import PURPLE_GRADIENT, BLUE_PRIMARY, INFO_BLUE, SUCCESS_GREEN, ERROR_RED
from config import config

logger = logging.getLogger(__name__)


class AllPanelsCog(commands.Cog):
    """Complete panel deployment system - ALL panels auto-post on startup"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.config: Config = config
        self.deployed = False
        logger.info("✅ All Panels System initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        """Deploy all panels when bot is ready"""
        logger.info("🔔 Panels cog on_ready triggered")

        if self.deployed:
            logger.info("⏭️ Panels already deployed, skipping")
            return

        try:
            logger.info(f"🔍 Looking for guild: {self.config.guild_id}")
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                logger.error(f"❌ Guild not found: {self.config.guild_id}")
                return

            logger.info("=" * 60)
            logger.info("📋 DEPLOYING ALL PANELS")
            logger.info("=" * 60)

            # Static Info Panels
            await self._deploy_tos_panel(guild)
            await self._deploy_fees_panel(guild)
            await self._deploy_website_panel(guild)

            # User Panels
            await self._deploy_support_panel(guild)
            await self._deploy_application_panel(guild)
            await self._deploy_leaderboard_panel(guild)
            await self._deploy_exchange_panel(guild)
            await self._deploy_swap_panel(guild)
            await self._deploy_automm_panel(guild)
            await self._deploy_wallet_panel(guild)
            await self._deploy_dashboard_panel(guild)

            # Exchanger Panels
            await self._deploy_exchanger_panel(guild)
            await self._deploy_exchanger_faq_panel(guild)
            await self._deploy_exchanger_rules_panel(guild)

            # Admin Panels
            await self._deploy_admin_panel(guild)

            self.deployed = True
            logger.info("=" * 60)
            logger.info("✅ ALL PANELS DEPLOYED SUCCESSFULLY!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Panel deployment failed: {e}", exc_info=True)

    async def _clear_channel(self, channel: discord.TextChannel, panel_name: str):
        """Clear channel messages"""
        try:
            deleted = await channel.purge(limit=100)
            if deleted:
                logger.info(f"  🗑️  Cleared {len(deleted)} messages from #{channel.name}")
        except Exception as e:
            logger.warning(f"  ⚠️  Could not clear #{channel.name}: {e}")

    # ========================================================================
    # STATIC INFORMATION PANELS
    # ========================================================================

    async def _deploy_tos_panel(self, guild: discord.Guild):
        """Deploy Terms of Service panel"""
        channel_id = self.config.tos_channel
        if not channel_id:
            logger.warning("⏭️  TOS Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ TOS Panel: Channel {channel_id} not found")
            return

        logger.info("📜 Deploying TOS Panel...")
        await self._clear_channel(channel, "TOS")

        server_name = "AfrooExch"

        description = (
            "By being in Afroo Exchange you agree to follow our TOS and agree to any changes to be made at any time.\n\n"
            "The TOS can be found at http://afrooexchange.com/tos"
        )

        embed = create_embed(
            title="Terms of Service",
            description=description,
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text=f"Last Updated: November 2025 | {server_name} Exchange")

        # Add buttons
        view = discord.ui.View(timeout=None)

        # Start Exchange button
        exchange_channel = guild.get_channel(self.config.exchange_channel)
        if exchange_channel:
            exchange_btn = discord.ui.Button(
                label="Start Exchange",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.exchange_channel}",
                emoji="🚀"
            )
            view.add_item(exchange_btn)

        # Get Support button
        support_channel = guild.get_channel(self.config.support_panel_channel)
        if support_channel:
            support_btn = discord.ui.Button(
                label="Get Support",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.support_panel_channel}",
                emoji="💬"
            )
            view.add_item(support_btn)

        # Website button
        website_btn = discord.ui.Button(
            label="Visit Website",
            style=discord.ButtonStyle.link,
            url="http://afrooexchange.com",
            emoji="🌐"
        )
        view.add_item(website_btn)

        msg = await channel.send(embed=embed, view=view)
        await msg.pin()
        logger.info("✅ TOS Panel deployed")

    async def _deploy_fees_panel(self, guild: discord.Guild):
        """Deploy Fees breakdown panel"""
        channel_id = self.config.fees_channel
        if not channel_id:
            logger.warning("⏭️  Fees Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Fees Panel: Channel {channel_id} not found")
            return

        logger.info("💰 Deploying Fees Panel...")
        await self._clear_channel(channel, "Fees")

        server_name = "AfrooExch"

        description = (
            f"## {server_name} Exchange Fee Structure\n\n"
            f"**Simple, transparent pricing.** All fees are shown before you confirm your exchange.\n\n"
            f"> Our fee structure is straightforward - no hidden charges or complicated calculations.\n\n"
            f""
        )

        embed = create_embed(
            title="",
            description=description,
            color=PURPLE_GRADIENT
        )

        # Standard Fee Structure
        embed.add_field(
            name="**Standard Fee Structure**",
            value=(
                "*Here's what you'll pay:*\n\n"
                "> `Minimum fee: $4` on all exchanges\n"
                "> `Under $40:` Flat $4 fee\n"
                "> `Over $40:` 10% fee\n"
                "> `Crypto to Crypto:` 5% fee (any amount)\n"
                "> `0.2% fee` on wallet transactions\n"
                "> `0.4% fee` on all swaps\n\n"
                ""
            ),
            inline=False
        )

        # Important Notes
        embed.add_field(
            name="**Important Notes**",
            value=(
                "*Things to keep in mind:*\n\n"
                "**Negotiable Fees:**\n"
                "> Fees can be negotiated with your exchanger.\n\n"
                "**Card Payments:**\n"
                "> Expect higher fees due to chargeback risk.\n\n"
                ""
            ),
            inline=False
        )

        # Example Calculations
        embed.add_field(
            name="**Example Calculations**",
            value=(
                "*Quick examples:*\n\n"
                "```\n"
                "$30 exchange   → $4 fee   → $26 received\n"
                "$100 exchange  → $10 fee  → $90 received\n"
                "$100 crypto/crypto → $5 fee → $95 received\n"
                "```\n\n"
                ""
            ),
            inline=False
        )

        # Ready to Start
        embed.add_field(
            name="",
            value=(
                "> **Ready to start an exchange?**\n"
                "> All fees will be clearly shown in your ticket before confirmation.\n\n"
            ),
            inline=False
        )

        embed.set_footer(text="Last Updated: October 2025")

        # Add buttons
        view = discord.ui.View(timeout=None)

        # Start Exchange button
        exchange_channel = guild.get_channel(self.config.exchange_channel)
        if exchange_channel:
            exchange_btn = discord.ui.Button(
                label="Start Exchange",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.exchange_channel}",
                emoji="🚀"
            )
            view.add_item(exchange_btn)

        # Get Support button
        support_channel = guild.get_channel(self.config.support_panel_channel)
        if support_channel:
            support_btn = discord.ui.Button(
                label="Get Support",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.support_panel_channel}",
                emoji="💬"
            )
            view.add_item(support_btn)

        # Website button
        website_btn = discord.ui.Button(
            label="Visit Website",
            style=discord.ButtonStyle.link,
            url="http://afrooexchange.com",
            emoji="🌐"
        )
        view.add_item(website_btn)

        msg = await channel.send(embed=embed, view=view)
        await msg.pin()
        logger.info("✅ Fees Panel deployed")

    async def _deploy_website_panel(self, guild: discord.Guild):
        """Deploy Website Overview panel"""
        channel_id = self.config.website_channel
        if not channel_id:
            logger.warning("⏭️  Website Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Website Panel: Channel {channel_id} not found")
            return

        logger.info("🌐 Deploying Website Panel...")
        await self._clear_channel(channel, "Website")

        server_name = "AfrooExch"

        description = (
            "Visit our website at http://afrooexchange.com to access your wallet, swap crypto, view the leaderboard, and manage your account.\n\n"
            "Our web platform offers a complete trading experience with wallet management, instant crypto swaps, live leaderboard stats, and full account control."
        )

        embed = create_embed(
            title="Afroo Exchange Website",
            description=description,
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text=f"Last Updated: November 2025 | {server_name} Exchange")

        # Add buttons for website and quick navigation
        view = discord.ui.View(timeout=None)

        # Website button
        website_btn = discord.ui.Button(
            label="Visit Website",
            style=discord.ButtonStyle.link,
            url="http://afrooexchange.com"
        )
        view.add_item(website_btn)

        # Exchange button
        if self.config.exchange_channel:
            exchange_btn = discord.ui.Button(
                label="Exchange",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.exchange_channel}"
            )
            view.add_item(exchange_btn)

        # Swap button
        if self.config.swap_panel_channel:
            swap_btn = discord.ui.Button(
                label="Swap",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.swap_panel_channel}"
            )
            view.add_item(swap_btn)

        # AutoMM button
        if self.config.automm_panel_channel:
            automm_btn = discord.ui.Button(
                label="AutoMM",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.automm_panel_channel}"
            )
            view.add_item(automm_btn)

        # Wallet button
        if self.config.wallet_panel_channel:
            wallet_btn = discord.ui.Button(
                label="Wallet",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{self.config.wallet_panel_channel}"
            )
            view.add_item(wallet_btn)

        msg = await channel.send(embed=embed, view=view)
        await msg.pin()
        logger.info("✅ Website Panel deployed")

    async def _deploy_exchanger_faq_panel(self, guild: discord.Guild):
        """Deploy Exchanger FAQ panel"""
        # Use dedicated exchanger FAQ channel
        channel_id = self.config.exchanger_faq_channel
        if not channel_id:
            logger.warning("⏭️  Exchanger FAQ: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Exchanger FAQ: Channel {channel_id} not found")
            return

        logger.info("❓ Deploying Exchanger FAQ Panel...")
        await self._clear_channel(channel, "Exchanger FAQ")

        server_name = "AfrooExch"

        description = (
            f"## Welcome to {server_name} — Exchanger Guide\n\n"
            f"**As an Exchanger, you operate as an independent service provider** within the {server_name} platform. "
            f"You're responsible for handling client exchanges, managing your own liquidity deposits, and ensuring smooth, "
            f"professional transactions. This guide explains everything you need to succeed.\n\n"
            f"> Understanding how the exchanger system works is crucial for your success and reputation.\n\n"
        )

        embed = create_embed(
            title="",
            description=description,
            color=PURPLE_GRADIENT
        )

        # Getting Started
        embed.add_field(
            name="**Getting Started**",
            value=(
                "*Your first steps as an exchanger:*\n\n"
                f"> **Access the Exchanger Panel** in <#{self.config.exchanger_panel_channel if self.config.exchanger_panel_channel else 'exchanger-panel'}>\n"
                "> **Deposit crypto** to establish your claim limit and start accepting tickets\n"
                "> **Claim tickets** up to your available balance to help clients exchange safely\n"
                "> **Build reputation** by completing exchanges professionally and efficiently\n\n"
            ),
            inline=False
        )

        # Exchanger Panel Overview
        embed.add_field(
            name="**Exchanger Panel Overview**",
            value=(
                "*The panel is your command center. Here's what each feature does:*\n\n"
                "> **Deposit** - Generate wallet addresses to add crypto liquidity (increases claim limit)\n"
                "> **My Balance & Active Holds** - View total balance, available funds, and locked funds in claimed tickets\n"
                "> **Withdraw** - Cash out your earnings to external wallets anytime (if not locked in tickets)\n"
                "> **History** - Review all deposits, withdrawals, holds, and completed exchanges\n"
                "> **Refresh** - Manually sync balances from blockchain (deposits update automatically)\n"
                "> **Ask Question** - Open support ticket to contact staff for help or clarification\n"
                "> **Ping Preferences** - Configure which ticket types you want to be notified about\n\n"
                "**Supported Coins:**\n"
                "> BTC • LTC • SOL • ETH • USDT-ETH • USDT-SOL • USDC-ETH • USDC-SOL\n\n"
            ),
            inline=False
        )

        # Ticket Workflow
        embed.add_field(
            name="**Ticket Workflow — Complete Exchange Process**",
            value=(
                "*Follow this step-by-step process for every exchange:*\n\n"
                "**1. Client Opens Ticket**\n"
                "> A client creates an exchange request specifying crypto, payment method, and amount.\n\n"
                "**2. Client Accepts TOS**\n"
                "> The client must accept Terms of Service before the ticket becomes claimable.\n\n"
                "**3. Claiming a Ticket**\n"
                "> You click \"Claim Ticket\" — this locks the required crypto amount from your balance.\n"
                "> Your available balance decreases, but total balance stays the same (funds are held).\n"
                "> You can only claim tickets up to your available balance.\n\n"
                "**4. Exchange Panel Appears**\n"
                "> After claiming, an exchange control panel appears with options:\n"
                "> - Request client payment info (via modal form)\n"
                "> - Confirm you received payment from client\n"
                "> - Process crypto payout (internal wallet or external address)\n"
                "> - Contact support if issues arise\n"
                "> - Unclaim ticket (only if necessary, may require admin approval)\n\n"
            ),
            inline=False
        )

        # Ticket Workflow Part 2
        embed.add_field(
            name="**Ticket Workflow — Continued**",
            value=(
                "**5. Client Pays You**\n"
                "> Client sends payment to you via their chosen method (PayPal, CashApp, Venmo, crypto, etc.).\n"
                "> Always verify payment fully clears before proceeding (no pending/holds).\n"
                "> Screenshot/document proof of payment for your records.\n\n"
                "**6. Payout Phase**\n"
                "> Once payment confirmed, you process crypto payout to client:\n"
                "> - **Internal Wallet:** Client has {server_name} wallet — instant, free transfer\n"
                "> - **External Wallet:** Client provides address — blockchain transfer, network fees apply\n"
                "> The held crypto is released from your balance and sent to the client.\n\n"
                "**7. Final Confirmation & Closure**\n"
                "> Client confirms they received their crypto.\n"
                "> Ticket closes automatically.\n"
                "> Your stats update (volume, completed exchanges, earnings).\n"
                "> Funds previously held are now freed (if not immediately paid out).\n\n"
            ),
            inline=False
        )

        # Need Help
        embed.add_field(
            name="**Need Help?**",
            value=(
                "*Support resources available:*\n\n"
                "> Use **Ask Question** in the exchanger panel to contact support staff directly\n"
                f"> Review policies in <#{self.config.exchanger_rules_channel if self.config.exchanger_rules_channel else 'exchanger-rules'}>\n"
                "> Open a support ticket if you encounter issues during an exchange\n\n"
            ),
            inline=False
        )

        embed.set_footer(text=f"Exchanger Guide • {server_name} • {datetime.now(timezone.utc).strftime('%B %Y')}")

        await channel.send(embed=embed)
        logger.info("✅ Exchanger FAQ deployed")

    async def _deploy_exchanger_rules_panel(self, guild: discord.Guild):
        """Deploy Exchanger Rules panel"""
        # Use dedicated exchanger rules channel
        channel_id = self.config.exchanger_rules_channel
        if not channel_id:
            logger.warning("⏭️  Exchanger Rules: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        logger.info("📋 Deploying Exchanger Rules Panel...")
        await self._clear_channel(channel, "Exchanger Rules")

        server_name = "AfrooExch"

        description = (
            f"## EXCHANGER RULES – READ BEFORE TRADING\n\n"
            f"**Mandatory rules for all exchangers.** Violations will result in warnings, suspension, or permanent removal.\n\n"
            f"> These rules ensure safe, professional exchanges for all users.\n\n"
        )

        embed = create_embed(
            title="",
            description=description,
            color=PURPLE_GRADIENT
        )

        # Rules 1-6
        embed.add_field(
            name="**Core Rules (1-6)**",
            value=(
                "**1. Professional Communication**\n"
                "> Always be respectful and professional with clients\n\n"
                "**2. Response Time**\n"
                "> Respond within 15 minutes of claiming a ticket\n\n"
                "**3. No Exit Scamming**\n"
                "> Stealing funds results in permanent ban and legal action\n\n"
                "**4. Accurate Information**\n"
                "> Provide correct payment details to clients\n\n"
                "**5. Ticket System Only**\n"
                "> All exchanges must happen through official tickets\n\n"
                "**6. No False Claims**\n"
                "> Never provide fake transaction IDs or proof\n\n"
            ),
            inline=False
        )

        # Rules 7-12
        embed.add_field(
            name="**Operational Rules (7-12)**",
            value=(
                "**7. Maintain Deposits**\n"
                "> Keep adequate balance to cover claimed tickets\n\n"
                "**8. Complete Tickets Properly**\n"
                "> Only mark complete when exchange is fully finished\n\n"
                "**9. No Unclaiming Without Reason**\n"
                "> Contact support if you need to unclaim a ticket\n\n"
                "**10. Verify Payments**\n"
                "> Confirm receipt before releasing crypto to clients\n\n"
                "**11. Double-Check Addresses**\n"
                "> Verify wallet addresses before sending funds\n\n"
                "**12. Follow Client Instructions**\n"
                "> Read and follow customer requirements carefully\n\n"
            ),
            inline=False
        )

        # Rules 13-18
        embed.add_field(
            name="**Conduct Rules (13-18)**",
            value=(
                "**13. No Customer Arguments**\n"
                "> Let staff handle disputes - never argue publicly\n\n"
                "**14. Report Issues Promptly**\n"
                "> Contact support immediately if problems arise\n\n"
                "**15. Document Everything**\n"
                "> Keep screenshots of payments and communications\n\n"
                "**16. No System Manipulation**\n"
                "> Attempting to abuse the system results in removal\n\n"
                "**17. Stay Available**\n"
                "> Don't claim tickets if you can't complete them\n\n"
                "**18. Clear Communication**\n"
                "> Provide simple, easy-to-follow instructions\n\n"
            ),
            inline=False
        )

        # Rules 19-23
        embed.add_field(
            name="**Consequences & Enforcement (19-23)**",
            value=(
                "**19. First Violation**\n"
                "> Written warning and account review\n\n"
                "**20. Second Violation**\n"
                "> Temporary suspension (7-30 days)\n\n"
                "**21. Third Violation**\n"
                "> Deposit freeze and extended suspension\n\n"
                "**22. Serious Violations**\n"
                "> Immediate exchanger removal and ban\n\n"
                "**23. Fraud or Theft**\n"
                "> Permanent ban, asset seizure, legal action\n\n"
            ),
            inline=False
        )

        embed.set_footer(text=f"Strict Enforcement • {server_name} Exchanger Program • {datetime.now(timezone.utc).strftime('%B %Y')}")

        await channel.send(embed=embed)
        logger.info("✅ Exchanger Rules deployed")

    # ========================================================================
    # INTERACTIVE PANELS (Using existing views)
    # ========================================================================

    async def _deploy_support_panel(self, guild: discord.Guild):
        """Deploy Support panel"""
        channel_id = self.config.support_panel_channel
        if not channel_id:
            logger.warning("⏭️  Support Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Support Panel: Channel {channel_id} not found")
            return

        logger.info("💬 Deploying Support Panel...")
        await self._clear_channel(channel, "Support")

        try:
            from cogs.panels.views.support_panel import SupportPanelView
            from utils.embeds import create_support_panel_embed

            embed = create_support_panel_embed()
            view = SupportPanelView(self.bot)

            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Support Panel deployed")
        except Exception as e:
            logger.error(f"❌ Support Panel failed: {e}")

    async def _deploy_application_panel(self, guild: discord.Guild):
        """Deploy Application panel"""
        channel_id = self.config.application_panel_channel
        if not channel_id:
            logger.warning("⏭️  Application Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Application Panel: Channel {channel_id} not found")
            return

        logger.info("📝 Deploying Application Panel...")
        await self._clear_channel(channel, "Application")

        try:
            from cogs.applications.views.application_panel import ApplicationPanelView

            server_name = "AfrooExch"

            description = (
                f"## Apply to Become an Exchanger\n\n"
                f"**Join our team of trusted exchangers!** Earn money by helping others exchange crypto and fiat safely.\n\n"
                f"> We're looking for reliable, trustworthy individuals to join our exchanger team.\n\n"
            )

            embed = create_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )

            # What is an Exchanger?
            embed.add_field(
                name="**What is an Exchanger?**",
                value=(
                    "*Exchangers facilitate secure crypto and fiat exchanges for clients.*\n\n"
                    "> Help users convert their assets safely\n"
                    "> Earn fees on each transaction you complete\n"
                    "> Build reputation and trust in the community\n\n"
                ),
                inline=False
            )

            # Requirements
            embed.add_field(
                name="**Requirements**",
                value=(
                    "*What you need to apply:*\n\n"
                    "> Active Discord account in good standing\n"
                    "> Ability to maintain crypto deposits for exchanges\n"
                    "> Respond to tickets within reasonable time\n"
                    "> Clean reputation with no scam history\n"
                    "> Access to payment methods (PayPal, CashApp, Venmo, etc.)\n\n"
                ),
                inline=False
            )

            # Benefits
            embed.add_field(
                name="**Benefits of Being an Exchanger**",
                value=(
                    "*Why become an exchanger?*\n\n"
                    "> `Earn 10%` of all transactions you complete\n"
                    "> `Minimum $4` per ticket guaranteed\n"
                    "> `Build Reputation:` Gain vouches and trust in the community\n"
                    "> `Exclusive Access:` Exchanger-only channels and perks\n"
                    "> `Priority Support:` Direct staff assistance when needed\n"
                    "> `Flexible Schedule:` Work whenever you're available\n"
                    "> `Growth Potential:` Higher volume = higher earnings\n\n"
                ),
                inline=False
            )

            # How Deposits Work
            embed.add_field(
                name="**How Deposits Work**",
                value=(
                    "*Ensuring client safety through escrow:*\n\n"
                    "> Exchangers deposit crypto into our escrow system\n"
                    "> Deposit locks when you claim a ticket\n"
                    "> Released after successful completion\n"
                    "> `Withdraw anytime` when not locked in active exchanges\n\n"
                ),
                inline=False
            )

            # Application Process
            embed.add_field(
                name="**Application Process**",
                value=(
                    "*Follow these steps to apply:*\n\n"
                    "> `1.` Click the **Apply Now** button below\n"
                    "> `2.` Fill out the application form in your ticket\n"
                    "> `3.` Staff reviews your application (24-48 hours)\n"
                    "> `4.` If approved, complete exchanger onboarding\n"
                    "> `5.` Deposit crypto and start claiming tickets!\n\n"
                ),
                inline=False
            )

            # What We're Looking For
            embed.add_field(
                name="**What We're Looking For**",
                value=(
                    "*Qualities of a great exchanger:*\n\n"
                    "> Professional and respectful communication\n"
                    "> Reliable and responsive to client needs\n"
                    "> Honest and transparent in all dealings\n"
                    "> Committed to following server rules\n"
                    "> Willing to learn and improve\n\n"
                ),
                inline=False
            )

            embed.set_footer(text=f"We carefully review all applications • {datetime.now(timezone.utc).strftime('%B %Y')}")

            view = ApplicationPanelView(self.bot)
            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Application Panel deployed")
        except Exception as e:
            logger.error(f"❌ Application Panel failed: {e}")

    async def _deploy_leaderboard_panel(self, guild: discord.Guild):
        """Deploy Leaderboard panel"""
        channel_id = self.config.leaderboard_channel
        if not channel_id:
            logger.warning("⏭️  Leaderboard Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Leaderboard Panel: Channel {channel_id} not found")
            return

        logger.info("🏆 Deploying Leaderboard Panel...")
        await self._clear_channel(channel, "Leaderboard")

        try:
            from cogs.leaderboard.views.leaderboard_view import LeaderboardView

            server_name = "AfrooExch"

            description = (
                "Check out the 4 different leaderboards on our website at http://afrooexchange.com/leaderboard to see live stats and rankings.\n\n"
                "View the Top Clients by exchange volume, Top Exchangers by completed trades, Top Swappers by swap activity, and Top AutoMM users by escrow transactions."
            )

            embed = create_embed(
                title="Leaderboard",
                description=description,
                color=PURPLE_GRADIENT
            )

            embed.set_footer(text=f"Last Updated: November 2025 | {server_name} Exchange")

            view = LeaderboardView()
            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Leaderboard Panel deployed")
        except Exception as e:
            logger.error(f"❌ Leaderboard Panel failed: {e}")

    async def _deploy_exchange_panel(self, guild: discord.Guild):
        """Deploy Exchange panel V2"""
        channel_id = self.config.exchange_channel
        if not channel_id:
            logger.warning("⏭️  Exchange Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Exchange Panel: Channel {channel_id} not found")
            return

        logger.info("🚀 Deploying Exchange Panel (Thread-based)...")
        await self._clear_channel(channel, "Exchange")

        try:
            from cogs.tickets.views.exchange_panel import send_exchange_panel

            # Use the proven working panel (adapted for threads)
            await send_exchange_panel(channel)
            logger.info("✅ Exchange Panel V2 deployed")
        except Exception as e:
            logger.error(f"❌ Exchange Panel V2 failed: {e}")

    async def _deploy_swap_panel(self, guild: discord.Guild):
        """Deploy Swap panel"""
        channel_id = self.config.swap_panel_channel
        if not channel_id:
            logger.warning("⏭️  Swap Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Swap Panel: Channel {channel_id} not found")
            return

        logger.info("🔄 Deploying Swap Panel...")
        await self._clear_channel(channel, "Swap")

        try:
            from cogs.panels.views.swap_panel import SwapPanelView

            server_name = "AfrooExch"

            description = (
                f"## 🔄 Afroo Swap\n\n"
                f"**Instant cryptocurrency swaps** with support for 1000+ mainstream coins.\n\n"
                f"> Swap crypto assets instantly at competitive market rates.\n\n"
            )

            embed = create_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )

            # Key Features
            embed.add_field(
                name="**Key Features**",
                value=(
                    "*Why use Afroo Swap:*\n\n"
                    "> `1000+ Coins:` Supports all major cryptocurrencies\n"
                    "> `Competitive Rates:` Best market exchange rates\n"
                    "> `Fast Processing:` Most swaps complete in 5-30 minutes\n"
                    "> `Secure:` Private ticket system with QR codes\n\n"
                ),
                inline=False
            )

            # How It Works
            embed.add_field(
                name="**How It Works**",
                value=(
                    "*Complete swaps in minutes:*\n\n"
                    "> `1.` Click **🔄 Start Swap** below\n"
                    "> `2.` Enter currencies, amount, and destination address\n"
                    "> `3.` Review exchange rate and estimated output\n"
                    "> `4.` Private ticket created with deposit address\n"
                    "> `5.` Send crypto and receive swapped funds\n\n"
                ),
                inline=False
            )

            # Important Notes
            embed.add_field(
                name="**Important Notes**",
                value=(
                    "*Before swapping:*\n\n"
                    "> Supports BTC, ETH, SOL, LTC, USDT, USDC, and 1000+ more\n"
                    "> Provide valid destination address for receiving crypto\n"
                    "> Exchange rates valid for 30 seconds\n"
                    "> Network fees apply to all transactions\n\n"
                ),
                inline=False
            )

            embed.set_footer(text=f"Secure & Fast • {datetime.now(timezone.utc).strftime('%B %Y')}")

            view = SwapPanelView(self.bot)
            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Swap Panel deployed")
        except Exception as e:
            logger.error(f"❌ Swap Panel failed: {e}")

    async def _deploy_automm_panel(self, guild: discord.Guild):
        """Deploy AutoMM panel"""
        channel_id = self.config.automm_panel_channel
        if not channel_id:
            logger.warning("⏭️  AutoMM Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ AutoMM Panel: Channel {channel_id} not found")
            return

        logger.info("🤝 Deploying AutoMM Panel...")
        await self._clear_channel(channel, "AutoMM")

        try:
            from cogs.automm.views.automm_panel import AutoMMPanelView

            server_name = "AfrooExch"

            description = (
                f"## P2P Escrow Service\n\n"
                f"**Secure peer-to-peer cryptocurrency transactions** with automated escrow protection.\n\n"
                f"> Trade safely with anyone using our trusted middleman service.\n\n"
            )

            embed = create_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )

            # What is AutoMM
            embed.add_field(
                name="**What is AutoMM?**",
                value=(
                    "*Automated middleman for safe P2P trading:*\n\n"
                    "> Holds crypto in escrow during transactions\n"
                    "> Protects both buyer and seller\n"
                    "> Automated release when conditions met\n"
                    "> Dispute resolution available\n\n"
                ),
                inline=False
            )

            # How It Works
            embed.add_field(
                name="**How It Works**",
                value=(
                    "*Simple escrow process:*\n\n"
                    "> `1.` Parties agree on terms\n"
                    "> `2.` Seller deposits crypto to escrow\n"
                    "> `3.` Buyer sends payment\n"
                    "> `4.` Seller confirms receipt\n"
                    "> `5.` Escrow releases crypto automatically\n\n"
                ),
                inline=False
            )

            # Why Use Escrow
            embed.add_field(
                name="**Benefits**",
                value=(
                    "*Why use escrow:*\n\n"
                    "> `Seller Protection:` Funds secured until payment\n"
                    "> `Buyer Protection:` Only pay when crypto escrowed\n"
                    "> `Dispute Resolution:` Staff assistance available\n"
                    "> `Free Service:` No additional escrow fees\n\n"
                ),
                inline=False
            )

            # Important Notes
            embed.add_field(
                name="**Important Notes**",
                value=(
                    "*Things to know:*\n\n"
                    "> Instant deposit and release\n"
                    "> Both parties must agree to use escrow\n"
                    "> Open disputes within 24 hours if needed\n\n"
                ),
                inline=False
            )

            embed.set_footer(text=f"Safe P2P Trading • {server_name} Escrow • {datetime.now(timezone.utc).strftime('%B %Y')}")

            view = AutoMMPanelView(self.bot)
            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ AutoMM Panel deployed")
        except Exception as e:
            logger.error(f"❌ AutoMM Panel failed: {e}")

    async def _deploy_wallet_panel(self, guild: discord.Guild):
        """Deploy Wallet panel"""
        channel_id = self.config.wallet_panel_channel
        if not channel_id:
            logger.warning("⏭️  Wallet Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Wallet Panel: Channel {channel_id} not found")
            return

        logger.info("💰 Deploying Wallet Panel...")
        await self._clear_channel(channel, "Wallet")

        try:
            from cogs.panels.views.wallet_panel import WalletPanelView

            server_name = "AfrooExch"

            description = (
                f"## Crypto Wallet Management\n\n"
                f"**Your secure cryptocurrency wallet** for deposits, storage, and withdrawals.\n\n"
                f"> Manage your crypto assets safely with our integrated wallet system.\n\n"
            )

            embed = create_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )

            # Wallet Features
            embed.add_field(
                name="**Wallet Features**",
                value=(
                    "*Complete crypto management:*\n\n"
                    "> `Deposit:` Get unique addresses\n"
                    "> `Balance:` View holdings in real-time\n"
                    "> `Withdraw:` Send to external wallets\n"
                    "> `History:` Track all transactions\n"
                    "> `Refresh:` Update from blockchain\n\n"
                ),
                inline=False
            )

            # Supported Assets
            embed.add_field(
                name="**Supported Cryptocurrencies**",
                value=(
                    "*Major assets available:*\n\n"
                    "> `BTC` Bitcoin • `ETH` Ethereum • `LTC` Litecoin\n"
                    "> `SOL` Solana • `USDT` Tether • `USDC` USD Coin\n\n"
                ),
                inline=False
            )

            # Security & Important Notes
            embed.add_field(
                name="**Security & Important Notes**",
                value=(
                    "*Keep your funds safe:*\n\n"
                    "> Secure storage with unique addresses\n"
                    "> Automatic deposit detection\n"
                    "> Network fees apply to withdrawals\n"
                    "> Double-check addresses - transactions are irreversible\n"
                    "> Confirmations required for deposits\n\n"
                ),
                inline=False
            )

            embed.set_footer(text=f"Secure Wallet System • {server_name} • {datetime.now(timezone.utc).strftime('%B %Y')}")

            view = WalletPanelView(self.bot)
            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Wallet Panel deployed")
        except Exception as e:
            logger.error(f"❌ Wallet Panel failed: {e}")

    async def _deploy_dashboard_panel(self, guild: discord.Guild):
        """Deploy Dashboard panel"""
        channel_id = self.config.user_dashboard_channel
        if not channel_id:
            logger.warning("⏭️  Dashboard Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Dashboard Panel: Channel {channel_id} not found")
            return

        logger.info("📊 Deploying Dashboard Panel...")
        await self._clear_channel(channel, "Dashboard")

        try:
            from cogs.dashboard.views.dashboard_panel import DashboardPanelView

            server_name = "AfrooExch"

            description = (
                f"## User Dashboard\n\n"
                f"**Manage your account, track statistics, and protect your data.** All your trading activity and security features in one place.\n\n"
                f"> Your personal command center for account management.\n\n"
            )

            embed = create_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )

            # Account Recovery
            embed.add_field(
                name="**Account Recovery System**",
                value=(
                    f"*Protect your account with a recovery code:*\n\n"
                    f"> Generate a unique recovery code to restore your account\n"
                    f"> `Restores:` Roles, statistics, milestones, deposit balances\n"
                    f"> `Security:` One-time use code with anti-abuse protection\n"
                    f"> Use if you lose access to your Discord account\n\n"
                ),
                inline=False
            )

            # View Statistics
            embed.add_field(
                name="**Your Statistics**",
                value=(
                    f"*Track your complete trading profile:*\n\n"
                    f"> `Exchange Volume:` Total USD volume traded\n"
                    f"> `Trade Count:` Number of completed exchanges\n"
                    f"> `Milestone Progress:` Track your tier advancement\n"
                    f"> `Active Tickets:` Current ongoing exchanges\n"
                    f"> `Exchanger Earnings:` If you're an exchanger\n\n"
                ),
                inline=False
            )

            # Security Best Practices
            embed.add_field(
                name="**Security Best Practices**",
                value=(
                    f"*Keep your account safe:*\n\n"
                    f"> `NEVER SHARE` your recovery code with anyone\n"
                    f"> Store codes in a password manager or encrypted file\n"
                    f"> `DO NOT` save codes on Discord (screenshots or messages)\n"
                    f"> Regenerate your code if you suspect it's compromised\n\n"
                ),
                inline=False
            )

            embed.set_footer(text=f"Account security is your responsibility • {datetime.now(timezone.utc).strftime('%B %Y')}")

            view = DashboardPanelView(self.bot)
            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Dashboard Panel deployed")
        except Exception as e:
            logger.error(f"❌ Dashboard Panel failed: {e}")

    async def _deploy_exchanger_panel(self, guild: discord.Guild):
        """Deploy Exchanger Deposit panel"""
        # Use dedicated exchanger panel channel
        channel_id = self.config.exchanger_panel_channel
        if not channel_id:
            logger.warning("⏭️  Exchanger Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Exchanger Panel: Channel {channel_id} not found")
            return

        logger.info("📥 Deploying Exchanger Panel...")
        await self._clear_channel(channel, "Exchanger")

        try:
            from cogs.panels.views.exchanger_deposit_panel import ExchangerDepositPanelView
            from utils.embeds import create_deposit_panel_embed

            embed = create_deposit_panel_embed()
            view = ExchangerDepositPanelView(self.bot)

            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Exchanger Panel deployed")
        except Exception as e:
            logger.error(f"❌ Exchanger Panel failed: {e}")

    async def _deploy_admin_panel(self, guild: discord.Guild):
        """Deploy Admin panel"""
        channel_id = self.config.admin_panel_channel
        if not channel_id:
            logger.warning("⏭️  Admin Panel: Channel not configured")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"❌ Admin Panel: Channel {channel_id} not found")
            return

        logger.info("⚙️ Deploying Admin Panel...")
        await self._clear_channel(channel, "Admin")

        try:
            from cogs.admin.views.admin_panel import AdminPanelView

            description = (
                f"## Admin Control Panel\n\n"
                f"**Comprehensive system management** for server operations.\n\n"
                f"> All administrative actions are logged and auditable.\n\n"
            )

            embed = create_embed(
                title="",
                description=description,
                color=PURPLE_GRADIENT
            )

            # User Management
            embed.add_field(
                name="**User Management**",
                value=(
                    "*Account control:*\n\n"
                    "> Search exchanger details\n"
                    "> Access wallet information\n"
                    "> Freeze/unfreeze accounts\n"
                    "> View user statistics\n\n"
                ),
                inline=True
            )

            # Fee Manager
            embed.add_field(
                name="**Fee Manager**",
                value=(
                    "*Revenue management:*\n\n"
                    "> Collect pending fees\n"
                    "> Target specific exchangers\n"
                    "> View fee statistics\n"
                    "> Monitor allocations\n\n"
                ),
                inline=True
            )

            # System Operations
            embed.add_field(
                name="**System Operations**",
                value=(
                    "*Platform maintenance:*\n\n"
                    "> Refresh exchanger wallets\n"
                    "> Update allocated funds\n"
                    "> Sync balances\n"
                    "> Database backups\n\n"
                ),
                inline=True
            )

            # Audit & Monitoring
            embed.add_field(
                name="**Audit & Monitoring**",
                value=(
                    "*System oversight:*\n\n"
                    "> View admin actions\n"
                    "> Track withdrawals\n"
                    "> Monitor modifications\n"
                    "> System health checks\n\n"
                ),
                inline=True
            )

            embed.set_footer(text=f"Restricted Access • All Actions Logged • {datetime.now(timezone.utc).strftime('%B %Y')}")

            view = AdminPanelView(self.bot)
            msg = await channel.send(embed=embed, view=view)
            await msg.pin()
            logger.info("✅ Admin Panel deployed")
        except Exception as e:
            logger.error(f"❌ Admin Panel failed: {e}")



def setup(bot: discord.Bot):
    """Load cog"""
    bot.add_cog(AllPanelsCog(bot))
