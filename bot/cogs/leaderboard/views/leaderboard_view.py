"""
Leaderboard View for V4
Simple view with website link button
"""

import logging

import discord
from discord.ui import View, Button

from config import Config

logger = logging.getLogger(__name__)


class LeaderboardView(View):
    """View for leaderboard panel with website link"""

    def __init__(self):
        super().__init__(timeout=None)

        # Add website link button
        website_button = Button(
            label="View Full Leaderboard",
            style=discord.ButtonStyle.link,
            url="http://afrooexchange.com/leaderboard",
            emoji="🌐"
        )
        self.add_item(website_button)
