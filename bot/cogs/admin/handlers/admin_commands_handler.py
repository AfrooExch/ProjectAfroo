"""
Admin Slash Commands Handler
Provides force commands for Exchange tickets, AutoMM key reveal, and Swap info
HEAD ADMIN & ASSISTANT ADMIN ONLY
"""

import logging
import discord
from discord.ext import commands
from typing import Optional, Dict, Any

from api.client import APIClient
from api.errors import APIError
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, RED_GRADIENT, GREEN_GRADIENT, BLUE_GRADIENT
from config import config

logger = logging.getLogger(__name__)


def is_admin_or_assistant():
    """Check if user has Head Admin or Assistant Admin role"""
    def predicate(ctx):
        if not ctx.guild:
            return False

        member = ctx.guild.get_member(ctx.author.id)
        if not member:
            return False

        role_ids = [role.id for role in member.roles]
        head_admin_role = config.head_admin_role
        assistant_admin_role = config.assistant_admin_role

        return head_admin_role in role_ids or assistant_admin_role in role_ids

    return commands.check(predicate)


async def get_ticket_by_number(api: APIClient, ticket_number: str) -> Optional[Dict[str, Any]]:
    """
    Get ticket by ticket_number from API

    Args:
        api: API client
        ticket_number: Visible ticket number (e.g., "12345")

    Returns:
        Ticket data dict or None if not found
    """
    try:
        # Get all tickets and find by ticket_number
        # Admin endpoint returns all tickets
        response = await api.get(
            "/api/v1/admin/tickets/all?limit=1000",
            discord_user_id="SYSTEM"
        )

        if not response.get("success") and not response.get("tickets"):
            return None

        tickets = response.get("tickets", [])

        # Search for matching ticket_number
        for ticket in tickets:
            if str(ticket.get("ticket_number")) == str(ticket_number):
                return ticket

        return None

    except APIError as e:
        logger.error(f"Failed to get ticket by number {ticket_number}: {e}")
        return None


async def get_automm_by_id(api: APIClient, mm_id: str) -> Optional[Dict[str, Any]]:
    """
    Get AutoMM escrow by MM ID

    Args:
        api: API client
        mm_id: AutoMM ID (e.g., "9362C5D8" or full escrow_id)

    Returns:
        AutoMM escrow data or None if not found
    """
    try:
        # Use admin search endpoint that handles both mm_id and ObjectId
        # Note: This is called from reveal_automm_key which has the interaction
        # We need to pass the discord_user_id through the API call
        response = await api.get(
            f"/api/v1/admin/automm/search/{mm_id}",
            discord_user_id="SYSTEM"  # Admin endpoints use bot token auth
        )

        if response.get("success") and response.get("escrow"):
            return response["escrow"]

        logger.warning(f"AutoMM {mm_id} not found")
        return None

    except APIError as e:
        logger.error(f"Failed to get AutoMM {mm_id}: {e}")
        return None


async def get_swap_by_id(api: APIClient, swap_id: str) -> Optional[Dict[str, Any]]:
    """
    Get swap by ID

    Args:
        api: API client
        swap_id: Swap ObjectId or identifier

    Returns:
        Swap data or None if not found
    """
    try:
        # Use admin endpoint that bypasses ownership check
        response = await api.get(
            f"/api/v1/admin/swaps/{swap_id}",
            discord_user_id="SYSTEM"
        )

        if response and response.get("success") and response.get("swap"):
            return response["swap"]

        logger.warning(f"Swap {swap_id} not found or invalid response: {response}")
        return None

    except APIError as e:
        logger.error(f"Failed to get swap {swap_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting swap {swap_id}: {e}", exc_info=True)
        return None


# ========================================
# EXCHANGE TICKET FORCE COMMANDS
# ========================================

async def force_close_ticket(
    bot: discord.Bot,
    interaction: discord.Interaction,
    ticket_number: str,
    reason: str
):
    """
    Force close an exchange ticket (bypasses approvals)

    Args:
        bot: Bot instance
        interaction: Discord interaction
        ticket_number: Visible ticket number
        reason: Reason for force closing
    """
    await interaction.response.defer(ephemeral=True)

    api: APIClient = bot.api_client

    try:
        # Get ticket by number
        ticket = await get_ticket_by_number(api, ticket_number)

        if not ticket:
            embed = create_themed_embed(
                title="Ticket Not Found",
                description=f"Could not find ticket #{ticket_number}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        ticket_id = ticket.get("id")

        # Call force-close endpoint
        response = await api.post(
            "/api/v1/admin/tickets/force-close",
            data={
                "ticket_id": ticket_id,
                "reason": reason,
                "release_holds": True
            },
            discord_user_id=str(interaction.user.id)
        )

        if response.get("success"):
            # Get the ticket channel
            channel_id = ticket.get("channel_id")
            if channel_id:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    try:
                        # Create transcript before deleting
                        from cogs.tickets.transcript import create_transcript
                        transcript_file = await create_transcript(channel)

                        # Send transcript to log channel if available
                        log_channel_id = config.channel_ticket_logs if hasattr(config, 'channel_ticket_logs') else None
                        if log_channel_id and transcript_file:
                            log_channel = bot.get_channel(log_channel_id)
                            if log_channel:
                                transcript_embed = create_themed_embed(
                                    title=f"Ticket #{ticket_number} Force Closed",
                                    description=f"**Reason:** {reason}\n**Admin:** {interaction.user.mention}",
                                    color=RED_GRADIENT
                                )
                                await log_channel.send(embed=transcript_embed, file=transcript_file)

                        # Delete the channel
                        await channel.delete(reason=f"Force closed by {interaction.user.name}: {reason}")

                        logger.info(f"Deleted channel {channel_id} for force-closed ticket #{ticket_number}")
                    except Exception as e:
                        logger.error(f"Failed to delete channel for ticket #{ticket_number}: {e}")

            embed = create_themed_embed(
                title="Ticket Force Closed",
                description=f"Successfully force closed ticket **#{ticket_number}**",
                color=GREEN_GRADIENT
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Holds Released", value="Yes", inline=True)
            embed.add_field(name="Channel", value="Deleted" if channel_id else "Not found", inline=True)
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(
                f"Admin {interaction.user.id} force closed ticket #{ticket_number} - Reason: {reason}"
            )
        else:
            error_msg = response.get("message", "Unknown error")
            embed = create_themed_embed(
                title="Force Close Failed",
                description=f"Failed to force close ticket: {error_msg}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    except APIError as e:
        embed = create_themed_embed(
            title="API Error",
            description=f"Failed to force close ticket: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Force close ticket error: {e}", exc_info=True)


async def admin_claim_ticket(
    bot: discord.Bot,
    interaction: discord.Interaction,
    ticket_number: str
):
    """
    Admin claims a ticket for themselves (bypasses balance/deposit checks)

    Args:
        bot: Bot instance
        interaction: Discord interaction
        ticket_number: Visible ticket number
    """
    await interaction.response.defer(ephemeral=True)

    api: APIClient = bot.api_client

    try:
        # Get ticket by number
        ticket = await get_ticket_by_number(api, ticket_number)

        if not ticket:
            embed = create_themed_embed(
                title="Ticket Not Found",
                description=f"Could not find ticket #{ticket_number}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        ticket_id = ticket.get("id")

        # Call force-claim endpoint with admin's own ID
        response = await api.post(
            "/api/v1/admin/tickets/force-claim",
            data={
                "ticket_id": ticket_id,
                "exchanger_discord_id": str(interaction.user.id)
            },
            discord_user_id=str(interaction.user.id)
        )

        if response.get("success"):
            # Update Discord channel permissions
            channel_id = ticket.get("channel_id")
            permissions_updated = False

            if channel_id:
                channel = bot.get_channel(int(channel_id))

                if channel and interaction.user:
                    try:
                        # Give the admin full access to the ticket channel
                        await channel.set_permissions(
                            interaction.user,
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True,
                            attach_files=True,
                            embed_links=True,
                            reason=f"Ticket claimed by admin {interaction.user.name}"
                        )

                        # Send notification in the ticket channel
                        claim_embed = create_themed_embed(
                            title="Ticket Claimed",
                            description=f"This ticket has been claimed by {interaction.user.mention}",
                            color=GREEN_GRADIENT
                        )
                        claim_embed.add_field(
                            name="Claimed By",
                            value=f"{interaction.user.mention} (Admin)",
                            inline=True
                        )
                        await channel.send(embed=claim_embed)

                        permissions_updated = True
                        logger.info(f"Updated permissions for admin {interaction.user.name} on ticket #{ticket_number} channel")
                    except Exception as e:
                        logger.error(f"Failed to update channel permissions for ticket #{ticket_number}: {e}")

            embed = create_themed_embed(
                title="Ticket Claimed",
                description=f"Successfully claimed ticket **#{ticket_number}**",
                color=GREEN_GRADIENT
            )
            embed.add_field(name="Claimed By", value=interaction.user.mention, inline=True)
            embed.add_field(name="Permissions", value="Updated" if permissions_updated else "Failed to update", inline=True)
            embed.add_field(name="Note", value="Deposit/balance checks bypassed (Admin)", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(
                f"Admin {interaction.user.id} claimed ticket #{ticket_number} (bypassed checks)"
            )
        else:
            error_msg = response.get("message", "Unknown error")
            embed = create_themed_embed(
                title="Claim Failed",
                description=f"Failed to claim ticket: {error_msg}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    except APIError as e:
        embed = create_themed_embed(
            title="API Error",
            description=f"Failed to claim ticket: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Admin claim ticket error: {e}", exc_info=True)


async def force_claim_ticket(
    bot: discord.Bot,
    interaction: discord.Interaction,
    ticket_number: str,
    exchanger_id: str
):
    """
    Force claim a ticket for an exchanger (bypasses balance checks)

    Args:
        bot: Bot instance
        interaction: Discord interaction
        ticket_number: Visible ticket number
        exchanger_id: Discord ID of exchanger to assign
    """
    await interaction.response.defer(ephemeral=True)

    api: APIClient = bot.api_client

    try:
        # Get ticket by number
        ticket = await get_ticket_by_number(api, ticket_number)

        if not ticket:
            embed = create_themed_embed(
                title="Ticket Not Found",
                description=f"Could not find ticket #{ticket_number}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        ticket_id = ticket.get("id")

        # Call force-claim endpoint
        response = await api.post(
            "/api/v1/admin/tickets/force-claim",
            data={
                "ticket_id": ticket_id,
                "exchanger_discord_id": exchanger_id
            },
            discord_user_id=str(interaction.user.id)
        )

        if response.get("success"):
            # Update Discord channel permissions
            channel_id = ticket.get("channel_id")
            permissions_updated = False

            if channel_id:
                channel = bot.get_channel(int(channel_id))
                exchanger_member = interaction.guild.get_member(int(exchanger_id))

                if channel and exchanger_member:
                    try:
                        # Give the exchanger full access to the ticket channel
                        await channel.set_permissions(
                            exchanger_member,
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True,
                            attach_files=True,
                            embed_links=True,
                            reason=f"Ticket force claimed by admin {interaction.user.name}"
                        )

                        # Send notification in the ticket channel
                        claim_embed = create_themed_embed(
                            title="Ticket Claimed",
                            description=f"This ticket has been claimed by {exchanger_member.mention}",
                            color=GREEN_GRADIENT
                        )
                        claim_embed.add_field(
                            name="Claimed By",
                            value=f"{exchanger_member.mention}",
                            inline=True
                        )
                        claim_embed.add_field(
                            name="Assigned By",
                            value=f"{interaction.user.mention} (Admin)",
                            inline=True
                        )
                        await channel.send(embed=claim_embed)

                        permissions_updated = True
                        logger.info(f"Updated permissions for {exchanger_member.name} on ticket #{ticket_number} channel")
                    except Exception as e:
                        logger.error(f"Failed to update channel permissions for ticket #{ticket_number}: {e}")

            embed = create_themed_embed(
                title="Ticket Force Claimed",
                description=f"Successfully force claimed ticket **#{ticket_number}** for exchanger",
                color=GREEN_GRADIENT
            )
            embed.add_field(name="Exchanger", value=f"<@{exchanger_id}>", inline=True)
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            embed.add_field(name="Permissions", value="Updated" if permissions_updated else "Failed to update", inline=True)
            embed.add_field(name="Note", value="Balance checks bypassed", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(
                f"Admin {interaction.user.id} force claimed ticket #{ticket_number} for exchanger {exchanger_id}"
            )
        else:
            error_msg = response.get("message", "Unknown error")
            embed = create_themed_embed(
                title="Force Claim Failed",
                description=f"Failed to force claim ticket: {error_msg}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    except APIError as e:
        embed = create_themed_embed(
            title="API Error",
            description=f"Failed to force claim ticket: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Force claim ticket error: {e}", exc_info=True)


async def force_unclaim_ticket(
    bot: discord.Bot,
    interaction: discord.Interaction,
    ticket_number: str
):
    """
    Force unclaim a ticket (releases holds and moves back to pending)

    Args:
        bot: Bot instance
        interaction: Discord interaction
        ticket_number: Visible ticket number
    """
    await interaction.response.defer(ephemeral=True)

    api: APIClient = bot.api_client

    try:
        # Get ticket by number
        ticket = await get_ticket_by_number(api, ticket_number)

        if not ticket:
            embed = create_themed_embed(
                title="Ticket Not Found",
                description=f"Could not find ticket #{ticket_number}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        ticket_id = ticket.get("id")

        # Call force-unclaim endpoint
        response = await api.post(
            f"/api/v1/admin/tickets/force-unclaim?ticket_id={ticket_id}&release_holds=true",
            discord_user_id=str(interaction.user.id)
        )

        if response.get("success"):
            embed = create_themed_embed(
                title="Ticket Force Unclaimed",
                description=f"Successfully force unclaimed ticket **#{ticket_number}**",
                color=GREEN_GRADIENT
            )
            embed.add_field(name="Status", value="Moved to Pending", inline=True)
            embed.add_field(name="Holds Released", value="Yes", inline=True)
            embed.add_field(name="Admin", value=interaction.user.mention, inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(
                f"Admin {interaction.user.id} force unclaimed ticket #{ticket_number}"
            )
        else:
            error_msg = response.get("message", "Unknown error")
            embed = create_themed_embed(
                title="Force Unclaim Failed",
                description=f"Failed to force unclaim ticket: {error_msg}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    except APIError as e:
        embed = create_themed_embed(
            title="API Error",
            description=f"Failed to force unclaim ticket: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Force unclaim ticket error: {e}", exc_info=True)


async def force_complete_ticket(
    bot: discord.Bot,
    interaction: discord.Interaction,
    ticket_number: str
):
    """
    Force complete a ticket (bypasses approvals, runs full completion workflow)
    Generates transcript, collects server fee, releases holds

    Args:
        bot: Bot instance
        interaction: Discord interaction
        ticket_number: Visible ticket number
    """
    await interaction.response.defer(ephemeral=True)

    api: APIClient = bot.api_client

    try:
        # Get ticket by number
        ticket = await get_ticket_by_number(api, ticket_number)

        if not ticket:
            embed = create_themed_embed(
                title="Ticket Not Found",
                description=f"Could not find ticket #{ticket_number}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        ticket_id = ticket.get("id")

        # Force complete by calling the approve_close workflow directly
        # This will generate transcript, collect fees, and release holds
        response = await api.post(
            "/api/v1/admin/tickets/force-complete",
            data={
                "ticket_id": ticket_id,
                "admin_id": str(interaction.user.id)
            },
            discord_user_id=str(interaction.user.id)
        )

        if response.get("success"):
            embed = create_themed_embed(
                title="Ticket Force Completed",
                description=f"Successfully force completed ticket **#{ticket_number}** with full workflow",
                color=GREEN_GRADIENT
            )
            embed.add_field(name="Transcript Generated", value="Yes", inline=True)
            embed.add_field(name="Server Fee Collected", value="Yes", inline=True)
            embed.add_field(name="Holds Released", value="Yes", inline=True)
            embed.add_field(name="Admin", value=interaction.user.mention, inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.warning(
                f"Admin {interaction.user.id} force completed ticket #{ticket_number} with full workflow"
            )
        else:
            error_msg = response.get("message", "Unknown error")
            embed = create_themed_embed(
                title="Force Complete Failed",
                description=f"Failed to force complete ticket: {error_msg}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    except APIError as e:
        embed = create_themed_embed(
            title="API Error",
            description=f"Failed to force complete ticket: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Force complete ticket error: {e}", exc_info=True)


# ========================================
# AUTOMM COMMAND
# ========================================

async def reveal_automm_key(
    bot: discord.Bot,
    interaction: discord.Interaction,
    mm_id: str
):
    """
    Reveal AutoMM escrow private key (for dispute resolution)
    Shows key only to admin who used the command

    Args:
        bot: Bot instance
        interaction: Discord interaction
        mm_id: AutoMM ID (MM# or escrow_id)
    """
    await interaction.response.defer(ephemeral=True)

    api: APIClient = bot.api_client

    try:
        # Get AutoMM escrow
        escrow = await get_automm_by_id(api, mm_id)

        if not escrow:
            embed = create_themed_embed(
                title="AutoMM Not Found",
                description=f"Could not find AutoMM escrow `{mm_id}`",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get escrow details with private key
        escrow_id = escrow.get("_id") or escrow.get("escrow_id")

        # Call admin endpoint to get decrypted private key
        response = await api.get(
            f"/api/v1/admin/automm/{escrow_id}/reveal-key",
            discord_user_id=str(interaction.user.id)
        )

        if response.get("success") and response.get("private_key"):
            private_key = response["private_key"]
            crypto = escrow.get("crypto", "Unknown")
            deposit_address = escrow.get("deposit_address", "N/A")
            status = escrow.get("status", "unknown")
            balance = escrow.get("balance", 0)

            embed = create_themed_embed(
                title="🔐 AutoMM Private Key Revealed",
                description=f"**AutoMM:** {mm_id}\n**Status:** {status}\n**Balance:** {balance} {crypto}",
                color=RED_GRADIENT
            )
            embed.add_field(name="Deposit Address", value=f"`{deposit_address}`", inline=False)
            embed.add_field(name="Private Key", value=f"```{private_key}```", inline=False)
            embed.add_field(name="Security Warning", value="This key grants full access to the escrow wallet. Handle with care.", inline=False)
            embed.add_field(name="Revealed By", value=interaction.user.mention, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.critical(
                f"ADMIN {interaction.user.id} revealed AutoMM private key for {mm_id} - Reason: Dispute Resolution"
            )
        else:
            error_msg = response.get("message", "Unknown error")
            embed = create_themed_embed(
                title="Key Reveal Failed",
                description=f"Failed to reveal private key: {error_msg}",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    except APIError as e:
        embed = create_themed_embed(
            title="API Error",
            description=f"Failed to reveal AutoMM key: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Reveal AutoMM key error: {e}", exc_info=True)


# ========================================
# SWAP INFO COMMAND
# ========================================

async def get_swap_info(
    bot: discord.Bot,
    interaction: discord.Interaction,
    swap_id: str
):
    """
    Get comprehensive swap information (internal + external)

    Args:
        bot: Bot instance
        interaction: Discord interaction
        swap_id: Swap ID
    """
    await interaction.response.defer(ephemeral=True)

    api: APIClient = bot.api_client

    try:
        # Get swap from database
        swap = await get_swap_by_id(api, swap_id)

        if not swap:
            embed = create_themed_embed(
                title="Swap Not Found",
                description=f"Could not find swap `{swap_id}`",
                color=RED_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get ChangeNOW external data
        changenow_id = swap.get("changenow_exchange_id")
        external_data = None

        if changenow_id:
            try:
                response = await api.get(
                    f"/api/v1/admin/swaps/{swap_id}/external-status",
                    discord_user_id=str(interaction.user.id)
                )
                if response.get("success"):
                    external_data = response.get("external_data")
            except Exception as e:
                logger.warning(f"Failed to get external swap data: {e}")

        # Build embed with internal + external info
        user_id = swap.get("user_id", "Unknown")
        from_asset = swap.get("from_asset", "?")
        to_asset = swap.get("to_asset", "?")
        from_amount = swap.get("from_amount", 0)
        estimated_output = swap.get("estimated_output", 0)
        status = swap.get("status", "unknown")
        created_at = swap.get("created_at", "N/A")

        embed = create_themed_embed(
            title="💱 Swap Information",
            description=f"**Swap ID:** `{swap_id}`\n**Status:** {status}",
            color=BLUE_GRADIENT
        )

        # Internal Info
        embed.add_field(
            name="Internal Info",
            value=(
                f"**User:** <@{user_id}>\n"
                f"**From:** {from_amount} {from_asset}\n"
                f"**To:** {estimated_output} {to_asset}\n"
                f"**Created:** {created_at}"
            ),
            inline=False
        )

        # External ChangeNOW Info
        if external_data:
            cn_status = external_data.get("status", "unknown")
            cn_deposit_received = external_data.get("amountFrom", "N/A")
            cn_expected_output = external_data.get("amountTo", "N/A")
            cn_tx_from = external_data.get("payinHash") or "Pending"
            cn_tx_to = external_data.get("payoutHash") or "Pending"

            embed.add_field(
                name="ChangeNOW Status",
                value=(
                    f"**Status:** {cn_status}\n"
                    f"**Deposit Received:** {cn_deposit_received} {from_asset}\n"
                    f"**Output Amount:** {cn_expected_output} {to_asset}"
                ),
                inline=False
            )

            # Format transaction hashes safely
            deposit_tx = f"`{cn_tx_from[:16]}...`" if cn_tx_from and cn_tx_from != "Pending" and len(cn_tx_from) > 16 else "Pending"
            payout_tx = f"`{cn_tx_to[:16]}...`" if cn_tx_to and cn_tx_to != "Pending" and len(cn_tx_to) > 16 else "Pending"

            embed.add_field(
                name="🔗 Transaction Hashes",
                value=(
                    f"**Deposit TX:** {deposit_tx}\n"
                    f"**Payout TX:** {payout_tx}"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="ChangeNOW Status",
                value="External data not available",
                inline=False
            )

        embed.add_field(name="Requested By", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

        logger.info(f"Admin {interaction.user.id} viewed swap info for {swap_id}")

    except APIError as e:
        embed = create_themed_embed(
            title="API Error",
            description=f"Failed to get swap info: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Get swap info error: {e}", exc_info=True)
    except Exception as e:
        embed = create_themed_embed(
            title="Unexpected Error",
            description=f"An unexpected error occurred: {str(e)}",
            color=RED_GRADIENT
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error(f"Unexpected error in get_swap_info: {e}", exc_info=True)
