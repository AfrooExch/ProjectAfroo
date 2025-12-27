"""
Support Ticket View - Close button with transcript generation and web viewing
"""

import discord
import asyncio
import logging
import io
from datetime import datetime

from utils.view_manager import PersistentView
from utils.embeds import create_themed_embed
from utils.colors import SUCCESS_GREEN, ERROR_RED, PURPLE_GRADIENT
from utils.support_transcript import generate_support_transcript_html
from config import config

logger = logging.getLogger(__name__)


class TranscriptButton(discord.ui.View):
    """View with button to view transcript online"""

    def __init__(self, ticket_number: int, ticket_category: str = "support"):
        super().__init__(timeout=None)
        self.ticket_number = ticket_number
        self.ticket_category = ticket_category

        # Add button to view transcript online
        # ticket_category can be "support" or "application"
        transcript_url = f"{config.transcript_base_url}/transcripts/{ticket_category}/{ticket_number}"
        button = discord.ui.Button(
            label="View Transcript Online",
            style=discord.ButtonStyle.link,
            url=transcript_url,
            emoji="🌐"
        )
        self.add_item(button)


class SupportTicketView(PersistentView):
    """View with close button for support tickets"""

    def __init__(
        self,
        bot: discord.Bot,
        ticket_number: int,
        ticket_type: str,
        opened_by: discord.User,
        opened_at: datetime
    ):
        super().__init__(bot)
        self.ticket_number = ticket_number
        self.ticket_type = ticket_type
        self.opened_by = opened_by
        self.opened_at = opened_at

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="close_support_ticket",
        emoji="🔒"
    )
    async def close_ticket_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Close the support ticket and generate transcript"""
        await interaction.response.defer()

        try:
            # Check if user has permission to close
            channel = interaction.channel
            user = interaction.user
            guild = interaction.guild

            # Check if user is staff or admin
            is_staff = False
            staff_role = guild.get_role(config.staff_role)
            admin_role = guild.get_role(config.head_admin_role)

            if staff_role and staff_role in user.roles:
                is_staff = True
            if admin_role and admin_role in user.roles:
                is_staff = True

            # Check if user is the ticket creator
            user_permissions = channel.permissions_for(user)
            is_creator = user_permissions.send_messages and not is_staff

            if not (is_staff or is_creator):
                await interaction.followup.send(
                    embed=create_themed_embed(
                        title="",
                        description="You don't have permission to close this ticket.",
                        color=ERROR_RED
                    ),
                    ephemeral=True
                )
                return

            # Create closing embed
            closing_embed = create_themed_embed(
                title="",
                description=(
                    f"**Ticket Closing**\n\n"
                    f"Ticket: #{self.ticket_number}\n"
                    f"Closed by: {user.mention}\n\n"
                    f"Generating transcript and sending to DMs..."
                ),
                color=PURPLE_GRADIENT
            )

            # Disable all buttons
            for item in self.children:
                item.disabled = True

            # Update the message with disabled buttons
            try:
                await interaction.message.edit(view=self)
            except:
                pass

            # Send closing message
            await interaction.followup.send(embed=closing_embed)

            # Fetch all messages from the channel
            logger.info(f"Generating transcript for ticket #{self.ticket_number}...")
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                messages.append(message)

            # Generate transcript
            closed_at = datetime.utcnow()

            html_transcript = generate_support_transcript_html(
                ticket_number=self.ticket_number,
                ticket_type=self.ticket_type,
                messages=messages,
                opened_by=self.opened_by,
                closed_by=user,
                opened_at=self.opened_at,
                closed_at=closed_at
            )

            # Upload transcript to backend API
            try:
                import aiohttp

                api_base = config.API_BASE_URL
                upload_url = f"{api_base}/api/v1/transcripts/upload"
                bot_token = config.BOT_SERVICE_TOKEN

                upload_data = {
                    "ticket_id": str(self.ticket_number),
                    "ticket_type": "support",
                    "ticket_number": self.ticket_number,
                    "user_id": str(self.opened_by.id),
                    "participants": [str(user.id)],
                    "html_content": html_transcript,
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
                            logger.info(f"Uploaded support transcript #{self.ticket_number} to backend: {public_url}")
                        else:
                            error_text = await response.text()
                            logger.error(f"Failed to upload support transcript: {response.status} - {error_text}")
            except Exception as e:
                logger.error(f"Error uploading support transcript: {e}", exc_info=True)

            # Create HTML file
            html_file_dm = discord.File(
                io.BytesIO(html_transcript.encode('utf-8')),
                filename=f"support_ticket_{self.ticket_number}.html"
            )

            html_file_channel = discord.File(
                io.BytesIO(html_transcript.encode('utf-8')),
                filename=f"support_ticket_{self.ticket_number}.html"
            )

            # Create view with button to website
            transcript_view = TranscriptButton(self.ticket_number)

            # Send to transcript channel first
            transcript_channel = guild.get_channel(config.transcript_channel)
            if transcript_channel:
                try:
                    transcript_log_embed = create_themed_embed(
                        title="",
                        description=(
                            f"**Support Ticket Transcript**\n\n"
                            f"Ticket Number: #{self.ticket_number}\n"
                            f"Type: {self.ticket_type.replace('_', ' ').title()}\n"
                            f"Opened By: {self.opened_by.name}\n"
                            f"Closed By: {user.name}\n"
                            f"Date: {closed_at.strftime('%B %d, %Y at %I:%M %p UTC')}"
                        ),
                        color=PURPLE_GRADIENT
                    )

                    await transcript_channel.send(
                        embed=transcript_log_embed,
                        file=html_file_channel,
                        view=transcript_view
                    )
                    logger.info(f"Transcript saved to transcript channel for ticket #{self.ticket_number}")
                except Exception as e:
                    logger.error(f"Failed to save transcript to channel: {e}")

            # Send DM to ticket creator
            try:
                dm_embed = create_themed_embed(
                    title="",
                    description=(
                        f"**Support Ticket Closed**\n\n"
                        f"Ticket: #{self.ticket_number}\n"
                        f"Type: {self.ticket_type.replace('_', ' ').title()}\n"
                        f"Closed By: {user.name}\n\n"
                        f"Your ticket transcript is attached below.\n"
                        f"Download and open the HTML file in your browser for the best viewing experience.\n\n"
                        f"You can also view it online using the button below.\n\n"
                        f"Thank you for contacting Afroo Exchange support."
                    ),
                    color=SUCCESS_GREEN
                )

                await self.opened_by.send(
                    embed=dm_embed,
                    file=html_file_dm,
                    view=transcript_view
                )

                logger.info(f"Transcript sent to {self.opened_by.name} for ticket #{self.ticket_number}")

                # Update closing message
                success_embed = create_themed_embed(
                    title="",
                    description=(
                        f"**Ticket Closed**\n\n"
                        f"Ticket: #{self.ticket_number}\n"
                        f"Closed By: {user.mention}\n\n"
                        f"Transcript sent to {self.opened_by.mention}'s DMs\n"
                        f"Transcript saved to transcript channel\n\n"
                        f"This channel will be deleted in 10 seconds."
                    ),
                    color=SUCCESS_GREEN
                )

                await channel.send(embed=success_embed)

            except discord.Forbidden:
                logger.warning(f"Cannot DM user {self.opened_by.id} - DMs are closed")

                # Update closing message
                warning_embed = create_themed_embed(
                    title="",
                    description=(
                        f"**Ticket Closed**\n\n"
                        f"Ticket: #{self.ticket_number}\n"
                        f"Closed By: {user.mention}\n\n"
                        f"Could not send transcript to {self.opened_by.mention} - DMs are disabled\n"
                        f"Transcript saved to transcript channel\n\n"
                        f"This channel will be deleted in 10 seconds."
                    ),
                    color=ERROR_RED
                )

                await channel.send(embed=warning_embed)

            # Wait 10 seconds then delete channel
            await asyncio.sleep(10)
            await channel.delete(reason=f"Support ticket #{self.ticket_number} closed by {user.name}")

            logger.info(f"Support ticket #{self.ticket_number} closed and deleted")

        except discord.Forbidden:
            logger.error(f"Missing permissions to delete support ticket channel #{self.ticket_number}")
            await interaction.followup.send(
                embed=create_themed_embed(
                    title="",
                    description="I don't have permission to delete this channel. Please contact an admin.",
                    color=ERROR_RED
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error closing support ticket: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    embed=create_themed_embed(
                        title="",
                        description=f"An error occurred while closing the ticket.\n\nError: {str(e)}",
                        color=ERROR_RED
                    ),
                    ephemeral=True
                )
            except:
                pass
