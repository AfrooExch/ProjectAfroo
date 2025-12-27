"""
Completion Handler for V4
Handles ticket completion: hold release, stats, transcripts, DMs, history
"""

import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

import discord

from api.client import APIClient
from api.errors import APIError
from utils.embeds import create_success_embed
from utils.colors import SUCCESS
from config import config

logger = logging.getLogger(__name__)


async def complete_ticket(
    bot: discord.Bot,
    ticket_id: str,
    channel: discord.TextChannel,
    ticket_data: Dict[str, Any]
):
    """
    Complete ticket workflow:
    1. Release holds (via API)
    2. Update stats (via API)
    3. Generate transcript
    4. Post to history channel
    5. DM both parties with vouch instructions
    6. Assign customer role
    7. Delete channel after delay
    """
    logger.info(f"[COMPLETION] Starting completion workflow for ticket #{ticket_id}")
    logger.info(f"[COMPLETION] Ticket data keys: {list(ticket_data.keys())}")

    api: APIClient = bot.api_client
    guild = channel.guild

    try:
        # Step 1: Complete ticket via API
        # This handles: hold release, fee deduction, stats update
        logger.info(f"[COMPLETION] Calling API to complete ticket {ticket_id}")

        # Get user context for API authentication - use customer ID from ticket_data
        customer_discord_id = ticket_data.get("discord_user_id")
        if not customer_discord_id:
            raise ValueError("Missing discord_user_id in ticket_data - cannot complete ticket")

        completion_result = await api.complete_ticket(
            ticket_id,
            discord_user_id=str(customer_discord_id),
            discord_roles=[]
        )

        logger.info(f"[COMPLETION] Ticket #{ticket_id} completed via API: {completion_result}")

        # Extract data - use correct field names from API response
        customer_id = int(ticket_data.get("discord_user_id", 0)) if ticket_data.get("discord_user_id") else 0
        exchanger_id = int(ticket_data.get("exchanger_discord_id", 0)) if ticket_data.get("exchanger_discord_id") else 0
        amount_usd = ticket_data.get("amount_usd", 0)
        fee_amount = ticket_data.get("fee_amount", 0)

        # Get members
        customer = guild.get_member(customer_id) if customer_id else None
        exchanger = guild.get_member(exchanger_id) if exchanger_id else None

        logger.info(f"[COMPLETION] Customer: id={customer_id}, member={customer}, name={customer.name if customer else 'None'}")
        logger.info(f"[COMPLETION] Exchanger: id={exchanger_id}, member={exchanger}, name={exchanger.name if exchanger else 'None'}")

        # Step 2: Post completion message in channel
        await post_completion_message(
            channel=channel,
            customer=customer,
            exchanger=exchanger,
            ticket_id=ticket_id,
            amount_usd=amount_usd
        )

        # Step 3: Generate transcript
        transcript_url = await generate_transcript(
            bot=bot,
            channel=channel,
            ticket_id=ticket_id
        )

        # Step 4: Post to history channel
        await post_to_history(
            bot=bot,
            guild=guild,
            ticket_id=ticket_id,
            ticket_data=ticket_data,
            transcript_url=transcript_url
        )

        # Step 5: DM both parties
        await dm_customer(
            customer=customer,
            exchanger=exchanger,
            ticket_id=ticket_id,
            amount_usd=amount_usd,
            transcript_url=transcript_url,
            guild=guild
        )

        await dm_exchanger(
            exchanger=exchanger,
            customer=customer,
            ticket_id=ticket_id,
            amount_usd=amount_usd,
            fee_amount=fee_amount,
            transcript_url=transcript_url,
            guild=guild,
            ticket_data=ticket_data
        )

        # Step 6: Assign customer role and milestone roles
        logger.info(f"[COMPLETION] Step 6: Assigning customer role and milestones to {customer}")
        await assign_customer_role_and_milestones(bot, guild, customer)
        logger.info(f"[COMPLETION] Step 6: Customer role assignment complete")

        # Step 7: Delete channel after delay
        logger.info(f"[COMPLETION] Step 7: Waiting 30 seconds before deleting channels")
        await asyncio.sleep(30)

        # Delete main client channel
        logger.info(f"[COMPLETION] Deleting client channel {channel.id}")
        try:
            await channel.delete(reason=f"Ticket #{ticket_id} completed")
            logger.info(f"[COMPLETION] ✅ Deleted client channel for completed ticket #{ticket_id}")
        except Exception as e:
            logger.error(f"[COMPLETION] ❌ Error deleting client channel: {e}", exc_info=True)

        # Also delete exchanger channel if it exists
        exchanger_channel_id = ticket_data.get("exchanger_channel_id")
        logger.info(f"[COMPLETION] Checking for exchanger channel: {exchanger_channel_id}")

        exchanger_channel = None
        if exchanger_channel_id:
            try:
                exchanger_channel = guild.get_channel(int(exchanger_channel_id))
                logger.info(f"[COMPLETION] Found exchanger channel by ID: {exchanger_channel}")
            except Exception as e:
                logger.error(f"[COMPLETION] Error getting exchanger channel by ID: {e}")

        # Fallback: Search claimed_tickets and exchanger_tickets categories for matching channel
        if not exchanger_channel:
            logger.info(f"[COMPLETION] Exchanger channel not found by ID, searching categories...")
            try:
                ticket_number = ticket_data.get("ticket_number", "")
                categories_to_search = [
                    ("claimed_tickets", config.CLAIMED_TICKETS_CATEGORY_ID),
                    ("exchanger_tickets", config.EXCHANGER_TICKETS_CATEGORY_ID)
                ]

                for cat_name, cat_id in categories_to_search:
                    if not exchanger_channel and cat_id:
                        category = guild.get_channel(cat_id)
                        if category and hasattr(category, 'channels'):
                            # Look for channel with "exchanger" in the name and matching ticket number
                            for ch in category.channels:
                                if "exchanger" in ch.name.lower() and (str(ticket_number) in ch.name or str(ticket_id) in ch.name):
                                    exchanger_channel = ch
                                    logger.info(f"[COMPLETION] Found exchanger channel in {cat_name} category: {exchanger_channel.name}")
                                    break
            except Exception as e:
                logger.error(f"[COMPLETION] Error searching for exchanger channel: {e}", exc_info=True)

        # Delete exchanger channel if found
        if exchanger_channel:
            try:
                await exchanger_channel.delete(reason=f"Ticket #{ticket_id} completed")
                logger.info(f"[COMPLETION] ✅ Deleted exchanger channel {exchanger_channel.id} for ticket #{ticket_id}")
            except Exception as e:
                logger.error(f"[COMPLETION] ❌ Error deleting exchanger channel: {e}", exc_info=True)
        else:
            logger.warning(f"[COMPLETION] No exchanger channel found to delete for ticket #{ticket_id}")

    except Exception as e:
        logger.error(f"Error in completion workflow: {e}", exc_info=True)
        await channel.send(
            f"❌ Error completing ticket: {str(e)}\n\nPlease contact staff for assistance."
        )


async def post_completion_message(
    channel: discord.TextChannel,
    customer: discord.Member,
    exchanger: discord.Member,
    ticket_id: str,
    amount_usd: float
):
    """Post completion message in ticket channel"""
    try:
        rep_channel_id = config.CHANNEL_REP
        rep_mention = f"<#{rep_channel_id}>" if rep_channel_id else "#reputation"

        embed = create_success_embed(
            title="🎉 Exchange Complete!",
            description=(
                f"### Ticket #{ticket_id} has been completed successfully!\n\n"
                f"**Customer:** {customer.mention if customer else 'Unknown'}\n"
                f"**Exchanger:** {exchanger.mention if exchanger else 'Unknown'}\n"
                f"**Amount:** `${amount_usd:,.2f} USD`\n\n"
                f"Thank you for using Afroo Exchange!\n\n"
                f"---\n\n"
                f"**{customer.mention if customer else '@Customer'}** - Please vouch for your exchanger in {rep_mention}:\n"
                f"```\n+rep @{channel.guild.me.name} and @{exchanger.name if exchanger else 'Exchanger'} ${amount_usd:.0f} CRYPTO\n```\n\n"
                f"Both parties will receive a DM with the full transcript.\n\n"
                f"*This channel will be deleted in 30 seconds.*"
            )
        )

        await channel.send(embed=embed)

    except Exception as e:
        logger.error(f"Error posting completion message: {e}")


async def generate_transcript(
    bot: discord.Bot,
    channel: discord.TextChannel,
    ticket_id: str
) -> str:
    """
    Generate HTML transcript of the channel and upload to backend API

    Returns public URL to transcript (or placeholder if generation fails)
    """
    try:
        # Try to use chat_exporter if available
        try:
            import chat_exporter
            import aiohttp

            # Generate transcript HTML
            transcript_html = await chat_exporter.export(channel)

            if transcript_html:
                logger.info(f"Generated HTML transcript for ticket #{ticket_id}")

                # Upload to backend API
                api_base = config.API_BASE_URL
                upload_url = f"{api_base}/api/v1/transcripts/upload"
                bot_token = config.BOT_SERVICE_TOKEN

                # Count messages in HTML for metadata
                message_count = transcript_html.count("class=\"chatlog__message\"")

                # Get customer and exchanger IDs from channel name or metadata
                # Channel name format: ticket-{number}-{customer_id}
                customer_id = "unknown"
                if channel.name.startswith("ticket-"):
                    parts = channel.name.split("-")
                    if len(parts) >= 3:
                        customer_id = parts[2]

                # Prepare upload data
                upload_data = {
                    "ticket_id": ticket_id,
                    "ticket_type": "ticket",
                    "ticket_number": None,
                    "user_id": customer_id,
                    "participants": [],
                    "html_content": transcript_html,
                    "message_count": message_count
                }

                # Upload to backend
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
                            logger.info(f"Uploaded transcript to backend API: {public_url}")
                            return public_url
                        else:
                            error_text = await response.text()
                            logger.error(f"Failed to upload transcript: {response.status} - {error_text}")
                            return f"transcript_{ticket_id}_upload_failed"

        except ImportError:
            logger.warning("chat_exporter not installed, skipping transcript generation")
            return f"transcript_{ticket_id}_unavailable"

    except Exception as e:
        logger.error(f"Error generating transcript: {e}", exc_info=True)
        return f"transcript_{ticket_id}_error"


async def post_to_history(
    bot: discord.Bot,
    guild: discord.Guild,
    ticket_id: str,
    ticket_data: Dict[str, Any],
    transcript_url: str
):
    """Post completed ticket to history channel"""
    try:
        history_channel_id = config.EXCHANGE_HISTORY_CHANNEL_ID
        if not history_channel_id:
            logger.warning("Exchange history channel not configured")
            return

        history_channel = guild.get_channel(history_channel_id)
        if not history_channel:
            logger.warning(f"History channel not found: {history_channel_id}")
            return

        # Get customer and exchanger - use correct field names
        customer_id = ticket_data.get("discord_user_id", "Unknown")
        exchanger_id = ticket_data.get("exchanger_discord_id", "Unknown")
        customer_name = ticket_data.get("client_username", "Unknown")
        exchanger_name = ticket_data.get("exchanger_username", "Unknown")

        # Get exchange details
        send_method = ticket_data.get("send_method", "N/A")
        receive_method = ticket_data.get("receive_method", "N/A")
        amount_usd = ticket_data.get("amount_usd", 0)
        created_at = ticket_data.get("created_at", datetime.utcnow().isoformat())
        completed_at = ticket_data.get("completed_at", datetime.utcnow().isoformat())

        # Create history embed
        embed = discord.Embed(
            title=f"Exchange Completed - #{ticket_id}",
            color=SUCCESS,
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="👤 Participants",
            value=(
                f"**Customer:** <@{customer_id}> (`{customer_name}`)\n"
                f"**Exchanger:** <@{exchanger_id}> (`{exchanger_name}`)"
            ),
            inline=False
        )

        embed.add_field(
            name="💱 Exchange Details",
            value=(
                f"**Sent:** {send_method}\n"
                f"**Received:** {receive_method}\n"
                f"**Amount:** `${amount_usd:,.2f} USD`"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Timeline",
            value=(
                f"**Created:** <t:{int(datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())}:R>\n"
                f"**Completed:** <t:{int(datetime.utcnow().timestamp())}:R>"
            ),
            inline=False
        )

        if transcript_url and "unavailable" not in transcript_url and "error" not in transcript_url:
            embed.add_field(
                name="📝 Transcript",
                value=f"[View Transcript]({transcript_url})",
                inline=False
            )

        embed.set_footer(text=f"Ticket ID: {ticket_id}")

        await history_channel.send(embed=embed)

        logger.info(f"Posted ticket #{ticket_id} to history channel")

    except Exception as e:
        logger.error(f"Error posting to history: {e}")


async def dm_customer(
    customer: discord.Member,
    exchanger: discord.Member,
    ticket_id: str,
    amount_usd: float,
    transcript_url: str,
    guild: discord.Guild
):
    """Send DM to customer with vouch instructions"""
    if not customer:
        return

    try:
        rep_channel_id = config.CHANNEL_REP
        rep_mention = f"<#{rep_channel_id}>" if rep_channel_id else "#reputation"

        # Add transcript URL to description if available
        transcript_line = f"\n**Transcript URL:** {transcript_url}\n" if transcript_url and "unavailable" not in transcript_url and "error" not in transcript_url else ""

        from utils.embeds import create_themed_embed
        from utils.colors import PURPLE_GRADIENT

        embed = create_themed_embed(
            title="",
            description=(
                f"## ✅ Exchange Completed!\n\n"
                f"Your exchange has been completed successfully!\n\n"
                f"**Ticket:** #{ticket_id}\n"
                f"**Amount:** `${amount_usd:,.2f} USD`\n"
                f"**Exchanger:** {exchanger.mention if exchanger else 'Unknown'}{transcript_line}\n"
                f"---\n\n"
                f"### Please Vouch in {rep_mention}\n\n"
                f"**Format:**\n"
                f"```\n+rep @{guild.me.name} and @{exchanger.name if exchanger else 'Exchanger'} ${amount_usd:.0f} CRYPTO\n```\n\n"
                f"**Example:**\n"
                f"```\n+rep @{guild.me.name} and @{exchanger.name if exchanger else 'Exchanger'} ${amount_usd:.0f} CRYPTO Excellent service!\n```\n\n"
                f"---\n\n"
                f"Thank you for using **Afroo Exchange**!"
            ),
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text=f"Ticket #{ticket_id} | Afroo Exchange")

        await customer.send(embed=embed)

        logger.info(f"Sent completion DM to customer {customer.id}")

    except discord.Forbidden:
        logger.warning(f"Could not DM customer {customer.id} - DMs disabled")
    except Exception as e:
        logger.error(f"Error sending customer DM: {e}")


async def dm_exchanger(
    exchanger: discord.Member,
    customer: discord.Member,
    ticket_id: str,
    amount_usd: float,
    fee_amount: float,
    transcript_url: str,
    guild: discord.Guild,
    ticket_data: Dict[str, Any] = None
):
    """Send DM to exchanger with completion details"""
    if not exchanger:
        return

    try:
        # Extract additional ticket details
        customer_method = ticket_data.get("customer_payment_method", "N/A") if ticket_data else "N/A"
        exchanger_method = ticket_data.get("exchanger_payment_method", "N/A") if ticket_data else "N/A"
        customer_amount = ticket_data.get("customer_amount", 0) if ticket_data else 0
        exchanger_amount = ticket_data.get("exchanger_amount", 0) if ticket_data else 0

        # Calculate final balance (amount after fee deduction)
        final_balance = amount_usd - fee_amount

        from utils.embeds import create_themed_embed
        from utils.colors import PURPLE_GRADIENT

        embed = create_themed_embed(
            title="",
            description=(
                f"## 🎉 Ticket Completed!\n\n"
                f"### Transaction Details\n"
                f"**Ticket ID:** #{ticket_id}\n"
                f"**Customer:** {customer.mention if customer else 'Unknown'}\n\n"
                f"**Customer Sent:** `{customer_method.upper()} ${customer_amount:,.2f}`\n"
                f"**You Sent:** `{exchanger_method.upper()} ${exchanger_amount:,.2f}`\n"
                f"**Exchange Amount:** `${amount_usd:,.2f} USD`\n\n"
                f"### Fees & Earnings\n"
                f"**Platform Fee:** `-${fee_amount:.2f} USD`\n"
                f"**Your Earnings:** `+${final_balance:,.2f} USD`\n\n"
                f"> Your locked funds have been released\n"
                f"> Fee has been automatically deducted\n\n"
                f"### Stats Updated\n"
                f"✅ Exchange count increased\n"
                f"✅ Total volume updated\n"
                f"✅ Reputation increased\n\n"
                f"Thank you for being a valued exchanger at **{guild.name}**!"
            ),
            color=PURPLE_GRADIENT
        )

        if transcript_url and "unavailable" not in transcript_url and "error" not in transcript_url:
            embed.add_field(
                name="📝 Transcript",
                value=f"[Download Transcript]({transcript_url})",
                inline=False
            )

        embed.set_footer(text=f"Ticket #{ticket_id} | Afroo Exchange")

        await exchanger.send(embed=embed)

        logger.info(f"Sent completion DM to exchanger {exchanger.id}")

    except discord.Forbidden:
        logger.warning(f"Could not DM exchanger {exchanger.id} - DMs disabled")
    except Exception as e:
        logger.error(f"Error sending exchanger DM: {e}")


async def assign_customer_role_and_milestones(bot: discord.Bot, guild: discord.Guild, customer: discord.Member):
    """Assign customer role and milestone roles based on total volume"""
    logger.info(f"[ROLE ASSIGN] Called for customer: {customer}")

    if not customer:
        logger.warning(f"[ROLE ASSIGN] Customer is None, returning early")
        return

    try:
        # Step 1: Assign CUSTOMER role (with error handling)
        customer_role_id = config.customer_role
        logger.info(f"[ROLE ASSIGN] customer_role from config: {customer_role_id}")

        customer_role_assigned = False
        if customer_role_id:
            try:
                customer_role = guild.get_role(customer_role_id)
                logger.info(f"[ROLE ASSIGN] Found customer role: {customer_role}")
                logger.info(f"[ROLE ASSIGN] Customer current roles: {[r.name for r in customer.roles]}")

                if customer_role:
                    if customer_role not in customer.roles:
                        logger.info(f"[ROLE ASSIGN] Adding customer role to {customer.name}")
                        await customer.add_roles(customer_role, reason="Completed exchange")
                        logger.info(f"[ROLE ASSIGN] ✅ Assigned customer role to user {customer.id}")
                        customer_role_assigned = True
                    else:
                        logger.info(f"[ROLE ASSIGN] Customer already has the role")
                        customer_role_assigned = True

                    # Verify role was added
                    await asyncio.sleep(0.5)  # Brief delay to let Discord API catch up
                    updated_member = guild.get_member(customer.id)
                    if updated_member and customer_role in updated_member.roles:
                        logger.info(f"[ROLE ASSIGN] ✅ Verified customer role is assigned")
                    else:
                        logger.warning(f"[ROLE ASSIGN] ⚠️ Customer role may not have been applied properly")
                else:
                    logger.warning(f"[ROLE ASSIGN] Customer role not found in guild (role ID: {customer_role_id})")
            except discord.Forbidden:
                logger.error(f"[ROLE ASSIGN] ❌ Missing permissions to assign customer role")
            except Exception as role_error:
                logger.error(f"[ROLE ASSIGN] ❌ Error assigning customer role: {role_error}", exc_info=True)
        else:
            logger.warning(f"[ROLE ASSIGN] CUSTOMER_ROLE_ID not configured")

        # Step 2: Fetch client stats to get total volume
        try:
            from utils.auth import get_user_context
            # Use bot user for API call
            logger.info(f"[ROLE ASSIGN] Fetching stats for customer {customer.id}")
            stats_result = await bot.api_client.get(
                f"/api/v1/users/{customer.id}/comprehensive-stats",
                discord_user_id=str(customer.id),
                discord_roles=[]
            )

            # Get total completed volume
            total_volume = stats_result.get("client_total_volume_usd", 0)
            logger.info(f"[ROLE ASSIGN] Client {customer.id} total volume: ${total_volume}")

            # Step 3: Determine which milestone role they should have
            milestone_thresholds = [
                (50000, config.milestone_50000_role),
                (25000, config.milestone_25000_role),
                (10000, config.milestone_10000_role),
                (5000, config.milestone_5000_role),
                (2500, config.milestone_2500_role),
                (1500, config.milestone_1500_role),
                (500, config.milestone_500_role),
            ]

            earned_role_id = None
            earned_threshold = 0

            for threshold, role_id in milestone_thresholds:
                if total_volume >= threshold and role_id:
                    earned_role_id = role_id
                    earned_threshold = threshold
                    break

            # Step 4: Update roles - add earned role, remove lower roles
            if earned_role_id:
                earned_role = guild.get_role(earned_role_id)

                if earned_role:
                    # Add the earned role if they don't have it
                    if earned_role not in customer.roles:
                        await customer.add_roles(earned_role, reason=f"Reached ${earned_threshold} volume")
                        logger.info(f"Assigned milestone role {earned_role.name} to user {customer.id}")

                    # Remove any lower milestone roles they might have
                    all_milestone_role_ids = [role_id for _, role_id in milestone_thresholds if role_id]

                    for role in customer.roles:
                        if role.id in all_milestone_role_ids and role.id != earned_role_id:
                            # This is a milestone role but not the one they should have
                            await customer.remove_roles(role, reason=f"Upgraded to {earned_role.name}")
                            logger.info(f"Removed lower milestone role {role.name} from user {customer.id}")

        except Exception as stats_e:
            logger.error(f"Error fetching stats or assigning milestone roles: {stats_e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in assign_customer_role_and_milestones: {e}", exc_info=True)
