"""
Ticket Completion Views
Manual confirmation, vouches, transcripts, and completion flow
"""

import discord
import logging
import aiohttp
from typing import Optional, Dict, Any
from datetime import datetime

from cogs.tickets.constants import get_payment_method, CRYPTO_ASSETS
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED, BLUE_PRIMARY
from utils.auth import get_user_context
from api.client import APIClient
from config import config

logger = logging.getLogger(__name__)


class TranscriptView(discord.ui.View):
    """View with button to view transcript online"""

    def __init__(self, public_url: str):
        super().__init__(timeout=None)
        # Add button with URL
        self.add_item(discord.ui.Button(
            label="View Transcript Online",
            style=discord.ButtonStyle.link,
            url=public_url,
            emoji="🔗"
        ))


class ExchangerReceivedConfirmView(discord.ui.View):
    """
    View for exchanger to confirm they received client's payment (FIAT)
    Then shows client confirmation button
    PERSISTENT: Uses custom_id so buttons work forever (no timeout)
    """

    def __init__(
        self,
        ticket_id: str,
        ticket_number: int,
        api: APIClient,
        receiving_amount: float,
        timeout: float = None
    ):
        super().__init__(timeout=timeout)
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.api = api
        self.receiving_amount = receiving_amount

    @discord.ui.button(
        label="I Received Client's Payment",
        style=discord.ButtonStyle.primary,
        emoji="✅",
        custom_id="exchanger_received_confirm:persistent"
    )
    async def exchanger_confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Exchanger confirms they received client's payment"""
        try:
            await interaction.response.defer()

            # Get user context
            user_id, roles = get_user_context(interaction)

            # Check for admin bypass (Head Admin or Assistant Admin)
            from config import config
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            admin_bypass = is_head_admin or is_assistant_admin

            # Verify it's the exchanger (or admin with bypass)
            if config.ROLE_EXCHANGER not in roles and not admin_bypass:
                embed = create_themed_embed(
                    title="Permission Denied",
                    description="Only the exchanger can confirm receipt.",
                    color=ERROR_RED
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Disable this button
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Show message telling exchanger to send payout
            step2_embed = create_themed_embed(
                title="",
                description=(
                    f"## Step 2: Send Payout\n\n"
                    f"✅ {interaction.user.mention} confirmed they received the client's payment.\n\n"
                    f"**Now send ${self.receiving_amount:,.2f}** to the client via your fiat payment method.\n\n"
                    f"Once sent, the client will confirm receipt below."
                ),
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=step2_embed)

            # Now show client confirmation button
            step3_embed = create_themed_embed(
                title="",
                description=(
                    f"## Step 3: Client Confirmation\n\n"
                    f"**Client**: Once you receive **${self.receiving_amount:,.2f}** from the exchanger, click the button below to complete the ticket."
                ),
                color=PURPLE_GRADIENT
            )

            client_view = ManualConfirmationView(
                ticket_id=self.ticket_id,
                ticket_number=self.ticket_number,
                api=self.api
            )

            await interaction.channel.send(embed=step3_embed, view=client_view)

        except Exception as e:
            logger.error(f"Error exchanger confirming receipt: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class ManualConfirmationView(discord.ui.View):
    """
    Manual confirmation view for client to confirm receipt
    Used when automatic verification fails
    PERSISTENT: Uses custom_id so buttons work forever (no timeout)
    """

    def __init__(
        self,
        ticket_id: str,
        ticket_number: int,
        api: APIClient,
        timeout: float = None  # No timeout
    ):
        super().__init__(timeout=timeout)
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.api = api

    @discord.ui.button(
        label="I Received Payment",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="client_confirm_receipt:persistent"
    )
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Client confirms they received payment"""
        try:
            await interaction.response.defer()

            # Get user context
            user_id, roles = get_user_context(interaction)

            # Check for admin bypass (Head Admin or Assistant Admin)
            from config import config
            is_head_admin = any(role.id == config.head_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            is_assistant_admin = any(role.id == config.assistant_admin_role for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False
            admin_bypass = is_head_admin or is_assistant_admin

            # Call API to complete ticket
            if admin_bypass:
                # Admin bypass: force complete
                result = await self.api.post(
                    f"/api/v1/admin/tickets/force-complete",
                    data={"ticket_id": self.ticket_id},
                    discord_user_id=user_id,
                    discord_roles=roles
                )
            else:
                # Normal: only client can confirm
                result = await self.api.post(
                    f"/api/v1/tickets/{self.ticket_id}/complete",
                    data={},
                    discord_user_id=user_id,
                    discord_roles=roles
                )

            ticket_data = result.get("ticket", {})

            # Disable buttons
            for item in self.children:
                item.disabled = True

            await interaction.message.edit(view=self)

            # Show completion embed
            embed = create_themed_embed(
                title="Exchange Complete",
                description=f"Ticket **#{self.ticket_number}** has been completed successfully!\n\nThank you for using our exchange service.",
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=embed)

            # Proceed with completion flow
            await self.complete_ticket(interaction, ticket_data)

        except ValueError as e:
            embed = create_themed_embed(
                title="Permission Denied",
                description=str(e),
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error confirming receipt: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Issue with Payment",
        style=discord.ButtonStyle.danger,
        emoji="⚠️",
        custom_id="client_payment_issue:persistent"
    )
    async def issue_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Client reports issue with payment"""
        try:
            await interaction.response.defer()

            # Alert staff
            embed = create_themed_embed(
                title="Payment Issue Reported",
                description=f"{interaction.user.mention} has reported an issue with the payment for ticket **#{self.ticket_number}**.\n\nA staff member will investigate shortly.",
                color=ERROR_RED
            )

            await interaction.channel.send(embed=embed)

            # Ping staff
            guild = interaction.guild
            staff_role = guild.get_role(config.ROLE_STAFF)

            if staff_role:
                await interaction.channel.send(
                    content=f"{staff_role.mention} Payment issue reported in this ticket."
                )

        except Exception as e:
            logger.error(f"Error reporting payment issue: {e}", exc_info=True)

    async def complete_ticket(self, interaction: discord.Interaction, ticket_data: Dict[str, Any]):
        """
        Complete ticket: vouches, transcripts, DMs, history log, fee collection
        """
        try:
            ticket_number = ticket_data.get("ticket_number")
            amount_usd = ticket_data.get("amount_usd", 0)
            receiving_amount = ticket_data.get("receiving_amount", 0)
            client_id = int(ticket_data.get("discord_user_id")) if ticket_data.get("discord_user_id") else None
            exchanger_id = int(ticket_data.get("exchanger_discord_id")) if ticket_data.get("exchanger_discord_id") else None

            send_method_id = ticket_data.get("send_method")
            receive_method_id = ticket_data.get("receive_method")
            send_crypto_id = ticket_data.get("send_crypto")
            receive_crypto_id = ticket_data.get("receive_crypto")

            guild = interaction.guild
            client_member = guild.get_member(client_id)
            exchanger_member = guild.get_member(exchanger_id) if exchanger_id else None

            # Get payment method details
            from utils.payment_methods import format_payment_method_display
            send_display = format_payment_method_display(send_crypto_id or send_method_id)
            receive_display = format_payment_method_display(receive_crypto_id or receive_method_id)

            # Get emoji for receive method (for history embed)
            receive_value = (receive_crypto_id or receive_method_id or "").lower()
            try:
                bot = guild.me._state._get_client()
                emojis = config.get_emojis(bot) if bot else {}
                emoji = emojis.get(receive_value, "💱")
            except Exception:
                emoji = "💱"

            # Keep send_method and receive_method for legacy compatibility
            send_method = get_payment_method(send_method_id)
            receive_method = get_payment_method(receive_method_id)

            # ====================================================================
            # 1. Generate Pre-made Vouch
            # ====================================================================

            # Clean vouch format: +rep @exchanger $Amount Method to Method
            vouch_text = f"+rep {exchanger_member.mention if exchanger_member else '@Exchanger'} ${amount_usd:,.2f} {send_display} to {receive_display}"

            vouch_embed = create_themed_embed(
                title="Leave a Vouch",
                description=f"Please leave a vouch for the exchanger in {guild.get_channel(config.CHANNEL_REPUTATION).mention if config.CHANNEL_REPUTATION else '#rep'}!\n\n**Copy and paste:**\n```{vouch_text}```",
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=vouch_embed)

            # ====================================================================
            # 2. Generate Professional HTML Transcript
            # ====================================================================

            try:
                from utils.support_transcript import generate_support_transcript_html

                # Get all messages from channel
                messages = []
                async for message in interaction.channel.history(limit=200, oldest_first=True):
                    messages.append(message)

                # Get ticket creation time (approximate from first message)
                opened_at = messages[0].created_at if messages else datetime.utcnow()
                closed_at = datetime.utcnow()

                # Generate HTML transcript
                transcript_html = generate_support_transcript_html(
                    ticket_number=ticket_number,
                    ticket_type="exchange_ticket",
                    messages=messages,
                    opened_by=client_member or interaction.user,
                    closed_by=interaction.user,
                    opened_at=opened_at,
                    closed_at=closed_at
                )

                # Save transcript to file
                import os
                import tempfile
                transcript_filename = f"exchange_ticket_{ticket_number}.html"
                transcript_path = os.path.join(tempfile.gettempdir(), transcript_filename)

                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write(transcript_html)

                transcript_file = discord.File(transcript_path, filename=transcript_filename)

                # Upload transcript to backend and get public URL
                transcript_url = None
                try:
                    # Collect participant discord IDs
                    participants = [str(client_id)] if client_id else []
                    if exchanger_id:
                        participants.append(str(exchanger_id))

                    # Prepare upload request
                    upload_data = {
                        "ticket_id": str(ticket_number),
                        "ticket_type": "application",
                        "ticket_number": ticket_number,
                        "user_id": str(client_id) if client_id else "unknown",
                        "participants": participants,
                        "html_content": transcript_html,
                        "message_count": len(messages)
                    }

                    # Upload to backend
                    api_base = config.API_BASE_URL
                    upload_url = f"{api_base}/transcripts/upload"
                    headers = {
                        "X-Bot-Token": config.BOT_SERVICE_TOKEN,
                        "Content-Type": "application/json"
                    }

                    async with aiohttp.ClientSession() as session:
                        async with session.post(upload_url, json=upload_data, headers=headers) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                transcript_url = result.get("public_url")
                                logger.info(f"Transcript uploaded successfully: {transcript_url}")
                            else:
                                error_text = await resp.text()
                                logger.error(f"Failed to upload transcript: {resp.status} - {error_text}")

                except Exception as e:
                    logger.error(f"Error uploading transcript to backend: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error generating transcript: {e}", exc_info=True)
                transcript_file = None
                transcript_url = None

            # ====================================================================
            # 3. DM Both Parties with Transcripts
            # ====================================================================

            # DM Client
            if client_member and transcript_file:
                try:
                    client_dm_embed = create_themed_embed(
                        title=f"Exchange Complete - Ticket #{ticket_number}",
                        description=f"Your exchange has been completed successfully!\n\n**Amount:** ${amount_usd:,.2f} → ${receiving_amount:,.2f}\n**Method:** {send_display} → {receive_display}\n\nThank you for using our service!",
                        color=PURPLE_GRADIENT
                    )
                    client_dm_embed.set_footer(text="Please leave a vouch in #reputation!")

                    await client_member.send(embed=client_dm_embed)

                    # Send vouch text
                    vouch_dm_embed = create_themed_embed(
                        title="Leave a Vouch",
                        description=f"Please leave a vouch for the exchanger in the reputation channel!\n\n**Copy and paste:**\n```{vouch_text}```",
                        color=PURPLE_GRADIENT
                    )
                    await client_member.send(embed=vouch_dm_embed)

                    # Send transcript file
                    with open(transcript_path, "rb") as f:
                        # If we have the public URL, send button with it
                        if transcript_url:
                            view = TranscriptView(transcript_url)
                            await client_member.send(
                                "Here's your ticket transcript:",
                                file=discord.File(f, filename=transcript_filename),
                                view=view
                            )
                        else:
                            await client_member.send(
                                "Here's your ticket transcript:",
                                file=discord.File(f, filename=transcript_filename)
                            )
                except discord.Forbidden:
                    logger.warning(f"Could not DM client {client_id}")
                except Exception as e:
                    logger.error(f"Error sending DM to client: {e}")

            # DM Exchanger
            if exchanger_member and transcript_file:
                try:
                    exchanger_dm_embed = create_themed_embed(
                        title=f"Exchange Complete - Ticket #{ticket_number}",
                        description=f"Exchange completed successfully!\n\n**Amount:** ${amount_usd:,.2f} → ${receiving_amount:,.2f}\n**Method:** {send_method.name} → {receive_method.name}\n\nYour funds have been released and fees deducted.",
                        color=PURPLE_GRADIENT
                    )

                    await exchanger_member.send(embed=exchanger_dm_embed)

                    # Send transcript file
                    with open(transcript_path, "rb") as f:
                        # If we have the public URL, send button with it
                        if transcript_url:
                            view = TranscriptView(transcript_url)
                            await exchanger_member.send(
                                "Here's your ticket transcript:",
                                file=discord.File(f, filename=transcript_filename),
                                view=view
                            )
                        else:
                            await exchanger_member.send(
                                "Here's your ticket transcript:",
                                file=discord.File(f, filename=transcript_filename)
                            )
                except discord.Forbidden:
                    logger.warning(f"Could not DM exchanger {exchanger_id}")
                except Exception as e:
                    logger.error(f"Error sending DM to exchanger: {e}")

            # ====================================================================
            # 4. Post to History Channel
            # ====================================================================

            history_channel = guild.get_channel(config.exchange_history_channel)
            if history_channel:
                # Create V3-style embed
                history_embed = discord.Embed(
                    title=f"{emoji} Exchange Completed",
                    description=(
                        f"<@{client_id}> → <@{exchanger_id}>\n\n"
                        f"**Exchange**\n"
                        f"{send_display} → {receive_display}\n\n"
                        f"**Amount**\n"
                        f"${amount_usd:,.2f}"
                    ),
                    color=PURPLE_GRADIENT
                )
                history_embed.set_footer(text=f"Ticket #{ticket_number}")
                history_embed.timestamp = datetime.utcnow()

                await history_channel.send(embed=history_embed)

            # ====================================================================
            # 5. Save Transcript to Transcript Channel
            # ====================================================================

            transcript_channel = guild.get_channel(config.transcript_channel)
            if transcript_channel and transcript_file:
                try:
                    transcript_embed = create_themed_embed(
                        title=f"Exchange Transcript - Ticket #{ticket_number}",
                        description=f"**Client:** {client_member.mention if client_member else 'Unknown'}\n**Exchanger:** {exchanger_member.mention if exchanger_member else 'Unknown'}\n**Amount:** ${amount_usd:,.2f}\n**Completed:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                        color=PURPLE_GRADIENT
                    )

                    with open(transcript_path, "rb") as f:
                        await transcript_channel.send(
                            embed=transcript_embed,
                            file=discord.File(f, filename=transcript_filename)
                        )
                except Exception as e:
                    logger.error(f"Error posting transcript to channel: {e}")

            # ====================================================================
            # 5. Release Funds and Collect Server Fee (handled by backend)
            # ====================================================================

            # The backend should:
            # - Release exchanger's locked funds
            # - Collect server fee (min 50 cents or 2% of amount)
            # - Send fee to admin wallet automatically

            # ====================================================================
            # 6. Close and Delete Channel
            # ====================================================================

            final_embed = create_themed_embed(
                title="Thank You!",
                description=f"This ticket has been completed.\n\nThis channel will be deleted in 30 seconds.\n\n**Don't forget to leave a vouch!**",
                color=PURPLE_GRADIENT
            )

            await interaction.channel.send(embed=final_embed)

            # Delete channel after 30 seconds
            import asyncio
            await asyncio.sleep(30)

            # Delete main client channel
            try:
                await interaction.channel.delete(reason=f"Ticket #{ticket_number} completed")
            except Exception as e:
                logger.error(f"Error deleting client channel: {e}")

            # Also delete exchanger channel if it exists
            exchanger_channel_id = ticket_data.get("exchanger_channel_id")
            if exchanger_channel_id:
                try:
                    exchanger_channel = guild.get_channel(int(exchanger_channel_id))
                    if exchanger_channel:
                        await exchanger_channel.delete(reason=f"Ticket #{ticket_number} completed")
                        logger.info(f"Deleted exchanger channel {exchanger_channel_id}")
                except Exception as e:
                    logger.error(f"Error deleting exchanger channel: {e}")

        except Exception as e:
            logger.error(f"Error completing ticket: {e}", exc_info=True)
