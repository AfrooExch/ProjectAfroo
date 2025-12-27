"""
Settings Handler for V4
Manage user profile and preferences
"""

import logging

import discord
from discord.ui import View, Button, Modal, InputText, Select

from api.errors import APIError
from utils.embeds import create_themed_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


async def show_settings(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show user settings

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get user profile (which includes some settings)
        user_data = await api.get(
            "/api/v1/users/profile",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        # For now, use default settings since full settings system isn't built yet
        settings = {
            "notifications_enabled": True,
            "dm_notifications": True,
            "email_notifications": False,
            "email": user_data.get("email", "Not set"),
            "privacy_mode": "public",
            "show_stats": True,
            "show_vouches": True,
            "preferred_currency": "USD"
        }

        notifications_enabled = settings.get("notifications_enabled", True)
        dm_notifications = settings.get("dm_notifications", True)
        email_notifications = settings.get("email_notifications", False)
        email = settings.get("email", "Not set")

        privacy_mode = settings.get("privacy_mode", "public")
        show_stats = settings.get("show_stats", True)
        show_vouches = settings.get("show_vouches", True)

        preferred_currency = settings.get("preferred_currency", "USD")

        # Get account info
        account_age_days = 0
        try:
            from datetime import datetime
            created_at = user_data.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    account_age_days = (datetime.utcnow() - created.replace(tzinfo=None)).days
        except:
            pass

        # Create settings embed
        embed = create_themed_embed(
            title="",
            description=(
                f"## ⚙️ Account Info & Settings\n\n"
                f"**User:** {interaction.user.mention}\n"
                f"**Discord ID:** `{interaction.user.id}`\n"
                f"**Account Age:** {account_age_days} days\n\n"
                f"### Account Status\n\n"
                f"**Status:** {user_data.get('status', 'active').title()}\n"
                f"**Reputation Score:** {user_data.get('reputation_score', 100)}/100\n"
                f"**KYC Level:** Level {user_data.get('kyc_level', 0)}\n\n"
                f"### Notifications\n\n"
                f"**DM Notifications:** ✅ Enabled (for ticket updates)\n"
                f"**Completion Alerts:** ✅ Enabled\n"
                f"**Transaction Alerts:** ✅ Enabled\n\n"
                f"### Privacy & Security\n\n"
                f"**Profile Visibility:** Public\n"
                f"**Stats Sharing:** Enabled\n"
                f"**Recovery Codes:** {'✅ Generated' if user_data.get('has_recovery_codes') else '⚠️ Not Generated'}\n\n"
                f"### Quick Actions\n\n"
                f"> • Generate recovery codes in Dashboard\n"
                f"> • View your stats and tier\n"
                f"> • Manage wallets and transactions\n\n"
                f"### Need Help?\n\n"
                f"> Contact support via the Support Panel for account-related questions."
            ),
            color=PURPLE_GRADIENT
        )

        embed.set_footer(text="💡 Tip: Generate recovery codes to secure your account")

        await interaction.followup.send(embed=embed, ephemeral=True)

        logger.info(f"Showed settings for user {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error fetching settings: {e}")
        await interaction.followup.send(
            f"❌ **Error Loading Settings**\n\n{e.user_message}",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing settings: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ **Error**\n\nFailed to load settings: {str(e)}",
            ephemeral=True
        )


class SettingsView(View):
    """View for managing settings"""

    def __init__(self, bot: discord.Bot, user_id: int, current_settings: dict):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.current_settings = current_settings

    @discord.ui.button(
        label="Toggle Notifications",
        style=discord.ButtonStyle.secondary,
        emoji="🔔"
    )
    async def toggle_notifications_button(self, button: Button, interaction: discord.Interaction):
        """Toggle notifications on/off"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You can only manage your own settings.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client

            current = self.current_settings.get("notifications_enabled", True)
            new_value = not current

            await api.patch(f"/api/v1/users/{self.user_id}/settings", {
                "notifications_enabled": new_value
            })

            await interaction.followup.send(
                f"✅ Notifications {'enabled' if new_value else 'disabled'}.",
                ephemeral=True
            )

            # Update settings
            self.current_settings["notifications_enabled"] = new_value

            logger.info(f"User {self.user_id} toggled notifications to {new_value}")

        except APIError as e:
            logger.error(f"API error toggling notifications: {e}")
            await interaction.followup.send(
                f"❌ **Error**\n\n{e.user_message}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error toggling notifications: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**\n\n{str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="Set Email",
        style=discord.ButtonStyle.secondary,
        emoji="📧"
    )
    async def set_email_button(self, button: Button, interaction: discord.Interaction):
        """Set email address"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You can only manage your own settings.",
                ephemeral=True
            )
            return

        modal = SetEmailModal(self.bot, self.user_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Privacy Settings",
        style=discord.ButtonStyle.secondary,
        emoji="🔒"
    )
    async def privacy_button(self, button: Button, interaction: discord.Interaction):
        """Adjust privacy settings"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You can only manage your own settings.",
                ephemeral=True
            )
            return

        # Show privacy options
        await interaction.response.send_message(
            "🔒 **Privacy Settings**\n\n"
            "Privacy options coming soon!\n"
            "You'll be able to control:\n"
            "• Who can see your stats\n"
            "• Who can see your vouches\n"
            "• Profile visibility\n",
            ephemeral=True
        )


class SetEmailModal(Modal):
    """Modal for setting email address"""

    def __init__(self, bot: discord.Bot, user_id: int):
        super().__init__(title="Set Email Address")
        self.bot = bot
        self.user_id = user_id

        self.email_input = InputText(
            label="Email Address",
            placeholder="your.email@example.com",
            required=True,
            max_length=100,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.email_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle email submission"""
        await interaction.response.defer(ephemeral=True)

        try:
            email = self.email_input.value.strip()

            # Basic email validation
            if "@" not in email or "." not in email:
                await interaction.followup.send(
                    "❌ Please enter a valid email address.",
                    ephemeral=True
                )
                return

            api = self.bot.api_client

            await api.patch(f"/api/v1/users/{self.user_id}/settings", {
                "email": email
            })

            await interaction.followup.send(
                f"✅ Email address set to: `{email}`",
                ephemeral=True
            )

            logger.info(f"User {self.user_id} set email address")

        except APIError as e:
            logger.error(f"API error setting email: {e}")
            await interaction.followup.send(
                f"❌ **Error**\n\n{e.user_message}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting email: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**\n\n{str(e)}",
                ephemeral=True
            )
