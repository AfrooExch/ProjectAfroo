"""
Application Review Views for V4
Two-tier approval system: Staff Accept/Decline → Admin Approve/Deny
"""

import logging
from datetime import datetime

import discord
from discord.ui import View, Button, Modal, InputText

from utils.view_manager import PersistentView

logger = logging.getLogger(__name__)


class StaffReviewView(PersistentView):
    """Review panel for staff - Accept or Decline application"""

    def __init__(self, bot: discord.Bot, app_id: str, app_number: int, user_id: int, opened_at: datetime):
        super().__init__(bot)
        self.app_id = app_id
        self.app_number = app_number
        self.user_id = user_id
        self.opened_at = opened_at

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="staff_accept_app"
    )
    async def accept_button(self, button: Button, interaction: discord.Interaction):
        """Applicant accepts escrow system - sends to staff for review"""
        # Check if user is the applicant
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the applicant can accept or decline their application.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Accept application
        from cogs.applications.handlers.application_handler import staff_accept_application

        await staff_accept_application(
            bot=self.bot,
            app_id=self.app_id,
            app_number=self.app_number,
            channel=interaction.channel,
            user_id=self.user_id,
            accepted_by=interaction.user,
            opened_at=self.opened_at
        )

    @discord.ui.button(
        label="Decline",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="staff_decline_app"
    )
    async def decline_button(self, button: Button, interaction: discord.Interaction):
        """Applicant declines escrow system"""
        # Check if user is the applicant
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the applicant can accept or decline their application.",
                ephemeral=True
            )
            return

        # Show decline modal
        modal = StaffDeclineModal(self.bot, self.app_id, self.app_number, self.user_id, self.opened_at, interaction.channel)
        await interaction.response.send_modal(modal)


class AdminReviewView(PersistentView):
    """Review panel for admin - Approve or Deny application"""

    def __init__(self, bot: discord.Bot, app_id: str, app_number: int, user_id: int, opened_at: datetime):
        super().__init__(bot)
        self.app_id = app_id
        self.app_number = app_number
        self.user_id = user_id
        self.opened_at = opened_at

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="admin_approve_app"
    )
    async def approve_button(self, button: Button, interaction: discord.Interaction):
        """Admin approves application - grants role, updates DB, changes nickname"""
        # Check if user is admin
        from config import config
        admin_role = interaction.guild.get_role(config.head_admin_role)

        is_admin = admin_role in interaction.user.roles if admin_role else False

        if not is_admin:
            await interaction.response.send_message(
                "❌ Only admins can approve applications.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Approve application
        from cogs.applications.handlers.application_handler import admin_approve_application

        await admin_approve_application(
            bot=self.bot,
            app_id=self.app_id,
            app_number=self.app_number,
            channel=interaction.channel,
            user_id=self.user_id,
            approved_by=interaction.user,
            opened_at=self.opened_at
        )

    @discord.ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="admin_deny_app"
    )
    async def deny_button(self, button: Button, interaction: discord.Interaction):
        """Admin denies application"""
        # Check if user is admin
        from config import config
        admin_role = interaction.guild.get_role(config.head_admin_role)

        is_admin = admin_role in interaction.user.roles if admin_role else False

        if not is_admin:
            await interaction.response.send_message(
                "❌ Only admins can deny applications.",
                ephemeral=True
            )
            return

        # Show deny modal
        modal = AdminDenyModal(self.bot, self.app_id, self.app_number, self.user_id, self.opened_at, interaction.channel)
        await interaction.response.send_modal(modal)


class StaffDeclineModal(Modal):
    """Modal for staff to provide decline reason"""

    def __init__(self, bot: discord.Bot, app_id: str, app_number: int, user_id: int, opened_at: datetime, channel: discord.TextChannel):
        super().__init__(title="Decline Application")
        self.bot = bot
        self.app_id = app_id
        self.app_number = app_number
        self.user_id = user_id
        self.opened_at = opened_at
        self.channel = channel

        self.reason_input = InputText(
            label="Decline Reason",
            placeholder="Explain why the application is being declined...",
            required=True,
            max_length=1000,
            style=discord.InputTextStyle.long
        )
        self.add_item(self.reason_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle decline"""
        await interaction.response.defer()

        reason = self.reason_input.value.strip()

        # Decline application
        from cogs.applications.handlers.application_handler import staff_decline_application

        await staff_decline_application(
            bot=self.bot,
            app_id=self.app_id,
            app_number=self.app_number,
            channel=self.channel,
            user_id=self.user_id,
            declined_by=interaction.user,
            reason=reason,
            opened_at=self.opened_at
        )


class AdminDenyModal(Modal):
    """Modal for admin to provide denial reason"""

    def __init__(self, bot: discord.Bot, app_id: str, app_number: int, user_id: int, opened_at: datetime, channel: discord.TextChannel):
        super().__init__(title="Deny Application")
        self.bot = bot
        self.app_id = app_id
        self.app_number = app_number
        self.user_id = user_id
        self.opened_at = opened_at
        self.channel = channel

        self.reason_input = InputText(
            label="Denial Reason",
            placeholder="Explain why the application is being denied...",
            required=True,
            max_length=1000,
            style=discord.InputTextStyle.long
        )
        self.add_item(self.reason_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle denial"""
        await interaction.response.defer()

        reason = self.reason_input.value.strip()

        # Deny application
        from cogs.applications.handlers.application_handler import admin_deny_application

        await admin_deny_application(
            bot=self.bot,
            app_id=self.app_id,
            app_number=self.app_number,
            channel=self.channel,
            user_id=self.user_id,
            denied_by=interaction.user,
            reason=reason,
            opened_at=self.opened_at
        )
