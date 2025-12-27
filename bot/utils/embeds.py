"""
Embed Templates - Clean embed creation following V3 design patterns
Purple/blue gradient theme with consistent formatting
"""

import discord
from datetime import datetime
from typing import Optional, List, Dict, Any
from utils.colors import get_color, PURPLE_GRADIENT, get_asset_color


def create_embed(
    title: str = "",
    description: str = "",
    color: int = PURPLE_GRADIENT,
    footer: Optional[str] = None,
    timestamp: bool = False
) -> discord.Embed:
    """
    Create a basic themed embed

    Args:
        title: Embed title (usually empty or backtick-wrapped)
        description: Main embed content
        color: Hex color value
        footer: Footer text (defaults to month/year)
        timestamp: Whether to add timestamp

    Returns:
        Configured Discord embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    if footer is None:
        footer = datetime.now().strftime("%B %Y")

    embed.set_footer(text=footer)

    if timestamp:
        embed.timestamp = datetime.now()

    return embed


def success_embed(
    title: str = "✅ Success",
    description: str = "",
    **kwargs
) -> discord.Embed:
    """Create a success embed (green)"""
    return create_embed(
        title=title,
        description=description,
        color=get_color("success"),
        **kwargs
    )


def error_embed(
    title: str = "",
    description: str = "",
    **kwargs
) -> discord.Embed:
    """Create an error embed (red) - Clean format without title emoji spam"""
    return create_embed(
        title=title,
        description=description,
        color=get_color("error"),
        **kwargs
    )


def warning_embed(
    title: str = "⚠️ Warning",
    description: str = "",
    **kwargs
) -> discord.Embed:
    """Create a warning embed (orange)"""
    return create_embed(
        title=title,
        description=description,
        color=get_color("warning"),
        **kwargs
    )


def info_embed(
    title: str = "ℹ️ Information",
    description: str = "",
    **kwargs
) -> discord.Embed:
    """Create an info embed (blue)"""
    return create_embed(
        title=title,
        description=description,
        color=get_color("info"),
        **kwargs
    )


# =======================
# Panel Embeds
# =======================

def create_exchange_panel_embed() -> discord.Embed:
    """Create the main exchange panel embed (matches V3 exactly)"""
    server_name = "AfrooExch"

    description = (
        f"## Welcome to {server_name} Exchange\n\n"
        f"**Your trusted platform for secure crypto and fiat exchanges.** We protect both clients and exchangers through our ticket-based escrow system.\n\n"
        f"> All exchanges are conducted safely through our official ticket system.\n\n"
    )

    embed = create_embed(
        title="",
        description=description,
        color=PURPLE_GRADIENT
    )

    # Safety First
    embed.add_field(
        name="**Stay Safe - Avoid Scams**",
        value=(
            "*Your security is our priority:*\n\n"
            "> `NEVER DM EXCHANGERS DIRECTLY`\n"
            "> All exchanges must happen through the ticket system\n"
            "> `WAIT FOR TICKET TO BE CLAIMED` before sending money\n"
            "> Only trust messages from our official bot\n"
            "> Report anyone asking you to exchange outside of tickets\n\n"
        ),
        inline=False
    )

    # How It Works
    embed.add_field(
        name="**How Our Exchange System Works**",
        value=(
            "*Safe, simple, and secure:*\n\n"
            "> `1.` Click **Start Exchange** to create a ticket\n"
            "> `2.` Fill out the exchange form with your details\n"
            "> `3.` Wait for an exchanger to claim your ticket\n"
            "> `4.` Follow the exchanger's instructions in the ticket\n"
            "> `5.` Complete the exchange safely through the ticket\n\n"
        ),
        inline=False
    )

    # What We Offer
    embed.add_field(
        name="**What We Offer**",
        value=(
            "*Why choose AfrooExch?*\n\n"
            "> `Secure Escrow System:` Your funds are protected\n"
            "> `Verified Exchangers:` All exchangers are vetted\n"
            "> `Multiple Payment Methods:` Crypto, PayPal, CashApp, Venmo, Zelle & more\n"
            "> `Transparent Fees:` Know exactly what you'll pay\n"
            "> `24/7 Support:` Get help anytime you need it\n\n"
        ),
        inline=False
    )

    # Before You Begin
    embed.add_field(
        name="**Before You Begin**",
        value=(
            "*Please review these first:*\n\n"
            "> **Terms of Service** - Understand the rules and safety guidelines\n"
            "> **Fee Information** - Know our transparent fee structure\n"
            "> **Support Panel** - Get help if you need it\n\n"
        ),
        inline=False
    )

    embed.set_footer(text=f"Always use the ticket system • Never DM exchangers • {datetime.now().strftime('%B %Y')}")

    return embed


def create_support_panel_embed() -> discord.Embed:
    """Create the support panel embed (matches V3 exactly)"""
    description = (
        "## AfrooExch Support Panel\n\n"
        "**Need help?** Select a support option below to open a ticket with our team.\n\n"
        "> Our staff are volunteers - please be patient while waiting for a response.\n\n"
    )

    embed = create_embed(
        title="",
        description=description,
        color=PURPLE_GRADIENT
    )

    # Important Rules Section
    embed.add_field(
        name="**Important Rules**",
        value=(
            "*Please follow these guidelines:*\n\n"
            "> `DO NOT DM STAFF MEMBERS DIRECTLY`\n"
            "> All support requests must go through the ticket system\n"
            "> `DO NOT CREATE TICKETS FOR FUN`\n"
            "> Misuse of the ticket system may result in warnings or bans\n\n"
        ),
        inline=False
    )

    # Available Support Options Section
    embed.add_field(
        name="**Available Support Options**",
        value=(
            "*Select the option that best matches your needs:*\n\n"
            "> `General Question` - General questions and support\n"
            "> `Report Exchanger` - Report an exchanger for violations\n"
            "> `Claim Giveaway` - Claim your giveaway prize\n"
            "> `Report Bug` - Report a bug with the bot\n"
            "> `Feature Request` - Request a new feature or improvement\n\n"
        ),
        inline=False
    )

    # Action field
    embed.add_field(
        name="",
        value="**Use the dropdown menu below to select your support type**",
        inline=False
    )

    return embed


def create_deposit_panel_embed() -> discord.Embed:
    """Create exchanger deposit panel embed"""
    return create_embed(
        title="",
        description=(
            "## 💰 EXCHANGER DEPOSITS\n\n"
            "**Manage your exchange liquidity**\n\n"
            "> Fund your wallets to start accepting exchanges.\n"
            "> Supported assets: BTC, LTC, ETH, SOL, USDT, USDC\n\n"
            "**Features:**\n"
            "> 📥 **Deposit** - Get deposit addresses\n"
            "> 💵 **Balance & Limits** - View available funds\n"
            "> 🔒 **Active Holds** - See locked funds\n"
            "> 📤 **Withdraw** - Cash out earnings\n"
            "> 📊 **History** - Track all activity\n"
            "> 🔄 **Refresh** - Update from blockchain\n\n"
        ),
        color=PURPLE_GRADIENT
    )


def create_user_dashboard_embed(user_data: Dict[str, Any]) -> discord.Embed:
    """
    Create user dashboard embed

    Args:
        user_data: User statistics from API
    """
    total_volume = user_data.get("total_volume", 0)
    total_trades = user_data.get("total_trades", 0)
    current_tier = user_data.get("current_tier", "None")

    return create_embed(
        title="",
        description=(
            f"## 📊 YOUR DASHBOARD\n\n"
            f"**Statistics:**\n"
            f"> **Total Volume:** `${total_volume:,.2f}`\n"
            f"> **Trades Completed:** `{total_trades}`\n"
            f"> **Current Tier:** `{current_tier}`\n\n"
            "*Use the buttons below to manage your account*\n"
        ),
        color=PURPLE_GRADIENT
    )


def create_deposit_panel_embed() -> discord.Embed:
    """Create exchanger deposit panel embed (matches V3 exactly)"""
    description = (
        "## Exchanger Deposit System\n\n"
        "Manage your crypto deposits securely. Use the dropdown below to:\n\n"
        "> **Deposit** - Get addresses for BTC, LTC, SOL, ETH, USDT, USDC\n"
        "> **My Balance & Active Holds** - View balances and locked funds\n"
        "> **Withdraw** - Send available funds to external wallet\n"
        "> **History** - View transaction history\n"
        "> **Refresh** - Update balances from blockchain\n"
        "> **Ask a Question** - Get help from support\n"
    )

    embed = create_embed(
        title="",
        description=description,
        color=PURPLE_GRADIENT
    )

    # Simple supported assets footer
    embed.add_field(
        name="Supported Assets",
        value="`BTC` Bitcoin • `LTC` Litecoin • `SOL` Solana • `ETH` Ethereum • `USDT` Tether • `USDC` USD Coin",
        inline=False
    )

    embed.set_footer(text=f"Secure escrow system • {datetime.now().strftime('%B %Y')}")

    return embed


# =======================
# Ticket Embeds
# =======================

def create_ticket_embed(ticket: Dict[str, Any]) -> discord.Embed:
    """
    Create ticket information embed

    Args:
        ticket: Ticket data from API
    """
    ticket_id = ticket.get("ticket_id", "N/A")
    input_currency = ticket.get("input_currency", "N/A")
    output_currency = ticket.get("output_currency", "N/A")
    amount = ticket.get("amount", 0)
    status = ticket.get("status", "unknown")

    status_emoji = {
        "created": "🆕",
        "tos_pending": "📋",
        "open": "🟢",
        "claimed": "👤",
        "in_progress": "⚙️",
        "awaiting_payout": "💰",
        "completed": "✅",
        "cancelled": "❌"
    }.get(status, "❓")

    return create_embed(
        title=f"",
        description=(
            f"## 🎫 Ticket #{ticket_id}\n\n"
            f"**Exchange Details:**\n"
            f"> **Sending:** `{amount:.8f} {input_currency}`\n"
            f"> **Receiving:** `{output_currency}`\n"
            f"> **Status:** {status_emoji} `{status.replace('_', ' ').title()}`\n\n"
        ),
        color=get_asset_color(input_currency)
    )


def create_tos_embed(payment_method: str) -> discord.Embed:
    """
    Create TOS agreement embed

    Args:
        payment_method: Payment method for specific TOS
    """
    return create_embed(
        title="",
        description=(
            f"## 📋 TERMS OF SERVICE\n\n"
            f"**Payment Method: {payment_method}**\n\n"
            "> **Please read carefully:**\n\n"
            f"*By clicking \"I Agree\", you acknowledge and accept:*\n\n"
            f"> 1. All transactions are final\n"
            f"> 2. Server fees apply as displayed\n"
            f"> 3. You are responsible for payment accuracy\n"
            f"> 4. Chargebacks result in permanent ban\n"
            f"> 5. Disputes must be filed within 24 hours\n\n"
            f"⏱️ **You have 10 minutes to agree**\n\n"
        ),
        color=get_color("warning")
    )


# =======================
# Wallet Embeds
# =======================

def create_wallet_embed(wallet: Dict[str, Any]) -> discord.Embed:
    """
    Create wallet information embed

    Args:
        wallet: Wallet data from API
    """
    asset = wallet.get("asset", "N/A")
    address = wallet.get("address", "N/A")
    balance = wallet.get("balance_units", 0)
    balance_usd = wallet.get("balance_usd", 0)

    return create_embed(
        title="",
        description=(
            f"## 💳 {asset} Wallet\n\n"
            f"**Balance:**\n"
            f"> `{balance:.8f} {asset}` (${balance_usd:,.2f})\n\n"
            f"**Address:**\n"
            f"> `{address}`\n\n"
        ),
        color=get_asset_color(asset)
    )


def create_deposit_instructions_embed(
    asset: str,
    address: str,
    network: Optional[str] = None
) -> discord.Embed:
    """
    Create deposit instructions embed

    Args:
        asset: Crypto asset (BTC, ETH, etc.)
        address: Deposit address
        network: Network name (for multi-network assets)
    """
    network_info = f"\n> **Network:** `{network}`\n" if network else ""

    return create_embed(
        title="",
        description=(
            f"## 📥 Deposit {asset}\n\n"
            f"**Deposit Address:**\n"
            f"> `{address}`\n"
            f"{network_info}\n"
            f"**Instructions:**\n"
            f"> 1. Copy the address above\n"
            f"> 2. Send {asset} to this address\n"
            f"> 3. Wait for network confirmations\n"
            f"> 4. Funds will appear automatically\n\n"
            f"⚠️ **Only send {asset} to this address**\n"
        ),
        color=get_asset_color(asset)
    )


# =======================
# Admin Embeds
# =======================

def create_admin_panel_embed() -> discord.Embed:
    """Create admin control panel embed"""
    return create_embed(
        title="",
        description=(
            "## 🛡️ ADMIN CONTROL PANEL\n\n"
            "**System Management**\n\n"
            "> Use the commands or buttons below to manage the system.\n\n"
            "**Available Actions:**\n"
            "> 👥 User Management\n"
            "> 🎫 Ticket Management\n"
            "> 💳 Wallet Management\n"
            "> 📊 System Statistics\n"
            "> 📝 Audit Logs\n\n"
        ),
        color=get_color("error")
    )


# =======================
# Notification Embeds
# =======================

def create_deposit_notification_embed(
    asset: str,
    amount: float,
    tx_hash: str
) -> discord.Embed:
    """
    Create deposit notification DM embed

    Args:
        asset: Crypto asset
        amount: Deposit amount
        tx_hash: Transaction hash
    """
    return create_embed(
        title="",
        description=(
            f"## 📥 Deposit Received!\n\n"
            f"**Amount:** `{amount:.8f} {asset}`\n"
            f"**Transaction:** `{tx_hash[:16]}...`\n\n"
            f"> Your deposit has been credited to your account.\n"
        ),
        color=get_color("success"),
        timestamp=True
    )


def create_swap_complete_notification_embed(
    swap_id: str,
    from_asset: str,
    to_asset: str,
    amount: float
) -> discord.Embed:
    """
    Create swap completion notification embed

    Args:
        swap_id: Swap identifier
        from_asset: Source asset
        to_asset: Destination asset
        amount: Amount swapped
    """
    return create_embed(
        title="",
        description=(
            f"## 🔄 Swap Complete!\n\n"
            f"**Swap ID:** `{swap_id}`\n"
            f"**Exchanged:** `{amount:.8f} {from_asset}` → `{to_asset}`\n\n"
            f"> Your swap has been completed successfully.\n"
        ),
        color=get_color("success"),
        timestamp=True
    )


# =======================
# Error Embeds
# =======================

def create_permission_error_embed() -> discord.Embed:
    """Create permission denied embed"""
    return error_embed(
        description=(
            "## ⛔ Access Denied\n\n"
            "> You don't have permission to use this command.\n"
        )
    )


def create_api_error_embed(message: str) -> discord.Embed:
    """
    Create API error embed

    Args:
        message: Error message from API
    """
    return error_embed(
        description=(
            f"## 💥 Something Went Wrong\n\n"
            f"> {message}\n\n"
            f"*If this problem persists, please contact support.*\n"
        )
    )


def create_rate_limit_embed(retry_after: int) -> discord.Embed:
    """
    Create rate limit embed

    Args:
        retry_after: Seconds until retry
    """
    return warning_embed(
        title="⏱️ Slow Down",
        description=(
            f"## You're doing that too fast!\n\n"
            f"> Please wait `{retry_after}` seconds before trying again.\n"
        )
    )


# =======================
# Aliases for compatibility
# =======================

def create_themed_embed(title: str = "", description: str = "", color: int = PURPLE_GRADIENT, **kwargs) -> discord.Embed:
    """Alias for create_embed"""
    return create_embed(title=title, description=description, color=color, **kwargs)


def create_success_embed(title: str = "✅ Success", description: str = "", **kwargs) -> discord.Embed:
    """Alias for success_embed"""
    return success_embed(title=title, description=description, **kwargs)


def create_error_embed(title: str = "", description: str = "", **kwargs) -> discord.Embed:
    """Alias for error_embed - Clean format without title emoji spam"""
    return error_embed(title=title, description=description, **kwargs)
