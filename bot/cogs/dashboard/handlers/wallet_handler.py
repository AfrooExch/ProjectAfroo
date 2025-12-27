"""
Wallet Access Handler for V4
Quick access to Afroo wallet portfolio
"""

import logging

import discord

from api.errors import APIError
from utils.embeds import create_themed_embed, create_error_embed
from utils.colors import PURPLE_GRADIENT, SUCCESS_GREEN

logger = logging.getLogger(__name__)


async def show_wallet_access(interaction: discord.Interaction, bot: discord.Bot) -> None:
    """
    Show wallet portfolio overview with quick access

    Args:
        interaction: Discord interaction
        bot: Bot instance
    """
    api = bot.api_client

    try:
        from utils.auth import get_user_context
        user_context_id, roles = get_user_context(interaction)

        # Get wallet portfolio
        portfolio_response = await api.get(
            "/api/v1/wallet/portfolio",
            discord_user_id=str(interaction.user.id),
            discord_roles=roles
        )

        wallets = portfolio_response.get("wallets", [])
        total_usd = portfolio_response.get("total_usd", 0.0)

        if not wallets:
            # No wallets yet
            embed = create_themed_embed(
                title="",
                description=(
                    f"## 💼 Your Crypto Wallet\n\n"
                    f"### Get Started\n\n"
                    f"You don't have any crypto wallets yet.\n\n"
                    f"**How to create a wallet:**\n\n"
                    f"> 1. Use the Wallet Panel to generate wallets\n"
                    f"> 2. Choose your cryptocurrency (BTC, ETH, SOL, etc.)\n"
                    f"> 3. Receive your unique deposit address\n"
                    f"> 4. Start receiving and sending crypto!\n\n"
                    f"### Supported Assets\n\n"
                    f"₿ Bitcoin (BTC)\n"
                    f"Ξ Ethereum (ETH)\n"
                    f"Ł Litecoin (LTC)\n"
                    f"◎ Solana (SOL)\n"
                    f"₮ USDT (Solana & Ethereum)\n"
                    f"$ USDC (Solana & Ethereum)\n\n"
                    f"> Click the button below to access the Wallet Panel!"
                ),
                color=PURPLE_GRADIENT
            )

            view = WalletAccessView(bot, has_wallets=False)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        # Build wallet list (top 10)
        wallet_list = ""
        for wallet in wallets[:10]:
            currency = wallet.get("currency", "???")
            balance = wallet.get("balance", 0.0)
            usd_value = wallet.get("usd_value", 0.0)

            # Get emoji for currency
            currency_emojis = {
                "BTC": "₿",
                "ETH": "Ξ",
                "LTC": "Ł",
                "SOL": "◎",
                "USDT-SOL": "₮",
                "USDT-ETH": "₮",
                "USDC-SOL": "$",
                "USDC-ETH": "$"
            }
            emoji = currency_emojis.get(currency, "💰")

            wallet_list += f"{emoji} **{currency}**: `{balance:.8f}` (${usd_value:,.2f})\n"

        # Add note if showing only top 10
        showing_note = "> *Showing top 10 wallets*\n\n" if len(wallets) > 10 else ""

        embed = create_themed_embed(
            title="",
            description=(
                f"## 💼 Your Crypto Wallet\n\n"
                f"### Portfolio Overview\n\n"
                f"**Total Balance:** `${total_usd:,.2f} USD`\n"
                f"**Active Wallets:** {len(wallets)}\n\n"
                f"### Your Wallets\n\n"
                f"{wallet_list}\n"
                f"{showing_note}"
                f"### Quick Actions\n\n"
                f"> • Generate new wallet addresses\n"
                f"> • View deposit addresses with QR codes\n"
                f"> • Withdraw to external wallets\n"
                f"> • View transaction history\n\n"
                f"> Click the button below to access the full Wallet Panel!"
            ),
            color=SUCCESS_GREEN if total_usd > 0 else PURPLE_GRADIENT
        )

        embed.set_footer(text="💡 Tip: Your private keys are encrypted and secure")

        view = WalletAccessView(bot, has_wallets=True)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        logger.info(f"Showed wallet access for user {interaction.user.id}: {len(wallets)} wallets, ${total_usd:.2f}")

    except APIError as e:
        logger.error(f"API error fetching wallet portfolio: {e}")
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error Loading Wallet",
                description=f"{e.user_message}"
            ),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error showing wallet access: {e}", exc_info=True)
        await interaction.followup.send(
            embed=create_error_embed(
                title="Error",
                description=f"Failed to load wallet: {str(e)}"
            ),
            ephemeral=True
        )


class WalletAccessView(discord.ui.View):
    """View with button to open Wallet Panel"""

    def __init__(self, bot: discord.Bot, has_wallets: bool = False):
        super().__init__(timeout=300)
        self.bot = bot
        self.has_wallets = has_wallets

    @discord.ui.button(
        label="Open Wallet Panel",
        style=discord.ButtonStyle.primary,
        emoji="💼"
    )
    async def wallet_panel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Open the full Wallet Panel"""
        # Import here to avoid circular imports
        from cogs.panels.views.wallet_panel import WalletPanelView

        embed = create_themed_embed(
            title="",
            description=(
                f"## 💼 Wallet Panel\n\n"
                f"Manage your cryptocurrency wallets.\n\n"
                f"**Available Actions:**\n\n"
                f"> • Generate new wallet\n"
                f"> • View deposit addresses\n"
                f"> • Withdraw funds\n"
                f"> • Transaction history\n"
            ),
            color=PURPLE_GRADIENT
        )

        view = WalletPanelView(self.bot)

        await interaction.response.edit_message(embed=embed, view=view)
        logger.info(f"User {interaction.user.id} opened Wallet Panel")
