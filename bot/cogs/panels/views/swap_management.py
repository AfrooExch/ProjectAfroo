"""
Swap Management View - Buttons to manage active swaps in private ticket channels
"""

import discord
import logging
import asyncio
from typing import Optional

from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED, INFO_BLUE
from utils.auth import get_user_context

logger = logging.getLogger(__name__)


class SwapManagementView(discord.ui.View):
    """Management view for swap tickets with status, refresh, and support buttons"""

    def __init__(
        self,
        bot: discord.Bot,
        swap_id: str,
        user_id: int,
        from_asset: str,
        to_asset: str,
        deposit_address: str = None
    ):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.swap_id = swap_id
        self.user_id = user_id
        self.from_asset = from_asset
        self.to_asset = to_asset
        self.deposit_address = deposit_address

    @discord.ui.button(
        label="Check Status",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="swap_check_status"
    )
    async def check_status_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Check current swap status"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get API client
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get swap details (with refresh from ChangeNOW)
            swap_data = await api.afroo_swap_get_details(
                swap_id=self.swap_id,
                user_id=str(interaction.user.id),
                discord_roles=roles,
                refresh=True  # Trigger status update from ChangeNOW
            )

            # Extract swap info
            status = swap_data.get("status", "unknown")
            changenow_status = swap_data.get("changenow_status", "")
            input_amount = swap_data.get("input_amount", 0)
            estimated_output = swap_data.get("estimated_output", 0)
            actual_output = swap_data.get("actual_output")
            exchange_rate = swap_data.get("exchange_rate", 0)
            changenow_deposit_address = swap_data.get("changenow_deposit_address", "N/A")
            destination_address = swap_data.get("destination_address", "N/A")

            # Truncate addresses for cleaner display
            deposit_addr_display = changenow_deposit_address if len(changenow_deposit_address) <= 30 else f"{changenow_deposit_address[:15]}...{changenow_deposit_address[-10:]}"
            dest_addr_display = destination_address if len(destination_address) <= 30 else f"{destination_address[:15]}...{destination_address[-10:]}"

            created_at = swap_data.get("created_at", "")
            completed_at = swap_data.get("completed_at")

            # Status-specific formatting
            if status == "completed":
                color = SUCCESS_GREEN
                status_emoji = "✅"
                status_text = "**Status:** ✅ Completed"
                output_text = f"**You Received:** `{actual_output or estimated_output:.8f} {self.to_asset}`"
            elif status == "failed":
                color = ERROR_RED
                status_emoji = "❌"
                status_text = "**Status:** ❌ Failed"
                output_text = f"**Refunded:** Your {self.from_asset} has been returned"
            elif status == "refunded":
                color = PURPLE_GRADIENT
                status_emoji = "↩️"
                status_text = "**Status:** ↩️ Refunded"
                output_text = f"**Refunded:** Your {self.from_asset} has been returned"
            elif status == "waiting":
                color = INFO_BLUE
                status_emoji = "⏰"
                status_text = "**Status:** ⏰ Waiting for Deposit"
                output_text = f"**Estimated Output:** `~{estimated_output:.8f} {self.to_asset}`"
            elif status == "confirming":
                color = INFO_BLUE
                status_emoji = "🔍"
                status_text = "**Status:** 🔍 Confirming Transaction"
                output_text = f"**Estimated Output:** `~{estimated_output:.8f} {self.to_asset}`"
            elif status == "exchanging":
                color = PURPLE_GRADIENT
                status_emoji = "⚡"
                status_text = "**Status:** ⚡ Exchanging"
                output_text = f"**Estimated Output:** `~{estimated_output:.8f} {self.to_asset}`"
            elif status == "sending":
                color = INFO_BLUE
                status_emoji = "📤"
                status_text = "**Status:** 📤 Sending to Your Address"
                output_text = f"**Estimated Output:** `~{estimated_output:.8f} {self.to_asset}`"
            elif status == "verifying":
                color = PURPLE_GRADIENT
                status_emoji = "🔐"
                status_text = "**Status:** 🔐 Under Verification"
                output_text = f"**Estimated Output:** `~{estimated_output:.8f} {self.to_asset}`"
            elif status == "processing":
                color = PURPLE_GRADIENT
                status_emoji = "⏳"
                status_text = "**Status:** ⏳ Processing"
                output_text = f"**Estimated Output:** `~{estimated_output:.8f} {self.to_asset}`"
            else:
                color = PURPLE_GRADIENT
                status_emoji = "🔄"
                status_text = f"**Status:** 🔄 {status.title()}"
                output_text = f"**Estimated Output:** `~{estimated_output:.8f} {self.to_asset}`"

            # Build status embed
            status_embed = create_themed_embed(
                title="",
                description=(
                    f"## Swap Status {status_emoji}\n\n"
                    f"{status_text}\n\n"
                    f"**You Send:** `{input_amount} {self.from_asset}`\n"
                    f"{output_text}\n"
                    f"**Rate:** `1 {self.from_asset} = {exchange_rate:.8f} {self.to_asset}`\n\n"
                    f"**Deposit Address:** `{deposit_addr_display}`\n"
                    f"**Receiving Address:** `{dest_addr_display}`\n\n"
                    f"**Exchange Status:** {changenow_status or 'pending'}\n"
                    f"**Created:** {created_at}\n"
                    + (f"**Completed:** {completed_at}\n\n" if completed_at else "\n")
                    + f"**Swap ID:** `{self.swap_id}`"
                ),
                color=color
            )

            await interaction.followup.send(embed=status_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error checking swap status: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to check swap status: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="View History",
        style=discord.ButtonStyle.secondary,
        emoji="📋",
        custom_id="swap_view_history"
    )
    async def view_history_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """View swap history"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get API client
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Get user's swap history
            swaps = await api.afroo_swap_get_history(
                user_id=str(interaction.user.id),
                discord_roles=roles,
                limit=10
            )

            if not swaps:
                await interaction.followup.send(
                    "📋 No swap history found.",
                    ephemeral=True
                )
                return

            # Build history embed
            history_lines = []
            for swap in swaps[:10]:
                swap_id_short = str(swap.get("_id", ""))[:8]
                from_asset = swap.get("from_asset", "")
                to_asset = swap.get("to_asset", "")
                input_amount = swap.get("input_amount", 0)
                status = swap.get("status", "unknown")

                # Status emoji
                status_emoji = {
                    "completed": "✅",
                    "failed": "❌",
                    "refunded": "↩️",
                    "processing": "⏳",
                    "pending": "🔄"
                }.get(status, "🔄")

                history_lines.append(
                    f"{status_emoji} `{swap_id_short}` - {input_amount:.6f} {from_asset} → {to_asset}"
                )

            history_embed = create_themed_embed(
                title="",
                description=(
                    f"## 📋 Your Swap History\n\n"
                    f"Recent swaps (showing last {len(swaps)}):\n\n"
                    + "\n".join(history_lines)
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.followup.send(embed=history_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error viewing swap history: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to view swap history: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="Contact Support",
        style=discord.ButtonStyle.danger,
        emoji="🆘",
        custom_id="swap_contact_support",
        row=1
    )
    async def contact_support_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Contact support about this swap"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get support channel
            from config import config
            support_channel_id = config.support_panel_channel

            if support_channel_id:
                support_channel = interaction.guild.get_channel(support_channel_id)
                support_mention = support_channel.mention if support_channel else "#support"
            else:
                support_mention = "#support"

            # Get staff role
            staff_role_id = config.ROLE_STAFF
            if staff_role_id:
                staff_role = interaction.guild.get_role(staff_role_id)
                staff_mention = staff_role.mention if staff_role else "@Staff"
            else:
                staff_mention = "@Staff"

            support_embed = create_themed_embed(
                title="",
                description=(
                    f"## Support Request\n\n"
                    f"Need help with your swap?\n\n"
                    f"**Swap ID:** `{self.swap_id}`\n"
                    f"**Swap:** {self.from_asset} → {self.to_asset}\n\n"
                    f"**How to Get Help:**\n"
                    f"1. Visit {support_mention}\n"
                    f"2. Click Create Ticket\n"
                    f"3. Mention your Swap ID: `{self.swap_id}`\n"
                    f"4. Describe your issue"
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.followup.send(embed=support_embed, ephemeral=True)

            # Also send alert in the swap channel for staff
            alert_embed = create_themed_embed(
                title="",
                description=(
                    f"## Support Requested\n\n"
                    f"{interaction.user.mention} has requested support for this swap.\n\n"
                    f"{staff_mention}"
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=alert_embed)

        except Exception as e:
            logger.error(f"Error contacting support: {e}", exc_info=True)
            await interaction.followup.send(
                "Failed to contact support. Please create a support ticket manually.",
                ephemeral=True
            )

    @discord.ui.button(
        label="View QR Code",
        style=discord.ButtonStyle.secondary,
        emoji="📱",
        custom_id="swap_view_qr",
        row=1
    )
    async def view_qr_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Show QR code for deposit address"""
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.deposit_address:
                await interaction.followup.send(
                    "Deposit address not available.",
                    ephemeral=True
                )
                return

            # Generate QR code
            try:
                import qrcode
                from io import BytesIO

                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(self.deposit_address)
                qr.make(fit=True)

                qr_img = qr.make_image(fill_color="black", back_color="white")

                buffer = BytesIO()
                qr_img.save(buffer, format="PNG")
                buffer.seek(0)

                qr_file = discord.File(buffer, filename="deposit_qr.png")

                qr_embed = create_themed_embed(
                    title="",
                    description=(
                        f"## QR Code\n\n"
                        f"Scan this QR code to send {self.from_asset}:\n"
                        f"```\n{self.deposit_address}\n```"
                    ),
                    color=PURPLE_GRADIENT
                )
                qr_embed.set_image(url="attachment://deposit_qr.png")

                await interaction.followup.send(embed=qr_embed, file=qr_file, ephemeral=True)

            except Exception as e:
                logger.error(f"Failed to generate QR code: {e}")
                await interaction.followup.send(
                    f"Failed to generate QR code. Address:\n```\n{self.deposit_address}\n```",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error showing QR code: {e}", exc_info=True)
            await interaction.followup.send(
                "Failed to display QR code.",
                ephemeral=True
            )

    @discord.ui.button(
        label="Copy Address",
        style=discord.ButtonStyle.secondary,
        emoji="📋",
        custom_id="swap_copy_address",
        row=1
    )
    async def copy_address_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Show deposit address for easy copying (mobile friendly)"""
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.deposit_address:
                await interaction.followup.send(
                    "Deposit address not available.",
                    ephemeral=True
                )
                return

            copy_embed = create_themed_embed(
                title="",
                description=(
                    f"## Deposit Address\n\n"
                    f"Copy and paste this address:\n"
                    f"```\n{self.deposit_address}\n```\n"
                    f"**Send {self.from_asset} only!**"
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.followup.send(embed=copy_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error showing address: {e}", exc_info=True)
            await interaction.followup.send(
                "Failed to display address.",
                ephemeral=True
            )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="swap_close_ticket",
        row=2
    )
    async def close_ticket_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Close swap ticket and send transcript"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get swap details
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            swap_data = await api.afroo_swap_get_details(
                swap_id=self.swap_id,
                user_id=str(interaction.user.id),
                discord_roles=roles
            )

            # Generate transcript
            from datetime import datetime
            messages = []
            async for msg in interaction.channel.history(limit=500, oldest_first=True):
                messages.append(msg)

            if messages:
                # Generate HTML transcript
                from utils.swap_transcript import generate_swap_transcript_html
                from io import BytesIO

                transcript_html = generate_swap_transcript_html(
                    swap_id=self.swap_id,
                    messages=messages,
                    swap_data=swap_data,
                    opened_by=interaction.user,
                    closed_at=datetime.utcnow()
                )

                # Upload transcript to backend API
                try:
                    import aiohttp
                    import logging
                    from config import config

                    logger = logging.getLogger(__name__)
                    api_base = config.API_BASE_URL
                    upload_url = f"{api_base}/api/v1/transcripts/upload"
                    bot_token = config.BOT_SERVICE_TOKEN

                    upload_data = {
                        "ticket_id": self.swap_id,
                        "ticket_type": "swap",
                        "ticket_number": None,
                        "user_id": str(interaction.user.id),
                        "participants": [],
                        "html_content": transcript_html,
                        "message_count": len(messages)
                    }

                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            upload_url,
                            json=upload_data,
                            headers={
                                'X-Bot-Token': bot_token,
                                'Content-Type': 'application/json'
                            }
                        ) as response:
                            if response.status in [200, 201]:
                                result = await response.json()
                                public_url = result.get("public_url")
                                logger.info(f"Uploaded swap transcript {self.swap_id} to backend: {public_url}")
                            else:
                                error_text = await response.text()
                                logger.error(f"Failed to upload swap transcript: {response.status} - {error_text}")
                except Exception as e:
                    logger.error(f"Error uploading swap transcript: {e}", exc_info=True)

                # Generate text transcript
                transcript_text = f"Swap Transcript - {self.swap_id}\n"
                transcript_text += f"Swap: {swap_data.get('input_amount')} {self.from_asset} → {self.to_asset}\n"
                transcript_text += f"User: {interaction.user.name}\n"
                transcript_text += f"Closed: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}\n"
                transcript_text += "\n" + "="*80 + "\n\n"

                for msg in messages:
                    if msg.type == discord.MessageType.default:
                        timestamp = msg.created_at.strftime("%I:%M %p")
                        transcript_text += f"[{timestamp}] {msg.author.name}: {msg.content}\n"

                # Send transcripts to user
                try:
                    # Create HTML file
                    html_buffer = BytesIO(transcript_html.encode('utf-8'))
                    html_file = discord.File(
                        fp=html_buffer,
                        filename=f"swap_{self.swap_id[:8]}_transcript.html"
                    )

                    # Create text file
                    text_buffer = BytesIO(transcript_text.encode('utf-8'))
                    text_file = discord.File(
                        fp=text_buffer,
                        filename=f"swap_{self.swap_id[:8]}_transcript.txt"
                    )

                    dm_embed = create_themed_embed(
                        title="",
                        description=(
                            f"## Swap Ticket Closed\n\n"
                            f"Your swap ticket has been closed.\n\n"
                            f"**Swap ID:** `{self.swap_id}`\n"
                            f"**Swap:** {self.from_asset} → {self.to_asset}\n\n"
                            f"Here are your ticket transcripts for your records."
                        ),
                        color=PURPLE_GRADIENT
                    )

                    await interaction.user.send(embed=dm_embed, files=[html_file, text_file])
                    logger.info(f"Swap {self.swap_id}: HTML and text transcripts sent to user")
                except discord.Forbidden:
                    logger.warning(f"Cannot DM user {interaction.user.id} - DMs are closed")
                except Exception as e:
                    logger.error(f"Failed to DM transcripts: {e}")

                # Post to history channel
                try:
                    from config import config
                    history_channel_id = config.history_channel

                    if history_channel_id:
                        history_channel = self.bot.get_channel(history_channel_id)
                        if history_channel:
                            # Create files again (can't reuse)
                            html_buffer2 = BytesIO(transcript_html.encode('utf-8'))
                            html_file2 = discord.File(
                                fp=html_buffer2,
                                filename=f"swap_{self.swap_id[:8]}_transcript.html"
                            )

                            text_buffer2 = BytesIO(transcript_text.encode('utf-8'))
                            text_file2 = discord.File(
                                fp=text_buffer2,
                                filename=f"swap_{self.swap_id[:8]}_transcript.txt"
                            )

                            history_embed = create_themed_embed(
                                title="",
                                description=(
                                    f"## Swap Ticket Closed\n\n"
                                    f"**User:** {interaction.user.mention}\n"
                                    f"**Swap ID:** `{self.swap_id}`\n"
                                    f"**Swap:** {self.from_asset} → {self.to_asset}\n"
                                    f"**Closed:** Manually by user\n"
                                    f"**Date:** {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}"
                                ),
                                color=PURPLE_GRADIENT
                            )

                            await history_channel.send(embed=history_embed, files=[html_file2, text_file2])
                            logger.info(f"Swap {self.swap_id}: Posted to history channel")
                except Exception as e:
                    logger.error(f"Failed to post to history channel: {e}")

            # Confirm closure
            await interaction.followup.send(
                embed=create_themed_embed(
                    title="✅ Ticket Closing",
                    description="Ticket will be deleted in 5 seconds. Transcript has been sent to your DMs.",
                    color=SUCCESS_GREEN
                ),
                ephemeral=True
            )

            # Delete channel after delay
            await asyncio.sleep(5)
            await interaction.channel.delete(reason=f"Swap ticket closed by user - {self.swap_id}")
            logger.info(f"Swap {self.swap_id}: Channel closed by user")

        except Exception as e:
            logger.error(f"Error closing swap ticket: {e}", exc_info=True)
            await interaction.followup.send(
                "Failed to close ticket. Please contact staff.",
                ephemeral=True
            )
