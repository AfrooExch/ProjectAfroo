"""
Ticket Sync Task - Auto-closes ghost tickets
Runs every 15 minutes to check Discord channels and close tickets that no longer exist
"""

import discord
import logging
from datetime import datetime
from typing import List, Set
import asyncio

logger = logging.getLogger(__name__)


class TicketSyncTask:
    """Background task to sync tickets with Discord channels"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.api = bot.api_client
        self.is_running = False

    async def start(self):
        """Start the ticket sync task"""
        if self.is_running:
            logger.warning("Ticket sync task is already running")
            return

        self.is_running = True
        logger.info("Starting ticket sync task (runs every 15 minutes)")

        while self.is_running:
            try:
                await self.sync_tickets()
            except Exception as e:
                logger.error(f"Error in ticket sync task: {e}", exc_info=True)

            # Wait 15 minutes before next sync
            await asyncio.sleep(900)  # 900 seconds = 15 minutes

    async def stop(self):
        """Stop the ticket sync task"""
        self.is_running = False
        logger.info("Stopping ticket sync task")

    async def sync_tickets(self):
        """
        Sync tickets with Discord channels
        - Get all active tickets from database
        - Get all ticket channels from Discord
        - Close tickets that don't have channels
        - Release held funds
        """
        try:
            logger.info("Running ticket sync...")

            # Get guild
            from config import config
            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                logger.error(f"Guild {config.guild_id} not found")
                return

            # Get Discord ticket channels
            discord_ticket_ids = await self._get_discord_ticket_ids(guild, config)

            # Get active tickets from database
            db_tickets = await self._get_active_tickets()

            # Find ghost tickets (in DB but not in Discord)
            ghost_tickets = []
            for ticket in db_tickets:
                ticket_id = ticket.get("ticket_id")
                if ticket_id and ticket_id not in discord_ticket_ids:
                    ghost_tickets.append(ticket)

            if not ghost_tickets:
                logger.info("No ghost tickets found")
                return

            logger.warning(f"Found {len(ghost_tickets)} ghost ticket(s) to close")

            # Close ghost tickets
            closed_count = 0
            for ticket in ghost_tickets:
                try:
                    await self._close_ghost_ticket(ticket)
                    closed_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to close ghost ticket {ticket.get('ticket_id')}: {e}",
                        exc_info=True
                    )

            logger.info(f"Closed {closed_count}/{len(ghost_tickets)} ghost ticket(s)")

        except Exception as e:
            logger.error(f"Ticket sync failed: {e}", exc_info=True)

    async def _get_discord_ticket_ids(
        self,
        guild: discord.Guild,
        config
    ) -> Set[str]:
        """
        Get all ticket IDs from Discord channels

        Args:
            guild: Discord guild
            config: Bot config

        Returns:
            Set of ticket IDs from channel names (e.g., "1234" from "ticket-1234")
        """
        ticket_ids = set()

        # Check both ticket categories
        categories_to_check = [
            config.CATEGORY_TICKETS,  # Unclaimed tickets
            config.CATEGORY_CLAIMED_TICKETS  # Claimed/active tickets
        ]

        for category_id in categories_to_check:
            category = guild.get_channel(category_id)
            if not category:
                logger.warning(f"Category {category_id} not found")
                continue

            # Get all channels in category
            for channel in category.channels:
                # Extract ticket ID from channel name (e.g., "ticket-1234" -> "1234")
                if channel.name.startswith("ticket-"):
                    ticket_id = channel.name.replace("ticket-", "")
                    ticket_ids.add(ticket_id)

        logger.info(f"Found {len(ticket_ids)} ticket channels in Discord")
        return ticket_ids

    async def _get_active_tickets(self) -> List[dict]:
        """
        Get all active tickets from database

        Returns:
            List of active ticket documents
        """
        try:
            # Get tickets with statuses that should have channels
            response = await self.api._request(
                "GET",
                "/api/v1/tickets/admin/all",
                params={
                    "status": "open,awaiting_claim,claimed,in_progress",
                    "limit": 1000
                },
                discord_user_id="SYSTEM"
            )

            tickets = response.get("tickets", [])
            logger.info(f"Found {len(tickets)} active tickets in database")
            return tickets

        except Exception as e:
            logger.error(f"Failed to get active tickets: {e}", exc_info=True)
            return []

    async def _close_ghost_ticket(self, ticket: dict):
        """
        Close a ghost ticket and release held funds

        Args:
            ticket: Ticket document from database
        """
        ticket_id = ticket.get("ticket_id")
        ticket_number = ticket.get("ticket_number")

        logger.info(
            f"Closing ghost ticket #{ticket_number} (ID: {ticket_id}) - "
            f"Channel not found in Discord"
        )

        try:
            # Close ticket via API (this handles hold release)
            await self.api._request(
                "POST",
                f"/api/v1/tickets/admin/{ticket_id}/close",
                data={
                    "reason": "auto_close",
                    "notes": "Ticket channel not found in Discord (auto-closed by sync task)"
                },
                discord_user_id="SYSTEM"
            )

            logger.info(f"Successfully closed ghost ticket #{ticket_number}")

        except Exception as e:
            logger.error(
                f"Failed to close ghost ticket #{ticket_number}: {e}",
                exc_info=True
            )
            raise


# Singleton instance
_ticket_sync_task = None


def get_ticket_sync_task(bot: discord.Bot) -> TicketSyncTask:
    """Get or create ticket sync task instance"""
    global _ticket_sync_task
    if _ticket_sync_task is None:
        _ticket_sync_task = TicketSyncTask(bot)
    return _ticket_sync_task


async def start_ticket_sync(bot: discord.Bot):
    """Start the ticket sync background task"""
    task = get_ticket_sync_task(bot)
    await task.start()


async def stop_ticket_sync():
    """Stop the ticket sync background task"""
    global _ticket_sync_task
    if _ticket_sync_task:
        await _ticket_sync_task.stop()
