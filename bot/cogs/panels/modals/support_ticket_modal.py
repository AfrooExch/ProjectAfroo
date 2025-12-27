"""
Support Ticket Modals - Custom forms for each ticket type
"""

import discord
import logging

from utils.embeds import create_themed_embed, error_embed
from utils.colors import PURPLE_GRADIENT
from config import config

logger = logging.getLogger(__name__)


class GeneralQuestionModal(discord.ui.Modal):
    """Modal for general questions"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="💬 General Question")
        self.bot = bot

        self.add_item(
            discord.ui.InputText(
                label="Subject",
                placeholder="Brief description of your question",
                style=discord.InputTextStyle.short,
                max_length=100,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Your Question",
                placeholder="Provide details about your question...",
                style=discord.InputTextStyle.long,
                max_length=1000,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        await create_support_ticket(
            interaction=interaction,
            bot=self.bot,
            ticket_type="general_question",
            emoji="💬",
            fields={
                "Subject": self.children[0].value.strip(),
                "Question": self.children[1].value.strip()
            }
        )


class ReportExchangerModal(discord.ui.Modal):
    """Modal for reporting exchangers"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="⚠️ Report Exchanger")
        self.bot = bot

        self.add_item(
            discord.ui.InputText(
                label="Exchanger Name or ID",
                placeholder="The Discord username or ID of the exchanger",
                style=discord.InputTextStyle.short,
                max_length=100,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Violation Type",
                placeholder="e.g., Scamming, Unprofessional, Delayed Payment, etc.",
                style=discord.InputTextStyle.short,
                max_length=100,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Evidence / Description",
                placeholder="Describe what happened and provide any proof (screenshots, transaction IDs, etc.)",
                style=discord.InputTextStyle.long,
                max_length=1000,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        await create_support_ticket(
            interaction=interaction,
            bot=self.bot,
            ticket_type="report_exchanger",
            emoji="⚠️",
            fields={
                "Exchanger": self.children[0].value.strip(),
                "Violation Type": self.children[1].value.strip(),
                "Evidence": self.children[2].value.strip()
            }
        )


class ClaimGiveawayModal(discord.ui.Modal):
    """Modal for claiming giveaways"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🎁 Claim Giveaway")
        self.bot = bot

        self.add_item(
            discord.ui.InputText(
                label="Giveaway Name",
                placeholder="Which giveaway did you win?",
                style=discord.InputTextStyle.short,
                max_length=100,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Proof / Screenshot",
                placeholder="Describe your proof or provide screenshot link (e.g., winning message)",
                style=discord.InputTextStyle.long,
                max_length=1000,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        await create_support_ticket(
            interaction=interaction,
            bot=self.bot,
            ticket_type="claim_giveaway",
            emoji="🎁",
            fields={
                "Giveaway Name": self.children[0].value.strip(),
                "Proof": self.children[1].value.strip()
            }
        )


class ReportBugModal(discord.ui.Modal):
    """Modal for reporting bugs"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="🐛 Report Bug")
        self.bot = bot

        self.add_item(
            discord.ui.InputText(
                label="Bug Summary",
                placeholder="Brief description of the bug",
                style=discord.InputTextStyle.short,
                max_length=100,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="How You Found It",
                placeholder="What were you doing when you encountered this bug?",
                style=discord.InputTextStyle.long,
                max_length=500,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Steps to Recreate",
                placeholder="How can we reproduce this bug? (Step 1, Step 2, etc.)",
                style=discord.InputTextStyle.long,
                max_length=500,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="What Does It Affect?",
                placeholder="What features or functionality are impacted?",
                style=discord.InputTextStyle.long,
                max_length=500,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        await create_support_ticket(
            interaction=interaction,
            bot=self.bot,
            ticket_type="report_bug",
            emoji="🐛",
            fields={
                "Bug Summary": self.children[0].value.strip(),
                "How Found": self.children[1].value.strip(),
                "Steps to Recreate": self.children[2].value.strip(),
                "What it Affects": self.children[3].value.strip()
            }
        )


class FeatureRequestModal(discord.ui.Modal):
    """Modal for feature requests"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="💡 Feature Request")
        self.bot = bot

        self.add_item(
            discord.ui.InputText(
                label="Feature Name",
                placeholder="What would you like to see added?",
                style=discord.InputTextStyle.short,
                max_length=100,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Description",
                placeholder="Describe the feature in detail...",
                style=discord.InputTextStyle.long,
                max_length=800,
                required=True
            )
        )

        self.add_item(
            discord.ui.InputText(
                label="Use Case / Why",
                placeholder="Why is this feature needed? How would it benefit users?",
                style=discord.InputTextStyle.long,
                max_length=500,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        await create_support_ticket(
            interaction=interaction,
            bot=self.bot,
            ticket_type="feature_request",
            emoji="💡",
            fields={
                "Feature Name": self.children[0].value.strip(),
                "Description": self.children[1].value.strip(),
                "Use Case": self.children[2].value.strip()
            }
        )


async def create_support_ticket(
    interaction: discord.Interaction,
    bot: discord.Bot,
    ticket_type: str,
    emoji: str,
    fields: dict
):
    """Create a support ticket channel and embed"""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        category = guild.get_channel(config.support_category)

        if not category:
            await interaction.followup.send(
                embed=error_embed(
                    description="❌ Support tickets category not configured. Please contact an admin."
                ),
                ephemeral=True
            )
            return

        # Create unique channel name
        # Get next ticket number by finding the highest existing number
        existing_channels = [ch for ch in category.channels if ch.name.startswith("support-")]
        highest_number = 0
        for ch in existing_channels:
            try:
                # Extract number from "support-X" format
                number = int(ch.name.split("-")[1])
                if number > highest_number:
                    highest_number = number
            except (IndexError, ValueError):
                continue

        # Also check transcript channel for highest ticket number
        transcript_channel = guild.get_channel(config.transcript_channel)
        if transcript_channel:
            try:
                # Fetch recent messages to find highest ticket number
                async for message in transcript_channel.history(limit=100):
                    if message.embeds and len(message.embeds) > 0:
                        embed = message.embeds[0]
                        if embed.description and "Ticket Number: #" in embed.description:
                            try:
                                # Extract ticket number from embed
                                lines = embed.description.split("\n")
                                for line in lines:
                                    if "Ticket Number: #" in line:
                                        num_str = line.split("#")[1].split("\n")[0].strip()
                                        number = int(num_str)
                                        if number > highest_number:
                                            highest_number = number
                                        break
                            except (IndexError, ValueError):
                                continue
            except Exception as e:
                logger.warning(f"Could not check transcript channel for ticket numbers: {e}")

        ticket_number = highest_number + 1

        # Create channel
        channel = await category.create_text_channel(
            name=f"support-{ticket_number}",
            topic=f"{ticket_type.replace('_', ' ').title()} by {interaction.user.name}"
        )

        # Set permissions - only user, staff, and admins can see
        await channel.set_permissions(
            guild.default_role,
            view_channel=False
        )

        # User permissions
        await channel.set_permissions(
            interaction.user,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True
        )

        # Staff role permissions
        staff_role = guild.get_role(config.staff_role)
        if staff_role:
            await channel.set_permissions(
                staff_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )

        # Admin role permissions
        admin_role = guild.get_role(config.head_admin_role)
        if admin_role:
            await channel.set_permissions(
                admin_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
                manage_channels=True
            )

        # Build field list for embed
        field_text = "\n".join([f"**{key}:**\n{value}\n" for key, value in fields.items()])

        # Send ticket embed in channel
        ticket_embed = create_themed_embed(
            title="",
            description=(
                f"**Support Ticket #{ticket_number}**\n\n"
                f"**Type:** {ticket_type.replace('_', ' ').title()}\n\n"
                f"{field_text}\n"
                f"**Opened By:** {interaction.user.mention}"
            ),
            color=PURPLE_GRADIENT
        )

        # Create close button view with ticket metadata
        from datetime import datetime
        from cogs.panels.views.support_ticket_view import SupportTicketView
        view = SupportTicketView(
            bot=bot,
            ticket_number=ticket_number,
            ticket_type=ticket_type,
            opened_by=interaction.user,
            opened_at=datetime.utcnow()
        )

        await channel.send(
            content=f"{interaction.user.mention}",
            embed=ticket_embed,
            view=view
        )

        # Ping staff role
        if staff_role:
            await channel.send(
                f"{staff_role.mention} New support ticket!",
                delete_after=5
            )

        # Confirm to user
        confirm_embed = create_themed_embed(
            title="",
            description=(
                f"**Support Ticket Created**\n\n"
                f"**Ticket:** #{ticket_number}\n"
                f"**Channel:** {channel.mention}\n\n"
                f"A staff member will assist you shortly."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.followup.send(
            embed=confirm_embed,
            ephemeral=True
        )

        logger.info(f"Support ticket #{ticket_number} created by {interaction.user.name} ({ticket_type})")

    except Exception as e:
        logger.error(f"Error creating support ticket: {e}", exc_info=True)
        await interaction.followup.send(
            embed=error_embed(
                description=f"❌ An error occurred while creating your ticket.\n\n**Error:** {str(e)}"
            ),
            ephemeral=True
        )
