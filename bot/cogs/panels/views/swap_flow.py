"""
Swap Flow Views - Dropdown-based swap creation with private ticket channels
Multi-step flow: Select From Asset → Select To Asset → Enter Amount → Confirm → Create Ticket
"""

import logging
from typing import Optional
import asyncio

import discord
from discord.ui import View, Select, Button, Modal, InputText

from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED
from utils.session_manager import session_manager
from config import config

logger = logging.getLogger(__name__)


# Supported swap assets
SWAP_ASSETS = [
    {"code": "BTC", "name": "Bitcoin", "emoji": "₿"},
    {"code": "ETH", "name": "Ethereum", "emoji": "⟠"},
    {"code": "SOL", "name": "Solana", "emoji": "◎"},
    {"code": "LTC", "name": "Litecoin", "emoji": "Ł"},
    {"code": "USDT-SOL", "name": "USDT (Solana)", "emoji": "₮"},
    {"code": "USDT-ETH", "name": "USDT (Ethereum)", "emoji": "₮"},
    {"code": "USDC-SOL", "name": "USDC (Solana)", "emoji": "$"},
    {"code": "USDC-ETH", "name": "USDC (Ethereum)", "emoji": "$"},
]


# ============================================================================
# MAIN SWAP PANEL
# ============================================================================

class SwapPanelView(View):
    """Main swap panel with Start Swap button"""

    def __init__(self, bot):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot

    @discord.ui.button(
        label="Start Swap",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="start_swap_button"
    )
    async def start_swap_button(self, button: Button, interaction: discord.Interaction):
        """Start swap flow"""
        logger.info(f"User {interaction.user.id} clicked Start Swap")

        # Create session
        session_manager.create_session(interaction.user.id, session_type="swap")

        # Show from asset selector
        await self.show_from_asset_selector(interaction)

    async def show_from_asset_selector(self, interaction: discord.Interaction):
        """Show from asset selection"""
        embed = create_themed_embed(
            title="",
            description=(
                "## 🔄 Start a Swap\n\n"
                "### Step 1: What are you swapping from?\n\n"
                "Select the cryptocurrency you want to swap.\n\n"
                "> Your balance will be checked before executing the swap."
            ),
            color=PURPLE_GRADIENT
        )

        view = FromAssetSelector(interaction.user.id, self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ============================================================================
# STEP 1: FROM ASSET SELECTION
# ============================================================================

class FromAssetSelector(View):
    """Dropdown for selecting source asset"""

    def __init__(self, user_id: int, bot):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot

        # Build asset options
        options = []
        for asset in SWAP_ASSETS:
            options.append(
                discord.SelectOption(
                    label=asset["name"],
                    value=asset["code"],
                    emoji=asset["emoji"],
                    description=f"Swap from {asset['code']}"
                )
            )

        self.from_select = Select(
            placeholder="Choose source cryptocurrency...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1,
            custom_id=f"from_asset_{user_id}"
        )
        self.from_select.callback = self.on_select
        self.add_item(self.from_select)

    async def on_select(self, interaction: discord.Interaction):
        """Handle from asset selection"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you.", ephemeral=True)
            return

        selected_value = self.from_select.values[0]
        logger.info(f"User {interaction.user.id} selected from asset: {selected_value}")

        # Update session
        session_manager.update_session(self.user_id, from_asset=selected_value)

        # Show to asset selector
        await self.show_to_asset_selector(interaction)

    async def show_to_asset_selector(self, interaction: discord.Interaction):
        """Show to asset selection"""
        session = session_manager.get_session(self.user_id)
        from_asset = session["from_asset"]

        # Get asset name
        from_asset_name = next((a["name"] for a in SWAP_ASSETS if a["code"] == from_asset), from_asset)

        embed = create_themed_embed(
            title="",
            description=(
                f"## Select Destination Asset\n\n"
                f"**Swapping From:** {from_asset_name} ({from_asset})\n\n"
                f"### Step 2: What do you want to receive?\n\n"
                f"Choose the cryptocurrency you want to swap to.\n\n"
                f"> You cannot select the same asset."
            ),
            color=PURPLE_GRADIENT
        )

        view = ToAssetSelector(self.user_id, bot=self.bot)
        await interaction.response.edit_message(embed=embed, view=view)


# ============================================================================
# STEP 2: TO ASSET SELECTION
# ============================================================================

class ToAssetSelector(View):
    """Dropdown for selecting destination asset"""

    def __init__(self, user_id: int, bot):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot

        # Build asset options
        options = []
        for asset in SWAP_ASSETS:
            options.append(
                discord.SelectOption(
                    label=asset["name"],
                    value=asset["code"],
                    emoji=asset["emoji"],
                    description=f"Swap to {asset['code']}"
                )
            )

        self.to_select = Select(
            placeholder="Choose destination cryptocurrency...",
            options=options[:25],
            min_values=1,
            max_values=1,
            custom_id=f"to_asset_{user_id}"
        )
        self.to_select.callback = self.on_select
        self.add_item(self.to_select)

    async def on_select(self, interaction: discord.Interaction):
        """Handle to asset selection"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you.", ephemeral=True)
            return

        selected_value = self.to_select.values[0]
        logger.info(f"User {interaction.user.id} selected to asset: {selected_value}")

        # Get session
        session = session_manager.get_session(self.user_id)
        from_asset = session.get("from_asset")

        # Check if same as from asset (not allowed)
        if selected_value == from_asset:
            await interaction.response.send_message(
                "❌ You cannot swap to the same asset!",
                ephemeral=True
            )
            return

        # Update session
        session_manager.update_session(self.user_id, to_asset=selected_value)

        # Show amount input
        await self.show_amount_modal(interaction)

    async def show_amount_modal(self, interaction: discord.Interaction):
        """Show amount input modal"""
        modal = SwapAmountModal(self.user_id, self.bot)
        await interaction.response.send_modal(modal)


# ============================================================================
# STEP 3: AMOUNT INPUT
# ============================================================================

class SwapAmountModal(Modal):
    """Modal for entering swap amount"""

    def __init__(self, user_id: int, bot):
        super().__init__(title="Enter Swap Amount")
        self.user_id = user_id
        self.bot = bot

        self.amount_input = InputText(
            label="Amount",
            placeholder="Enter amount to swap (e.g., 0.001)",
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.amount_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle amount submission"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your modal.", ephemeral=True)
            return

        # Parse amount
        try:
            amount = float(self.amount_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid amount format. Please enter a valid number (e.g., 0.001).",
                ephemeral=True
            )
            return

        # Validate amount
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return

        if amount > 1000000:
            await interaction.response.send_message(
                "❌ Amount too large. Maximum is 1,000,000.",
                ephemeral=True
            )
            return

        logger.info(f"User {interaction.user.id} entered amount: {amount}")

        # Update session
        session_manager.update_session(self.user_id, amount=amount)

        # Get quote and show confirmation
        await self.show_confirmation(interaction, amount)

    async def show_confirmation(self, interaction: discord.Interaction, amount: float):
        """Show swap confirmation with quote"""
        await interaction.response.defer(ephemeral=True)

        session = session_manager.get_session(self.user_id)
        from_asset = session["from_asset"]
        to_asset = session["to_asset"]

        try:
            # Get API client
            api = self.bot.api_client

            # Get user context
            from utils.auth import get_user_context
            user_context_id, roles = get_user_context(interaction)

            # Get quote from API
            result = await api.afroo_swap_get_quote(
                from_asset=from_asset,
                to_asset=to_asset,
                amount=amount,
                user_id=str(interaction.user.id),
                discord_roles=roles
            )

            quote = result.get("quote", {})

            # Store quote in session
            session_manager.update_session(self.user_id, quote=quote)

            # Build confirmation embed
            platform_fee_percent = quote.get("platform_fee_percent", 0.2)
            platform_fee_units = quote.get("platform_fee_units", 0)
            estimated_output = quote.get("estimated_output", 0)
            exchange_rate = quote.get("exchange_rate", 0)
            total_deducted = quote.get("total_deducted", 0)

            # Get asset names
            from_asset_name = next((a["name"] for a in SWAP_ASSETS if a["code"] == from_asset), from_asset)
            to_asset_name = next((a["name"] for a in SWAP_ASSETS if a["code"] == to_asset), to_asset)

            embed = create_themed_embed(
                title="",
                description=(
                    f"## Confirm Swap\n\n"
                    f"### Swap Details\n\n"
                    f"**From:** {from_asset_name} ({from_asset})\n"
                    f"**To:** {to_asset_name} ({to_asset})\n\n"
                    f"**You Send:** `{amount} {from_asset}`\n"
                    f"**Platform Fee ({platform_fee_percent}%):** `{platform_fee_units:.8f} {from_asset}`\n"
                    f"**Total Deducted:** `{total_deducted:.8f} {from_asset}`\n\n"
                    f"**Exchange Rate:** `1 {from_asset} = {exchange_rate:.8f} {to_asset}`\n"
                    f"**You Receive:** `~{estimated_output:.8f} {to_asset}`\n\n"
                    f"> Click **Confirm** to create your swap ticket."
                ),
                color=PURPLE_GRADIENT
            )

            view = SwapConfirmation(self.user_id, self.bot)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting swap quote: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to get swap quote: {str(e)}",
                ephemeral=True
            )


# ============================================================================
# STEP 4: CONFIRMATION & TICKET CREATION
# ============================================================================

class SwapConfirmation(View):
    """Confirmation view for swap creation"""

    def __init__(self, user_id: int, bot):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bot = bot

    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm_button(self, button: Button, interaction: discord.Interaction):
        """Create swap ticket"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Get session
        session = session_manager.get_session(self.user_id)
        if not session:
            await interaction.followup.send("❌ Session expired. Please start over.", ephemeral=True)
            return

        # Import here to avoid circular import
        from cogs.panels.handlers.swap_handler import create_swap_ticket

        # Create swap ticket
        try:
            await create_swap_ticket(
                bot=self.bot,
                user=interaction.user,
                guild=interaction.guild,
                session_data=session
            )

            # Clear session
            session_manager.clear_session(self.user_id)

            await interaction.followup.send(
                "✅ Swap ticket created! Check your private swap channel.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error creating swap ticket: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to create swap ticket: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="❌"
    )
    async def cancel_button(self, button: Button, interaction: discord.Interaction):
        """Cancel swap creation"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
            return

        # Clear session
        session_manager.clear_session(self.user_id)

        await interaction.response.edit_message(
            content="❌ Swap creation cancelled.",
            embed=None,
            view=None
        )
