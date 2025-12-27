"""
Application Handler for V4
Creates and manages exchanger applications with two-tier approval system
"""

import logging
from typing import Optional
from datetime import datetime
import io

import discord

from api.errors import APIError
from config import config
from utils.embeds import create_themed_embed, error_embed
from utils.colors import PURPLE_GRADIENT, ERROR_RED
from utils.support_transcript import generate_support_transcript_html

logger = logging.getLogger(__name__)


async def create_application(
    bot: discord.Bot,
    interaction: discord.Interaction,
    payment_methods: str,
    crypto_amount: str,
    experience: str,
    availability: str,
    account_age_days: int
) -> None:
    """
    Create exchanger application with two-tier approval system

    Args:
        bot: Bot instance
        interaction: Discord interaction
        payment_methods: Payment methods available
        crypto_amount: Crypto amount available
        experience: Past experience or vouches
        availability: Availability and timezone
        account_age_days: Discord account age in days
    """
    api = bot.api_client
    guild = interaction.guild

    try:
        # Create application via API
        app_data = await api.post(
            "/api/v1/exchanger-applications/submit",
            data={
                "payment_methods": payment_methods,
                "crypto_holdings": crypto_amount,
                "experience": experience,
                "availability": availability
            },
            discord_user_id=str(interaction.user.id)
        )

        app_id = app_data.get("application_id", "unknown")

        # Get highest application number
        category = guild.get_channel(config.applications_category)
        if not category:
            await interaction.followup.send(
                embed=error_embed(
                    description="Application category not configured. Please contact an admin."
                ),
                ephemeral=True
            )
            return

        existing_channels = [ch for ch in category.channels if ch.name.startswith("application-")]
        highest_number = 0
        for ch in existing_channels:
            try:
                number = int(ch.name.split("-")[1])
                if number > highest_number:
                    highest_number = number
            except (IndexError, ValueError):
                continue

        # Also check transcript channel for highest application number
        transcript_channel = guild.get_channel(config.transcript_channel)
        if transcript_channel:
            try:
                # Fetch recent messages to find highest application number
                async for message in transcript_channel.history(limit=100):
                    if message.embeds and len(message.embeds) > 0:
                        embed = message.embeds[0]
                        if embed.description and "Application Number: #" in embed.description:
                            try:
                                # Extract application number from embed
                                lines = embed.description.split("\n")
                                for line in lines:
                                    if "Application Number: #" in line:
                                        num_str = line.split("#")[1].split("\n")[0].strip()
                                        number = int(num_str)
                                        if number > highest_number:
                                            highest_number = number
                                        break
                            except (IndexError, ValueError):
                                continue
            except Exception as e:
                logger.warning(f"Could not check transcript channel for application numbers: {e}")

        app_number = highest_number + 1

        # Create private application channel
        channel = await category.create_text_channel(
            name=f"application-{app_number}",
            topic=f"Exchanger Application | User: {interaction.user.name} | ID: {app_id}"
        )

        # Set permissions - only applicant, staff, and admins
        await channel.set_permissions(
            guild.default_role,
            view_channel=False
        )

        await channel.set_permissions(
            interaction.user,
            view_channel=True,
            send_messages=False,
            read_message_history=True,
            attach_files=False,
            embed_links=False,
            add_reactions=True  # Need this to click buttons
        )

        staff_role = guild.get_role(config.staff_role)
        if staff_role:
            await channel.set_permissions(
                staff_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )

        admin_role = guild.get_role(config.head_admin_role)
        if admin_role:
            await channel.set_permissions(
                admin_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                manage_channels=True
            )

        # Post application details with exchanger system explanation
        await post_application_details(
            channel=channel,
            user=interaction.user,
            app_id=app_id,
            app_number=app_number,
            payment_methods=payment_methods,
            crypto_amount=crypto_amount,
            experience=experience,
            availability=availability,
            account_age_days=account_age_days,
            bot=bot
        )

        # Send confirmation to user
        confirm_embed = create_themed_embed(
            title="",
            description=(
                f"**Application Submitted**\n\n"
                f"**Application:** #{app_number}\n"
                f"**Channel:** {channel.mention}\n\n"
                f"Our staff team will review your application shortly.\n"
                f"You'll be notified once a decision has been made."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.followup.send(
            embed=confirm_embed,
            ephemeral=True
        )

        logger.info(f"Created application #{app_number} (ID: {app_id}) for user {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error creating application: {e}")

        # Parse validation errors for user-friendly messages
        error_msg = e.user_message
        if "String should have at least" in str(e):
            error_msg = (
                "Your application responses are too short. Please provide more detail:\n\n"
                "• Payment Methods: At least 10 characters\n"
                "• Crypto Amount: At least 5 characters\n"
                "• Experience/Vouches: At least 20 characters\n"
                "• Availability: At least 10 characters"
            )

        await interaction.followup.send(
            embed=error_embed(
                description=error_msg
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error creating application: {e}", exc_info=True)

        # Check if it's a validation error
        error_str = str(e)
        if "string_too_short" in error_str or "String should have at least" in error_str:
            error_msg = (
                "Your application responses are too short. Please provide more detail:\n\n"
                "• Payment Methods: At least 10 characters\n"
                "• Crypto Amount: At least 5 characters\n"
                "• Experience/Vouches: At least 20 characters\n"
                "• Availability: At least 10 characters"
            )
        else:
            error_msg = "An error occurred while creating your application. Please try again."

        await interaction.followup.send(
            embed=error_embed(
                description=error_msg
            ),
            ephemeral=True
        )


async def post_application_details(
    channel: discord.TextChannel,
    user: discord.User,
    app_id: str,
    app_number: int,
    payment_methods: str,
    crypto_amount: str,
    experience: str,
    availability: str,
    account_age_days: int,
    bot: discord.Bot
) -> None:
    """Post application details with exchanger system explanation"""

    # Application details embed
    app_embed = create_themed_embed(
        title="",
        description=(
            f"**Exchanger Application #{app_number}**\n\n"
            f"**Applicant:** {user.mention}\n"
            f"**Account Age:** {account_age_days} days\n"
            f"**Application Number:** `#{app_number}`\n\n"
            f"**Payment Methods:**\n```\n{payment_methods}\n```\n"
            f"**Crypto Amount:**\n```\n{crypto_amount}\n```\n"
            f"**Experience / Vouches:**\n```\n{experience}\n```\n"
            f"**Availability:**\n```\n{availability}\n```"
        ),
        color=PURPLE_GRADIENT
    )

    # Exchanger system explanation embed
    system_embed = create_themed_embed(
        title="",
        description=(
            f"**Our Exchange System with Escrow**\n\n"
            f"Before proceeding, please review how our exchange system works:\n\n"
            f"**How It Works:**\n"
            f"• Customers create exchange tickets through our bot\n"
            f"• You (exchanger) claim tickets you can fulfill\n"
            f"• Your deposited crypto is held in escrow during active tickets\n"
            f"• Customer sends their payment (PayPal, CashApp, etc.)\n"
            f"• You send crypto to customer (from bot wallet or external)\n"
            f"• Escrow releases your held funds after completion\n\n"
            f"**Deposit Requirements:**\n"
            f"• You must deposit crypto into the bot to become an exchanger\n"
            f"• We support 8 cryptocurrencies: BTC, LTC, SOL, ETH, USDT (SOL/ETH), USDC (SOL/ETH)\n"
            f"• Deposits are held in escrow only during active exchanges\n"
            f"• You can withdraw your funds anytime when not locked in tickets\n"
            f"• You can pay customers from bot wallet OR external wallet\n\n"
            f"**Benefits:**\n"
            f"• Protects customers from scammers\n"
            f"• Builds trust in the platform\n"
            f"• Simple and secure\n\n"
            f"**Do you accept this system?**\n"
            f"Please click Accept or Decline below:"
        ),
        color=PURPLE_GRADIENT
    )

    # Import view
    from cogs.applications.views.review_view import StaffReviewView

    view = StaffReviewView(bot, app_id, app_number, user.id, datetime.utcnow())

    await channel.send(content=f"{user.mention}", embed=app_embed)
    await channel.send(embed=system_embed, view=view)

    # Ping staff role
    staff_role = channel.guild.get_role(config.staff_role)
    if staff_role:
        await channel.send(
            f"{staff_role.mention} New exchanger application to review!",
            delete_after=5
        )

    logger.info(f"Posted application #{app_number} details in {channel.id}")


async def staff_accept_application(
    bot: discord.Bot,
    app_id: str,
    app_number: int,
    channel: discord.TextChannel,
    user_id: int,
    accepted_by: discord.User,
    opened_at: datetime
) -> None:
    """
    Staff accepts application - sends to admin for final approval
    """
    guild = channel.guild

    try:
        # Get applicant
        applicant = guild.get_member(user_id)
        if not applicant:
            await channel.send("❌ Applicant not found in server.")
            return

        # Disable staff buttons
        for msg in [msg async for msg in channel.history(limit=10)]:
            if msg.components:
                try:
                    for component in msg.components:
                        for item in component.children:
                            item.disabled = True
                    await msg.edit(view=discord.ui.View.from_message(msg))
                except:
                    pass

        # Post applicant acceptance message
        applicant_accept_embed = create_themed_embed(
            title="",
            description=(
                f"**Applicant Accepted Escrow System**\n\n"
                f"{accepted_by.mention} has agreed to the escrow system requirements.\n\n"
                f"**Status:** Pending Staff Review\n\n"
                f"Waiting for staff review..."
            ),
            color=PURPLE_GRADIENT
        )

        await channel.send(embed=applicant_accept_embed)

        # Create admin overview embed with quick info
        admin_embed = create_themed_embed(
            title="",
            description=(
                f"**Staff Review Required**\n\n"
                f"**Applicant:** {applicant.mention}\n"
                f"**Application:** #{app_number}\n"
                f"**Applicant Accepted:** {accepted_by.mention}\n"
                f"**Account Age:** {(discord.utils.utcnow() - applicant.created_at).days} days\n\n"
                f"Please review the application details above and make a decision."
            ),
            color=PURPLE_GRADIENT
        )

        # Import admin view
        from cogs.applications.views.review_view import AdminReviewView

        admin_view = AdminReviewView(bot, app_id, app_number, user_id, opened_at)

        # Ping admin
        admin_role = guild.get_role(config.head_admin_role)
        admin_mention = admin_role.mention if admin_role else "@Admin"

        await channel.send(
            content=f"{admin_mention} Please review this application!",
            embed=admin_embed,
            view=admin_view
        )

        logger.info(f"Application #{app_number} accepted by staff {accepted_by.id}, awaiting admin")

    except Exception as e:
        logger.error(f"Error in staff accept: {e}", exc_info=True)
        await channel.send(
            embed=error_embed(description=f"Error processing acceptance: {str(e)}")
        )


async def staff_decline_application(
    bot: discord.Bot,
    app_id: str,
    app_number: int,
    channel: discord.TextChannel,
    user_id: int,
    declined_by: discord.User,
    reason: str,
    opened_at: datetime
) -> None:
    """
    Staff declines application - generates transcript and closes
    """
    guild = channel.guild

    try:
        # Get applicant
        applicant = guild.get_member(user_id)

        # Post decline message
        decline_embed = create_themed_embed(
            title="",
            description=(
                f"**Application Declined**\n\n"
                f"**Application:** #{app_number}\n"
                f"**Declined By:** {declined_by.mention}\n\n"
                f"**Reason:**\n{reason}\n\n"
                f"Generating transcript and closing ticket..."
            ),
            color=ERROR_RED
        )

        await channel.send(embed=decline_embed)

        # Generate and save transcript
        await save_application_transcript(
            bot=bot,
            channel=channel,
            app_number=app_number,
            app_type="Exchanger Application",
            applicant=applicant or discord.Object(id=user_id),
            closed_by=declined_by,
            opened_at=opened_at,
            closed_at=datetime.utcnow(),
            status="Declined by Staff"
        )

        # DM applicant
        if applicant:
            try:
                dm_embed = create_themed_embed(
                    title="",
                    description=(
                        f"**Exchanger Application Update**\n\n"
                        f"Your exchanger application on **{guild.name}** has been reviewed.\n\n"
                        f"**Status:** Declined\n\n"
                        f"**Reason:**\n{reason}\n\n"
                        f"You may reapply after addressing the feedback above."
                    ),
                    color=ERROR_RED
                )
                await applicant.send(embed=dm_embed)
            except:
                logger.warning(f"Could not DM declined applicant {user_id}")

        logger.info(f"Application #{app_number} declined by staff {declined_by.id}")

        # Close channel after delay
        import asyncio
        await asyncio.sleep(10)
        await channel.delete(reason=f"Application #{app_number} declined by staff")

    except Exception as e:
        logger.error(f"Error in staff decline: {e}", exc_info=True)
        await channel.send(
            embed=error_embed(description=f"Error processing decline: {str(e)}")
        )


async def admin_approve_application(
    bot: discord.Bot,
    app_id: str,
    app_number: int,
    channel: discord.TextChannel,
    user_id: int,
    approved_by: discord.User,
    opened_at: datetime
) -> None:
    """
    Admin approves application - gives role, updates DB, changes nickname, posts welcome
    """
    guild = channel.guild

    try:
        # Get applicant
        applicant = guild.get_member(user_id)
        if not applicant:
            await channel.send("❌ Applicant not found in server.")
            return

        # Update status in API (marks user as approved exchanger)
        await bot.api_client.post(
            f"/api/v1/admin/exchanger-applications/{app_id}/review",
            data={
                "status": "approved",
                "review_notes": f"Approved by {approved_by.name} via Discord bot"
            },
            discord_user_id=str(approved_by.id)
        )

        # Assign exchanger role
        exchanger_role = guild.get_role(config.exchanger_role)
        if exchanger_role:
            await applicant.add_roles(exchanger_role, reason=f"Application approved by {approved_by.name}")
            logger.info(f"Assigned exchanger role to {applicant.id}")

        # Change nickname to include "(Claim Needed)"
        try:
            current_nick = applicant.display_name
            # Remove any existing (Claim Needed) to avoid duplicates
            clean_nick = current_nick.replace(" (Claim Needed)", "").strip()
            new_nick = f"{clean_nick} (Claim Needed)"

            # Check if nickname would exceed Discord's 32 character limit
            if len(new_nick) > 32:
                # If too long, just use generic nickname
                new_nick = "Exchanger (Claim Needed)"
                logger.warning(f"Original nickname too long, using generic: {new_nick}")

            await applicant.edit(nick=new_nick, reason="New exchanger - needs to claim first ticket")
            logger.info(f"✅ Changed nickname to: {new_nick}")
        except discord.Forbidden as e:
            logger.error(f"❌ No permission to change nickname for {applicant.id} ({applicant.name}): {e}")
            await channel.send(
                f"⚠️ **Warning:** Could not change {applicant.mention}'s nickname to add (Claim Needed). "
                f"Please ensure the bot has Manage Nicknames permission and is higher in the role hierarchy."
            )
        except discord.HTTPException as e:
            logger.error(f"❌ Failed to change nickname for {applicant.id}: {e}")
            await channel.send(f"⚠️ **Warning:** Failed to change nickname: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error changing nickname for {applicant.id}: {e}", exc_info=True)
            await channel.send(f"⚠️ **Warning:** Could not change nickname due to an error.")

        # Post approval message in ticket
        approval_embed = create_themed_embed(
            title="",
            description=(
                f"**Application Approved**\n\n"
                f"**Applicant:** {applicant.mention}\n"
                f"**Approved By:** {approved_by.mention}\n\n"
                f"Congratulations! You are now an exchanger.\n\n"
                f"Generating transcript and sending welcome messages..."
            ),
            color=PURPLE_GRADIENT
        )

        await channel.send(embed=approval_embed)

        # Post welcome message in exchanger chat
        exchanger_chat = guild.get_channel(config.exchanger_chat_channel)
        if exchanger_chat:
            welcome_embed = create_themed_embed(
                title="",
                description=(
                    f"**Welcome New Exchanger!**\n\n"
                    f"Please welcome {applicant.mention} to the Afroo Exchange team!\n\n"
                    f"**Next Steps:**\n"
                    f"• Read <#{config.exchanger_faq_channel}>\n"
                    f"• Read <#{config.exchanger_rules_channel}>\n"
                    f"• Deposit crypto to get started\n"
                    f"• Start claiming tickets!\n\n"
                    f"Good luck and happy exchanging!"
                ),
                color=PURPLE_GRADIENT
            )
            await exchanger_chat.send(content=f"{applicant.mention}", embed=welcome_embed)
            logger.info(f"Posted welcome message for {applicant.id}")

        # Generate and save transcript
        await save_application_transcript(
            bot=bot,
            channel=channel,
            app_number=app_number,
            app_type="Exchanger Application",
            applicant=applicant,
            closed_by=approved_by,
            opened_at=opened_at,
            closed_at=datetime.utcnow(),
            status="Approved"
        )

        # DM applicant
        try:
            dm_embed = create_themed_embed(
                title="",
                description=(
                    f"**Exchanger Application Approved**\n\n"
                    f"Congratulations! Your exchanger application on **{guild.name}** has been approved!\n\n"
                    f"**Next Steps:**\n"
                    f"• Visit the exchanger channels in the server\n"
                    f"• Read the exchanger FAQ and rules\n"
                    f"• Deposit crypto to your bot wallet\n"
                    f"• Start claiming tickets!\n\n"
                    f"Welcome to the Afroo Exchange team!"
                ),
                color=PURPLE_GRADIENT
            )
            await applicant.send(embed=dm_embed)
        except:
            logger.warning(f"Could not DM approved applicant {user_id}")

        logger.info(f"Application #{app_number} approved by admin {approved_by.id}")

        # Close channel after delay
        import asyncio
        await asyncio.sleep(10)
        await channel.delete(reason=f"Application #{app_number} approved")

    except Exception as e:
        logger.error(f"Error in admin approve: {e}", exc_info=True)
        await channel.send(
            embed=error_embed(description=f"Error processing approval: {str(e)}")
        )


async def admin_deny_application(
    bot: discord.Bot,
    app_id: str,
    app_number: int,
    channel: discord.TextChannel,
    user_id: int,
    denied_by: discord.User,
    reason: str,
    opened_at: datetime
) -> None:
    """
    Admin denies application - generates transcript and closes
    """
    guild = channel.guild

    try:
        # Update status in API
        await bot.api_client.post(
            f"/api/v1/admin/exchanger-applications/{app_id}/review",
            data={
                "status": "rejected",
                "review_notes": f"Denied by {denied_by.name}: {reason}"
            },
            discord_user_id=str(denied_by.id)
        )

        # Get applicant
        applicant = guild.get_member(user_id)

        # Post denial message
        denial_embed = create_themed_embed(
            title="",
            description=(
                f"**Application Denied**\n\n"
                f"**Application:** #{app_number}\n"
                f"**Denied By:** {denied_by.mention}\n\n"
                f"**Reason:**\n{reason}\n\n"
                f"Generating transcript and closing ticket..."
            ),
            color=ERROR_RED
        )

        await channel.send(embed=denial_embed)

        # Generate and save transcript
        await save_application_transcript(
            bot=bot,
            channel=channel,
            app_number=app_number,
            app_type="Exchanger Application",
            applicant=applicant or discord.Object(id=user_id),
            closed_by=denied_by,
            opened_at=opened_at,
            closed_at=datetime.utcnow(),
            status="Denied by Admin"
        )

        # DM applicant
        if applicant:
            try:
                dm_embed = create_themed_embed(
                    title="",
                    description=(
                        f"**Exchanger Application Update**\n\n"
                        f"Your exchanger application on **{guild.name}** has been reviewed.\n\n"
                        f"**Status:** Denied\n\n"
                        f"**Reason:**\n{reason}\n\n"
                        f"You may reapply after addressing the feedback above."
                    ),
                    color=ERROR_RED
                )
                await applicant.send(embed=dm_embed)
            except:
                logger.warning(f"Could not DM denied applicant {user_id}")

        logger.info(f"Application #{app_number} denied by admin {denied_by.id}")

        # Close channel after delay
        import asyncio
        await asyncio.sleep(10)
        await channel.delete(reason=f"Application #{app_number} denied by admin")

    except Exception as e:
        logger.error(f"Error in admin deny: {e}", exc_info=True)
        await channel.send(
            embed=error_embed(description=f"Error processing denial: {str(e)}")
        )


async def save_application_transcript(
    bot: discord.Bot,
    channel: discord.TextChannel,
    app_number: int,
    app_type: str,
    applicant: discord.User,
    closed_by: discord.User,
    opened_at: datetime,
    closed_at: datetime,
    status: str
) -> None:
    """Generate and save application transcript"""
    try:
        guild = channel.guild

        # Fetch all messages
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            messages.append(message)

        # Generate transcript HTML
        html_transcript = generate_support_transcript_html(
            ticket_number=app_number,
            ticket_type=app_type,
            messages=messages,
            opened_by=applicant,
            closed_by=closed_by,
            opened_at=opened_at,
            closed_at=closed_at
        )

        # Upload transcript to backend API
        try:
            import aiohttp
            from config import config

            api_base = config.API_BASE_URL
            upload_url = f"{api_base}/api/v1/transcripts/upload"
            bot_token = config.BOT_SERVICE_TOKEN

            upload_data = {
                "ticket_id": str(app_number),
                "ticket_type": "application",
                "ticket_number": app_number,
                "user_id": str(applicant.id),
                "participants": [str(closed_by.id)],
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
                        logger.info(f"Uploaded application transcript #{app_number} to backend: {public_url}")
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to upload application transcript: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Error uploading application transcript: {e}", exc_info=True)

        # Create HTML file for channel
        html_file_channel = discord.File(
            io.BytesIO(html_transcript.encode('utf-8')),
            filename=f"application_{app_number}.html"
        )

        # Create HTML file for DM
        html_file_dm = discord.File(
            io.BytesIO(html_transcript.encode('utf-8')),
            filename=f"application_{app_number}.html"
        )

        # Send to transcript channel
        transcript_channel = guild.get_channel(config.transcript_channel)
        if transcript_channel:
            try:
                transcript_embed = create_themed_embed(
                    title="",
                    description=(
                        f"**Exchanger Application Transcript**\n\n"
                        f"Application Number: #{app_number}\n"
                        f"Type: {app_type}\n"
                        f"Applicant: {applicant.name}\n"
                        f"Closed By: {closed_by.name}\n"
                        f"Status: {status}\n"
                        f"Date: {closed_at.strftime('%B %d, %Y at %I:%M %p UTC')}"
                    ),
                    color=PURPLE_GRADIENT
                )

                from cogs.panels.views.support_ticket_view import TranscriptButton
                view = TranscriptButton(app_number, ticket_category="application")

                await transcript_channel.send(
                    embed=transcript_embed,
                    file=html_file_channel,
                    view=view
                )
                logger.info(f"Saved transcript for application #{app_number}")
            except Exception as e:
                logger.error(f"Failed to save transcript to channel: {e}")

        # Send DM to applicant
        if isinstance(applicant, discord.Member):
            try:
                dm_embed = create_themed_embed(
                    title="",
                    description=(
                        f"**Exchanger Application Closed**\n\n"
                        f"Application: #{app_number}\n"
                        f"Status: {status}\n"
                        f"Closed By: {closed_by.name}\n\n"
                        f"Your application transcript is attached below."
                    ),
                    color=PURPLE_GRADIENT
                )

                from cogs.panels.views.support_ticket_view import TranscriptButton
                view = TranscriptButton(app_number, ticket_category="application")

                await applicant.send(
                    embed=dm_embed,
                    file=html_file_dm,
                    view=view
                )
            except:
                logger.warning(f"Could not DM transcript to applicant {applicant.id}")

    except Exception as e:
        logger.error(f"Error generating application transcript: {e}", exc_info=True)
