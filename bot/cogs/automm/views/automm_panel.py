"""AutoMM P2P Escrow Panel - Buyer protection escrow system"""
import logging
import discord
from discord.ui import View, Button, Modal, InputText, Select

logger = logging.getLogger(__name__)

# Crypto emojis matching wallet panel
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

# Custom emoji names on Discord server
CURRENCY_EMOJI_NAMES = {
    "BTC": "BTC",
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

# Native cryptocurrencies (no gas fee issues)
NATIVE_CRYPTOS = [
    {"name": "BTC", "label": "BTC - Bitcoin"},
    {"name": "LTC", "label": "LTC - Litecoin"},
    {"name": "ETH", "label": "ETH - Ethereum"},
    {"name": "SOL", "label": "SOL - Solana"},
    {"name": "XRP", "label": "XRP - Ripple"},
    {"name": "BNB", "label": "BNB - Binance Coin"},
    {"name": "TRX", "label": "TRX - Tron"},
    {"name": "MATIC", "label": "MATIC - Polygon"},
    {"name": "AVAX", "label": "AVAX - Avalanche"},
    {"name": "DOGE", "label": "DOGE - Dogecoin"}
]

# Stablecoins REMOVED - too complex with gas fees
# Only native cryptocurrencies supported

# All cryptos for API
ALL_SUPPORTED_CRYPTOS = [c["name"] for c in NATIVE_CRYPTOS]


class AutoMMPanelView(View):
    """Main AutoMM P2P Escrow panel"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Create Escrow", style=discord.ButtonStyle.primary, emoji="🔒", custom_id="create_escrow_button")
    async def create_escrow_button(self, button: Button, interaction: discord.Interaction):
        """Create new escrow transaction"""
        modal = CreateEscrowModal(self.bot)
        await interaction.response.send_modal(modal)


class CreateEscrowModal(Modal):
    """Modal for creating escrow - collects seller, amount, and service description"""
    def __init__(self, bot):
        super().__init__(title="Create Escrow Transaction")
        self.bot = bot

        self.seller_input = InputText(
            label="Seller (User ID or @mention)",
            placeholder="Who are you buying from? Enter user ID or @mention",
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.seller_input)

        self.amount_input = InputText(
            label="Amount in USD",
            placeholder="Example: 50 (USD value)",
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.amount_input)

        self.service_input = InputText(
            label="What are you buying?",
            placeholder="Example: Logo design, Website, Discord members, etc.",
            required=True,
            style=discord.InputTextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.service_input)

    async def callback(self, interaction: discord.Interaction):
        """Process escrow creation - show crypto selection"""
        await interaction.response.defer(ephemeral=True)
        try:
            # Parse seller
            seller_str = self.seller_input.value.strip()
            seller_id = int(seller_str.replace("<@", "").replace(">", "").replace("!", "")) if seller_str.startswith("<@") else int(seller_str)
            seller = interaction.guild.get_member(seller_id)

            if not seller:
                await interaction.followup.send("❌ Seller not found in this server.", ephemeral=True)
                return

            if seller.id == interaction.user.id:
                await interaction.followup.send("❌ You cannot create an escrow with yourself.", ephemeral=True)
                return

            if seller.bot:
                await interaction.followup.send("❌ You cannot create an escrow with a bot.", ephemeral=True)
                return

            # Validate USD amount
            try:
                usd_amount = float(self.amount_input.value.strip())
                if usd_amount <= 0:
                    await interaction.followup.send("❌ Amount must be greater than 0.", ephemeral=True)
                    return
            except ValueError:
                await interaction.followup.send("❌ Invalid amount. Please enter a valid number.", ephemeral=True)
                return

            service_description = self.service_input.value.strip()

            # Show crypto selection
            from utils.embeds import create_themed_embed
            from utils.colors import PURPLE_GRADIENT

            embed = create_themed_embed(
                title="",
                description=(
                    f"## Select Cryptocurrency\n\n"
                    f"**Buyer:** {interaction.user.mention}\n"
                    f"**Seller:** {seller.mention}\n"
                    f"**Amount:** `${usd_amount:.2f} USD`\n"
                    f"**Service:** {service_description}\n\n"
                    f"Choose which cryptocurrency you'll pay with:"
                ),
                color=PURPLE_GRADIENT
            )

            view = CryptoSelectionView(
                bot=self.bot,
                buyer=interaction.user,
                seller=seller,
                usd_amount=usd_amount,
                service_description=service_description
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except ValueError:
            await interaction.followup.send("❌ Invalid user ID. Please enter a valid Discord user ID or @mention.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error creating escrow: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


class CryptoSelectionView(View):
    """View for selecting cryptocurrency"""
    def __init__(self, bot, buyer, seller, usd_amount, service_description):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
        self.buyer = buyer
        self.seller = seller
        self.usd_amount = usd_amount
        self.service_description = service_description

        # Add crypto select dropdown
        self.add_item(CryptoSelectDropdown(self))


class CryptoSelectDropdown(Select):
    """Dropdown for selecting cryptocurrency"""
    def __init__(self, parent_view):
        self.parent_view = parent_view

        # Build options: Native cryptos only
        options = []

        # Get guild to fetch custom emojis
        from config import config
        bot = parent_view.bot
        guild = bot.get_guild(config.guild_id) if bot else None

        for crypto in NATIVE_CRYPTOS:
            crypto_name = crypto["name"]

            # Try to get custom server emoji first, fallback to unicode
            emoji = None
            emoji_name = CURRENCY_EMOJI_NAMES.get(crypto_name)
            if guild and emoji_name:
                emoji = discord.utils.get(guild.emojis, name=emoji_name)

            # Fallback to unicode if custom emoji not found
            if not emoji:
                emoji = CURRENCY_EMOJIS.get(crypto_name, "💰")

            options.append(
                discord.SelectOption(
                    label=crypto["label"],
                    value=crypto_name,
                    emoji=emoji
                )
            )

        super().__init__(
            placeholder="Select cryptocurrency...",
            options=options,
            custom_id="crypto_select"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle crypto selection"""
        selected_crypto = self.values[0]

        # Create escrow immediately (stablecoins removed)
        await self.create_escrow(interaction, selected_crypto)

    async def create_escrow(self, interaction, selected_crypto):
        """Create the escrow transaction"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Create escrow via handler
            from cogs.automm.handlers.escrow_handler import create_buyer_escrow

            await create_buyer_escrow(
                interaction=interaction,
                buyer=self.parent_view.buyer,
                seller=self.parent_view.seller,
                usd_amount=self.parent_view.usd_amount,
                crypto=selected_crypto,
                service_description=self.parent_view.service_description,
                bot=self.parent_view.bot
            )

        except Exception as e:
            logger.error(f"Error creating escrow: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
