"""
Swap Views - Confirmation and status tracking for Afroo Swap
"""

import discord
import logging
import asyncio
from typing import Optional

from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED
from utils.auth import get_user_context
from api.client import APIClient
from api.errors import APIError, ValidationError

logger = logging.getLogger(__name__)


class SwapConfirmationView(discord.ui.View):
    """
    Shows swap quote details and confirms execution
    """

    def __init__(
        self,
        user_id: int,
        api: APIClient,
        from_asset: str,
        to_asset: str,
        amount: float,
        quote: dict
    ):
        super().__init__(timeout=60)  # Quote valid for 60 seconds
        self.user_id = user_id
        self.api = api
        self.from_asset = from_asset
        self.to_asset = to_asset
        self.amount = amount
        self.quote = quote

    @discord.ui.button(
        label="Confirm Swap",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Execute the swap"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your swap confirmation.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get user context
            user_context_id, roles = get_user_context(interaction)

            # Execute swap via API
            result = await self.api.afroo_swap_execute(
                from_asset=self.from_asset,
                to_asset=self.to_asset,
                amount=self.amount,
                user_id=str(interaction.user.id),
                discord_roles=roles
            )

            # Disable buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            # Get swap data
            swap_data = result.get("swap", {})

            # Show success message
            success_embed = create_themed_embed(
                title="",
                description=(
                    f"## ✅ Swap Created!\n\n"
                    f"Your **{self.from_asset}** is being swapped to **{self.to_asset}**.\n\n"
                    f"**Status:** Processing\n"
                    f"**Swap ID:** `{swap_data.get('_id', 'N/A')}`\n\n"
                    f"> Your swap is being processed. You'll receive **{self.to_asset}** in your Afroo Wallet shortly."
                ),
                color=SUCCESS_GREEN
            )

            await interaction.followup.send(embed=success_embed, ephemeral=True)

            # Show status tracking in original message
            await self.show_status_view(interaction, swap_data)

        except ValidationError as e:
            logger.error(f"Validation error executing swap: {e}")
            error_embed = create_themed_embed(
                title="❌ Swap Failed",
                description=f"{e.user_message}\n\n> Please try again or contact support if the issue persists.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

        except APIError as e:
            logger.error(f"API error executing swap: {e}")
            error_embed = create_themed_embed(
                title="❌ Swap Failed",
                description=f"{e.user_message}\n\n> Please try again or contact support if the issue persists.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error executing swap: {e}", exc_info=True)
            error_embed = create_themed_embed(
                title="❌ Swap Failed",
                description="An unexpected error occurred. Please try again or contact support.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="❌"
    )
    async def cancel_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Cancel the swap"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your swap confirmation.",
                ephemeral=True
            )
            return

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="❌ Swap cancelled.",
            embed=None,
            view=self
        )

    async def show_status_view(self, interaction: discord.Interaction, swap_data: dict):
        """Show swap status tracking"""
        status_view = SwapStatusView(
            user_id=self.user_id,
            api=self.api,
            swap_id=str(swap_data.get("_id", "")),
            from_asset=self.from_asset,
            to_asset=self.to_asset,
            amount=self.amount,
            estimated_output=swap_data.get("estimated_output", 0)
        )

        status_embed = create_themed_embed(
            title="",
            description=(
                f"## 🔄 Swap Status\n\n"
                f"**From:** `{self.amount} {self.from_asset}`\n"
                f"**To:** `~{swap_data.get('estimated_output', 0)} {self.to_asset}`\n"
                f"**Status:** `Processing`\n\n"
                f"> Click **Refresh Status** to check progress."
            ),
            color=PURPLE_GRADIENT
        )

        await interaction.message.edit(embed=status_embed, view=status_view)


class SwapStatusView(discord.ui.View):
    """
    Shows swap status and allows refreshing
    """

    def __init__(
        self,
        user_id: int,
        api: APIClient,
        swap_id: str,
        from_asset: str,
        to_asset: str,
        amount: float,
        estimated_output: float
    ):
        super().__init__(timeout=None)  # Persistent view for status checking
        self.user_id = user_id
        self.api = api
        self.swap_id = swap_id
        self.from_asset = from_asset
        self.to_asset = to_asset
        self.amount = amount
        self.estimated_output = estimated_output

    @discord.ui.button(
        label="Refresh Status",
        style=discord.ButtonStyle.primary,
        emoji="🔄"
    )
    async def refresh_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Refresh swap status"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your swap.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # Get user context
            user_context_id, roles = get_user_context(interaction)

            # Get swap details from API
            swap_data = await self.api.afroo_swap_get_details(
                swap_id=self.swap_id,
                user_id=str(interaction.user.id),
                discord_roles=roles
            )

            status = swap_data.get("status", "unknown")
            changenow_status = swap_data.get("changenow_status", "")
            actual_output = swap_data.get("actual_output")

            # Status-specific messages and colors
            if status == "completed":
                color = SUCCESS_GREEN
                status_display = "✅ Completed"
                message = f"> Your swap is complete! **{actual_output or self.estimated_output} {self.to_asset}** has been credited to your Afroo Wallet."

                # Disable refresh button when completed
                for item in self.children:
                    item.disabled = True

            elif status == "failed" or status == "refunded":
                color = ERROR_RED
                status_display = f"❌ {status.title()}"
                message = f"> Your swap {status}. Your **{self.from_asset}** has been refunded to your wallet."

                # Disable refresh button
                for item in self.children:
                    item.disabled = True

            elif status == "processing":
                color = PURPLE_GRADIENT
                status_display = "⏳ Processing"
                message = f"> Your swap is being processed by our exchange partner. This usually takes 5-30 minutes."

            else:
                color = PURPLE_GRADIENT
                status_display = f"🔄 {status.title()}"
                message = f"> Your swap is in progress. Check back soon for updates."

            # Build status embed
            status_embed = create_themed_embed(
                title="",
                description=(
                    f"## 🔄 Swap Status\n\n"
                    f"**From:** `{self.amount} {self.from_asset}`\n"
                    f"**To:** `~{self.estimated_output} {self.to_asset}`\n"
                    f"**Status:** {status_display}\n"
                    f"**Swap ID:** `{self.swap_id}`\n\n"
                    f"{message}"
                ),
                color=color
            )

            await interaction.message.edit(embed=status_embed, view=self)

        except APIError as e:
            logger.error(f"API error getting swap status: {e}")
            await interaction.followup.send(
                f"❌ Failed to get swap status: {e.user_message}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error getting swap status: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while checking swap status.",
                ephemeral=True
            )
