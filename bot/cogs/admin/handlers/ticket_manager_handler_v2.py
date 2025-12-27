"""
Admin Ticket Manager Handler V2
Category-based menu system for ticket force actions
"""

import discord
from discord.ui import View, Button, Select
import logging
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


async def show_ticket_manager(interaction, bot):
    """Show ticket manager main menu"""
    # NOTE: interaction is already deferred by admin panel callback
    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Show main category selection
        view = TicketCategoryView(bot, user_context_id, roles, interaction.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🎫 Ticket Manager\n\n"
                "**Select a ticket category to manage:**\n\n"
                "💱 **Exchange Tickets** - Force claim, unclaim, complete, close\n"
                "**Swap Tickets** - Force complete, close\n"
                "🤖 **AutoMM Tickets** - Force complete, close, reveal escrow key\n"
                "🎫 **Support Tickets** - Force close\n"
                "📝 **Application Tickets** - Accept, deny\n\n"
                "> Select a category below to see available actions."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    except Exception as e:
        logger.error(f"Error loading ticket manager: {e}", exc_info=True)
        await interaction.followup.send(f"Error loading ticket manager: {str(e)}", ephemeral=True)


class TicketCategoryView(View):
    """Main category selection view"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

    @discord.ui.button(label="Exchange Tickets", style=discord.ButtonStyle.primary, emoji="💱", row=0)
    async def exchange_button(self, button: Button, interaction: discord.Interaction):
        """Show exchange ticket actions"""
        await interaction.response.defer()

        view = ExchangeActionsView(self.bot, self.user_id, self.roles, self.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 💱 Exchange Ticket Actions\n\n"
                "**Available Actions:**\n\n"
                "🔵 **Force Claim** - Assign ticket to exchanger (bypass holds)\n"
                "🔓 **Force Unclaim** - Remove exchanger and reopen ticket\n"
                "**Force Complete** - Complete ticket (deduct funds, collect fees)\n"
                "🔒 **Force Close** - Close ticket and refund holds\n"
                "➕ **Add User** - Grant channel access to user\n"
                "➖ **Remove User** - Remove channel access from user\n\n"
                "> Click an action button below and enter the ticket ID."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Swap Tickets", style=discord.ButtonStyle.primary, emoji="", row=0)
    async def swap_button(self, button: Button, interaction: discord.Interaction):
        """Show swap ticket actions"""
        await interaction.response.defer()

        view = SwapActionsView(self.bot, self.user_id, self.roles, self.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## Swap Ticket Actions\n\n"
                "**Available Actions:**\n\n"
                "**Force Complete** - Complete swap ticket\n"
                "🔒 **Force Close** - Close swap ticket\n"
                "➕ **Add User** - Grant channel access to user\n"
                "➖ **Remove User** - Remove channel access from user\n\n"
                "> Click an action button below and enter the ticket ID."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="AutoMM Tickets", style=discord.ButtonStyle.primary, emoji="🤖", row=1)
    async def automm_button(self, button: Button, interaction: discord.Interaction):
        """Show AutoMM ticket actions"""
        await interaction.response.defer()

        view = AutoMMActionsView(self.bot, self.user_id, self.roles, self.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🤖 AutoMM Ticket Actions\n\n"
                "**Available Actions:**\n\n"
                "**Force Complete** - Complete AutoMM deal\n"
                "🔒 **Force Close** - Close AutoMM deal\n"
                "🔑 **Reveal Escrow Key** - Show private key (admin only)\n"
                "**Force Withdraw to Admin** - Withdraw escrow funds\n"
                "➕ **Add User** - Grant channel access to user\n"
                "➖ **Remove User** - Remove channel access from user\n\n"
                "> Click an action button below and enter the ticket ID."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Support Tickets", style=discord.ButtonStyle.primary, emoji="🎫", row=1)
    async def support_button(self, button: Button, interaction: discord.Interaction):
        """Show support ticket actions"""
        await interaction.response.defer()

        view = SupportActionsView(self.bot, self.user_id, self.roles, self.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🎫 Support Ticket Actions\n\n"
                "**Available Actions:**\n\n"
                "🔒 **Force Close** - Close support ticket\n"
                "➕ **Add User** - Grant channel access to user\n"
                "➖ **Remove User** - Remove channel access from user\n\n"
                "> Click an action button below and enter the ticket ID."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Application Tickets", style=discord.ButtonStyle.primary, emoji="📝", row=2)
    async def application_button(self, button: Button, interaction: discord.Interaction):
        """Show application ticket actions"""
        await interaction.response.defer()

        view = ApplicationActionsView(self.bot, self.user_id, self.roles, self.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 📝 Application Ticket Actions\n\n"
                "**Available Actions:**\n\n"
                "**Accept Application** - Grant Exchanger role and approve\n"
                "**Deny Application** - Reject application with reason\n"
                "🔒 **Force Close** - Close application ticket\n"
                "➕ **Add User** - Grant channel access to user\n"
                "➖ **Remove User** - Remove channel access from user\n\n"
                "> Click an action button below and enter the ticket ID."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)


class ExchangeActionsView(View):
    """Exchange ticket action buttons"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

    @discord.ui.button(label="Force Claim", style=discord.ButtonStyle.primary, emoji="🔵", row=0)
    async def force_claim_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceClaimActionModal
        await interaction.response.send_modal(ForceClaimActionModal(self.bot, self.user_id, self.roles, self.guild, "exchange"))

    @discord.ui.button(label="Force Unclaim", style=discord.ButtonStyle.secondary, emoji="🔓", row=0)
    async def force_unclaim_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceUnclaimActionModal
        await interaction.response.send_modal(ForceUnclaimActionModal(self.bot, self.user_id, self.roles, self.guild, "exchange"))

    @discord.ui.button(label="Force Complete", style=discord.ButtonStyle.success, emoji="", row=0)
    async def force_complete_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCompleteActionModal
        await interaction.response.send_modal(ForceCompleteActionModal(self.bot, self.user_id, self.roles, self.guild, "exchange"))

    @discord.ui.button(label="Force Close", style=discord.ButtonStyle.danger, emoji="🔒", row=1)
    async def force_close_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCloseActionModal
        await interaction.response.send_modal(ForceCloseActionModal(self.bot, self.user_id, self.roles, self.guild, "exchange"))

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕", row=1)
    async def add_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import AddUserActionModal
        await interaction.response.send_modal(AddUserActionModal(self.bot, self.user_id, self.roles, self.guild, "exchange"))

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, emoji="➖", row=1)
    async def remove_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import RemoveUserActionModal
        await interaction.response.send_modal(RemoveUserActionModal(self.bot, self.user_id, self.roles, self.guild, "exchange"))

    @discord.ui.button(label="« Back to Categories", style=discord.ButtonStyle.secondary, emoji="🔙", row=2)
    async def back_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.defer()

        # Recreate category view
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        view = TicketCategoryView(self.bot, user_context_id, roles, interaction.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🎫 Ticket Manager\n\n"
                "**Select a ticket category to manage:**\n\n"
                "💱 **Exchange Tickets** - Force claim, unclaim, complete, close\n"
                "**Swap Tickets** - Force complete, close\n"
                "🤖 **AutoMM Tickets** - Force complete, close, reveal escrow key\n"
                "🎫 **Support Tickets** - Force close\n"
                "📝 **Application Tickets** - Accept, deny\n\n"
                "> Select a category below to see available actions."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)


class SwapActionsView(View):
    """Swap ticket action buttons"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

    @discord.ui.button(label="Force Complete", style=discord.ButtonStyle.success, emoji="", row=0)
    async def force_complete_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCompleteActionModal
        await interaction.response.send_modal(ForceCompleteActionModal(self.bot, self.user_id, self.roles, self.guild, "swap"))

    @discord.ui.button(label="Force Close", style=discord.ButtonStyle.danger, emoji="🔒", row=0)
    async def force_close_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCloseActionModal
        await interaction.response.send_modal(ForceCloseActionModal(self.bot, self.user_id, self.roles, self.guild, "swap"))

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕", row=1)
    async def add_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import AddUserActionModal
        await interaction.response.send_modal(AddUserActionModal(self.bot, self.user_id, self.roles, self.guild, "swap"))

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, emoji="➖", row=1)
    async def remove_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import RemoveUserActionModal
        await interaction.response.send_modal(RemoveUserActionModal(self.bot, self.user_id, self.roles, self.guild, "swap"))

    @discord.ui.button(label="« Back to Categories", style=discord.ButtonStyle.secondary, emoji="🔙", row=2)
    async def back_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.defer()

        # Recreate category view
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        view = TicketCategoryView(self.bot, user_context_id, roles, interaction.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🎫 Ticket Manager\n\n"
                "**Select a ticket category to manage:**\n\n"
                "💱 **Exchange Tickets** - Force claim, unclaim, complete, close\n"
                "**Swap Tickets** - Force complete, close\n"
                "🤖 **AutoMM Tickets** - Force complete, close, reveal escrow key\n"
                "🎫 **Support Tickets** - Force close\n"
                "📝 **Application Tickets** - Accept, deny\n\n"
                "> Select a category below to see available actions."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)


class AutoMMActionsView(View):
    """AutoMM ticket action buttons"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

    @discord.ui.button(label="Force Complete", style=discord.ButtonStyle.success, emoji="", row=0)
    async def force_complete_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCompleteActionModal
        await interaction.response.send_modal(ForceCompleteActionModal(self.bot, self.user_id, self.roles, self.guild, "automm"))

    @discord.ui.button(label="Force Close", style=discord.ButtonStyle.danger, emoji="🔒", row=0)
    async def force_close_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCloseActionModal
        await interaction.response.send_modal(ForceCloseActionModal(self.bot, self.user_id, self.roles, self.guild, "automm"))

    @discord.ui.button(label="Reveal Escrow Key", style=discord.ButtonStyle.danger, emoji="🔑", row=1)
    async def reveal_key_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import RevealEscrowKeyModal
        await interaction.response.send_modal(RevealEscrowKeyModal(self.bot, self.user_id, self.roles, self.guild))

    @discord.ui.button(label="Force Withdraw to Admin", style=discord.ButtonStyle.danger, emoji="", row=1)
    async def force_withdraw_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceWithdrawAdminModal
        await interaction.response.send_modal(ForceWithdrawAdminModal(self.bot, self.user_id, self.roles, self.guild))

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕", row=2)
    async def add_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import AddUserActionModal
        await interaction.response.send_modal(AddUserActionModal(self.bot, self.user_id, self.roles, self.guild, "automm"))

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, emoji="➖", row=2)
    async def remove_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import RemoveUserActionModal
        await interaction.response.send_modal(RemoveUserActionModal(self.bot, self.user_id, self.roles, self.guild, "automm"))

    @discord.ui.button(label="« Back to Categories", style=discord.ButtonStyle.secondary, emoji="🔙", row=3)
    async def back_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.defer()

        # Recreate category view
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        view = TicketCategoryView(self.bot, user_context_id, roles, interaction.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🎫 Ticket Manager\n\n"
                "**Select a ticket category to manage:**\n\n"
                "💱 **Exchange Tickets** - Force claim, unclaim, complete, close\n"
                "**Swap Tickets** - Force complete, close\n"
                "🤖 **AutoMM Tickets** - Force complete, close, reveal escrow key\n"
                "🎫 **Support Tickets** - Force close\n"
                "📝 **Application Tickets** - Accept, deny\n\n"
                "> Select a category below to see available actions."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)


class SupportActionsView(View):
    """Support ticket action buttons"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

    @discord.ui.button(label="Force Close", style=discord.ButtonStyle.danger, emoji="🔒", row=0)
    async def force_close_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCloseActionModal
        await interaction.response.send_modal(ForceCloseActionModal(self.bot, self.user_id, self.roles, self.guild, "support"))

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕", row=0)
    async def add_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import AddUserActionModal
        await interaction.response.send_modal(AddUserActionModal(self.bot, self.user_id, self.roles, self.guild, "support"))

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, emoji="➖", row=0)
    async def remove_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import RemoveUserActionModal
        await interaction.response.send_modal(RemoveUserActionModal(self.bot, self.user_id, self.roles, self.guild, "support"))

    @discord.ui.button(label="« Back to Categories", style=discord.ButtonStyle.secondary, emoji="🔙", row=1)
    async def back_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.defer()

        # Recreate category view
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        view = TicketCategoryView(self.bot, user_context_id, roles, interaction.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🎫 Ticket Manager\n\n"
                "**Select a ticket category to manage:**\n\n"
                "💱 **Exchange Tickets** - Force claim, unclaim, complete, close\n"
                "**Swap Tickets** - Force complete, close\n"
                "🤖 **AutoMM Tickets** - Force complete, close, reveal escrow key\n"
                "🎫 **Support Tickets** - Force close\n"
                "📝 **Application Tickets** - Accept, deny\n\n"
                "> Select a category below to see available actions."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)


class ApplicationActionsView(View):
    """Application ticket action buttons"""

    def __init__(self, bot, user_id: str, roles: list, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.roles = roles
        self.guild = guild

    @discord.ui.button(label="Accept Application", style=discord.ButtonStyle.success, emoji="", row=0)
    async def accept_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import AcceptApplicationModal
        await interaction.response.send_modal(AcceptApplicationModal(self.bot, self.user_id, self.roles, self.guild))

    @discord.ui.button(label="Deny Application", style=discord.ButtonStyle.danger, emoji="", row=0)
    async def deny_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import DenyApplicationActionModal
        await interaction.response.send_modal(DenyApplicationActionModal(self.bot, self.user_id, self.roles, self.guild))

    @discord.ui.button(label="Force Close", style=discord.ButtonStyle.danger, emoji="🔒", row=1)
    async def force_close_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import ForceCloseActionModal
        await interaction.response.send_modal(ForceCloseActionModal(self.bot, self.user_id, self.roles, self.guild, "application"))

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕", row=1)
    async def add_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import AddUserActionModal
        await interaction.response.send_modal(AddUserActionModal(self.bot, self.user_id, self.roles, self.guild, "application"))

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, emoji="➖", row=1)
    async def remove_user_button(self, button: Button, interaction: discord.Interaction):
        from cogs.admin.modals.ticket_action_modals import RemoveUserActionModal
        await interaction.response.send_modal(RemoveUserActionModal(self.bot, self.user_id, self.roles, self.guild, "application"))

    @discord.ui.button(label="« Back to Categories", style=discord.ButtonStyle.secondary, emoji="🔙", row=2)
    async def back_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.defer()

        # Recreate category view
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        view = TicketCategoryView(self.bot, user_context_id, roles, interaction.guild)
        embed = create_themed_embed(
            title="",
            description=(
                "## 🎫 Ticket Manager\n\n"
                "**Select a ticket category to manage:**\n\n"
                "💱 **Exchange Tickets** - Force claim, unclaim, complete, close\n"
                "**Swap Tickets** - Force complete, close\n"
                "🤖 **AutoMM Tickets** - Force complete, close, reveal escrow key\n"
                "🎫 **Support Tickets** - Force close\n"
                "📝 **Application Tickets** - Accept, deny\n\n"
                "> Select a category below to see available actions."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.edit_original_response(embed=embed, view=view)
