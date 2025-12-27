"""
Support Panel View - Support ticket creation dropdown (V3 style)
"""

import discord
import logging

from utils.view_manager import PersistentView
from utils.embeds import create_embed, error_embed, success_embed, get_color
from cogs.panels.modals.support_ticket_modal import (
    GeneralQuestionModal,
    ReportExchangerModal,
    ClaimGiveawayModal,
    ReportBugModal,
    FeatureRequestModal
)
from config import config

logger = logging.getLogger(__name__)

# Support ticket types
SUPPORT_TYPES = {
    "general_question": {
        "name": "General Question",
        "emoji": "💬",
        "description": "General questions and support"
    },
    "report_exchanger": {
        "name": "Report Exchanger",
        "emoji": "⚠️",
        "description": "Report an exchanger for violations"
    },
    "claim_giveaway": {
        "name": "Claim Giveaway",
        "emoji": "🎁",
        "description": "Claim your giveaway prize"
    },
    "report_bug": {
        "name": "Report Bug",
        "emoji": "🐛",
        "description": "Report a bug with the bot"
    },
    "feature_request": {
        "name": "Feature Request",
        "emoji": "💡",
        "description": "Request a new feature or improvement"
    }
}


class SupportPanelView(PersistentView):
    """Support panel with dropdown for ticket types"""

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)

        # Create dropdown options (no emojis on labels)
        options = []
        for ticket_type, data in SUPPORT_TYPES.items():
            options.append(
                discord.SelectOption(
                    label=data["name"],
                    description=data["description"],
                    value=ticket_type
                )
            )

        # Create select dropdown
        select = discord.ui.Select(
            placeholder="🎫 Select your support type...",
            custom_id="support_type_select",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.dropdown_callback
        self.add_item(select)

    async def dropdown_callback(self, interaction: discord.Interaction):
        """Handle support type selection"""
        try:
            logger.info(f"🎫 Support dropdown triggered by {interaction.user.id}")

            selected_type = interaction.data["values"][0]
            logger.info(f"🎫 Selected type: {selected_type}")

            # Open the correct modal for the selected type
            modal_map = {
                "general_question": GeneralQuestionModal,
                "report_exchanger": ReportExchangerModal,
                "claim_giveaway": ClaimGiveawayModal,
                "report_bug": ReportBugModal,
                "feature_request": FeatureRequestModal
            }

            modal_class = modal_map.get(selected_type)
            if modal_class:
                modal = modal_class(self.bot)
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message(
                    f"❌ Unknown ticket type: {selected_type}",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in support dropdown callback: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    f"❌ Error: {str(e)}",
                    ephemeral=True
                )
            except Exception as followup_error:
                logger.error(f"Could not send error message: {followup_error}")
