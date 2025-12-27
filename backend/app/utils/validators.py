"""Validation utilities"""

import re


def is_valid_blockchain_address(address: str, blockchain: str) -> bool:
    """Validate blockchain address format"""
    patterns = {
        "bitcoin": r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$",
        "ethereum": r"^0x[a-fA-F0-9]{40}$",
        "solana": r"^[1-9A-HJ-NP-Za-km-z]{32,44}$",
    }

    pattern = patterns.get(blockchain.lower())
    if not pattern:
        return False

    return bool(re.match(pattern, address))


def is_valid_discord_id(discord_id: str) -> bool:
    """Validate Discord ID format"""
    return discord_id.isdigit() and len(discord_id) >= 17 and len(discord_id) <= 20


def is_valid_slug(slug: str) -> bool:
    """Validate slug format"""
    return bool(re.match(r"^[a-z0-9-]+$", slug))
