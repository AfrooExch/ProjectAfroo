"""
Color Constants - V3 Design System
Purple/Blue gradient theme with status and crypto colors
"""

from typing import Literal

# Primary Colors (V3 Theme)
BLUE_PRIMARY = 0x5865F2      # Discord Blurple - Main blue
PURPLE_GRADIENT = 0x9E6BFF   # V3 Purple Gradient - Pretty purple!
BLUE_GRADIENT = 0x9FC1FF     # V3 Blue gradient
GREEN_GRADIENT = 0x2ECC71    # Green gradient for success
RED_GRADIENT = 0xE74C3C      # Red gradient for errors
PURPLE_PRIMARY = PURPLE_GRADIENT
DISCORD_BLURPLE = BLUE_PRIMARY

# Status Colors
SUCCESS_GREEN = 0x2ECC71
ERROR_RED = 0xE74C3C
WARNING_ORANGE = 0xF39C12  # Deprecated - replaced with PURPLE_GRADIENT
INFO_BLUE = 0x3498DB

# Aliases for backward compatibility
SUCCESS = SUCCESS_GREEN
ERROR = ERROR_RED
WARNING = PURPLE_GRADIENT  # Changed from WARNING_ORANGE
INFO = INFO_BLUE

# Crypto Asset Colors
BTC_ORANGE = 0xF7931A
ETH_BLUE = 0x627EEA
LTC_BLUE = 0x345D9D
SOL_GREEN = 0x14F195
USDT_GREEN = 0x26A17B
USDC_BLUE = 0x2775CA

# Default theme color
DEFAULT = PURPLE_GRADIENT


def get_color(
    color_name: Literal[
        "primary", "success", "error", "warning", "info",
        "btc", "eth", "ltc", "sol", "usdt", "usdc"
    ] = "primary"
) -> int:
    """
    Get color value by name

    Args:
        color_name: Color identifier

    Returns:
        Hex color value
    """
    colors = {
        "primary": PURPLE_GRADIENT,
        "success": SUCCESS_GREEN,
        "error": ERROR_RED,
        "warning": PURPLE_GRADIENT,  # Changed from WARNING_ORANGE
        "info": INFO_BLUE,
        "btc": BTC_ORANGE,
        "eth": ETH_BLUE,
        "ltc": LTC_BLUE,
        "sol": SOL_GREEN,
        "usdt": USDT_GREEN,
        "usdc": USDC_BLUE,
    }
    return colors.get(color_name, DEFAULT)


def get_asset_color(asset: str) -> int:
    """
    Get color for crypto asset

    Args:
        asset: Asset symbol (BTC, ETH, etc.)

    Returns:
        Hex color value
    """
    asset_colors = {
        "BTC": BTC_ORANGE,
        "ETH": ETH_BLUE,
        "LTC": LTC_BLUE,
        "SOL": SOL_GREEN,
        "USDT": USDT_GREEN,
        "USDC": USDC_BLUE,
    }
    return asset_colors.get(asset.upper(), PURPLE_GRADIENT)
