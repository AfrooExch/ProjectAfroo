"""
Swap Panel View - Instant crypto-to-crypto swaps
"""

import discord
import logging

from utils.view_manager import PersistentView
from cogs.panels.modals.swap_modal import SwapModal

logger = logging.getLogger(__name__)


class SwapPanelView(PersistentView):
    """Afroo Swap panel with start swap button"""

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)

    @discord.ui.button(
        label="Start Swap",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="start_swap_button"
    )
    async def start_swap(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Handle start swap button click - opens modal"""
        logger.info(f"Start swap clicked by {interaction.user.name} ({interaction.user.id})")

        # Show swap modal
        modal = SwapModal(self.bot)
        await interaction.response.send_modal(modal)
