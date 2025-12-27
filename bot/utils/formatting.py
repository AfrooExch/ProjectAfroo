"""
Formatting - Text and value formatting utilities
"""

from typing import Optional
from datetime import datetime


def format_currency(amount: float, decimals: int = 2) -> str:
    """
    Format currency amount

    Args:
        amount: Amount to format
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "$1,234.56")
    """
    return f"${amount:,.{decimals}f}"


def format_crypto(amount: float, symbol: str, decimals: int = 8) -> str:
    """
    Format crypto amount

    Args:
        amount: Amount to format
        symbol: Asset symbol (BTC, ETH, etc.)
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "0.00123456 BTC")
    """
    return f"{amount:.{decimals}f} {symbol}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format percentage

    Args:
        value: Percentage value (0.1 = 10%)
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "10.00%")
    """
    return f"{value * 100:.{decimals}f}%"


def format_timestamp(dt: datetime, style: str = "f") -> str:
    """
    Format timestamp as Discord timestamp

    Args:
        dt: Datetime object
        style: Discord timestamp style
            - t: Short time (16:20)
            - T: Long time (16:20:30)
            - d: Short date (20/04/2021)
            - D: Long date (20 April 2021)
            - f: Short date/time (20 April 2021 16:20)
            - F: Long date/time (Tuesday, 20 April 2021 16:20)
            - R: Relative time (2 months ago)

    Returns:
        Discord timestamp markdown
    """
    timestamp = int(dt.timestamp())
    return f"<t:{timestamp}:{style}>"


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to max length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_user(user_id: str, username: str) -> str:
    """
    Format user mention

    Args:
        user_id: Discord user ID
        username: Username (fallback)

    Returns:
        User mention or username
    """
    return f"<@{user_id}>" if user_id else username


def format_channel(channel_id: str) -> str:
    """
    Format channel mention

    Args:
        channel_id: Discord channel ID

    Returns:
        Channel mention
    """
    return f"<#{channel_id}>"


def format_role(role_id: str) -> str:
    """
    Format role mention

    Args:
        role_id: Discord role ID

    Returns:
        Role mention
    """
    return f"<@&{role_id}>"


def format_duration(seconds: int) -> str:
    """
    Format duration in human-readable format

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1h 30m")
    """
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours < 24:
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"

    days = hours // 24
    remaining_hours = hours % 24

    if remaining_hours > 0:
        return f"{days}d {remaining_hours}h"
    return f"{days}d"


def format_list(items: list, prefix: str = "•") -> str:
    """
    Format list of items

    Args:
        items: List of items
        prefix: Bullet point prefix

    Returns:
        Formatted list string
    """
    return "\n".join(f"{prefix} {item}" for item in items)


def format_code_block(text: str, language: str = "") -> str:
    """
    Format text as Discord code block

    Args:
        text: Text to format
        language: Syntax highlighting language

    Returns:
        Code block markdown
    """
    return f"```{language}\n{text}\n```"


def format_inline_code(text: str) -> str:
    """
    Format text as inline code

    Args:
        text: Text to format

    Returns:
        Inline code markdown
    """
    return f"`{text}`"


def format_bold(text: str) -> str:
    """Format text as bold"""
    return f"**{text}**"


def format_italic(text: str) -> str:
    """Format text as italic"""
    return f"*{text}*"


def format_quote(text: str) -> str:
    """Format text as quote"""
    lines = text.split("\n")
    return "\n".join(f"> {line}" for line in lines)
