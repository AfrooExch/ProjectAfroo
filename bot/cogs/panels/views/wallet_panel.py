"""
Wallet Panel View - V4 Crypto Wallet Management
Complete rewrite to use V4 Crypto Wallet API
"""

import discord
import logging
import io
import qrcode
from decimal import Decimal

from utils.view_manager import PersistentView
from utils.embeds import create_embed, error_embed, get_color
from utils.formatting import format_crypto
from api.errors import APIError, NotFoundError

logger = logging.getLogger(__name__)


class CopyAddressView(discord.ui.View):
    """View with copy button for wallet address (mobile-friendly)"""

    def __init__(self, address: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.address = address

    @discord.ui.button(label="📋 Copy Address", style=discord.ButtonStyle.primary)
    async def copy_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Button to copy wallet address"""
        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description=(
                    f"## 📋 Address Copied!\n\n"
                    f"**Wallet Address:**\n"
                    f"```\n{self.address}\n```\n\n"
                    f"> ✅ Tap and hold to select, then copy\n"
                    f"> 📱 Perfect for mobile users!"
                ),
                color=get_color("success")
            ),
            ephemeral=True
        )


# All 14 supported cryptocurrencies
SUPPORTED_CURRENCIES = [
    "BTC", "LTC", "ETH", "SOL",
    "USDC-SOL", "USDC-ETH",
    "USDT-SOL", "USDT-ETH",
    "XRP", "BNB", "TRX",
    "MATIC", "AVAX", "DOGE"
]

CURRENCY_NAMES = {
    "BTC": "Bitcoin",
    "LTC": "Litecoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "USDC-SOL": "USD Coin (Solana)",
    "USDC-ETH": "USD Coin (Ethereum)",
    "USDT-SOL": "Tether (Solana)",
    "USDT-ETH": "Tether (Ethereum)",
    "XRP": "Ripple",
    "BNB": "Binance Coin",
    "TRX": "Tron",
    "MATIC": "Polygon",
    "AVAX": "Avalanche",
    "DOGE": "Dogecoin"
}

# Fallback unicode emojis for dropdowns (Discord select doesn't support custom emojis)
CURRENCY_EMOJIS = {
    "BTC": "🔶",
    "LTC": "⚪",
    "ETH": "🔷",
    "SOL": "🟣",
    "USDC-SOL": "🔵",
    "USDC-ETH": "🔵",
    "USDT-SOL": "🟢",
    "USDT-ETH": "🟢",
    "XRP": "💙",
    "BNB": "💛",
    "TRX": "🔴",
    "MATIC": "🟣",
    "AVAX": "🔴",
    "DOGE": "🐶"
}

# Mapping for server emojis (matches your Discord server emoji names)
CURRENCY_EMOJI_NAMES = {
    "BTC": "BITCOIN",
    "LTC": "LTC",
    "ETH": "ETH",
    "SOL": "SOL",
    "USDC-SOL": "USDC",
    "USDC-ETH": "USDC",
    "USDT-SOL": "USDT",
    "USDT-ETH": "USDT",
    "XRP": "XRP",
    "BNB": "BINANCE",
    "TRX": "TRX",
    "MATIC": "MATIC",
    "AVAX": "AVAX",
    "DOGE": "DOGE"
}

def get_crypto_emoji(bot, currency: str) -> str:
    """Get server emoji for cryptocurrency in embeds, or fallback to unicode"""
    from config import config
    emoji_name = CURRENCY_EMOJI_NAMES.get(currency)
    if emoji_name and bot:
        try:
            emoji = config.get_emoji(bot, emoji_name)
            if emoji and emoji != "❓":
                return emoji  # Return custom server emoji
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
    # Fallback to unicode if custom emoji not found
    return CURRENCY_EMOJIS.get(currency, "💰")


class WalletPanelView(PersistentView):
    """V4 Crypto Wallet panel with dropdown menu"""

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)
        self.add_item(WalletActionsDropdown(bot))


class WalletActionsDropdown(discord.ui.Select):
    """Dropdown for wallet actions"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot

        options = [
            discord.SelectOption(
                label="My Balances",
                value="balances",
                description="View all your crypto balances"
            ),
            discord.SelectOption(
                label="Refresh All",
                value="refresh",
                description="Refresh all wallet balances with latest on-chain data"
            ),
            discord.SelectOption(
                label="Deposit",
                value="deposit",
                description="Get deposit address for any crypto"
            ),
            discord.SelectOption(
                label="Withdraw",
                value="withdraw",
                description="Send crypto to external wallet"
            ),
            discord.SelectOption(
                label="Transaction History",
                value="history",
                description="View your transaction history"
            ),
        ]

        super().__init__(
            placeholder="Choose an action...",
            options=options,
            custom_id="wallet_actions_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection"""
        action = self.values[0]

        try:
            if action == "balances":
                await self.show_balances(interaction)
            elif action == "refresh":
                await self.refresh_all_balances(interaction)
            elif action == "deposit":
                await self.show_deposit_options(interaction)
            elif action == "withdraw":
                await self.show_withdraw_options(interaction)
            elif action == "history":
                await self.show_history_options(interaction)

        except Exception as e:
            logger.error(f"Error in wallet dropdown: {e}", exc_info=True)
            await interaction.response.send_message(
                embed=error_embed(
                    description=(
                        "❌ Something went wrong while processing your request.\n\n"
                        "**What to do:**\n"
                        "> • Try selecting the action again\n"
                        "> • If the problem persists, contact support"
                    )
                ),
                ephemeral=True
            )

    async def show_balances(self, interaction: discord.Interaction):
        """Show user's wallet balances from V4 portfolio"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            # Get current portfolio (before sync)
            portfolio_before = await api.v4_get_portfolio(user_id)
            old_balances = {
                b["currency"]: b.get("available", "0")
                for b in portfolio_before.get("balances", [])
            }

            # Sync all wallet balances with blockchain
            balance_changes = []
            for balance in portfolio_before.get("balances", []):
                currency = balance["currency"]
                try:
                    # Sync each wallet with blockchain
                    await api.v4_sync_wallet(user_id, currency)
                except Exception as sync_err:
                    logger.warning(f"Failed to sync {currency} for {user_id}: {sync_err}")

            # Get updated portfolio (after sync)
            portfolio = await api.v4_get_portfolio(user_id)
            balances = portfolio.get("balances", [])

            # Check for balance changes
            for balance in balances:
                currency = balance["currency"]
                new_amount = balance.get("available", "0")
                old_amount = old_balances.get(currency, "0")

                if new_amount != old_amount:
                    balance_changes.append({
                        "currency": currency,
                        "old": old_amount,
                        "new": new_amount
                    })

            # Send DM if there were balance changes
            if balance_changes:
                try:
                    await self._send_balance_change_dm(interaction.user, balance_changes)
                except Exception as dm_err:
                    logger.error(f"Failed to send balance change DM: {dm_err}")

            if not balances:
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            "## 💳 Your Wallets\n\n"
                            "> You don't have any wallet balances yet.\n"
                            "> Use the **Deposit** option to create a wallet!"
                        ),
                        color=get_color("primary")  # V3 Purple 0x9B59B6
                    ),
                    ephemeral=True
                )
                return

            # Build balances description
            description = "## 💳 Your Crypto Portfolio\n\n"

            # Show refresh notice if balances changed
            if balance_changes:
                description += "> Balance updated! Check DM for details.\n\n"

            for balance in balances:
                currency = balance["currency"]
                emoji = get_crypto_emoji(self.bot, currency)
                name = CURRENCY_NAMES.get(currency, currency)

                available = balance.get("available", "0")
                locked = balance.get("locked", "0")
                pending = balance.get("pending", "0")
                usd_value = balance.get("usd_value")

                description += f"{emoji} **{name}** ({currency})\n"
                description += f"```\n"
                description += f"Available: {available}"
                if usd_value:
                    description += f" (${usd_value} USD)"
                description += f"\n"

                if locked != "0":
                    description += f"Locked:    {locked}\n"
                if pending != "0":
                    description += f"Pending:   {pending}\n"

                description += f"```\n"

                # Add activation warnings for XRP/TRX/DOGE if balance is 0
                if available == "0" or available == "0.0":
                    if currency == "XRP":
                        description += f"> ⚠️ **XRP requires 10 XRP minimum** to activate address\n\n"
                    elif currency == "TRX":
                        description += f"> ⚠️ **TRX requires ~1 TRX** to activate address\n\n"
                    elif currency == "DOGE":
                        description += f"> ⚠️ **DOGE address not yet activated**\n\n"

            embed = create_embed(
                title="",
                description=description,
                color=get_color("primary")
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"Portfolio API error: {e}")
            await interaction.followup.send(
                embed=error_embed(description=f"❌ {e.user_message}"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Portfolio error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to load your wallet balances right now.\n\n"
                        "**What to do:**\n"
                        "> • Wait a moment and try again\n"
                        "> • Check if the bot is online\n"
                        "> • Contact support if this keeps happening"
                    )
                ),
                ephemeral=True
            )

    async def _send_balance_change_dm(self, user: discord.User, changes: list):
        """Send DM to user about balance changes"""
        try:
            description = "## Crypto Wallet Management\n\n"

            for change in changes:
                currency = change["currency"]
                old_val = change["old"]
                new_val = change["new"]
                emoji = get_crypto_emoji(self.bot, currency)
                name = CURRENCY_NAMES.get(currency, currency)

                # Calculate difference
                try:
                    old_float = float(old_val) if old_val != "0" else 0
                    new_float = float(new_val) if new_val != "0" else 0
                    diff = new_float - old_float
                    diff_str = f"+{diff}" if diff > 0 else str(diff)
                except Exception as e:
                    diff_str = "?"

                description += f"{emoji} **{name}** ({currency})\n"
                description += f"```\n"
                description += f"Old: {old_val}\n"
                description += f"New: {new_val}\n"
                description += f"Change: {diff_str}\n"
                description += f"```\n"

            embed = create_embed(
                title="",
                description=description,
                color=get_color("primary")
            )

            await user.send(embed=embed)
            logger.info(f"Sent balance change DM to {user.id} ({len(changes)} changes)")

        except discord.Forbidden:
            logger.warning(f"Cannot send DM to user {user.id} (DMs disabled)")
        except Exception as e:
            logger.error(f"Error sending balance change DM: {e}", exc_info=True)
            raise

    async def refresh_all_balances(self, interaction: discord.Interaction):
        """Refresh all wallet balances with latest on-chain data"""
        await interaction.response.defer(ephemeral=True)

        try:
            api = self.bot.api_client
            user_id = str(interaction.user.id)

            # Get current portfolio
            portfolio_before = await api.v4_get_portfolio(user_id)
            balances_before = {
                b["currency"]: b.get("available", "0")
                for b in portfolio_before.get("balances", [])
            }

            if not balances_before:
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            "## Crypto Wallet Management\n\n"
                            "> You don't have any wallets yet\n"
                            "> Use the **Deposit** option to create a wallet"
                        ),
                        color=get_color("primary")
                    ),
                    ephemeral=True
                )
                return

            # Sync all wallets with blockchain
            total_wallets = len(balances_before)
            synced_count = 0
            failed_currencies = []

            # Show progress message
            await interaction.followup.send(
                embed=create_embed(
                    title="",
                    description=f"## Crypto Wallet Management\n\n> Syncing {total_wallets} wallet(s) with blockchain...",
                    color=get_color("primary")
                ),
                ephemeral=True
            )

            for currency in balances_before.keys():
                try:
                    await api.v4_sync_wallet(user_id, currency)
                    synced_count += 1
                except Exception as sync_err:
                    logger.warning(f"Failed to sync {currency} for {user_id}: {sync_err}")
                    failed_currencies.append(currency)

            # Get updated portfolio
            portfolio_after = await api.v4_get_portfolio(user_id)
            balances_after = {
                b["currency"]: b.get("available", "0")
                for b in portfolio_after.get("balances", [])
            }

            # Check for changes
            balance_changes = []
            for currency, new_amount in balances_after.items():
                old_amount = balances_before.get(currency, "0")
                if new_amount != old_amount:
                    balance_changes.append({
                        "currency": currency,
                        "old": old_amount,
                        "new": new_amount
                    })

            # Build result message
            description = "## Crypto Wallet Management\n\n"
            description += f"**Synced:** {synced_count}/{total_wallets} wallet(s)\n\n"

            if balance_changes:
                description += "**Balance Changes:**\n"
                for change in balance_changes:
                    currency = change["currency"]
                    emoji = get_crypto_emoji(self.bot, currency)
                    name = CURRENCY_NAMES.get(currency, currency)

                    try:
                        old_float = float(change["old"]) if change["old"] != "0" else 0
                        new_float = float(change["new"]) if change["new"] != "0" else 0
                        diff = new_float - old_float
                        diff_str = f"+{diff:.8f}" if diff > 0 else f"{diff:.8f}"
                    except Exception as e:
                        diff_str = "?"

                    description += f"{emoji} **{name}**: `{diff_str}` {currency}\n"

                # Send DM with changes
                try:
                    await self._send_balance_change_dm(interaction.user, balance_changes)
                except Exception as dm_err:
                    logger.error(f"Failed to send refresh DM: {dm_err}")
            else:
                description += "> No balance changes detected"

            if failed_currencies:
                description += f"\n\n> Failed to sync: {', '.join(failed_currencies)}"

            embed = create_embed(
                title="",
                description=description,
                color=get_color("primary")
            )

            # Send final results as new message
            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"Refresh API error: {e}")
            await interaction.followup.send(
                embed=error_embed(description=f"❌ {e.user_message}"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Refresh error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to refresh wallet balances right now.\n\n"
                        "**What to do:**\n"
                        "> • Wait a moment and try again\n"
                        "> • Check if the bot is online\n"
                        "> • Contact support if this keeps happening"
                    )
                ),
                ephemeral=True
            )

    async def show_deposit_options(self, interaction: discord.Interaction):
        """Show crypto selection for deposit (auto-generates wallet)"""
        view = CryptoSelectorView(self.bot, mode="deposit")

        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description=(
                    "## Select Cryptocurrency\n\n"
                    "Choose which crypto you want to deposit.\n"
                    "Your wallet will be generated automatically if you don't have one."
                ),
                color=get_color("primary")
            ),
            view=view,
            ephemeral=True
        )

    async def show_withdraw_options(self, interaction: discord.Interaction):
        """Show crypto selection for withdrawal"""
        view = CryptoSelectorView(self.bot, mode="withdraw")

        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description="## Select Cryptocurrency\n\nChoose which crypto you want to withdraw:",
                color=get_color("primary")
            ),
            view=view,
            ephemeral=True
        )

    async def show_history_options(self, interaction: discord.Interaction):
        """Show crypto selection for transaction history"""
        view = CryptoSelectorView(self.bot, mode="history")

        await interaction.response.send_message(
            embed=create_embed(
                title="",
                description="## Select Cryptocurrency\n\nChoose which crypto's history you want to view:",
                color=get_color("primary")
            ),
            view=view,
            ephemeral=True
        )


class CryptoSelectorView(discord.ui.View):
    """View for selecting cryptocurrency (chunked for Discord 25 option limit)"""

    def __init__(self, bot: discord.Bot, mode: str):
        super().__init__()
        self.bot = bot
        self.mode = mode  # "deposit", "withdraw", or "history"

        # Split currencies into chunks of 12 each (Discord allows max 25 per select)
        chunk_1 = SUPPORTED_CURRENCIES[:12]  # BTC, LTC, ETH, SOL, USDC-SOL, USDC-ETH, USDT-SOL, USDT-ETH, XRP, BNB, TRX, MATIC
        chunk_2 = SUPPORTED_CURRENCIES[12:]  # AVAX, DOGE

        # Get guild to fetch custom emojis
        from config import config
        guild = bot.get_guild(config.guild_id) if bot else None

        # First dropdown - use custom server emojis
        options_1 = []
        for currency in chunk_1:
            emoji_name = CURRENCY_EMOJI_NAMES.get(currency)
            emoji = None

            # Try to get custom server emoji
            if guild and emoji_name:
                emoji = discord.utils.get(guild.emojis, name=emoji_name)

            # Fallback to unicode if custom emoji not found
            if not emoji:
                emoji = CURRENCY_EMOJIS.get(currency, "💰")

            options_1.append(discord.SelectOption(
                label=f"{CURRENCY_NAMES.get(currency, currency)} ({currency})",
                value=currency,
                emoji=emoji
            ))

        select_1 = discord.ui.Select(
            placeholder="Popular cryptos...",
            options=options_1
        )
        select_1.callback = lambda i: self.currency_selected(i, select_1)
        self.add_item(select_1)

        # Second dropdown if needed
        if chunk_2:
            options_2 = []
            for currency in chunk_2:
                emoji_name = CURRENCY_EMOJI_NAMES.get(currency)
                emoji = None

                # Try to get custom server emoji
                if guild and emoji_name:
                    emoji = discord.utils.get(guild.emojis, name=emoji_name)

                # Fallback to unicode if custom emoji not found
                if not emoji:
                    emoji = CURRENCY_EMOJIS.get(currency, "💰")

                options_2.append(discord.SelectOption(
                    label=f"{CURRENCY_NAMES.get(currency, currency)} ({currency})",
                    value=currency,
                    emoji=emoji
                ))

            select_2 = discord.ui.Select(
                placeholder="More cryptos...",
                options=options_2
            )
            select_2.callback = lambda i: self.currency_selected(i, select_2)
            self.add_item(select_2)

    async def currency_selected(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle currency selection"""
        currency = select.values[0]
        user_id = str(interaction.user.id)
        api = self.bot.api_client

        try:
            if self.mode == "deposit":
                await interaction.response.defer(ephemeral=True)
                await self.handle_deposit(interaction, api, user_id, currency)
            elif self.mode == "withdraw":
                # Don't defer for withdraw - we need to send modal immediately
                await self.handle_withdraw(interaction, api, user_id, currency)
            elif self.mode == "history":
                await interaction.response.defer(ephemeral=True)
                await self.handle_history(interaction, api, user_id, currency)

        except Exception as e:
            logger.error(f"Currency selection error: {e}", exc_info=True)
            # Try to send error message - use response if not responded, otherwise followup
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=error_embed(
                            description=(
                                "❌ Unable to process your cryptocurrency selection.\n\n"
                                "**What to do:**\n"
                                "> • Try selecting the crypto again\n"
                                "> • Make sure the bot has proper permissions\n"
                                "> • Contact support if the issue continues"
                            )
                        ),
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        embed=error_embed(
                            description=(
                                "❌ Unable to process your cryptocurrency selection.\n\n"
                                "**What to do:**\n"
                                "> • Try selecting the crypto again\n"
                                "> • Make sure the bot has proper permissions\n"
                                "> • Contact support if the issue continues"
                            )
                        ),
                        ephemeral=True
                    )
            except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)  # Failed to send error message

    async def handle_deposit(self, interaction, api, user_id, currency):
        """Handle deposit - get or generate wallet"""
        try:
            # Try to get existing wallet
            wallet = await api.v4_get_wallet(user_id, currency)
        except NotFoundError:
            # Wallet doesn't exist, generate it
            try:
                wallet = await api.v4_generate_wallet(user_id, currency)
            except Exception as gen_error:
                logger.error(f"Failed to generate wallet: {gen_error}")
                await interaction.followup.send(
                    embed=error_embed(
                        description=(
                            f"❌ Unable to create your {currency} wallet.\n\n"
                            f"**What to do:**\n"
                            f"> • The blockchain service may be temporarily unavailable\n"
                            f"> • Wait a few minutes and try again\n"
                            f"> • Contact support if this error persists"
                        )
                    ),
                    ephemeral=True
                )
                return

        address = wallet.get("address")
        balance = wallet.get("balance", "0")

        # Generate QR code
        qr_file = self._generate_qr_code(address)

        name = CURRENCY_NAMES.get(currency, currency)
        emoji = get_crypto_emoji(self.bot, currency)

        embed = create_embed(
            title="",
            description=(
                f"## {emoji} {name} Deposit\n\n"
                f"**Deposit Address:**\n"
                f"```\n{address}\n```\n\n"
                f"**Current Balance:** `{balance} {currency}`\n\n"
                f"> Send {currency} to this address from any wallet\n"
                f"> Balance will update automatically after confirmations\n"
                f"> Only send {currency} to this address\n"
                f"> Sending other currencies will result in permanent loss"
            ),
            color=get_color("primary")
        )

        embed.set_image(url="attachment://qr.png")

        # Add copy button for mobile users
        view = CopyAddressView(address)

        await interaction.followup.send(
            embed=embed,
            file=qr_file,
            view=view,
            ephemeral=True
        )

    async def handle_withdraw(self, interaction, api, user_id, currency):
        """Handle withdraw - show modal"""
        try:
            # Sync wallet with blockchain first to get latest balance and prices
            try:
                await api.v4_sync_wallet(user_id, currency)
                logger.info(f"Synced {currency} wallet for {user_id} before withdrawal")
            except Exception as sync_err:
                logger.warning(f"Failed to sync {currency} before withdrawal for {user_id}: {sync_err}")
                # Continue anyway - we'll use cached balance

            # Check if wallet exists and get balance
            wallet = await api.v4_get_wallet(user_id, currency)

            if not wallet:
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            f"❌ You don't have a {currency} wallet yet.\n\n"
                            f"**What to do:**\n"
                            f"> • Use **Deposit** to create your {currency} wallet\n"
                            f"> • Then you can deposit funds and withdraw them"
                        )
                    ),
                    ephemeral=True
                )
                return

            balance = wallet.get("balance", "0")

            # Validate balance is a valid number
            try:
                balance_decimal = Decimal(balance)
            except Exception as e:
                logger.error(f"Invalid balance format for {user_id}/{currency}: {balance}")
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            "❌ Unable to read wallet balance.\n\n"
                            "**What to do:**\n"
                            "> • Try using **Refresh All** first\n"
                            "> • Contact support if this persists"
                        )
                    ),
                    ephemeral=True
                )
                return

            if balance_decimal <= 0:
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            f"❌ Your {currency} wallet is empty.\n\n"
                            f"**What to do:**\n"
                            f"> • Use **Deposit** to add {currency} to your wallet\n"
                            f"> • Check **My Balances** to see all your funds"
                        )
                    ),
                    ephemeral=True
                )
                return

            # Show withdraw modal
            modal = WithdrawModal(self.bot, currency, balance)
            await interaction.response.send_modal(modal)

        except APIError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            f"❌ You don't have a {currency} wallet yet.\n\n"
                            f"**What to do:**\n"
                            f"> • Use **Deposit** to create your {currency} wallet\n"
                            f"> • Then you can deposit funds and withdraw them"
                        )
                    ),
                    ephemeral=True
                )
            else:
                logger.error(f"Withdraw check error: {e}")
                await interaction.response.send_message(
                    embed=error_embed(
                        description=(
                            "❌ Unable to check your wallet status.\n\n"
                            "**What to do:**\n"
                            "> • The wallet service may be temporarily down\n"
                            "> • Try again in a few moments\n"
                            "> • Contact support if the problem continues"
                        )
                    ),
                    ephemeral=True
                )

    async def handle_history(self, interaction, api, user_id, currency):
        """Handle transaction history"""
        try:
            # Get transactions from V4 API
            result = await api.v4_get_transactions(user_id, currency, limit=10)
            transactions = result.get("transactions", [])

            if not transactions:
                await interaction.followup.send(
                    embed=create_embed(
                        title="",
                        description=(
                            f"## Crypto Wallet Management\n\n"
                            f"> No {currency} transactions yet"
                        ),
                        color=get_color("primary")
                    ),
                    ephemeral=True
                )
                return

            # Build history description
            name = CURRENCY_NAMES.get(currency, currency)
            emoji = get_crypto_emoji(self.bot, currency)

            description = f"## {emoji} {name} History\n\n"

            for tx in transactions[:10]:
                tx_type = tx.get("type", "unknown")
                amount = tx.get("amount", "0")
                usd_value = tx.get("usd_value")
                status = tx.get("status", "unknown")
                created = tx.get("created_at", "")[:10]  # Date only
                tx_id = tx.get("tx_id", "")[:8]
                network_fee = tx.get("network_fee")
                server_fee = tx.get("server_fee")
                to_address = tx.get("to_address")

                # Status indicator
                status_text = {
                    "pending": "Pending",
                    "confirming": "Confirming",
                    "confirmed": "Confirmed",
                    "failed": "Failed",
                    "cancelled": "Cancelled"
                }.get(status, "Unknown")

                # Build transaction display
                tx_info = f"**{tx_type.title()}** - {status_text}\n```\n"
                tx_info += f"Amount:  {amount} {currency}"
                if usd_value:
                    tx_info += f" (${usd_value} USD)"
                tx_info += f"\n"

                # Show fees for withdrawals
                if tx_type == "withdrawal":
                    if network_fee:
                        tx_info += f"Net Fee: {network_fee} {currency}\n"
                    if server_fee:
                        tx_info += f"Srv Fee: {server_fee} {currency}\n"
                    if to_address:
                        tx_info += f"To:      {to_address}\n"

                tx_info += f"ID:      {tx_id}\n"
                tx_info += f"Date:    {created}\n"
                tx_info += f"```\n"

                description += tx_info

            embed = create_embed(
                title="",
                description=description,
                color=get_color("primary")
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except APIError as e:
            logger.error(f"History error: {e}")
            await interaction.followup.send(
                embed=error_embed(
                    description=(
                        "❌ Unable to load your transaction history.\n\n"
                        "**What to do:**\n"
                        "> • Wait a moment and try again\n"
                        "> • Check if you have any transactions\n"
                        "> • Contact support if this error persists"
                    )
                ),
                ephemeral=True
            )

    def _generate_qr_code(self, data: str) -> discord.File:
        """Generate QR code image"""
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return discord.File(buffer, filename="qr.png")


class WithdrawModal(discord.ui.Modal):
    """Modal for withdrawal"""

    def __init__(self, bot: discord.Bot, currency: str, max_balance: str):
        super().__init__(title=f"Withdraw {currency}")
        self.bot = bot
        self.currency = currency
        self.max_balance = max_balance

        self.address_input = discord.ui.InputText(
            label="Destination Address",
            placeholder=f"Enter {currency} address...",
            required=True,
            max_length=200
        )

        self.amount_input = discord.ui.InputText(
            label="Amount (or type 'max')",
            placeholder=f"Type 'max' or amount. Balance: {max_balance} {currency}",
            required=True,
            max_length=50
        )

        self.add_item(self.address_input)
        self.add_item(self.amount_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle withdrawal submission"""
        await interaction.response.defer(ephemeral=True)

        to_address = self.address_input.value.strip()
        amount = self.amount_input.value.strip()
        user_id = str(interaction.user.id)
        api = self.bot.api_client

        # Check if user wants max withdrawal
        is_max = amount.lower() == "max"

        # Validate amount (skip for 'max')
        if not is_max:
            try:
                amount_float = float(amount)
                if amount_float <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError:
                await interaction.followup.send(
                    embed=error_embed(
                        description=(
                            "❌ Invalid withdrawal amount.\n\n"
                            "**What to do:**\n"
                            f"> • Enter a valid number (e.g., 0.5, 1.25) or 'max'\n"
                            f"> • Amount must be positive\n"
                            f"> • Available balance: {self.max_balance} {self.currency}"
                        )
                    ),
                    ephemeral=True
                )
                return

        try:
            # Preview withdrawal fees
            fee_info = await api.v4_withdraw_preview(user_id, self.currency, amount)

            # Get amounts from preview
            actual_amount = fee_info.get('amount', amount)
            is_max_response = fee_info.get('is_max', False)

            # Show confirmation
            name = CURRENCY_NAMES.get(self.currency, self.currency)

            # Build description with max indicator
            max_indicator = " (MAX)" if is_max_response else ""

            emoji = get_crypto_emoji(self.bot, self.currency)

            embed = create_embed(
                title="",
                description=(
                    f"## {emoji} Confirm {name} Withdrawal{max_indicator}\n\n"
                    f"**You Will Send:** `{actual_amount} {self.currency}`\n"
                    f"**To Address:** `{to_address[:20]}...`\n\n"
                    f"**Fee Breakdown:**\n"
                    f"```\n"
                    f"Network Fee: {fee_info.get('network_fee', '?')} {self.currency}\n"
                    f"Service Fee: {fee_info.get('server_fee', '?')} {self.currency} (0.4%)\n"
                    f"Total Cost:  {fee_info.get('total_deducted', '?')} {self.currency}\n"
                    f"```\n"
                    + (f"**Available Balance:** `{fee_info.get('available_balance', self.max_balance)} {self.currency}`\n\n" if is_max_response else "") +
                    f"> Double-check the address\n"
                    f"> Transactions cannot be reversed\n"
                    f"> Wrong address = permanent loss"
                ),
                color=get_color("primary")
            )

            view = WithdrawConfirmView(
                self.bot,
                self.currency,
                to_address,
                actual_amount,
                fee_info.get('network_fee'),
                fee_info.get('server_fee'),
                fee_info.get('total_deducted')
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except APIError as e:
            await interaction.followup.send(
                embed=error_embed(description=f"❌ {e.user_message}"),
                ephemeral=True
            )


class WithdrawConfirmView(discord.ui.View):
    """Confirmation view for withdrawal"""

    def __init__(self, bot: discord.Bot, currency: str, to_address: str, amount: str, network_fee: str = None, server_fee: str = None, total_deducted: str = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.currency = currency
        self.to_address = to_address
        self.amount = amount
        self.network_fee = network_fee
        self.server_fee = server_fee
        self.total_deducted = total_deducted

    @discord.ui.button(label="Confirm Withdrawal", style=discord.ButtonStyle.danger)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            user_id = str(interaction.user.id)
            api = self.bot.api_client

            # Execute withdrawal with precomputed fees if available
            result = await api.v4_withdraw(
                user_id,
                self.currency,
                self.to_address,
                self.amount,
                network_fee=self.network_fee,
                server_fee=self.server_fee,
                total_deducted=self.total_deducted
            )

            name = CURRENCY_NAMES.get(self.currency, self.currency)
            emoji = get_crypto_emoji(self.bot, self.currency)

            embed = create_embed(
                title="",
                description=(
                    f"## {emoji} {name} Withdrawal Initiated\n\n"
                    f"**Transaction ID:** `{result.get('tx_id', 'N/A')}`\n"
                    f"**Amount:** `{result.get('amount', self.amount)} {self.currency}`\n"
                    f"**Status:** Processing\n\n"
                    f"> Withdrawal has been broadcast to the blockchain\n"
                    f"> Balance will update once confirmed"
                ),
                color=get_color("primary")
            )

            # Disable buttons
            for item in self.children:
                item.disabled = True

            await interaction.followup.edit_message(
                interaction.message.id,
                embed=embed,
                view=self
            )

        except APIError as e:
            await interaction.followup.send(
                embed=error_embed(description=f"❌ {e.user_message}"),
                ephemeral=True
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = create_embed(
            title="",
            description="## Crypto Wallet Management\n\n> Withdrawal cancelled",
            color=get_color("primary")
        )

        for item in self.children:
            item.disabled = True

        await interaction.followup.edit_message(
            interaction.message.id,
            embed=embed,
            view=self
        )
