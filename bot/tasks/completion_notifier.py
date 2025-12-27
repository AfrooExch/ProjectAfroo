"""
Completion Notifier Task - Monitors for completed tickets and sends notifications
Handles DMs, vouch posting, and history channel updates
"""

import discord
import asyncio
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path
import aiofiles

from api.client import APIClient
from utils.embeds import create_themed_embed
from utils.colors import SUCCESS_GREEN, PURPLE_GRADIENT
import config

logger = logging.getLogger(__name__)


class CompletionNotifier:
    """Background task that monitors for completed tickets and sends notifications"""

    def __init__(self, bot: discord.Bot, api: APIClient, bot_config):
        self.bot = bot
        self.api = api
        self.config = bot_config
        self.running = False
        self.task: Optional[asyncio.Task] = None

    def start(self):
        """Start the background task"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._notification_loop())
            logger.info("Completion notifier task started")

    def stop(self):
        """Stop the background task"""
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("Completion notifier task stopped")

    async def _notification_loop(self):
        """Main loop that checks for pending notifications"""
        await self.bot.wait_until_ready()

        while self.running:
            try:
                # Check for pending exchange ticket notifications
                result = await self.api.get(
                    "/api/v1/tickets/pending-notifications",
                    discord_user_id="SYSTEM"
                )

                pending_tickets = result.get("tickets", [])

                for ticket_data in pending_tickets:
                    try:
                        await self._process_completion(ticket_data)
                    except Exception as e:
                        logger.error(f"Error processing completion for ticket {ticket_data.get('_id')}: {e}", exc_info=True)

                # Check for pending swap notifications
                swap_result = await self.api.get(
                    "/api/v1/afroo-swaps/pending-notifications",
                    discord_user_id="SYSTEM"
                )

                pending_swaps = swap_result.get("swaps", [])

                for swap_data in pending_swaps:
                    try:
                        await self._process_swap_completion(swap_data)
                    except Exception as e:
                        logger.error(f"Error processing swap completion {swap_data.get('_id')}: {e}", exc_info=True)

                # Check every 10 seconds
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in completion notification loop: {e}", exc_info=True)
                await asyncio.sleep(30)  # Wait longer on error

    async def _process_completion(self, ticket_data: dict):
        """
        Process completion notifications for a ticket
        Sends DMs, posts vouches, and posts to history channel
        """
        ticket_id = ticket_data.get("_id")
        ticket_number = ticket_data.get("ticket_number")
        notification = ticket_data.get("completion_notification", {})

        logger.info(f"Processing completion notifications for ticket {ticket_number}")

        # Get Discord user objects
        client_discord_id = notification.get("client_discord_id")
        exchanger_discord_id = notification.get("exchanger_discord_id")

        client_user = None
        exchanger_user = None

        try:
            if client_discord_id:
                client_user = await self.bot.fetch_user(int(client_discord_id))
        except Exception as e:
            logger.error(f"Failed to fetch client user {client_discord_id}: {e}")

        try:
            if exchanger_discord_id:
                exchanger_user = await self.bot.fetch_user(int(exchanger_discord_id))
        except Exception as e:
            logger.error(f"Failed to fetch exchanger user {exchanger_discord_id}: {e}")

        # Get transcript and vouch templates
        transcript_html = notification.get("transcript_html", "")
        transcript_text = notification.get("transcript_text", "")
        client_vouch = notification.get("client_vouch_template", "")
        exchanger_vouch = notification.get("exchanger_vouch_template", "")

        # DM Client
        if client_user and transcript_text:
            try:
                await self._dm_completion_transcript(
                    user=client_user,
                    ticket_number=ticket_number,
                    transcript_text=transcript_text,
                    vouch_template=client_vouch,
                    role="client"
                )
                logger.info(f"Ticket {ticket_number}: DM sent to client")
            except Exception as e:
                logger.error(f"Failed to DM client for ticket {ticket_number}: {e}")

        # DM Exchanger
        if exchanger_user and transcript_text:
            try:
                await self._dm_completion_transcript(
                    user=exchanger_user,
                    ticket_number=ticket_number,
                    transcript_text=transcript_text,
                    vouch_template=exchanger_vouch,
                    role="exchanger"
                )
                logger.info(f"Ticket {ticket_number}: DM sent to exchanger")
            except Exception as e:
                logger.error(f"Failed to DM exchanger for ticket {ticket_number}: {e}")

        # Post to history channel
        if transcript_html:
            try:
                await self._post_to_history_channel(
                    ticket_number=ticket_number,
                    ticket_data=ticket_data,
                    transcript_text=transcript_text
                )
                logger.info(f"Ticket {ticket_number}: Posted to history channel")
            except Exception as e:
                logger.error(f"Failed to post to history channel for ticket {ticket_number}: {e}")

        # NOTE: Vouches are sent in DMs only (not posted to rep channel)
        # Users can manually post their vouch in the rep channel if they want
        logger.info(f"Ticket {ticket_number}: Vouch templates sent in DMs (not posted to rep channel)")

        # Mark notification as processed
        try:
            await self.api.post(
                f"/api/v1/tickets/{ticket_id}/mark-notification-processed",
                data={},
                discord_user_id="SYSTEM"
            )
            logger.info(f"Ticket {ticket_number}: Marked notification as processed")
        except Exception as e:
            logger.error(f"Failed to mark notification as processed for ticket {ticket_number}: {e}")

    async def _dm_completion_transcript(
        self,
        user: discord.User,
        ticket_number: int,
        transcript_text: str,
        vouch_template: str,
        role: str
    ):
        """Send completion DM with transcript and vouch template"""

        # Create completion embed
        embed = create_themed_embed(
            title="",
            description=(
                f"## ✅ Exchange Completed - Ticket #{ticket_number}\n\n"
                f"Congratulations! Your exchange has been completed successfully.\n\n"
                f"**Your role:** {role.capitalize()}\n\n"
                f"### 📋 Transcript\n"
                f"See below for the full exchange transcript.\n\n"
                f"### 💬 Vouch Template\n"
                f"A pre-made vouch message has been prepared for you below. "
                f"Feel free to post it in the reputation channel!"
            ),
            color=SUCCESS_GREEN
        )

        try:
            # Send embed
            await user.send(embed=embed)

            # Send transcript as text file
            transcript_file = discord.File(
                fp=transcript_text.encode('utf-8'),
                filename=f"transcript_{ticket_number}.txt"
            )
            await user.send(
                content="**Exchange Transcript:**",
                file=transcript_file
            )

            # Send vouch template
            vouch_embed = create_themed_embed(
                title="",
                description=(
                    f"## 💜 Pre-Made Vouch\n\n"
                    f"Copy and paste this into the reputation channel:\n\n"
                    f"{vouch_template}"
                ),
                color=PURPLE_GRADIENT
            )
            await user.send(embed=vouch_embed)

        except discord.Forbidden:
            logger.warning(f"Cannot DM user {user.id} - DMs are closed")
        except Exception as e:
            logger.error(f"Error sending DM to user {user.id}: {e}")
            raise

    async def _post_to_history_channel(
        self,
        ticket_number: int,
        ticket_data: dict,
        transcript_text: str
    ):
        """Post transcript summary to history channel"""

        history_channel_id = self.config.CHANNEL_EXCHANGE_HISTORY
        if not history_channel_id:
            logger.warning("History channel not configured")
            return

        channel = self.bot.get_channel(history_channel_id)
        if not channel:
            logger.warning(f"History channel {history_channel_id} not found")
            return

        notification = ticket_data.get("completion_notification", {})

        # Create history embed
        embed = create_themed_embed(
            title="",
            description=(
                f"## 📜 Exchange Completed - Ticket #{ticket_number}\n\n"
                f"**Amount:** ${notification.get('amount_usd', 0):,.2f} USD\n"
                f"**Client Received:** ${notification.get('receiving_amount', 0):,.2f} USD\n"
                f"**Server Fee:** ${notification.get('server_fee_collected', 0):.2f} USD\n\n"
                f"**Client:** <@{notification.get('client_discord_id')}>\n"
                f"**Exchanger:** <@{notification.get('exchanger_discord_id')}>\n\n"
                f"**Status:** ✅ Successfully Completed"
            ),
            color=SUCCESS_GREEN
        )

        embed.set_footer(text=f"Completed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Send transcript as file attachment
        transcript_file = discord.File(
            fp=transcript_text.encode('utf-8'),
            filename=f"transcript_{ticket_number}.txt"
        )

        await channel.send(embed=embed, file=transcript_file)

    async def _post_vouches_to_rep_channel(
        self,
        ticket_number: int,
        client_user: Optional[discord.User],
        exchanger_user: Optional[discord.User],
        client_vouch: str,
        exchanger_vouch: str
    ):
        """Post vouch templates to reputation channel"""

        rep_channel_id = self.config.CHANNEL_REP
        if not rep_channel_id:
            logger.warning("Rep channel not configured")
            return

        channel = self.bot.get_channel(rep_channel_id)
        if not channel:
            logger.warning(f"Rep channel {rep_channel_id} not found")
            return

        # Post client's vouch for exchanger
        if client_user:
            client_vouch_embed = create_themed_embed(
                title="",
                description=(
                    f"**{client_user.mention}'s Vouch:**\n\n"
                    f"{client_vouch}"
                ),
                color=PURPLE_GRADIENT
            )
            client_vouch_embed.set_footer(text=f"Exchange Ticket #{ticket_number}")
            await channel.send(embed=client_vouch_embed)

        # Post exchanger's vouch for client
        if exchanger_user:
            exchanger_vouch_embed = create_themed_embed(
                title="",
                description=(
                    f"**{exchanger_user.mention}'s Vouch:**\n\n"
                    f"{exchanger_vouch}"
                ),
                color=PURPLE_GRADIENT
            )
            exchanger_vouch_embed.set_footer(text=f"Exchange Ticket #{ticket_number}")
            await channel.send(embed=exchanger_vouch_embed)

    async def _process_swap_completion(self, swap_data: dict):
        """
        Process completion notifications for a swap
        Sends DM with transcript, posts vouch message in ticket channel, posts to history channel with transcript
        """
        swap_id = swap_data.get("_id")
        user_id = swap_data.get("user_id")

        logger.info(f"Processing swap completion for swap {swap_id}")

        # Get swap channel
        from_asset = swap_data.get("from_asset")
        to_asset = swap_data.get("to_asset")
        input_amount = swap_data.get("input_amount")
        actual_output = swap_data.get("actual_output", swap_data.get("estimated_output"))
        payout_hash = swap_data.get("payout_hash")
        payout_link = swap_data.get("payout_link")
        destination_address = swap_data.get("destination_address", "N/A")

        # Truncate addresses
        dest_addr_display = destination_address if len(destination_address) <= 20 else f"{destination_address[:10]}...{destination_address[-6:]}"

        # Get user
        user = None
        try:
            if user_id:
                user = await self.bot.fetch_user(int(user_id))
        except Exception as e:
            logger.error(f"Failed to fetch user {user_id}: {e}")

        # Find swap channel (format: swap-username-swapidshort)
        swap_channel = None
        guild = self.bot.get_guild(self.config.GUILD_ID)
        if guild:
            swap_id_short = swap_id[:8]
            for channel in guild.text_channels:
                if f"swap-" in channel.name and swap_id_short in channel.name:
                    swap_channel = channel
                    break

        # Generate transcript
        transcript_html = None
        transcript_text = None
        if swap_channel:
            try:
                # Fetch all messages
                messages = []
                async for msg in swap_channel.history(limit=500, oldest_first=True):
                    messages.append(msg)

                if messages:
                    # Generate HTML transcript
                    from utils.swap_transcript import generate_swap_transcript_html

                    transcript_html = generate_swap_transcript_html(
                        swap_id=swap_id,
                        messages=messages,
                        swap_data=swap_data,
                        opened_by=user if user else messages[0].author,
                        closed_at=datetime.utcnow()
                    )

                    # Generate text transcript
                    transcript_text = f"Swap Transcript - {swap_id}\n"
                    transcript_text += f"Swap: {input_amount} {from_asset} → {actual_output:.8f} {to_asset}\n"
                    transcript_text += f"User: {user.name if user else 'Unknown'}\n"
                    transcript_text += f"Completed: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}\n"
                    transcript_text += "\n" + "="*80 + "\n\n"

                    for msg in messages:
                        if msg.type == discord.MessageType.default:
                            timestamp = msg.created_at.strftime("%I:%M %p")
                            transcript_text += f"[{timestamp}] {msg.author.name}: {msg.content}\n"

                    logger.info(f"Generated transcript for swap {swap_id}")

            except Exception as e:
                logger.error(f"Failed to generate transcript for swap {swap_id}: {e}", exc_info=True)

        # Generate pre-made vouch in +rep format
        bot_user = self.bot.user
        bot_mention = bot_user.mention if bot_user else "@Afroo Exchange"

        # Calculate USD value (rough estimate)
        from_asset_usd_rates = {
            "BTC": 90000, "ETH": 3200, "SOL": 150, "LTC": 85,
            "USDT-SOL": 1, "USDT-ETH": 1, "USDC-SOL": 1, "USDC-ETH": 1
        }
        base_asset = from_asset.split('-')[0] if '-' in from_asset else from_asset
        usd_rate = from_asset_usd_rates.get(base_asset, 1)
        amount_usd = input_amount * usd_rate

        vouch_text = f"+rep {bot_mention} ${amount_usd:.2f} {from_asset} to {to_asset}"

        # Post completion message in swap ticket channel
        if swap_channel:
            try:
                completion_embed = create_themed_embed(
                    title="",
                    description=(
                        f"## Swap Completed\n\n"
                        f"Congratulations {user.mention if user else 'User'}, your swap has been completed successfully!\n\n"
                        f"**You Sent:** `{input_amount} {from_asset}`\n"
                        f"**You Received:** `{actual_output:.8f} {to_asset}`\n"
                        f"**Destination:** `{dest_addr_display}`\n\n"
                        f"**Transaction Hash:** `{payout_hash or 'N/A'}`\n"
                        + (f"[View Transaction]({payout_link})\n\n" if payout_link else "\n")
                        + f"**Pre-Made Vouch:**\n```\n{vouch_text}\n```\n\n"
                        + f"Feel free to post this in the reputation channel!"
                    ),
                    color=SUCCESS_GREEN
                )
                await swap_channel.send(embed=completion_embed)
                logger.info(f"Swap {swap_id}: Completion message posted to ticket")
            except Exception as e:
                logger.error(f"Failed to post completion in swap channel: {e}")

        # DM User with transcript
        if user and transcript_text:
            try:
                dm_embed = create_themed_embed(
                    title="",
                    description=(
                        f"## Swap Completed\n\n"
                        f"Your swap has been completed successfully.\n\n"
                        f"**Swap ID:** `{swap_id}`\n"
                        f"**You Sent:** `{input_amount} {from_asset}`\n"
                        f"**You Received:** `{actual_output:.8f} {to_asset}`\n"
                        f"**Destination:** `{dest_addr_display}`\n\n"
                        f"**Transaction Hash:**\n`{payout_hash or 'N/A'}`\n"
                        + (f"\n[View Transaction]({payout_link})\n\n" if payout_link else "\n\n")
                        + f"**Pre-Made Vouch:**\n```\n{vouch_text}\n```"
                    ),
                    color=SUCCESS_GREEN
                )
                await user.send(embed=dm_embed)

                # Send transcript as file
                transcript_file = discord.File(
                    fp=transcript_text.encode('utf-8'),
                    filename=f"swap_{swap_id[:8]}_transcript.txt"
                )
                await user.send(content="**Swap Transcript:**", file=transcript_file)

                logger.info(f"Swap {swap_id}: DM with transcript sent to user")
            except discord.Forbidden:
                logger.warning(f"Cannot DM user {user_id} - DMs are closed")
            except Exception as e:
                logger.error(f"Failed to DM user for swap {swap_id}: {e}")

        # Post to history channel with transcript
        try:
            await self._post_swap_to_history(swap_data, user, transcript_text)
            logger.info(f"Swap {swap_id}: Posted to history channel")
        except Exception as e:
            logger.error(f"Failed to post swap to history channel: {e}")

        # NOTE: Vouches are sent in DMs only (not posted to rep channel)
        # Users can manually post their vouch in the rep channel if they want
        logger.info(f"Swap {swap_id}: Vouch template sent in DM (not posted to rep channel)")

        # Schedule channel deletion after 2 hours
        if swap_channel:
            try:
                asyncio.create_task(self._schedule_swap_channel_deletion(swap_channel, swap_id))
                logger.info(f"Swap {swap_id}: Scheduled channel deletion in 2 hours")
            except Exception as e:
                logger.error(f"Failed to schedule channel deletion for swap {swap_id}: {e}")

        # Mark notification as processed
        try:
            await self.api.post(
                f"/api/v1/afroo-swaps/{swap_id}/mark-notification-processed",
                data={},
                discord_user_id="SYSTEM"
            )
            logger.info(f"Swap {swap_id}: Marked notification as processed")
        except Exception as e:
            logger.error(f"Failed to mark swap notification as processed: {e}")

    async def _schedule_swap_channel_deletion(self, channel: discord.TextChannel, swap_id: str):
        """Delete swap channel after 2 hours"""
        try:
            # Wait 2 hours
            await asyncio.sleep(7200)  # 2 hours = 7200 seconds

            # Delete channel
            await channel.delete(reason=f"Swap {swap_id} completed - auto-cleanup after 2 hours")
            logger.info(f"Deleted swap channel for {swap_id} after 2 hours")

        except Exception as e:
            logger.error(f"Failed to delete swap channel for {swap_id}: {e}")

    async def _post_swap_to_history(self, swap_data: dict, user: Optional[discord.User], transcript_text: Optional[str] = None):
        """Post swap summary to history channel with transcript"""

        history_channel_id = self.config.CHANNEL_EXCHANGE_HISTORY
        if not history_channel_id:
            logger.warning("History channel not configured")
            return

        channel = self.bot.get_channel(history_channel_id)
        if not channel:
            logger.warning(f"History channel {history_channel_id} not found")
            return

        swap_id = swap_data.get("_id")
        from_asset = swap_data.get("from_asset")
        to_asset = swap_data.get("to_asset")
        input_amount = swap_data.get("input_amount")
        actual_output = swap_data.get("actual_output", swap_data.get("estimated_output"))
        payout_hash = swap_data.get("payout_hash", "N/A")

        # Fetch user if not provided
        if not user:
            user_id = swap_data.get("user_id")
            if user_id:
                try:
                    # Handle both string Discord IDs and MongoDB ObjectIds
                    # Try to get discord_id from user document
                    from app.core.database import get_users_collection
                    from bson import ObjectId

                    users = get_users_collection()
                    user_doc = await users.find_one({"_id": ObjectId(user_id)})

                    if user_doc and user_doc.get("discord_id"):
                        user = await self.bot.fetch_user(int(user_doc["discord_id"]))
                except Exception as e:
                    logger.error(f"Failed to fetch user for swap history: {e}")

        # Create history embed with purple gradient
        embed = create_themed_embed(
            title="",
            description=(
                f"## 💜 Swap Completed - ID: `{swap_id[:8]}`\n\n"
                f"**User:** {user.mention if user else '*User Not Found*'}\n"
                f"**Swap:** `{input_amount} {from_asset}` → `{actual_output:.8f} {to_asset}`\n"
                f"**Transaction:** `{payout_hash}`\n\n"
                f"**Status:** ✅ Successfully Completed"
            ),
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text=f"Completed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Send with transcript if available
        if transcript_text:
            transcript_file = discord.File(
                fp=transcript_text.encode('utf-8'),
                filename=f"swap_{swap_id[:8]}_transcript.txt"
            )
            await channel.send(embed=embed, file=transcript_file)
        else:
            await channel.send(embed=embed)

    async def _post_swap_vouch_to_rep_channel(self, swap_data: dict, user: discord.User, vouch_text: str):
        """Post vouch to reputation channel"""

        rep_channel_id = self.config.CHANNEL_REP
        if not rep_channel_id:
            logger.warning("Rep channel not configured")
            return

        channel = self.bot.get_channel(rep_channel_id)
        if not channel:
            logger.warning(f"Rep channel {rep_channel_id} not found")
            return

        swap_id = swap_data.get("_id")

        # Post vouch
        vouch_embed = create_themed_embed(
            title="",
            description=(
                f"**{user.mention}'s Swap Vouch:**\n\n"
                f"{vouch_text}"
            ),
            color=PURPLE_GRADIENT
        )
        vouch_embed.set_footer(text=f"Swap ID: {swap_id[:8]}")

        await channel.send(embed=vouch_embed)
