"""
Constants for Exchange Ticket System
Payment methods, crypto assets, and other configurations
"""

from typing import Dict, List, Literal
from dataclasses import dataclass

# Payment Method Types
PaymentMethodType = Literal[
    "crypto",
    "paypal_balance",
    "paypal_card",
    "cashapp_balance",
    "cashapp_card",
    "applepay_balance",
    "applepay_card",
    "venmo_balance",
    "venmo_card",
    "zelle",
    "chime_balance",
    "chime_card",
    "revolut",
    "skrill",
    "bank",
    "paysafe",
    "binance_giftcard",
    "other"
]

# Crypto Asset Types
CryptoAssetType = Literal[
    "BTC", "ETH", "SOL", "LTC",
    "USDT-ETH", "USDT-SOL",
    "USDC-ETH", "USDC-SOL",
    "XRP", "BNB", "XMR", "TRX",
    "OTHER"
]


@dataclass
class PaymentMethod:
    """Payment method definition"""
    id: str
    name: str
    emoji: str
    tos_key: str  # Key to lookup in payment_method_tos.json
    requires_crypto_selection: bool = False
    is_crypto: bool = False


@dataclass
class CryptoAsset:
    """Crypto asset definition"""
    symbol: str
    name: str
    emoji: str
    network: str = ""


# Payment Methods for SENDING (17 total - with balance/card distinctions)
SEND_PAYMENT_METHODS: Dict[str, PaymentMethod] = {
    "crypto": PaymentMethod(
        id="crypto",
        name="Cryptocurrency",
        emoji="💰",
        tos_key="crypto",
        requires_crypto_selection=True,
        is_crypto=True
    ),
    "paypal_balance": PaymentMethod(
        id="paypal_balance",
        name="PayPal (Balance Only)",
        emoji="💳",
        tos_key="paypal_balance"
    ),
    "paypal_card": PaymentMethod(
        id="paypal_card",
        name="PayPal (Card/Bank)",
        emoji="💳",
        tos_key="paypal_goods"
    ),
    "cashapp_balance": PaymentMethod(
        id="cashapp_balance",
        name="CashApp (Balance Only)",
        emoji="💵",
        tos_key="cashapp"
    ),
    "cashapp_card": PaymentMethod(
        id="cashapp_card",
        name="CashApp (Card/Bank)",
        emoji="💵",
        tos_key="cashapp"
    ),
    "applepay_balance": PaymentMethod(
        id="applepay_balance",
        name="Apple Pay (Balance Only)",
        emoji="🍎",
        tos_key="applepay"
    ),
    "applepay_card": PaymentMethod(
        id="applepay_card",
        name="Apple Pay (Card/Bank)",
        emoji="🍎",
        tos_key="applepay"
    ),
    "venmo_balance": PaymentMethod(
        id="venmo_balance",
        name="Venmo (Balance Only)",
        emoji="💙",
        tos_key="venmo"
    ),
    "venmo_card": PaymentMethod(
        id="venmo_card",
        name="Venmo (Card/Bank)",
        emoji="💙",
        tos_key="venmo"
    ),
    "zelle": PaymentMethod(
        id="zelle",
        name="Zelle",
        emoji="⚡",
        tos_key="zelle"
    ),
    "chime_balance": PaymentMethod(
        id="chime_balance",
        name="Chime (Balance Only)",
        emoji="💚",
        tos_key="chime"
    ),
    "chime_card": PaymentMethod(
        id="chime_card",
        name="Chime (Card/Bank)",
        emoji="💚",
        tos_key="chime"
    ),
    "revolut": PaymentMethod(
        id="revolut",
        name="Revolut",
        emoji="🔵",
        tos_key="bank_transfer"
    ),
    "skrill": PaymentMethod(
        id="skrill",
        name="Skrill",
        emoji="🔷",
        tos_key="bank_transfer"
    ),
    "bank": PaymentMethod(
        id="bank",
        name="Bank Transfer / Wire",
        emoji="🏦",
        tos_key="bank_transfer"
    ),
    "paysafe": PaymentMethod(
        id="paysafe",
        name="PaySafe",
        emoji="🔒",
        tos_key="bank_transfer"
    ),
    "binance_giftcard": PaymentMethod(
        id="binance_giftcard",
        name="Binance Giftcard",
        emoji="🎁",
        tos_key="crypto"
    )
}

# Payment Methods for RECEIVING (Simplified - no balance/card distinction)
RECEIVE_PAYMENT_METHODS: Dict[str, PaymentMethod] = {
    "crypto": PaymentMethod(
        id="crypto",
        name="Cryptocurrency",
        emoji="💰",
        tos_key="crypto",
        requires_crypto_selection=True,
        is_crypto=True
    ),
    "paypal": PaymentMethod(
        id="paypal",
        name="PayPal",
        emoji="💳",
        tos_key="paypal_balance"
    ),
    "cashapp": PaymentMethod(
        id="cashapp",
        name="CashApp",
        emoji="💵",
        tos_key="cashapp"
    ),
    "applepay": PaymentMethod(
        id="applepay",
        name="Apple Pay",
        emoji="🍎",
        tos_key="applepay"
    ),
    "venmo": PaymentMethod(
        id="venmo",
        name="Venmo",
        emoji="💙",
        tos_key="venmo"
    ),
    "zelle": PaymentMethod(
        id="zelle",
        name="Zelle",
        emoji="⚡",
        tos_key="zelle"
    ),
    "chime": PaymentMethod(
        id="chime",
        name="Chime",
        emoji="💚",
        tos_key="chime"
    ),
    "revolut": PaymentMethod(
        id="revolut",
        name="Revolut",
        emoji="🔵",
        tos_key="bank_transfer"
    ),
    "skrill": PaymentMethod(
        id="skrill",
        name="Skrill",
        emoji="🔷",
        tos_key="bank_transfer"
    ),
    "bank": PaymentMethod(
        id="bank",
        name="Bank Transfer / Wire",
        emoji="🏦",
        tos_key="bank_transfer"
    ),
    "paysafe": PaymentMethod(
        id="paysafe",
        name="PaySafe",
        emoji="🔒",
        tos_key="bank_transfer"
    ),
    "binance_giftcard": PaymentMethod(
        id="binance_giftcard",
        name="Binance Giftcard",
        emoji="🎁",
        tos_key="crypto"
    )
}

# Backwards compatibility - use sending methods by default
PAYMENT_METHODS = SEND_PAYMENT_METHODS


# Crypto Assets (13 total)
CRYPTO_ASSETS: Dict[str, CryptoAsset] = {
    "BTC": CryptoAsset(
        symbol="BTC",
        name="Bitcoin",
        emoji="🟠",
        network="Bitcoin"
    ),
    "ETH": CryptoAsset(
        symbol="ETH",
        name="Ethereum",
        emoji="💎",
        network="Ethereum"
    ),
    "SOL": CryptoAsset(
        symbol="SOL",
        name="Solana",
        emoji="🟣",
        network="Solana"
    ),
    "LTC": CryptoAsset(
        symbol="LTC",
        name="Litecoin",
        emoji="⚪",
        network="Litecoin"
    ),
    "USDT-ETH": CryptoAsset(
        symbol="USDT-ETH",
        name="Tether (ERC-20)",
        emoji="₮",
        network="Ethereum"
    ),
    "USDT-SOL": CryptoAsset(
        symbol="USDT-SOL",
        name="Tether (Solana)",
        emoji="₮",
        network="Solana"
    ),
    "USDC-ETH": CryptoAsset(
        symbol="USDC-ETH",
        name="USD Coin (ERC-20)",
        emoji="🔵",
        network="Ethereum"
    ),
    "USDC-SOL": CryptoAsset(
        symbol="USDC-SOL",
        name="USD Coin (Solana)",
        emoji="🔵",
        network="Solana"
    ),
    "XRP": CryptoAsset(
        symbol="XRP",
        name="Ripple",
        emoji="⚫",
        network="XRP Ledger"
    ),
    "BNB": CryptoAsset(
        symbol="BNB",
        name="Binance Coin",
        emoji="🟡",
        network="BNB Chain"
    ),
    "XMR": CryptoAsset(
        symbol="XMR",
        name="Monero",
        emoji="🟠",
        network="Monero"
    ),
    "TRX": CryptoAsset(
        symbol="TRX",
        name="Tron",
        emoji="🔴",
        network="Tron"
    ),
    "OTHER": CryptoAsset(
        symbol="OTHER",
        name="Other (Specify in ticket)",
        emoji="❓",
        network="Various"
    )
}


# Fee Configuration
FEE_CONFIG = {
    "crypto_to_crypto_percentage": 5.0,  # 5% for crypto-to-crypto
    "standard_percentage": 10.0,  # 10% for amounts >= $40
    "minimum_fee": 4.0,  # $4 minimum fee for amounts < $40
    "minimum_amount": 4.0,  # Minimum transaction amount
    "maximum_amount": 100000.0  # Maximum transaction amount
}


# Ticket Status
TICKET_STATUS = {
    "awaiting_tos": "awaiting_tos",
    "tos_agreed": "tos_agreed",
    "claimed": "claimed",
    "in_progress": "in_progress",
    "client_sent": "client_sent",
    "completed": "completed",
    "cancelled": "cancelled",
    "expired": "expired"
}


# TOS System Configuration
TOS_CONFIG = {
    "timeout_minutes": 10,
    "reminder_minutes": [3, 6, 9]
}


def get_payment_method(method_id: str) -> PaymentMethod:
    """Get payment method by ID - checks both send and receive dictionaries"""
    # Try send methods first (detailed)
    method = SEND_PAYMENT_METHODS.get(method_id)
    if method:
        return method
    # Try receive methods (simplified)
    return RECEIVE_PAYMENT_METHODS.get(method_id)


def get_crypto_asset(symbol: str) -> CryptoAsset:
    """Get crypto asset by symbol"""
    return CRYPTO_ASSETS.get(symbol.upper())


def calculate_fee(amount_usd: float, send_method_id: str, receive_method_id: str) -> tuple[float, float, float]:
    """
    Calculate fee for exchange

    Args:
        amount_usd: Transaction amount in USD
        send_method_id: Sending payment method ID
        receive_method_id: Receiving payment method ID

    Returns:
        Tuple of (fee_amount, fee_percentage, receiving_amount)
    """
    send_method = get_payment_method(send_method_id)
    receive_method = get_payment_method(receive_method_id)

    # Crypto to crypto gets 5% fee
    if send_method.is_crypto and receive_method.is_crypto:
        fee_percentage = FEE_CONFIG["crypto_to_crypto_percentage"]
        fee_amount = amount_usd * (fee_percentage / 100)
    # Amounts >= $40 get 10% fee
    elif amount_usd >= 40.0:
        fee_percentage = FEE_CONFIG["standard_percentage"]
        fee_amount = amount_usd * (fee_percentage / 100)
    # Amounts < $40 get $4 minimum fee
    else:
        fee_amount = FEE_CONFIG["minimum_fee"]
        fee_percentage = (fee_amount / amount_usd) * 100

    receiving_amount = amount_usd - fee_amount

    return fee_amount, fee_percentage, receiving_amount


def validate_amount(amount: float) -> tuple[bool, str]:
    """
    Validate transaction amount

    Args:
        amount: Amount to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if amount < FEE_CONFIG["minimum_amount"]:
        return False, f"Minimum amount is ${FEE_CONFIG['minimum_amount']:.2f}"

    if amount > FEE_CONFIG["maximum_amount"]:
        return False, f"Maximum amount is ${FEE_CONFIG['maximum_amount']:,.2f}"

    return True, ""
