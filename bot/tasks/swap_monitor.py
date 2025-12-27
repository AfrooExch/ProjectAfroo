"""
Swap Monitor Task - Periodically checks pending swap statuses
Monitors active swaps and updates their status from ChangeNOW
"""

import discord
import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

from api.client import APIClient

logger = logging.getLogger(__name__)


class SwapMonitor:
    """Background task that monitors pending swaps and updates their status"""

    def __init__(self, bot: discord.Bot, api: APIClient):
        self.bot = bot
        self.api = api
        self.running = False
        self.task: Optional[asyncio.Task] = None

    def start(self):
        """Start the background task"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._monitor_loop())
            logger.info("Swap monitor task started")

    def stop(self):
        """Stop the background task"""
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("Swap monitor task stopped")

    async def _monitor_loop(self):
        """Main loop that checks pending swaps"""
        await self.bot.wait_until_ready()

        # Wait 30 seconds before first check to let bot fully initialize
        await asyncio.sleep(30)

        # Cache of swap IDs we've seen to track status changes
        last_known_statuses = {}

        while self.running:
            try:
                # Get active swaps from API - need to get all users' swaps
                # We'll collect swaps from all open swap channels
                guild = self.bot.get_guild(self.bot.guilds[0].id if self.bot.guilds else None)

                if not guild:
                    logger.warning("No guild found, skipping swap monitoring")
                    await asyncio.sleep(30)
                    continue

                active_swaps = []

                # Find all swap channels (format: swap-username-swapidshort)
                for channel in guild.text_channels:
                    if channel.name.startswith("swap-"):
                        # Extract swap ID from channel topic if available
                        # Topic format: "Swap Ticket | BTC → ETH | User: 123456"
                        try:
                            # Get last 8 chars of channel name which should be swap ID prefix
                            parts = channel.name.split("-")
                            if len(parts) >= 3:
                                swap_id_short = parts[-1]
                                user_id = channel.topic.split("User: ")[-1] if channel.topic else None

                                if user_id:
                                    active_swaps.append({
                                        "swap_id_short": swap_id_short,
                                        "user_id": user_id,
                                        "channel": channel
                                    })
                        except Exception as e:
                            logger.debug(f"Could not parse swap channel {channel.name}: {e}")
                            continue

                if active_swaps:
                    logger.debug(f"Monitoring {len(active_swaps)} swap channels...")

                for swap_info in active_swaps:
                    try:
                        user_id = swap_info["user_id"]
                        swap_id_short = swap_info["swap_id_short"]

                        # Get user's swap history to find full swap ID
                        try:
                            history = await self.api.afroo_swap_get_history(
                                user_id=user_id,
                                discord_roles=[],
                                limit=50
                            )

                            swaps = history.get("swaps", [])

                            # Find the swap matching the short ID
                            matching_swap = None
                            for s in swaps:
                                full_id = str(s.get("_id", ""))
                                if full_id.startswith(swap_id_short):
                                    matching_swap = s
                                    break

                            if not matching_swap:
                                continue

                            swap_id = str(matching_swap.get("_id", ""))
                            old_status = last_known_statuses.get(swap_id, matching_swap.get("status"))

                            # Only refresh if not in final state
                            if matching_swap.get("status") not in ["completed", "failed", "refunded"]:
                                # Refresh status from ChangeNOW
                                updated_swap = await self.api.afroo_swap_get_details(
                                    swap_id=swap_id,
                                    user_id=user_id,
                                    discord_roles=[],
                                    refresh=True
                                )

                                new_status = updated_swap.get("status")
                                last_known_statuses[swap_id] = new_status

                                if old_status != new_status:
                                    logger.info(
                                        f"✅ Swap {swap_id[:8]} status changed: {old_status} → {new_status}"
                                    )

                        except Exception as e:
                            logger.debug(f"Error fetching swap history for user {user_id}: {e}")
                            continue

                    except Exception as e:
                        logger.error(f"Error updating swap: {e}")
                        continue

                # Check every 30 seconds
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in swap monitor loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on error
