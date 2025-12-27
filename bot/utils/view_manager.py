"""
View Manager - Persistent Discord UI component management
Preserves views across bot restarts (V3 pattern)
"""

import discord
import logging
from typing import Dict, Type, Optional

logger = logging.getLogger(__name__)


class ViewManager:
    """
    Manages persistent Discord views (buttons, select menus)

    Views registered with the manager survive bot restarts and can
    handle interactions from messages sent before restart.
    """

    def __init__(self, bot: discord.Bot):
        """
        Initialize view manager

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.views: Dict[str, Type[discord.ui.View]] = {}
        logger.info("ViewManager initialized")

    def register(self, custom_id: str, view_class: Type[discord.ui.View]):
        """
        Register a view class to persist across restarts

        Args:
            custom_id: Unique identifier for the view
            view_class: View class (not instance)
        """
        self.views[custom_id] = view_class
        logger.debug(f"Registered view: {custom_id} -> {view_class.__name__}")

    async def restore_views(self):
        """
        Restore all registered views on bot startup

        This makes views from old messages functional again
        """
        for custom_id, view_class in self.views.items():
            try:
                # Create view instance
                view = view_class(self.bot)

                # Add to bot (global view - no message_id needed)
                self.bot.add_view(view)

                logger.info(f"Restored view: {custom_id}")
            except Exception as e:
                logger.error(f"Failed to restore view {custom_id}: {e}", exc_info=True)

        logger.info(f"Restored {len(self.views)} persistent views")

    def create_view(self, custom_id: str, **kwargs) -> Optional[discord.ui.View]:
        """
        Create an instance of a registered view

        Args:
            custom_id: View identifier
            **kwargs: Arguments to pass to view constructor

        Returns:
            View instance or None if not registered
        """
        view_class = self.views.get(custom_id)
        if not view_class:
            logger.warning(f"View not registered: {custom_id}")
            return None

        return view_class(self.bot, **kwargs)

    def is_registered(self, custom_id: str) -> bool:
        """Check if view is registered"""
        return custom_id in self.views


class PersistentView(discord.ui.View):
    """
    Base class for persistent views

    Subclass this for views that should survive bot restarts
    """

    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=None)  # No timeout for persistent views
        self.bot = bot

    async def on_error(
        self,
        error: Exception,
        item: discord.ui.Item,
        interaction: discord.Interaction
    ):
        """Handle view errors"""
        logger.error(
            f"Error in view {self.__class__.__name__}: {error}",
            exc_info=True
        )

        # Try to respond to user
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again or contact support.",
                    ephemeral=True
                )
        except:
            pass
