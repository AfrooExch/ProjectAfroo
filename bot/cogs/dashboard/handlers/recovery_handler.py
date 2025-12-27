"""
Recovery Codes Handler for V4
Generates and displays account recovery codes
"""

import logging

import discord
from discord.ui import View, Button

from api.errors import APIError
from utils.embeds import create_themed_embed, create_success_embed
from utils.colors import PURPLE_GRADIENT, WARNING

logger = logging.getLogger(__name__)


async def show_recovery_codes(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show recovery codes or generate new ones

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Check if user has recovery codes
        recovery_data = await api.get(
            f"/api/v1/recovery/{interaction.user.id}/info",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        has_codes = recovery_data.get("has_codes", False)
        generated_at = recovery_data.get("generated_at", "")
        used = recovery_data.get("used", False)
        recovery_code = recovery_data.get("recovery_code")

        if has_codes:
            # Show recovery code info
            embed = create_themed_embed(
                title="",
                description=(
                    f"## 🔑 Your Recovery Code\n\n"
                    f"**Generated:** {generated_at}\n"
                    f"**Status:** {'✅ Active' if not used else '❌ Used'}\n\n"
                    f"### ⚠️ IMPORTANT\n\n"
                    f"> • Your recovery code is linked to THIS Discord account only\n"
                    f"> • The code can only be used ONCE to transfer your account\n"
                    f"> • You'll need it if you lose access to your Discord account\n"
                    f"> • Never share this code with anyone\n"
                    f"> • Staff will NEVER ask for your recovery code\n\n"
                    f"### 🔄 Need a New Code?\n\n"
                    f"> If you lost your code or want to refresh it, you can generate a new one.\n"
                    f"> **WARNING:** This will invalidate your existing code!\n\n"
                    f"> Click the button below to regenerate."
                ),
                color=WARNING
            )

            view = RecoveryCodesView(bot, interaction.user.id)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        else:
            # No codes yet, prompt to generate
            embed = create_themed_embed(
                title="",
                description=(
                    f"## 🔑 Recovery Codes\n\n"
                    f"### Account Security\n\n"
                    f"Recovery codes allow you to regain access to your Afroo account if you lose access to your Discord account.\n\n"
                    f"**What are recovery codes?**\n"
                    f"> • One-time use codes for account recovery\n"
                    f"> • Must be stored securely (password manager recommended)\n"
                    f"> • Required if you lose Discord account access\n\n"
                    f"**Why do I need them?**\n"
                    f"> • Your Afroo balance and stats are tied to your Discord ID\n"
                    f"> • If you lose Discord access, these codes can transfer your account\n"
                    f"> • They're your backup plan for account security\n\n"
                    f"> Click the button below to generate your recovery codes."
                ),
                color=PURPLE_GRADIENT
            )

            view = GenerateCodesView(bot, interaction.user.id)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed recovery codes for user {interaction.user.id}")

    except APIError as e:
        logger.error(f"API error fetching recovery codes: {e}")
        await interaction.followup.send(
            f"❌ **Error Loading Recovery Codes**\n\n{e.user_message}",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing recovery codes: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ **Error**\n\nFailed to load recovery codes: {str(e)}",
            ephemeral=True
        )


class RecoveryCodesView(View):
    """View for managing existing recovery codes"""

    def __init__(self, bot: discord.Bot, user_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id

    @discord.ui.button(
        label="Generate New Codes",
        style=discord.ButtonStyle.danger,
        emoji="🔄"
    )
    async def regenerate_button(self, button: Button, interaction: discord.Interaction):
        """Regenerate recovery codes"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You can only manage your own recovery codes.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Generate new codes
            result = await api.post(
                f"/api/v1/recovery/{self.user_id}/regenerate",
                {},
                discord_user_id=str(self.user_id),
                discord_roles=roles
            )

            new_code = result.get("codes", [""])[0]

            embed = create_success_embed(
                title="Recovery Code Regenerated",
                description=(
                    f"### Your New Recovery Code\n\n"
                    f"# `{new_code}`\n\n"
                    f"### ⚠️ SAVE THIS CODE NOW\n\n"
                    f"> • Your old code is now **INVALID**\n"
                    f"> • This code is linked to your account only\n"
                    f"> • Use it to recover your account if you lose Discord access\n"
                    f"> • Store it securely (password manager, paper in safe, etc.)\n"
                    f"> • Never share with anyone (not even staff)\n\n"
                    f"### How to Use:\n\n"
                    f"> If you lose access to this Discord account:\n"
                    f"> 1. Create a new Discord account\n"
                    f"> 2. Join Afroo server\n"
                    f"> 3. Click 'Redeem Code' in Dashboard\n"
                    f"> 4. Enter this code to transfer everything\n\n"
                    f"> **This code will only be shown this one time!**"
                )
            )

            # Send the new codes in followup
            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Regenerated recovery codes for user {self.user_id}")

        except APIError as e:
            logger.error(f"API error regenerating codes: {e}")
            await interaction.followup.send(
                f"❌ **Error**\n\n{e.user_message}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error regenerating codes: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**\n\n{str(e)}",
                ephemeral=True
            )


class GenerateCodesView(View):
    """View for first-time code generation"""

    def __init__(self, bot: discord.Bot, user_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id

    @discord.ui.button(
        label="Generate Recovery Codes",
        style=discord.ButtonStyle.primary,
        emoji="🔑"
    )
    async def generate_button(self, button: Button, interaction: discord.Interaction):
        """Generate recovery codes for first time"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You can only generate codes for your own account.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from utils.auth import get_user_context
            api = self.bot.api_client
            user_context_id, roles = get_user_context(interaction)

            # Generate codes
            result = await api.post(
                f"/api/v1/recovery/{self.user_id}/generate",
                {},
                discord_user_id=str(self.user_id),
                discord_roles=roles
            )

            recovery_code = result.get("codes", [""])[0]

            embed = create_success_embed(
                title="Recovery Code Generated",
                description=(
                    f"### Your Recovery Code\n\n"
                    f"# `{recovery_code}`\n\n"
                    f"### ⚠️ SAVE THIS CODE NOW\n\n"
                    f"> • This code is linked to your account only\n"
                    f"> • Use it to recover your account if you lose Discord access\n"
                    f"> • Store it securely (password manager, paper in safe, etc.)\n"
                    f"> • The code can only be used ONCE\n"
                    f"> • Never share with anyone (not even staff)\n\n"
                    f"### How to Use:\n\n"
                    f"> If you lose access to this Discord account:\n"
                    f"> 1. Create a new Discord account\n"
                    f"> 2. Join Afroo server\n"
                    f"> 3. Click 'Redeem Code' in Dashboard\n"
                    f"> 4. Enter this code to transfer everything\n\n"
                    f"> **This is the only time this code will be shown!**"
                )
            )

            # Send the new codes in followup
            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Generated recovery codes for user {self.user_id}")

        except APIError as e:
            logger.error(f"API error generating codes: {e}")
            await interaction.followup.send(
                f"❌ **Error**\n\n{e.user_message}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error generating codes: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**\n\n{str(e)}",
                ephemeral=True
            )
