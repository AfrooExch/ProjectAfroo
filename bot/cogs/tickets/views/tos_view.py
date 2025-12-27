"""
TOS Acceptance View for V4
Handles TOS agreement with 10-minute timer and reminders
"""

import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

import discord
from discord.ui import View, Button

from utils.embeds import create_themed_embed, create_success_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS, ERROR
from config import config

logger = logging.getLogger(__name__)


class TOSAcceptanceView(View):
    """
    TOS Acceptance View with timer
    - 10 minute timeout
    - 3/6/9 minute reminder pings
    - Auto-close on timeout
    """

    def __init__(
        self,
        bot: discord.Bot,
        ticket_id: str,
        channel: discord.TextChannel,
        customer_id: int
    ):
        super().__init__(timeout=None)  # We handle timeout manually
        self.bot = bot
        self.ticket_id = ticket_id
        self.channel = channel
        self.customer_id = customer_id
        self.message: Optional[discord.Message] = None

        # Timer tasks
        self.timer_tasks = []
        self.timer_cancelled = False

    @discord.ui.button(
        label="I Agree",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="tos_agree"
    )
    async def agree_button(self, button: Button, interaction: discord.Interaction):
        """Handle TOS acceptance"""
        # Check for admin bypass (Head Admin or Assistant Admin)
        from config import config
        is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
        admin_bypass = is_head_admin or is_assistant_admin

        # Verify it's the customer (or admin with bypass)
        if interaction.user.id != self.customer_id and not admin_bypass:
            await interaction.response.send_message(
                "❌ Only the ticket owner can accept the TOS.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        logger.info(f"User {interaction.user.id} accepted TOS for ticket #{self.ticket_id}")

        # Get user context for API authentication
        from utils.auth import get_user_context
        user_id, roles = get_user_context(interaction)

        # Cancel timer tasks
        self.cancel_timer()

        # Update ticket status via API
        try:
            await self.bot.api_client.update_ticket(
                self.ticket_id,
                discord_user_id=user_id,
                discord_roles=roles,
                status="awaiting_claim",
                tos_accepted=True
            )
        except Exception as e:
            logger.error(f"Error updating ticket status: {e}")
            await interaction.followup.send(
                "❌ Error updating ticket. Please contact staff.",
                ephemeral=True
            )
            return

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

        # Post acceptance message in client thread
        accept_embed = create_success_embed(
            title="TOS Accepted",
            description=(
                f"{interaction.user.mention} has accepted the Terms of Service.\n\n"
                f"**Your ticket is now in the exchanger queue. You'll be notified when an exchanger claims it.**"
            )
        )
        await self.channel.send(embed=accept_embed)

        # Create exchanger thread (V4 thread-based system)
        await self.create_exchanger_thread(user_id, roles)

    async def create_exchanger_thread(self, user_id: str = None, roles: list = None):
        """Create exchanger thread in forum after TOS acceptance"""
        try:
            # Get ticket data from API
            ticket = await self.bot.api_client.get_ticket(
                self.ticket_id,
                discord_user_id=user_id,
                discord_roles=roles
            )
            if not ticket:
                logger.error(f"Ticket {self.ticket_id} not found when creating exchanger thread")
                return

            ticket_number = ticket.get("ticket_number", "Unknown")
            amount_usd = ticket.get("amount_usd", 0)
            send_method = ticket.get("send_method", "Unknown")
            receive_method = ticket.get("receive_method", "Unknown")

            # Get exchanger forum
            forum = self.channel.guild.get_channel(config.FORUM_EXCHANGER_QUEUE)
            if not forum:
                logger.error(f"Exchanger forum not found: {config.FORUM_EXCHANGER_QUEUE}")
                return

            # Create anonymous thread (ticket number only, no client info)
            thread_name = f"Ticket #{ticket_number} - ${amount_usd:.2f} {send_method}→{receive_method}"

            initial_message = f"**New Exchange Ticket Available**\n\nTicket #{ticket_number} is ready to claim!"

            # Create the thread
            thread_response = await forum.create_thread(
                name=thread_name,
                content=initial_message,
                auto_archive_duration=10080,  # 7 days
                applied_tags=[],
            )

            # Get thread object
            if hasattr(thread_response, 'thread'):
                exchanger_thread = thread_response.thread
            else:
                exchanger_thread = thread_response

            # Add admin role members to exchanger thread
            await self.add_admin_members_to_thread(exchanger_thread)

            # Update ticket with exchanger thread ID
            try:
                await self.bot.api_client.patch(
                    f"/tickets/{self.ticket_id}",
                    json={
                        "exchanger_thread_id": str(exchanger_thread.id),
                        "exchanger_forum_id": str(config.FORUM_EXCHANGER_QUEUE)
                    }
                )
                logger.info(f"Updated ticket {self.ticket_id} with exchanger thread {exchanger_thread.id}")
            except Exception as api_error:
                logger.error(f"Failed to update ticket with exchanger thread_id: {api_error}")

            # Post anonymous ticket info with claim button
            await self.post_exchanger_ticket_info(exchanger_thread, ticket)

            logger.info(f"Created exchanger thread {exchanger_thread.id} for ticket #{ticket_number}")

        except Exception as e:
            logger.error(f"Error creating exchanger thread: {e}", exc_info=True)

    async def post_exchanger_ticket_info(self, thread: discord.Thread, ticket: dict):
        """Post anonymous ticket information in exchanger thread"""
        try:
            ticket_number = ticket.get("ticket_number", "Unknown")
            amount_usd = ticket.get("amount_usd", 0)
            send_method = ticket.get("send_method", "Unknown")
            receive_method = ticket.get("receive_method", "Unknown")
            send_crypto = ticket.get("send_crypto")
            receive_crypto = ticket.get("receive_crypto")

            # Build additional info
            additional_info = []
            if send_crypto:
                additional_info.append(f"📤 Sending: {send_crypto}")
            if receive_crypto:
                additional_info.append(f"📥 Receiving: {receive_crypto}")

            # Calculate estimated profit (simplified)
            fee_amount = ticket.get("fee_amount", 0)
            server_fee = max(0.50, amount_usd * 0.02)
            estimated_profit = fee_amount - server_fee

            description = (
                f"**Amount:** ${amount_usd:.2f} USD\n"
                f"**Sending Method:** {send_method}\n"
                f"**Receiving Method:** {receive_method}\n"
                f"**Estimated Profit:** ${estimated_profit:.2f}\n"
            )

            if additional_info:
                description += f"\n**Additional Info:**\n" + "\n".join(additional_info)

            embed = create_themed_embed(
                title=f"🎫 Exchange Ticket #{ticket_number}",
                description=description,
                color=PURPLE_GRADIENT
            )

            # Import claim view
            from cogs.tickets.views.claim_view import ClaimTicketView

            claim_view = ClaimTicketView(
                bot=self.bot,
                ticket_id=self.ticket_id,
                channel=thread
            )

            await thread.send(embed=embed, view=claim_view)

        except Exception as e:
            logger.error(f"Error posting exchanger ticket info: {e}", exc_info=True)

    async def add_admin_members_to_thread(self, thread: discord.Thread):
        """Add Head Admin and Assistant Admin role members to thread"""
        try:
            guild = thread.guild
            head_admin_role = guild.get_role(config.head_admin_role)
            assistant_admin_role = guild.get_role(config.assistant_admin_role)

            added_count = 0

            # Add Head Admin role members
            if head_admin_role:
                for member in head_admin_role.members:
                    try:
                        await thread.add_user(member)
                        added_count += 1
                    except Exception as e:
                        logger.warning(f"Could not add Head Admin {member.name} to thread: {e}")

            # Add Assistant Admin role members
            if assistant_admin_role:
                for member in assistant_admin_role.members:
                    try:
                        await thread.add_user(member)
                        added_count += 1
                    except Exception as e:
                        logger.warning(f"Could not add Assistant Admin {member.name} to thread: {e}")

            logger.info(f"Added {added_count} admin members to thread {thread.id}")

        except Exception as e:
            logger.error(f"Error adding admin members to thread: {e}", exc_info=True)

    @discord.ui.button(
        label="I Deny",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="tos_deny"
    )
    async def deny_button(self, button: Button, interaction: discord.Interaction):
        """Handle TOS denial"""
        # Verify it's the customer
        if interaction.user.id != self.customer_id:
            await interaction.response.send_message(
                "❌ Only the ticket owner can deny the TOS.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        logger.info(f"User {interaction.user.id} denied TOS for ticket #{self.ticket_id}")

        # Get user context for API authentication
        from utils.auth import get_user_context
        user_id, roles = get_user_context(interaction)

        # Cancel timer tasks
        self.cancel_timer()

        # Update ticket status via API
        try:
            await self.bot.api_client.update_ticket(
                self.ticket_id,
                discord_user_id=user_id,
                discord_roles=roles,
                status="closed",
                close_reason="TOS denied by customer"
            )
        except Exception as e:
            logger.error(f"Error updating ticket status: {e}")

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

        # Post denial message
        deny_embed = create_error_embed(
            title="TOS Denied",
            description=(
                f"{interaction.user.mention} has denied the Terms of Service.\n\n"
                f"This ticket will be closed in 10 seconds."
            )
        )
        await self.channel.send(embed=deny_embed)

        # Close channel after delay
        await asyncio.sleep(10)
        try:
            await self.channel.delete(reason=f"TOS denied - ticket #{self.ticket_id}")
        except:
            pass

    def start_timer(self, message: discord.Message):
        """Start the 10-minute timer with reminders"""
        self.message = message

        # Create tasks for reminders and auto-close
        self.timer_tasks.append(asyncio.create_task(self._reminder_at_3min()))
        self.timer_tasks.append(asyncio.create_task(self._reminder_at_6min()))
        self.timer_tasks.append(asyncio.create_task(self._reminder_at_9min()))
        self.timer_tasks.append(asyncio.create_task(self._auto_close_at_10min()))

        logger.info(f"Started TOS timer for ticket #{self.ticket_id}")

    def cancel_timer(self):
        """Cancel all timer tasks"""
        self.timer_cancelled = True

        for task in self.timer_tasks:
            if not task.done():
                task.cancel()

        logger.info(f"Cancelled TOS timer for ticket #{self.ticket_id}")

    async def _reminder_at_3min(self):
        """Send reminder at 3 minutes"""
        await asyncio.sleep(180)  # 3 minutes

        if self.timer_cancelled:
            return

        logger.info(f"Sending 3-minute TOS reminder for ticket #{self.ticket_id}")

        reminder_embed = create_themed_embed(
            title="",
            description=(
                f"## TOS Response Required\n\n"
                f"<@{self.customer_id}> You need to accept or deny the Terms of Service to proceed.\n\n"
                f"**Time Elapsed:** 3 minutes\n"
                f"**Time Remaining:** 7 minutes\n\n"
                f"> Your ticket will auto-close in 7 minutes if you don't respond."
            ),
            color=PURPLE_GRADIENT
        )

        try:
            await self.channel.send(content=f"<@{self.customer_id}>", embed=reminder_embed)
        except:
            pass

    async def _reminder_at_6min(self):
        """Send reminder at 6 minutes"""
        await asyncio.sleep(360)  # 6 minutes

        if self.timer_cancelled:
            return

        logger.info(f"Sending 6-minute TOS reminder for ticket #{self.ticket_id}")

        reminder_embed = create_themed_embed(
            title="",
            description=(
                f"## TOS Response Required\n\n"
                f"<@{self.customer_id}> You need to accept or deny the Terms of Service to proceed.\n\n"
                f"**Time Elapsed:** 6 minutes\n"
                f"**Time Remaining:** 4 minutes\n\n"
                f"> Your ticket will auto-close in 4 minutes if you don't respond."
            ),
            color=PURPLE_GRADIENT
        )

        try:
            await self.channel.send(content=f"<@{self.customer_id}>", embed=reminder_embed)
        except:
            pass

    async def _reminder_at_9min(self):
        """Send reminder at 9 minutes"""
        await asyncio.sleep(540)  # 9 minutes

        if self.timer_cancelled:
            return

        logger.info(f"Sending 9-minute TOS reminder for ticket #{self.ticket_id}")

        reminder_embed = create_themed_embed(
            title="",
            description=(
                f"## ⚠️ FINAL WARNING\n\n"
                f"<@{self.customer_id}> You need to accept or deny the Terms of Service **NOW**.\n\n"
                f"**Time Elapsed:** 9 minutes\n"
                f"**Time Remaining:** 1 minute\n\n"
                f"> Your ticket will auto-close in **1 minute** if you don't respond!"
            ),
            color=ERROR
        )

        try:
            await self.channel.send(content=f"<@{self.customer_id}>", embed=reminder_embed)
        except:
            pass

    async def _auto_close_at_10min(self):
        """Auto-close ticket at 10 minutes"""
        await asyncio.sleep(600)  # 10 minutes

        if self.timer_cancelled:
            return

        logger.info(f"Auto-closing ticket #{self.ticket_id} - TOS timeout")

        # Update ticket status via API
        try:
            await self.bot.api_client.update_ticket(
                self.ticket_id,
                status="closed",
                close_reason="TOS timeout - No response after 10 minutes"
            )
        except Exception as e:
            logger.error(f"Error updating ticket status: {e}")

        # Disable buttons
        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

        # Post timeout message
        timeout_embed = create_error_embed(
            title="Ticket Auto-Closed",
            description=(
                f"<@{self.customer_id}> did not respond to the Terms of Service within 10 minutes.\n\n"
                f"This ticket has been automatically closed due to inactivity.\n\n"
                f"> This channel will be deleted in 10 seconds."
            )
        )

        try:
            await self.channel.send(embed=timeout_embed)
        except:
            pass

        # Delete channel after delay
        await asyncio.sleep(10)
        try:
            await self.channel.delete(reason=f"TOS timeout - ticket #{self.ticket_id}")
        except:
            pass

