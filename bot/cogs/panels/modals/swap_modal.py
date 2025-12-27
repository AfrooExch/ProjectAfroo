"""
Swap Modal - Form for creating instant swaps
Creates private swap ticket with quote confirmation
"""

import discord
import logging

from api.errors import APIError, ValidationError
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, ERROR_RED
from utils.auth import get_user_context

logger = logging.getLogger(__name__)


class SwapModal(discord.ui.Modal):
    """Modal for creating swaps - creates private ticket"""

    def __init__(self, bot: discord.Bot):
        super().__init__(title="Afroo Swap")
        self.bot = bot

        # From asset
        self.add_item(
            discord.ui.InputText(
                label="From (What you're sending)",
                placeholder="e.g., BTC, ETH, SOL, USDT-SOL, LTC",
                style=discord.InputTextStyle.short,
                max_length=15
            )
        )

        # To asset
        self.add_item(
            discord.ui.InputText(
                label="To (What you want to receive)",
                placeholder="e.g., BTC, ETH, SOL, USDT-SOL, LTC",
                style=discord.InputTextStyle.short,
                max_length=15
            )
        )

        # Amount
        self.add_item(
            discord.ui.InputText(
                label="Amount (crypto only)",
                placeholder="e.g., 0.001 BTC or 50 USDT",
                style=discord.InputTextStyle.short,
                max_length=20
            )
        )

        # Destination address
        self.add_item(
            discord.ui.InputText(
                label="Your receiving wallet address",
                placeholder="Where you want to receive the swapped crypto",
                style=discord.InputTextStyle.short,
                max_length=100
            )
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle modal submission - get quote and show confirmation"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get form values
            from_asset = self.children[0].value.strip().upper()
            to_asset = self.children[1].value.strip().upper()
            amount_str = self.children[2].value.strip()
            destination_address = self.children[3].value.strip()

            # Validate destination address
            if not destination_address or len(destination_address) < 10:
                await interaction.followup.send(
                    embed=create_themed_embed(
                        title="❌ Invalid Address",
                        description="Please provide a valid wallet address to receive your swapped crypto.",
                        color=ERROR_RED
                    ),
                    ephemeral=True
                )
                return

            # Validate same asset
            if from_asset == to_asset:
                await interaction.followup.send(
                    embed=create_themed_embed(
                        title="❌ Invalid Swap",
                        description="You cannot swap the same asset. Please choose different currencies.",
                        color=ERROR_RED
                    ),
                    ephemeral=True
                )
                return

            # Parse amount - detect USD or coin amount
            is_usd = False
            if amount_str.startswith('$') or 'USD' in amount_str.upper():
                is_usd = True
                # Remove $, USD, and whitespace
                amount_str = amount_str.replace('$', '').replace('USD', '').replace('usd', '').strip()

            # Validate amount
            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError:
                await interaction.followup.send(
                    embed=create_themed_embed(
                        title="❌ Invalid Amount",
                        description="Please enter a valid positive number for the amount.",
                        color=ERROR_RED
                    ),
                    ephemeral=True
                )
                return

            # Get user context and API client (needed for USD conversion)
            user_context_id, roles = get_user_context(interaction)
            api = self.bot.api_client

            # If USD amount, convert to coin amount using live ChangeNOW rates
            original_amount = amount
            amount_display = f"${amount:.2f} USD" if is_usd else f"{amount} {from_asset}"

            if is_usd:
                # Use ChangeNOW to get live USD price
                try:
                    # Check if from_asset is a stablecoin (1:1 with USD)
                    base_asset = from_asset.split('-')[0] if '-' in from_asset else from_asset
                    is_stablecoin = base_asset in ["USDT", "USDC", "DAI", "BUSD"]

                    if is_stablecoin:
                        # Stablecoins are ~$1 each, so $X USD = ~X coins
                        amount = original_amount
                        logger.info(f"Stablecoin detected: ${original_amount} USD = {amount} {from_asset} (1:1 rate)")
                    else:
                        # For non-stablecoins, query ChangeNOW for live rate
                        # Strategy: Get how much from_asset you get for 1 USDT, then multiply by USD amount
                        # Always use USDT-ETH for price checking (better liquidity and more trading pairs)
                        stablecoin = "USDT-ETH"

                        # Get live rate: 1 USDT = X from_asset
                        usd_to_crypto_quote = await api.afroo_swap_get_quote(
                            from_asset=stablecoin,
                            to_asset=from_asset,
                            amount=1.0,  # 1 USD = ? crypto
                            user_id=str(interaction.user.id),
                            discord_roles=roles
                        )

                        crypto_per_usd = usd_to_crypto_quote.get("quote", {}).get("estimated_output", 0)

                        if crypto_per_usd <= 0:
                            raise ValueError("Could not get live exchange rate")

                        # Convert USD amount to crypto amount
                        amount = amount * crypto_per_usd
                        usd_price = 1.0 / crypto_per_usd  # Calculate USD price per coin

                        logger.info(f"Converted ${original_amount} USD to {amount} {from_asset} using live ChangeNOW rate (${usd_price:.2f} per {from_asset})")

                except Exception as e:
                    logger.error(f"Failed to get live USD price from ChangeNOW: {e}")
                    await interaction.followup.send(
                        embed=create_themed_embed(
                            title="❌ USD Conversion Failed",
                            description=f"Could not get live price for {from_asset}. Please enter the coin amount instead (e.g., 0.02 {from_asset}).",
                            color=ERROR_RED
                        ),
                        ephemeral=True
                    )
                    return

            logger.info(
                f"Swap quote requested: {interaction.user.name} ({interaction.user.id}) - "
                f"{amount} {from_asset} → {to_asset}"
            )

            # Get quote from API
            result = await api.afroo_swap_get_quote(
                from_asset=from_asset,
                to_asset=to_asset,
                amount=amount,
                user_id=str(interaction.user.id),
                discord_roles=roles
            )

            quote = result.get("quote", {})

            # Build confirmation embed
            estimated_output = quote.get("estimated_output", 0)
            exchange_rate = quote.get("exchange_rate", 0)

            # Build amount display text
            if is_usd:
                amount_text = f"`{amount_display}` (≈ `{amount:.8f} {from_asset}`)"
            else:
                amount_text = f"`{amount} {from_asset}`"

            # Truncate address for display
            addr_display = destination_address if len(destination_address) <= 20 else f"{destination_address[:10]}...{destination_address[-6:]}"

            confirmation_embed = create_themed_embed(
                title="",
                description=(
                    f"## 🔄 Confirm Swap\n\n"
                    f"**You Send:** {amount_text}\n"
                    f"**Exchange Rate:** `1 {from_asset} = {exchange_rate:.8f} {to_asset}`\n"
                    f"**You Receive:** `~{estimated_output:.8f} {to_asset}`\n"
                    f"**Receiving Address:** `{addr_display}`\n\n"
                    f"> ⚠️ **Note:** The final amount may vary slightly due to market fluctuations.\n"
                    f"> You'll send to the provided deposit address and receive at your destination address.\n"
                    f"> Exchange fees are included in the rate.\n\n"
                    f"> Click **Confirm** to create your swap ticket."
                ),
                color=PURPLE_GRADIENT
            )

            # Show confirmation view (creates ticket on confirm)
            from cogs.panels.views.swap_ticket_confirm import SwapTicketConfirmView

            confirmation_view = SwapTicketConfirmView(
                bot=self.bot,
                user_id=interaction.user.id,
                from_asset=from_asset,
                to_asset=to_asset,
                amount=amount,
                destination_address=destination_address,
                quote=quote
            )

            await interaction.followup.send(
                embed=confirmation_embed,
                view=confirmation_view,
                ephemeral=True
            )

        except ValidationError as e:
            logger.error(f"Validation error getting quote: {e}")
            await interaction.followup.send(
                embed=create_themed_embed(
                    title="❌ Swap Error",
                    description=f"{e.user_message}\n\n> Please check your input and try again.",
                    color=ERROR_RED
                ),
                ephemeral=True
            )

        except APIError as e:
            logger.error(f"API error getting quote: {e}")
            await interaction.followup.send(
                embed=create_themed_embed(
                    title="❌ Swap Error",
                    description=f"{e.user_message}\n\n> Please try again or contact support.",
                    color=ERROR_RED
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error getting swap quote: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_themed_embed(
                    title="❌ Unexpected Error",
                    description="An error occurred while getting the swap quote. Please try again or contact support.",
                    color=ERROR_RED
                ),
                ephemeral=True
            )
