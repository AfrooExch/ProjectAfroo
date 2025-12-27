"""
Exchange Ticket Creation Views
Multi-step dropdown flow for creating exchange tickets
"""

import discord
import logging
from typing import Optional

from cogs.tickets.constants import (
    SEND_PAYMENT_METHODS, RECEIVE_PAYMENT_METHODS, PAYMENT_METHODS,
    CRYPTO_ASSETS, calculate_fee, validate_amount, get_payment_method
)
from cogs.tickets.session_manager import ExchangeSessionManager
from cogs.tickets.views.tos_views import TOSView, create_tos_embed
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN, ERROR_RED
from utils.auth import get_user_context
from api.client import APIClient
from config import config

logger = logging.getLogger(__name__)


class SendMethodSelector(discord.ui.View):
    """
    Step 1: Select sending payment method
    Dropdown with 18 payment options
    """

    def __init__(
        self,
        session_manager: ExchangeSessionManager,
        api: APIClient,
        bot=None,
        timeout: float = 600  # 10 minutes - longer timeout to prevent interaction failures
    ):
        super().__init__(timeout=timeout)
        self.session_manager = session_manager
        self.api = api
        self.bot = bot
        self.add_item(SendMethodDropdown(bot))


class SendMethodDropdown(discord.ui.Select):
    """Dropdown for selecting sending payment method"""

    def __init__(self, bot=None):
        # Get guild to fetch custom emojis (same as Wallet Panel)
        from config import config
        guild = bot.get_guild(config.guild_id) if bot else None

        options = []
        for method_id, method in SEND_PAYMENT_METHODS.items():
            emoji = method.emoji  # Default fallback

            # Try to get custom server emoji
            if guild:
                emoji_name = None
                # Map method ID to emoji name
                if method_id == "crypto":
                    emoji_name = "CRYPTO"
                elif "paypal" in method_id:
                    emoji_name = "PAYPAL"
                elif "cashapp" in method_id:
                    emoji_name = "CASHAPP"
                elif "applepay" in method_id:
                    emoji_name = "APPLEPAY"
                elif "venmo" in method_id:
                    emoji_name = "VENMO"
                elif "zelle" in method_id:
                    emoji_name = "ZELLE"
                elif "chime" in method_id:
                    emoji_name = "CHIME"
                elif "revolut" in method_id:
                    emoji_name = "REVOLUT"
                elif "skrill" in method_id:
                    emoji_name = "SKRIL"
                elif "bank" in method_id:
                    emoji_name = "BANK"
                elif "paysafe" in method_id:
                    emoji_name = "PAYSAFE"
                elif "binance" in method_id:
                    emoji_name = "BINANCE"

                if emoji_name:
                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                    if custom_emoji:
                        emoji = custom_emoji

            options.append(
                discord.SelectOption(
                    label=method.name,
                    value=method_id,
                    emoji=emoji,
                    description=f"Send via {method.name}"
                )
            )

        super().__init__(
            placeholder="Select your sending payment method...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle send method selection"""
        try:
            await interaction.response.defer(ephemeral=True)

            selected_method_id = self.values[0]
            selected_method = SEND_PAYMENT_METHODS[selected_method_id]

            user_id, roles = get_user_context(interaction)

            view: SendMethodSelector = self.view
            session_manager = view.session_manager
            api = view.api
            bot = view.bot

            # Update session
            session_manager.set_send_method(user_id, selected_method_id, None)

            # If crypto selected, ask which crypto asset
            if selected_method.requires_crypto_selection:
                embed = create_themed_embed(
                    title="Select Cryptocurrency",
                    description="Which cryptocurrency will you be sending?",
                    color=PURPLE_GRADIENT
                )
                view_next = CryptoAssetSelector(session_manager, api, selection_type="send", bot=bot)
                await interaction.followup.send(embed=embed, view=view_next, ephemeral=True)
            else:
                # Move to receive method selection
                embed = create_themed_embed(
                    title="Select Receiving Method",
                    description=f"You're sending via **{selected_method.name}**.\n\nNow, how would you like to receive your funds?",
                    color=PURPLE_GRADIENT
                )
                view_next = ReceiveMethodSelector(session_manager, api, bot=bot)
                await interaction.followup.send(embed=embed, view=view_next, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in SendMethodSelector: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description="An error occurred. Please try again.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class CryptoAssetSelector(discord.ui.View):
    """
    Step 1.5 / 2.5: Select cryptocurrency asset
    Shown when user selects crypto as send or receive method
    """

    def __init__(
        self,
        session_manager: ExchangeSessionManager,
        api: APIClient,
        selection_type: str,  # "send" or "receive"
        bot=None,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.session_manager = session_manager
        self.api = api
        self.selection_type = selection_type
        self.bot = bot
        self.add_item(CryptoAssetDropdown(selection_type, bot))


class CryptoAssetDropdown(discord.ui.Select):
    """Dropdown for selecting crypto asset"""

    def __init__(self, selection_type: str, bot=None):
        self.selection_type = selection_type

        # Get guild to fetch custom emojis
        from config import config
        guild = bot.get_guild(config.guild_id) if bot else None

        options = []
        for symbol, asset in CRYPTO_ASSETS.items():
            emoji = asset.emoji  # Default fallback

            # Try to get custom server emoji
            if guild:
                # Map symbol to emoji name (e.g., "BTC" -> "BITCOIN", "USDT-ETH" -> "USDT")
                emoji_name = None

                # Check if symbol is in emoji_names config
                if hasattr(config, 'emoji_names') and symbol in config.emoji_names:
                    emoji_name = config.emoji_names[symbol]
                else:
                    # For symbols with network suffix (e.g., "USDT-ETH"), extract base symbol
                    base_symbol = symbol.split('-')[0]
                    if hasattr(config, 'emoji_names') and base_symbol in config.emoji_names:
                        emoji_name = config.emoji_names[base_symbol]
                    else:
                        # Fallback to using symbol itself
                        emoji_name = symbol

                if emoji_name:
                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                    if custom_emoji:
                        emoji = custom_emoji

            options.append(
                discord.SelectOption(
                    label=f"{asset.name} ({symbol})",
                    value=symbol,
                    emoji=emoji,
                    description=f"{asset.network} network"
                )
            )

        super().__init__(
            placeholder="Select cryptocurrency...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle crypto asset selection"""
        try:
            selected_crypto = self.values[0]
            selected_asset = CRYPTO_ASSETS[selected_crypto]

            user_id, roles = get_user_context(interaction)

            view: CryptoAssetSelector = self.view
            session_manager = view.session_manager
            api = view.api
            bot = view.bot

            # Update session
            if self.selection_type == "send":
                # Defer for send path since we're sending followup
                await interaction.response.defer(ephemeral=True)

                session_manager.update_session(user_id, send_crypto=selected_crypto)

                # Move to receive method selection
                embed = create_themed_embed(
                    title="Select Receiving Method",
                    description=f"You're sending **{selected_asset.name}**.\n\nHow would you like to receive your funds?",
                    color=PURPLE_GRADIENT
                )
                view_next = ReceiveMethodSelector(session_manager, api, bot=bot)
                await interaction.followup.send(embed=embed, view=view_next, ephemeral=True)

            else:  # receive - auto-open modal
                session_manager.update_session(user_id, receive_crypto=selected_crypto)

                # Directly open amount modal (no button, no embed clutter)
                modal = AmountInputModal(session_manager, api)
                await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in CryptoAssetSelector: {e}", exc_info=True)

            # Check if we already responded
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            embed = create_themed_embed(
                title="Error",
                description="An error occurred. Please try again.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class ReceiveMethodSelector(discord.ui.View):
    """
    Step 2: Select receiving payment method
    Dropdown with 18 payment options
    """

    def __init__(
        self,
        session_manager: ExchangeSessionManager,
        api: APIClient,
        bot=None,
        timeout: float = 600  # 10 minutes - longer timeout to prevent interaction failures
    ):
        super().__init__(timeout=timeout)
        self.session_manager = session_manager
        self.api = api
        self.bot = bot
        self.add_item(ReceiveMethodDropdown(bot))


class ReceiveMethodDropdown(discord.ui.Select):
    """Dropdown for selecting receiving payment method"""

    def __init__(self, bot=None):
        # Get guild to fetch custom emojis (same as Wallet Panel)
        from config import config
        guild = bot.get_guild(config.guild_id) if bot else None

        options = []
        for method_id, method in RECEIVE_PAYMENT_METHODS.items():
            emoji = method.emoji  # Default fallback

            # Try to get custom server emoji
            if guild:
                emoji_name = None
                # Map method ID to emoji name
                if method_id == "crypto":
                    emoji_name = "CRYPTO"
                elif "paypal" in method_id:
                    emoji_name = "PAYPAL"
                elif "cashapp" in method_id:
                    emoji_name = "CASHAPP"
                elif "applepay" in method_id:
                    emoji_name = "APPLEPAY"
                elif "venmo" in method_id:
                    emoji_name = "VENMO"
                elif "zelle" in method_id:
                    emoji_name = "ZELLE"
                elif "chime" in method_id:
                    emoji_name = "CHIME"
                elif "revolut" in method_id:
                    emoji_name = "REVOLUT"
                elif "skrill" in method_id:
                    emoji_name = "SKRIL"
                elif "bank" in method_id:
                    emoji_name = "BANK"
                elif "paysafe" in method_id:
                    emoji_name = "PAYSAFE"
                elif "binance" in method_id:
                    emoji_name = "BINANCE"

                if emoji_name:
                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                    if custom_emoji:
                        emoji = custom_emoji  # Use custom emoji OBJECT

            options.append(
                discord.SelectOption(
                    label=method.name,
                    value=method_id,
                    emoji=emoji,
                    description=f"Receive via {method.name}"
                )
            )

        super().__init__(
            placeholder="Select your receiving payment method...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle receive method selection"""
        try:
            selected_method_id = self.values[0]
            selected_method = RECEIVE_PAYMENT_METHODS[selected_method_id]

            user_id, roles = get_user_context(interaction)

            view: ReceiveMethodSelector = self.view
            session_manager = view.session_manager
            api = view.api
            bot = view.bot

            # Get current session to check send method
            session = session_manager.get_session(user_id)

            # Validation: Can't send and receive with same method
            if session and session.send_method == selected_method_id:
                # Check if both are crypto with different assets
                if selected_method.is_crypto and session.send_crypto:
                    # This is allowed - crypto to crypto (different assets)
                    pass
                else:
                    # Defer for error message
                    await interaction.response.defer(ephemeral=True)
                    embed = create_themed_embed(
                        title="Invalid Selection",
                        description="You cannot send and receive using the same payment method.\n\nPlease select a different receiving method.",
                        color=PURPLE_GRADIENT
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

            # Update session
            session_manager.set_receive_method(user_id, selected_method_id, None)

            # If crypto selected, ask which crypto asset
            if selected_method.requires_crypto_selection:
                # Defer for embed/view
                await interaction.response.defer(ephemeral=True)
                embed = create_themed_embed(
                    title="Select Cryptocurrency",
                    description="Which cryptocurrency would you like to receive?",
                    color=PURPLE_GRADIENT
                )
                view_next = CryptoAssetSelector(session_manager, api, selection_type="receive", bot=bot)
                await interaction.followup.send(embed=embed, view=view_next, ephemeral=True)
            else:
                # Directly open amount modal (no button, no embed clutter)
                modal = AmountInputModal(session_manager, api)
                await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in ReceiveMethodSelector: {e}", exc_info=True)

            # Check if we already responded
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            embed = create_themed_embed(
                title="Error",
                description="An error occurred. Please try again.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class AmountInputModal(discord.ui.Modal):
    """
    Modal for entering exchange amount
    """

    def __init__(self, session_manager: ExchangeSessionManager, api: APIClient):
        super().__init__(title="Enter Exchange Amount")
        self.session_manager = session_manager
        self.api = api

        self.amount_input = discord.ui.InputText(
            label="Amount (USD)",
            placeholder="Enter amount in USD (e.g., 100.00)",
            style=discord.InputTextStyle.short,
            required=True,
            min_length=1,
            max_length=20
        )
        self.add_item(self.amount_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle amount submission"""
        try:
            await interaction.response.defer(ephemeral=True)

            amount_str = self.amount_input.value.strip().replace("$", "").replace(",", "")

            # Parse amount
            try:
                amount_usd = float(amount_str)
            except ValueError:
                embed = create_themed_embed(
                    title="Invalid Amount",
                    description="Please enter a valid number.\n\nExample: `100` or `100.50`",
                    color=ERROR_RED
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Validate amount
            is_valid, error_msg = validate_amount(amount_usd)
            if not is_valid:
                embed = create_themed_embed(
                    title="Invalid Amount",
                    description=error_msg,
                    color=ERROR_RED
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            user_id, roles = get_user_context(interaction)

            # Update session
            session = self.session_manager.set_amount(user_id, amount_usd)

            # Get session to calculate fees - use correct dictionaries
            send_method = SEND_PAYMENT_METHODS[session.send_method]
            receive_method = RECEIVE_PAYMENT_METHODS[session.receive_method]

            # Calculate fee
            fee_amount, fee_percentage, receiving_amount = calculate_fee(
                amount_usd,
                session.send_method,
                session.receive_method
            )

            # Build confirmation embed
            embed = create_themed_embed(
                title="Confirm Exchange",
                description="Please review your exchange details:",
                color=PURPLE_GRADIENT
            )

            # Get bot instance for custom emojis from interaction
            bot = interaction.client
            guild = bot.get_guild(config.guild_id) if bot else None

            # Send method info with custom emoji
            send_emoji = send_method.emoji  # Default fallback
            if guild:
                emoji_name = None
                if session.send_method == "crypto":
                    emoji_name = "CRYPTO"
                elif "paypal" in session.send_method:
                    emoji_name = "PAYPAL"
                elif "cashapp" in session.send_method:
                    emoji_name = "CASHAPP"
                elif "applepay" in session.send_method:
                    emoji_name = "APPLEPAY"
                elif "venmo" in session.send_method:
                    emoji_name = "VENMO"
                elif "zelle" in session.send_method:
                    emoji_name = "ZELLE"
                elif "chime" in session.send_method:
                    emoji_name = "CHIME"
                elif "revolut" in session.send_method:
                    emoji_name = "REVOLUT"
                elif "skrill" in session.send_method:
                    emoji_name = "SKRIL"
                elif "bank" in session.send_method:
                    emoji_name = "BANK"
                elif "paysafe" in session.send_method:
                    emoji_name = "PAYSAFE"
                elif "binance" in session.send_method:
                    emoji_name = "BINANCE"

                if emoji_name:
                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                    if custom_emoji:
                        send_emoji = custom_emoji

            send_display = f"{send_emoji} {send_method.name}"
            if session.send_crypto:
                crypto_asset = CRYPTO_ASSETS[session.send_crypto]
                # Get custom emoji for crypto asset
                crypto_emoji = crypto_asset.emoji  # Default fallback
                if guild and hasattr(config, 'emoji_names') and session.send_crypto in config.emoji_names:
                    emoji_name = config.emoji_names[session.send_crypto]
                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                    if custom_emoji:
                        crypto_emoji = custom_emoji
                send_display += f" ({crypto_emoji} {crypto_asset.name})"

            # Receive method info with custom emoji
            receive_emoji = receive_method.emoji  # Default fallback
            if guild:
                emoji_name = None
                if session.receive_method == "crypto":
                    emoji_name = "CRYPTO"
                elif "paypal" in session.receive_method:
                    emoji_name = "PAYPAL"
                elif "cashapp" in session.receive_method:
                    emoji_name = "CASHAPP"
                elif "applepay" in session.receive_method:
                    emoji_name = "APPLEPAY"
                elif "venmo" in session.receive_method:
                    emoji_name = "VENMO"
                elif "zelle" in session.receive_method:
                    emoji_name = "ZELLE"
                elif "chime" in session.receive_method:
                    emoji_name = "CHIME"
                elif "revolut" in session.receive_method:
                    emoji_name = "REVOLUT"
                elif "skrill" in session.receive_method:
                    emoji_name = "SKRIL"
                elif "bank" in session.receive_method:
                    emoji_name = "BANK"
                elif "paysafe" in session.receive_method:
                    emoji_name = "PAYSAFE"
                elif "binance" in session.receive_method:
                    emoji_name = "BINANCE"

                if emoji_name:
                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                    if custom_emoji:
                        receive_emoji = custom_emoji

            receive_display = f"{receive_emoji} {receive_method.name}"
            if session.receive_crypto:
                crypto_asset = CRYPTO_ASSETS[session.receive_crypto]
                # Get custom emoji for crypto asset
                crypto_emoji = crypto_asset.emoji  # Default fallback
                if guild and hasattr(config, 'emoji_names') and session.receive_crypto in config.emoji_names:
                    emoji_name = config.emoji_names[session.receive_crypto]
                    custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
                    if custom_emoji:
                        crypto_emoji = custom_emoji
                receive_display += f" ({crypto_emoji} {crypto_asset.name})"

            embed.add_field(
                name="Sending",
                value=send_display,
                inline=True
            )

            embed.add_field(
                name="Receiving",
                value=receive_display,
                inline=True
            )

            embed.add_field(
                name="\u200b",  # Empty field for line break
                value="\u200b",
                inline=False
            )

            embed.add_field(
                name="Amount",
                value=f"${amount_usd:,.2f}",
                inline=True
            )

            # Smart fee display: show "minimum fee" for <$40, percentage for >=$40
            if send_method.is_crypto and receive_method.is_crypto:
                # Crypto-to-crypto: show 5%
                fee_display = f"${fee_amount:,.2f} ({fee_percentage:.1f}%)"
            elif amount_usd >= 40.0:
                # Standard fee: show 10%
                fee_display = f"${fee_amount:,.2f} ({fee_percentage:.1f}%)"
            else:
                # Minimum fee: show "minimum fee" instead of confusing percentage
                fee_display = f"${fee_amount:,.2f} (minimum fee)"

            embed.add_field(
                name="Fee",
                value=fee_display,
                inline=True
            )

            embed.add_field(
                name="You Receive",
                value=f"**${receiving_amount:,.2f}**",
                inline=True
            )

            embed.set_footer(text="Click Confirm to create your exchange ticket")

            # Show confirmation view
            view = ConfirmationView(self.session_manager, self.api)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in AmountInputModal: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description="An error occurred. Please try again.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class ConfirmationView(discord.ui.View):
    """
    Step 4: Confirm exchange details
    Final confirmation before creating ticket
    """

    def __init__(
        self,
        session_manager: ExchangeSessionManager,
        api: APIClient,
        timeout: float = 600  # 10 minutes - longer timeout to prevent interaction failures
    ):
        super().__init__(timeout=timeout)
        self.session_manager = session_manager
        self.api = api

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary, emoji="✅")
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Confirm and create ticket"""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id, roles = get_user_context(interaction)

            # Get session
            session = self.session_manager.get_session(user_id)
            if not session or not session.is_complete():
                embed = create_themed_embed(
                    title="Session Expired",
                    description="Your session has expired. Please start over.",
                    color=ERROR_RED
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Calculate fee
            fee_amount, fee_percentage, receiving_amount = calculate_fee(
                session.amount_usd,
                session.send_method,
                session.receive_method
            )

            # Create ticket via API
            ticket_data = await self.api.create_exchange_ticket(
                user_id=user_id,
                username=interaction.user.name,
                send_method=session.send_method,
                receive_method=session.receive_method,
                amount_usd=session.amount_usd,
                fee_amount=fee_amount,
                fee_percentage=fee_percentage,
                receiving_amount=receiving_amount,
                send_crypto=session.send_crypto,
                receive_crypto=session.receive_crypto
            )

            # Clear session
            self.session_manager.clear_session(user_id)

            # Create Discord ticket CHANNEL (V4 channel-based system for true privacy)
            guild = interaction.guild
            ticket_number = ticket_data.get("ticket_number")
            ticket_id = ticket_data.get("ticket_id")

            # Get tickets category
            tickets_category = guild.get_channel(config.TICKETS_CATEGORY_ID)
            if not tickets_category:
                logger.error(f"Tickets category not found: {config.TICKETS_CATEGORY_ID}")
                raise ValueError("Tickets category not configured")

            # Get payment method details for channel topic and TOS
            send_method = get_payment_method(session.send_method)
            receive_method = get_payment_method(session.receive_method)

            # Create permission overwrites for true privacy
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True
                )
            }

            # Add admin roles to channel
            head_admin_role = guild.get_role(config.head_admin_role)
            if head_admin_role:
                overwrites[head_admin_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True
                )

            assistant_admin_role = guild.get_role(config.assistant_admin_role)
            if assistant_admin_role:
                overwrites[assistant_admin_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    embed_links=True
                )

            # Create client channel with proper permissions (anonymous - no username)
            channel_name = f"ticket-{ticket_number}"
            channel = await guild.create_text_channel(
                name=channel_name,
                category=tickets_category,
                overwrites=overwrites,
                topic=f"Exchange Ticket #{ticket_number} | {send_method.name} → {receive_method.name} | ${session.amount_usd:.2f}",
                reason=f"Exchange ticket #{ticket_number}"
            )

            logger.info(f"Created client channel {channel.id} for ticket #{ticket_number}")

            # Update ticket with channel_id in database
            try:
                await self.api.patch(
                    f"/api/v1/tickets/{ticket_id}",
                    data={
                        "channel_id": str(channel.id),
                        "category_id": str(config.TICKETS_CATEGORY_ID)
                    }
                )
                logger.info(f"Updated ticket {ticket_id} with client channel {channel.id}")
            except Exception as api_error:
                logger.error(f"Failed to update ticket with channel_id: {api_error}", exc_info=True)
                # Don't fail the entire flow if this update fails

            # Build display names with crypto asset if applicable (already got send_method and receive_method above)
            send_method_name = send_method.name
            if send_method.is_crypto and session.send_crypto:
                # Get crypto asset details
                crypto_asset = CRYPTO_ASSETS.get(session.send_crypto)
                if crypto_asset:
                    send_method_name = f"{crypto_asset.name} ({session.send_crypto})"

            receive_method_name = receive_method.name
            if receive_method.is_crypto and session.receive_crypto:
                # Get crypto asset details
                crypto_asset = CRYPTO_ASSETS.get(session.receive_crypto)
                if crypto_asset:
                    receive_method_name = f"{crypto_asset.name} ({session.receive_crypto})"

            # Create TOS embed (V3 style) - pass all required parameters
            tos_embed = create_tos_embed(
                send_method_name=send_method_name,
                receive_method_name=receive_method_name,
                send_tos_key=send_method.tos_key,
                receive_tos_key=receive_method.tos_key,
                ticket_number=ticket_number,
                amount_usd=session.amount_usd,
                fee_amount=fee_amount,
                fee_percentage=fee_percentage,
                receiving_amount=receiving_amount,
                customer=interaction.user
            )

            # Create TOS view with channel and user for reminders
            tos_view = TOSView(
                ticket_id=ticket_id,
                ticket_number=ticket_number,
                api=self.api,
                channel=channel,  # Pass channel object
                user=interaction.user
            )

            # Send TOS message in ticket channel
            tos_message = await channel.send(
                content=f"{interaction.user.mention} **Please read and accept the Terms of Service:**",
                embed=tos_embed,
                view=tos_view
            )

            # Store message reference and start reminder task
            tos_view.message = tos_message
            await tos_view.start_reminder_task()

            # DM the client with ticket information
            try:
                dm_embed = create_themed_embed(
                    title="🎫 Your Exchange Ticket Has Been Created!",
                    description=(
                        f"## Ticket #{ticket_number}\n\n"
                        f"Your exchange ticket has been successfully created and is waiting for your acceptance.\n\n"
                        f"**Exchange Details:**\n"
                        f"• Sending: {send_method_name}\n"
                        f"• Receiving: {receive_method_name}\n"
                        f"• Amount: ${session.amount_usd:.2f} USD\n"
                        f"• Fee: ${fee_amount:.2f} ({fee_percentage}%)\n"
                        f"• You'll Receive: ${receiving_amount:.2f}\n\n"
                        f"**Next Steps:**\n"
                        f"1. Go to your ticket channel: {channel.mention}\n"
                        f"2. Read the Terms of Service carefully\n"
                        f"3. Click **Accept Terms** to proceed\n\n"
                        f"⏱️ You have **10 minutes** to accept the TOS, or your ticket will be automatically closed."
                    ),
                    color=PURPLE_GRADIENT
                )

                # Add direct channel link button
                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Go to Your Ticket",
                    style=discord.ButtonStyle.link,
                    url=channel.jump_url,
                    emoji="🎫"
                ))

                await interaction.user.send(embed=dm_embed, view=view)
                logger.info(f"Sent DM to user {interaction.user.id} for ticket #{ticket_number}")
            except discord.Forbidden:
                logger.warning(f"Could not DM user {interaction.user.id} - DMs disabled")
            except Exception as dm_error:
                logger.error(f"Error sending DM to user {interaction.user.id}: {dm_error}")

            # Success message
            embed = create_themed_embed(
                title="Ticket Created!",
                description=f"Your exchange ticket has been created successfully.\n\n**Please check {channel.mention} and accept the Terms of Service within 10 minutes.**\n\n*A DM with ticket details has been sent to you.*",
                color=SUCCESS_GREEN
            )

            embed.add_field(
                name="Ticket Number",
                value=f"#{ticket_number}",
                inline=True
            )

            embed.add_field(
                name="Ticket Channel",
                value=channel.mention,
                inline=True
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Disable buttons (try to edit if possible, but don't fail if message is gone)
            try:
                for item in self.children:
                    item.disabled = True
                await interaction.message.edit(view=self)
            except discord.errors.NotFound:
                # Message already deleted or ephemeral message expired
                pass
            except Exception as edit_error:
                logger.warning(f"Could not disable buttons: {edit_error}")

        except Exception as e:
            logger.error(f"Error confirming exchange: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error Creating Ticket",
                description="An error occurred while creating your ticket. Please contact support.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Cancel exchange creation"""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id, roles = get_user_context(interaction)

            # Clear session
            self.session_manager.clear_session(user_id)

            embed = create_themed_embed(
                title="Exchange Cancelled",
                description="Your exchange has been cancelled.\n\nClick the **Start Exchange** button to create a new exchange.",
                color=PURPLE_GRADIENT
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Disable buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            logger.error(f"Error cancelling exchange: {e}", exc_info=True)
