"""
Exchange Flow Views for V4
Multi-step exchange creation flow with send/receive method selection
"""

import logging
from typing import Optional
import asyncio

import discord
from discord.ui import View, Select, Button, Modal, InputText

from utils.embeds import create_themed_embed, create_success_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS, ERROR
from utils.payment_methods import (
    get_payment_methods_for_selection,
    get_crypto_assets_for_selection,
    format_payment_method_display,
    get_tos_for_method
)
from utils.session_manager import session_manager
from config import config

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN EXCHANGE PANEL
# ============================================================================

class ExchangePanelView(View):
    """Main exchange panel with Start Exchange button"""

    def __init__(self, bot):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot

    @discord.ui.button(
        label="Start Exchange",
        style=discord.ButtonStyle.primary,
        emoji="🚀",
        custom_id="start_exchange_button"
    )
    async def start_exchange_button(self, button: Button, interaction: discord.Interaction):
        """Start exchange flow"""
        logger.info(f"User {interaction.user.id} clicked Start Exchange")

        # Create session
        session_manager.create_session(interaction.user.id, session_type="exchange")

        # Show send method selector
        await self.show_send_method_selector(interaction)

    async def show_send_method_selector(self, interaction: discord.Interaction):
        """Show send method selection"""
        embed = create_themed_embed(
            title="",
            description=(
                "## Start an Exchange\n\n"
                "### Step 1: What are you sending?\n\n"
                "Select the payment method you'll use to send funds.\n\n"
                "> Choose carefully - this cannot be changed later."
            ),
            color=PURPLE_GRADIENT
        )

        view = SendMethodSelector(interaction.user.id, self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ============================================================================
# STEP 1: SEND METHOD SELECTION
# ============================================================================

class SendMethodSelector(View):
    """Dropdown for selecting what the user will send"""

    def __init__(self, user_id: int, bot):
        super().__init__(timeout=600)  # 10 minutes - longer timeout to prevent interaction failures
        self.user_id = user_id
        self.bot = bot

        # Get guild to fetch custom emojis (same as Wallet Panel)
        guild = bot.get_guild(config.guild_id) if bot else None

        # Get payment methods
        methods = get_payment_methods_for_selection()

        # Convert to discord SelectOptions with custom emojis
        options = []
        for m in methods[:25]:  # Discord limit
            emoji = None

            # Get emoji name from payment_methods.py
            method_obj = None
            from utils.payment_methods import PAYMENT_METHODS
            for key, pm in PAYMENT_METHODS.items():
                if pm.value == m["value"]:
                    method_obj = pm
                    break

            # Try to get custom server emoji
            if guild and method_obj and method_obj.emoji_name:
                emoji = discord.utils.get(guild.emojis, name=config._config.get("emoji_names", {}).get(method_obj.emoji_name))

            # Fallback to unicode if custom emoji not found
            if not emoji:
                emoji = m["emoji"]

            options.append(discord.SelectOption(
                label=m["label"],
                value=m["value"],
                emoji=emoji,
                description=m["description"]
            ))

        self.send_select = Select(
            placeholder="Choose what you're sending...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"send_method_{user_id}"
        )
        self.send_select.callback = self.on_select
        self.add_item(self.send_select)

    async def on_select(self, interaction: discord.Interaction):
        """Handle send method selection"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you.", ephemeral=True)
            return

        selected_value = self.send_select.values[0]
        logger.info(f"User {interaction.user.id} selected send method: {selected_value}")

        # Update session
        session_manager.update_session(self.user_id, send_method=selected_value)

        # If crypto selected, show crypto asset selector
        if selected_value == "crypto":
            await self.show_crypto_selector(interaction, is_send=True)
        else:
            # Show receive method selector
            await self.show_receive_selector(interaction)

    async def show_crypto_selector(self, interaction: discord.Interaction, is_send: bool):
        """Show cryptocurrency selection"""
        embed = create_themed_embed(
            title="",
            description=(
                f"## Select Cryptocurrency\n\n"
                f"Choose which cryptocurrency you want to {'send' if is_send else 'receive'}.\n\n"
                f"> Make sure to select the correct network for USDT/USDC."
            ),
            color=PURPLE_GRADIENT
        )

        view = CryptoAssetSelector(self.user_id, is_send=is_send, bot=self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_receive_selector(self, interaction: discord.Interaction):
        """Show receive method selection"""
        session = session_manager.get_session(self.user_id)
        send_display = format_payment_method_display(session["send_method"])

        embed = create_themed_embed(
            title="",
            description=(
                f"## Select Receive Method\n\n"
                f"**Sending:** {send_display}\n\n"
                f"### Step 2: What do you want to receive?\n\n"
                f"Choose what you want to receive in exchange.\n\n"
                f"> You cannot select the same payment method."
            ),
            color=PURPLE_GRADIENT
        )

        view = ReceiveMethodSelector(self.user_id, bot=self.bot)
        await interaction.response.edit_message(embed=embed, view=view)


# ============================================================================
# STEP 1B: CRYPTO ASSET SELECTION (if crypto chosen)
# ============================================================================

class CryptoAssetSelector(View):
    """Dropdown for selecting specific cryptocurrency"""

    def __init__(self, user_id: int, is_send: bool, bot):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.is_send = is_send
        self.bot = bot

        # Get guild to fetch custom emojis (same as Wallet Panel)
        guild = bot.get_guild(config.guild_id) if bot else None

        # Get crypto assets
        assets = get_crypto_assets_for_selection()

        # Convert to discord SelectOptions with custom emojis
        options = []
        for a in assets[:25]:
            emoji = None

            # Get emoji name from CRYPTO_ASSETS
            from utils.payment_methods import CRYPTO_ASSETS
            asset_obj = CRYPTO_ASSETS.get(a["value"])

            # Try to get custom server emoji
            if guild and asset_obj and asset_obj.emoji_name:
                emoji = discord.utils.get(guild.emojis, name=config._config.get("emoji_names", {}).get(asset_obj.emoji_name))

            # Fallback to unicode if custom emoji not found
            if not emoji:
                emoji = a["emoji"]

            options.append(discord.SelectOption(
                label=a["label"],
                value=a["value"],
                emoji=emoji,
                description=a["description"]
            ))

        self.crypto_select = Select(
            placeholder="Choose a cryptocurrency...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"crypto_asset_{user_id}"
        )
        self.crypto_select.callback = self.on_select
        self.add_item(self.crypto_select)

    async def on_select(self, interaction: discord.Interaction):
        """Handle crypto selection"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you.", ephemeral=True)
            return

        selected_value = self.crypto_select.values[0]
        logger.info(f"User {interaction.user.id} selected crypto: {selected_value}")

        # Update session
        if self.is_send:
            session_manager.update_session(self.user_id, send_crypto=selected_value)
            # Show receive method selector
            await self.show_receive_selector(interaction)
        else:
            session_manager.update_session(self.user_id, receive_crypto=selected_value)
            # Show amount input
            await self.show_amount_modal(interaction)

    async def show_receive_selector(self, interaction: discord.Interaction):
        """Show receive method selection"""
        session = session_manager.get_session(self.user_id)
        send_display = format_payment_method_display(session["send_method"], session.get("send_crypto"))

        embed = create_themed_embed(
            title="",
            description=(
                f"## Select Receive Method\n\n"
                f"**Sending:** {send_display}\n\n"
                f"### Step 2: What do you want to receive?\n\n"
                f"Choose what you want to receive in exchange.\n\n"
                f"> You cannot select the same payment method."
            ),
            color=PURPLE_GRADIENT
        )

        view = ReceiveMethodSelector(self.user_id, bot=self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_amount_modal(self, interaction: discord.Interaction):
        """Show amount input modal"""
        modal = AmountModal(self.user_id, self.bot)
        await interaction.response.send_modal(modal)


# ============================================================================
# STEP 2: RECEIVE METHOD SELECTION
# ============================================================================

class ReceiveMethodSelector(View):
    """Dropdown for selecting what the user will receive"""

    def __init__(self, user_id: int, bot):
        super().__init__(timeout=600)  # 10 minutes - longer timeout to prevent interaction failures
        self.user_id = user_id
        self.bot = bot

        # Get guild to fetch custom emojis (same as Wallet Panel)
        guild = bot.get_guild(config.guild_id) if bot else None

        # Get payment methods
        methods = get_payment_methods_for_selection()

        # Convert to discord SelectOptions with custom emojis
        options = []
        for m in methods[:25]:  # Discord limit
            emoji = None

            # Get emoji name from payment_methods.py
            method_obj = None
            from utils.payment_methods import PAYMENT_METHODS
            for key, pm in PAYMENT_METHODS.items():
                if pm.value == m["value"]:
                    method_obj = pm
                    break

            # Try to get custom server emoji
            if guild and method_obj and method_obj.emoji_name:
                emoji = discord.utils.get(guild.emojis, name=config._config.get("emoji_names", {}).get(method_obj.emoji_name))

            # Fallback to unicode if custom emoji not found
            if not emoji:
                emoji = m["emoji"]

            options.append(discord.SelectOption(
                label=m["label"],
                value=m["value"],
                emoji=emoji,
                description=m["description"]
            ))

        self.receive_select = Select(
            placeholder="Choose what you're receiving...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"receive_method_{user_id}"
        )
        self.receive_select.callback = self.on_select
        self.add_item(self.receive_select)

    async def on_select(self, interaction: discord.Interaction):
        """Handle receive method selection"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This panel is not for you.", ephemeral=True)
            return

        selected_value = self.receive_select.values[0]
        logger.info(f"User {interaction.user.id} selected receive method: {selected_value}")

        # Get session
        session = session_manager.get_session(self.user_id)

        # Check if same as send method (not allowed)
        send_method = session.get("send_method")
        send_crypto = session.get("send_crypto")

        if selected_value == send_method:
            await interaction.response.send_message(
                "❌ You cannot send and receive the same payment method!",
                ephemeral=True
            )
            return

        # Update session
        session_manager.update_session(self.user_id, receive_method=selected_value)

        # If crypto selected, show crypto asset selector
        if selected_value == "crypto":
            await self.show_crypto_selector(interaction, is_send=False)
        else:
            # Show amount input
            await self.show_amount_modal(interaction)

    async def show_crypto_selector(self, interaction: discord.Interaction, is_send: bool):
        """Show cryptocurrency selection"""
        embed = create_themed_embed(
            title="",
            description=(
                f"## Select Cryptocurrency\n\n"
                f"Choose which cryptocurrency you want to receive.\n\n"
                f"> Make sure to select the correct network for USDT/USDC."
            ),
            color=PURPLE_GRADIENT
        )

        view = CryptoAssetSelector(self.user_id, is_send=is_send, bot=self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_amount_modal(self, interaction: discord.Interaction):
        """Show amount input modal"""
        modal = AmountModal(self.user_id, self.bot)
        await interaction.response.send_modal(modal)


# ============================================================================
# STEP 3: AMOUNT INPUT
# ============================================================================

class AmountModal(Modal):
    """Modal for entering exchange amount in USD"""

    def __init__(self, user_id: int, bot):
        super().__init__(title="Enter Amount")
        self.user_id = user_id
        self.bot = bot

        self.amount_input = InputText(
            label="Amount (USD)",
            placeholder="Enter amount in USD (e.g., 50.00)",
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
            amount_usd = float(self.amount_input.value.replace("$", "").replace(",", "").strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid amount format. Please enter a valid number (e.g., 50.00).",
                ephemeral=True
            )
            return

        # Validate minimum amount
        if amount_usd < 4.00:
            await interaction.response.send_message(
                "❌ Minimum exchange amount is **$4.00 USD**.",
                ephemeral=True
            )
            return

        # Validate maximum amount
        if amount_usd > 100000.00:
            await interaction.response.send_message(
                "❌ Maximum exchange amount is **$100,000 USD**. Contact staff for higher amounts.",
                ephemeral=True
            )
            return

        logger.info(f"User {interaction.user.id} entered amount: ${amount_usd:.2f}")

        # Update session
        session_manager.update_session(self.user_id, amount_usd=amount_usd)

        # Show confirmation
        await self.show_confirmation(interaction, amount_usd)

    async def show_confirmation(self, interaction: discord.Interaction, amount_usd: float):
        """Show exchange confirmation"""
        session = session_manager.get_session(self.user_id)

        send_display = format_payment_method_display(
            session["send_method"],
            session.get("send_crypto")
        )
        receive_display = format_payment_method_display(
            session["receive_method"],
            session.get("receive_crypto")
        )

        # Calculate fees (simplified - API will do full calculation)
        # Crypto-to-crypto: 5%, Fiat >= $40: 10%, Fiat < $40: $4 min
        is_send_crypto = session["send_method"] == "crypto" or session.get("send_crypto")
        is_receive_crypto = session["receive_method"] == "crypto" or session.get("receive_crypto")

        if is_send_crypto and is_receive_crypto:
            fee_percent = 5.0
            fee_amount = amount_usd * 0.05
        elif amount_usd >= 40.0:
            fee_percent = 10.0
            fee_amount = amount_usd * 0.10
        else:
            fee_percent = (4.0 / amount_usd) * 100
            fee_amount = 4.0

        receiving_amount = amount_usd - fee_amount

        embed = create_themed_embed(
            title="",
            description=(
                f"## Confirm Exchange\n\n"
                f"### Exchange Details\n\n"
                f"**Sending:** {send_display}\n"
                f"**Receiving:** {receive_display}\n"
                f"**You Send:** `${amount_usd:,.2f} USD`\n"
                f"**Service Fee:** `${fee_amount:.2f} ({fee_percent:.0f}%)`\n"
                f"**You Receive:** `${receiving_amount:,.2f} USD`\n\n"
                f"> Click **Confirm** to create your exchange ticket."
            ),
            color=PURPLE_GRADIENT
        )

        view = ExchangeConfirmation(self.user_id, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)


# ============================================================================
# STEP 4: CONFIRMATION
# ============================================================================

class ExchangeConfirmation(View):
    """Confirmation view for exchange creation"""

    def __init__(self, user_id: int, bot):
        super().__init__(timeout=600)  # 10 minutes - longer timeout to prevent interaction failures
        self.user_id = user_id
        self.bot = bot

    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm_button(self, button: Button, interaction: discord.Interaction):
        """Create exchange ticket"""
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
        from cogs.tickets.handlers.ticket_creation import create_exchange_ticket

        # Create ticket
        try:
            await create_exchange_ticket(
                bot=self.bot,
                user=interaction.user,
                guild=interaction.guild,
                session_data=session
            )

            # Clear session
            session_manager.clear_session(self.user_id)

            await interaction.followup.send(
                "✅ Exchange ticket created! Check your private ticket channel.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error creating exchange ticket: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to create exchange ticket: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="❌"
    )
    async def cancel_button(self, button: Button, interaction: discord.Interaction):
        """Cancel exchange creation"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
            return

        # Clear session
        session_manager.clear_session(self.user_id)

        await interaction.response.edit_message(
            content="❌ Exchange creation cancelled.",
            embed=None,
            view=None
        )


# ============================================================================
# HELPER: Deploy Exchange Panel
# ============================================================================

async def send_exchange_panel(channel: discord.TextChannel, bot=None):
    """Deploy exchange panel to channel"""
    embed = create_themed_embed(
        title="",
        description=(
            "## 🔄 AFROO EXCHANGE\n\n"
            "### Start an Exchange\n\n"
            "**How it works:**\n"
            "> 1. Click **Start Exchange** below\n"
            "> 2. Select your payment methods\n"
            "> 3. Agree to our Terms of Service\n"
            "> 4. An exchanger will assist you\n\n"
            "**Supported Payment Methods:**\n"
            "> • Crypto (BTC, ETH, SOL, USDT, USDC, LTC)\n"
            "> • PayPal, CashApp, Venmo, Zelle\n"
            "> • Gift Cards (Amazon, Steam)\n"
            "> • And more...\n\n"
            "> 💡 **Tip:** Have your payment ready before starting!"
        ),
        color=PURPLE_GRADIENT
    )

    view = ExchangePanelView(bot)
    await channel.send(embed=embed, view=view)
