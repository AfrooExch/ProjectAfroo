import asyncio
import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

from config import config
from api.client import APIClient
from utils.view_manager import ViewManager

# Configure logging with rotation
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            'bot.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger(__name__)


class AfrooBot(discord.Bot):
    """Afroo Exchange Discord Bot"""

    def __init__(self):
        """Initialize bot"""
        super().__init__(
            intents=discord.Intents.all(),
            debug_guilds=[config.DISCORD_GUILD_ID] 
        )

        self.api_client: APIClient = None
        self.view_manager: ViewManager = None
        self._initialized = False 

    async def load_cogs(self):
        """Load all cogs from cogs directory"""
        cogs_dir = Path("cogs")

        if not cogs_dir.exists():
            logger.warning("Cogs directory not found")
            return

        loaded = 0
        failed = 0

        # Find all cog files
        for cog_path in cogs_dir.rglob("cog.py"):
            # Skip disabled cogs
            if "_DISABLED" in str(cog_path):
                continue

            # Convert path to module name (e.g., cogs.tickets.cog)
            parts = cog_path.with_suffix("").parts
            module_name = ".".join(parts)

            try:
                self.load_extension(module_name)
                loaded += 1
                logger.info(f"Loaded cog: {module_name}")
            except Exception as e:
                failed += 1
                logger.error(f"Failed to load cog {module_name}: {e}", exc_info=True)

        logger.info(f"📦 Loaded {loaded} cogs ({failed} failed)")

    async def on_ready(self):
        """Called when bot is ready"""
        if not self._initialized:
            self._initialized = True
            await self._setup()

        logger.info("=" * 60)
        logger.info(f"Bot ready as {self.user.name} (ID: {self.user.id})")
        logger.info(f"   Connected to {len(self.guilds)} guilds")
        logger.info(f"   Loaded {len(self.cogs)} cogs")
        logger.info(f"   Registered {len(self.pending_application_commands)} commands")
        logger.info("=" * 60)

        # Set bot presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Afroo Exchanges"
            ),
            status=discord.Status.online
        )

        # Sync commands to Discord (skip if there are duplicates)
        logger.info("Syncing commands to Discord...")
        try:
            synced = await self.sync_commands()
            logger.info(f"Synced {len(synced)} commands to Discord")
        except Exception as e:
            logger.warning(f"Command sync issue (may have duplicates): {e}")
            logger.info("Commands will still work in Discord, just may not update immediately")

    async def _setup(self):
        logger.info("Starting Afroo Exchange Bot V4...")

        # Validate configuration
        try:
            config.validate()
            logger.info("Configuration validated")
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise

        # Initialize API client
        try:
            self.api_client = APIClient(
                base_url=config.API_BASE_URL,
                bot_service_token=config.BOT_SERVICE_TOKEN
            )
            await self.api_client.connect()
            logger.info("API client connected")
        except Exception as e:
            logger.error(f"Failed to connect to API: {e}")
            raise

        # Initialize completion notifier task
        try:
            from tasks.completion_notifier import CompletionNotifier
            self.completion_notifier = CompletionNotifier(self, self.api_client, config)
            self.completion_notifier.start()
            logger.info("Completion notifier task started")
        except Exception as e:
            logger.error(f"Failed to start completion notifier: {e}", exc_info=True)
        try:
            from tasks.ticket_sync import start_ticket_sync
            asyncio.create_task(start_ticket_sync(self))
            logger.info("Ticket sync task started (runs every 15 minutes)")
        except Exception as e:
            logger.error(f"Failed to start ticket sync task: {e}", exc_info=True)

        logger.info("⏸Role sync task disabled (backend 500 errors)")

        try:
            from tasks.swap_monitor import SwapMonitor
            self.swap_monitor = SwapMonitor(self, self.api_client)
            self.swap_monitor.start()
            logger.info("Swap monitor task started")
        except Exception as e:
            logger.error(f"Failed to start swap monitor task: {e}", exc_info=True)

        self.view_manager = ViewManager(self)
        logger.info("View manager initialized")

        await self.load_cogs()
        await self.view_manager.restore_views()
        logger.info("Persistent views restored")
        logger.info("Triggering panel deployment...")
        panels_cog = self.get_cog("AllPanelsCog")
        if panels_cog and hasattr(panels_cog, 'on_ready'):
            try:
                await panels_cog.on_ready()
            except Exception as e:
                logger.error(f"Panel deployment failed: {e}", exc_info=True)

    async def on_application_command(self, ctx: discord.ApplicationContext):
        """Called when slash command is used"""
        logger.info(
            f"Command used: /{ctx.command.name} by {ctx.author.name} "
            f"in {ctx.guild.name if ctx.guild else 'DM'}"
        )

    async def on_application_command_error(
        self,
        ctx: discord.ApplicationContext,
        error: discord.DiscordException
    ):
        logger.error(
            f"Command error in /{ctx.command.name}: {error}",
            exc_info=True
        )

        try:
            if isinstance(error, commands.CommandOnCooldown):
                await ctx.respond(
                    f"⏱This command is on cooldown. Try again in {error.retry_after:.1f}s.",
                    ephemeral=True
                )
            elif isinstance(error, commands.MissingPermissions):
                await ctx.respond(
                    "You don't have permission to use this command.",
                    ephemeral=True
                )
            elif isinstance(error, commands.BotMissingPermissions):
                await ctx.respond(
                    "I don't have the necessary permissions to execute this command.",
                    ephemeral=True
                )
            else:
                await ctx.respond(
                    "In error occurred while executing this command. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)  # Failed to send error message

    async def close(self):
        """Called when bot is shutting down"""
        logger.info("👋 Shutting down Afroo Exchange Bot...")

        # Stop completion notifier
        if hasattr(self, 'completion_notifier'):
            self.completion_notifier.stop()
            logger.info("Completion notifier stopped")

        # Stop role sync task
        if hasattr(self, 'role_sync_task'):
            self.role_sync_task.stop()
            logger.info("Role sync task stopped")

        # Close API client
        if self.api_client:
            await self.api_client.close()
            logger.info("API client closed")

        # Close bot
        await super().close()
        logger.info("Bot closed")


def main():
    """Main entry point"""
    bot = AfrooBot()
    try:
        bot.run(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
