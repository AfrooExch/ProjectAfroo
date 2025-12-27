"""
Moderation Cog - Server moderation and logging
Handles message logging, member tracking, welcome messages, and auto-protection
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime
from typing import Optional

from config import config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED

logger = logging.getLogger(__name__)


class ModerationCog(commands.Cog):
    """
    Moderation system for server management

    Features:
        - Message edit/delete logging
        - Member join/leave logging
        - Welcome DM to new members
        - Role/nickname change logging
        - Auto-ban impersonators
    """

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        logger.info("Moderation cog loaded")

        # Whitelisted user IDs (immune to impersonator ban)
        self.whitelisted_users = {
            1419744557054169128,  # You
            1401506804873302076,
            972700026423894036,
            537080477631119360,
            483994863818244096,
            1436864167108673617,  # Bot itself
            1440057552921694249   # Added whitelist
        }

        # Impersonator detection patterns (case-insensitive)
        self.banned_name_patterns = [
            "afrooexchange",
            "afrooexch",
            "afroo",
            "exchange mod"
        ]

        # Admin user ID for impersonator alerts
        self.admin_user_id = 1419744557054169128

    @commands.Cog.listener()
    async def on_ready(self):
        """Setup on bot ready"""
        logger.info("Moderation system initialized")

    # ==================== MESSAGE LOGGING ====================

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log edited messages"""
        # Ignore bots
        if before.author.bot:
            return

        # Ignore if content didn't change
        if before.content == after.content:
            return

        # Get message logs channel
        log_channel_id = config.CHANNEL_MESSAGE_LOGS
        log_channel = before.guild.get_channel(log_channel_id)

        if not log_channel:
            return

        try:
            # Create clean embed
            embed = create_themed_embed(
                title="Message Edited",
                description=(
                    f"**Author:** {before.author.mention} (`{before.author.name}`)\n"
                    f"**Channel:** {before.channel.mention}\n"
                    f"**Message ID:** `{before.id}`\n\n"
                    f"**Before:**\n{before.content[:1000] if before.content else '*No content*'}\n\n"
                    f"**After:**\n{after.content[:1000] if after.content else '*No content*'}"
                ),
                color=PURPLE_GRADIENT
            )

            embed.set_footer(text=f"User ID: {before.author.id}")
            embed.timestamp = datetime.utcnow()

            await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging message edit: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log deleted messages"""
        # Ignore bots
        if message.author.bot:
            return

        # Get message logs channel
        log_channel_id = config.CHANNEL_MESSAGE_LOGS
        log_channel = message.guild.get_channel(log_channel_id)

        if not log_channel:
            return

        try:
            # Create clean embed
            embed = create_themed_embed(
                title="Message Deleted",
                description=(
                    f"**Author:** {message.author.mention} (`{message.author.name}`)\n"
                    f"**Channel:** {message.channel.mention}\n"
                    f"**Message ID:** `{message.id}`\n\n"
                    f"**Content:**\n{message.content[:1000] if message.content else '*No content*'}"
                ),
                color=ERROR_RED
            )

            # Add attachments info if any
            if message.attachments:
                attachment_info = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments])
                embed.add_field(
                    name="Attachments",
                    value=attachment_info[:1024],
                    inline=False
                )

            embed.set_footer(text=f"User ID: {message.author.id}")
            embed.timestamp = datetime.utcnow()

            await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging message delete: {e}")

    # ==================== MEMBER LOGGING ====================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member joins - log, send welcome DM, check for impersonators"""

        # Check for impersonators first (before they can do anything)
        await self._check_impersonator(member)

        # Log member join
        await self._log_member_join(member)

        # Send welcome DM
        await self._send_welcome_dm(member)

    async def _log_member_join(self, member: discord.Member):
        """Log member joins to member logs channel"""
        log_channel_id = config.CHANNEL_MEMBER_LOGS
        log_channel = member.guild.get_channel(log_channel_id)

        if not log_channel:
            return

        try:
            embed = create_themed_embed(
                title="Member Joined",
                description=(
                    f"**User:** {member.mention} (`{member.name}`)\n"
                    f"**User ID:** `{member.id}`\n"
                    f"**Member Count:** {member.guild.member_count}"
                ),
                color=SUCCESS_GREEN
            )

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = datetime.utcnow()

            await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging member join: {e}")

    async def _send_welcome_dm(self, member: discord.Member):
        """Send welcome DM to new members"""
        try:
            embed = create_themed_embed(
                title="Welcome to Afroo Exchange",
                description=(
                    f"Welcome {member.mention}! Please verify in <#1427356965100851241> to gain full access.\n\n"
                    f"**What We Offer:**\n"
                    f"• Low fee exchanges for all payment methods\n"
                    f"• No KYC wallet supporting 20+ coins\n"
                    f"• No KYC swap with $1 minimum\n"
                    f"• Lowest fees on the market\n"
                    f"• And many other services\n\n"
                    f"We look forward to serving you!"
                ),
                color=PURPLE_GRADIENT
            )

            await member.send(embed=embed)
            logger.info(f"Welcome DM sent to {member.name} ({member.id})")

        except discord.Forbidden:
            logger.warning(f"Could not DM {member.name} ({member.id}) - DMs closed")
        except Exception as e:
            logger.error(f"Error sending welcome DM to {member.name}: {e}")

    async def _check_impersonator(self, member: discord.Member):
        """Check if member is impersonating and ban if detected"""
        # Skip whitelisted users
        if member.id in self.whitelisted_users:
            return

        # Check both username and display name (case-insensitive)
        username_lower = member.name.lower().replace(" ", "")
        display_name_lower = member.display_name.lower().replace(" ", "")

        is_impersonator = False
        matched_pattern = None

        for pattern in self.banned_name_patterns:
            if pattern in username_lower or pattern in display_name_lower:
                is_impersonator = True
                matched_pattern = pattern
                break

        if is_impersonator:
            try:
                # Ban the impersonator
                await member.ban(reason=f"Impersonation detected - matched pattern: {matched_pattern}")

                logger.warning(
                    f"BANNED IMPERSONATOR: {member.name} ({member.id}) - "
                    f"Display: {member.display_name} - Matched: {matched_pattern}"
                )

                # DM admin with details
                await self._alert_admin_impersonator(member, matched_pattern)

            except Exception as e:
                logger.error(f"Error banning impersonator {member.name}: {e}")

    async def _alert_admin_impersonator(self, member: discord.Member, pattern: str):
        """Alert admin about banned impersonator"""
        try:
            admin = await self.bot.fetch_user(self.admin_user_id)

            embed = create_themed_embed(
                title="Impersonator Banned",
                description=(
                    f"**User:** {member.name}\n"
                    f"**Display Name:** {member.display_name}\n"
                    f"**User ID:** `{member.id}`\n"
                    f"**Matched Pattern:** `{pattern}`\n"
                    f"**Account Created:** <t:{int(member.created_at.timestamp())}:R>"
                ),
                color=ERROR_RED
            )

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = datetime.utcnow()

            await admin.send(embed=embed)
            logger.info(f"Impersonator alert sent to admin for {member.name}")

        except Exception as e:
            logger.error(f"Error alerting admin about impersonator: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        log_channel_id = config.CHANNEL_MEMBER_LOGS
        log_channel = member.guild.get_channel(log_channel_id)

        if not log_channel:
            return

        try:
            embed = create_themed_embed(
                title="Member Left",
                description=(
                    f"**User:** {member.mention} (`{member.name}`)\n"
                    f"**User ID:** `{member.id}`\n"
                    f"**Member Count:** {member.guild.member_count}"
                ),
                color=ERROR_RED
            )

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = datetime.utcnow()

            await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging member leave: {e}")

    # ==================== MEMBER UPDATE LOGGING ====================

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member role and nickname changes"""
        log_channel_id = config.CHANNEL_MEMBER_LOGS
        log_channel = before.guild.get_channel(log_channel_id)

        if not log_channel:
            return

        try:
            changes = []

            # Check for role changes
            if before.roles != after.roles:
                added_roles = [role for role in after.roles if role not in before.roles]
                removed_roles = [role for role in before.roles if role not in after.roles]

                if added_roles:
                    changes.append(f"**Roles Added:** {', '.join([r.mention for r in added_roles])}")
                if removed_roles:
                    changes.append(f"**Roles Removed:** {', '.join([r.mention for r in removed_roles])}")

            # Check for nickname change
            if before.nick != after.nick:
                changes.append(
                    f"**Nickname Changed:**\n"
                    f"Before: `{before.nick or 'None'}`\n"
                    f"After: `{after.nick or 'None'}`"
                )

            # Only log if there were changes we care about
            if changes:
                embed = create_themed_embed(
                    title="Member Updated",
                    description=(
                        f"**User:** {after.mention} (`{after.name}`)\n"
                        f"**User ID:** `{after.id}`\n\n"
                        + "\n\n".join(changes)
                    ),
                    color=PURPLE_GRADIENT
                )

                embed.timestamp = datetime.utcnow()

                await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging member update: {e}")

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Log username changes"""
        # Only log if username changed
        if before.name == after.name:
            return

        log_channel_id = config.CHANNEL_MEMBER_LOGS

        # Get the guild to access the log channel
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        try:
            embed = create_themed_embed(
                title="Username Changed",
                description=(
                    f"**User:** {after.mention}\n"
                    f"**User ID:** `{after.id}`\n\n"
                    f"**Before:** `{before.name}`\n"
                    f"**After:** `{after.name}`"
                ),
                color=PURPLE_GRADIENT
            )

            embed.set_thumbnail(url=after.display_avatar.url)
            embed.timestamp = datetime.utcnow()

            await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging username change: {e}")


def setup(bot: discord.Bot):
    """Required function to load cog"""
    bot.add_cog(ModerationCog(bot))
