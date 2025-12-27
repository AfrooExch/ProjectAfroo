"""
Payment Methods Configuration for V4
Defines all payment methods, their properties, TOS templates, and risk levels
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PaymentMethod:
    """Payment method configuration"""
    value: str  # Internal value (e.g., "paypal_balance")
    display_name: str  # Display name (e.g., "PayPal Balance")
    category: str  # "crypto", "fiat", "giftcard"
    emoji_fallback: str  # Fallback emoji if custom emoji not available
    emoji_name: Optional[str] = None  # Custom emoji name from config
    tos_template: Optional[str] = None  # TOS message template
    risk_level: str = "medium"  # "low", "medium", "high"
    min_amount: float = 4.00  # Minimum transaction amount
    fee_multiplier: float = 1.0  # Fee adjustment (1.0 = normal, 1.2 = 20% higher)


# ============================================================================
# PAYMENT METHOD DEFINITIONS
# ============================================================================

PAYMENT_METHODS: Dict[str, PaymentMethod] = {
    # Crypto
    "crypto": PaymentMethod(
        value="crypto",
        display_name="Crypto",
        category="crypto",
        emoji_fallback="🟠",
        emoji_name="crypto",
        tos_template=None,  # Will show crypto-specific TOS
        risk_level="low",
        fee_multiplier=0.95  # Lower fees for crypto
    ),

    # PayPal
    "paypal_balance": PaymentMethod(
        value="paypal_balance",
        display_name="PayPal Balance",
        category="fiat",
        emoji_fallback="💳",
        emoji_name="paypal",
        tos_template=(
            "**PayPal Balance Terms:**\n"
            "> • You must send using your **PayPal balance only** — no cards or linked bank accounts\n"
            "> • Only **Friends & Family** payments are accepted — **no Goods & Services**\n"
            "> • Include a **screenshot of the payment confirmation** after sending\n"
            "> • Payments must be sent from an **account registered in your name**\n"
            "> • Any **chargebacks, disputes, or unauthorized transactions** will result in a **permanent ban**"
        ),
        risk_level="medium"
    ),
    "paypal_card": PaymentMethod(
        value="paypal_card",
        display_name="PayPal Card",
        category="fiat",
        emoji_fallback="💳",
        emoji_name="paypal",
        tos_template=(
            "**PayPal Card Terms:**\n"
            "> • You must send using a **card linked directly to your PayPal account**\n"
            "> • Card-based payments carry **higher fees** due to increased chargeback risk\n"
            "> • Only **Friends & Family** payments are accepted — no Goods & Services\n"
            "> • Include a **screenshot of the payment confirmation** after sending\n"
            "> • Payments must be sent from an **account registered in your name**\n"
            "> • Any **chargebacks, disputes, or unauthorized transactions** will result in a **permanent ban**"
        ),
        risk_level="high",
        fee_multiplier=1.25  # Higher fees for card payments
    ),

    # CashApp
    "cashapp_balance": PaymentMethod(
        value="cashapp_balance",
        display_name="CashApp Balance",
        category="fiat",
        emoji_fallback="💵",
        emoji_name="cashapp",
        tos_template=(
            "**CashApp Balance Terms:**\n"
            "> • You must send from your **CashApp balance only**\n"
            "> • Do **not** use any external funding sources (cards/banks)\n"
            "> • Include your **$Cashtag** in the ticket for verification\n"
            "> • Provide a **screenshot of payment confirmation** after sending\n"
            "> • Any **chargebacks or disputes** will result in a **permanent ban**"
        ),
        risk_level="medium"
    ),
    "cashapp_card": PaymentMethod(
        value="cashapp_card",
        display_name="CashApp Card",
        category="fiat",
        emoji_fallback="💵",
        emoji_name="cashapp",
        tos_template=(
            "**CashApp Card Terms:**\n"
            "> • You must send using a **card linked to your CashApp account**\n"
            "> • Card payments have **higher fees** due to increased chargeback risk\n"
            "> • Include your **$Cashtag** in the ticket for verification\n"
            "> • Provide a **screenshot of payment confirmation** after sending\n"
            "> • Any **chargebacks, disputes, or third-party cards** will result in a **permanent ban**"
        ),
        risk_level="high",
        fee_multiplier=1.25
    ),

    # Venmo
    "venmo_balance": PaymentMethod(
        value="venmo_balance",
        display_name="Venmo Balance",
        category="fiat",
        emoji_fallback="💰",
        emoji_name="venmo",
        tos_template=(
            "**Venmo Balance Terms:**\n"
            "> • You must send from your **Venmo balance only**\n"
            "> • Do **not** use external funding sources (cards/banks)\n"
            "> • Provide your **@Username** for payment verification\n"
            "> • Upload a **screenshot of payment confirmation** after sending\n"
            "> • Any **disputes or chargebacks** will result in a **permanent ban**"
        ),
        risk_level="medium"
    ),

    # Zelle
    "zelle": PaymentMethod(
        value="zelle",
        display_name="Zelle",
        category="fiat",
        emoji_fallback="💸",
        emoji_name="zelle",
        tos_template=(
            "**Zelle Terms:**\n"
            "> • Zelle payments are typically **irreversible** once sent\n"
            "> • Provide your **phone number or email** registered with Zelle\n"
            "> • Upload a **screenshot of payment confirmation** after sending\n"
            "> • Bank-initiated chargebacks will result in a **permanent ban**"
        ),
        risk_level="low"
    ),

    # Chime
    "chime": PaymentMethod(
        value="chime",
        display_name="Chime",
        category="fiat",
        emoji_fallback="💳",
        emoji_name="chime",
        tos_template=(
            "**Chime Terms:**\n"
            "> • Payments must be sent from your **Chime account**\n"
            "> • Provide your **$ChimeTag** or email for payment\n"
            "> • Upload a **screenshot of payment confirmation** after sending\n"
            "> • Any **disputes or chargebacks** will result in a **permanent ban**"
        ),
        risk_level="medium"
    ),

    # Revolut
    "revolut": PaymentMethod(
        value="revolut",
        display_name="Revolut",
        category="fiat",
        emoji_fallback="🏦",
        emoji_name="revolut",
        tos_template=(
            "**Revolut Terms:**\n"
            "> • Payments must be sent from your **Revolut account**\n"
            "> • Provide your **@Username** or phone number for payment\n"
            "> • Upload a **screenshot of payment confirmation** after sending\n"
            "> • Any **disputes or chargebacks** will result in a **permanent ban**"
        ),
        risk_level="medium"
    ),

    # Gift Cards
    "amazon_gc": PaymentMethod(
        value="amazon_gc",
        display_name="Amazon Gift Card",
        category="giftcard",
        emoji_fallback="🎁",
        emoji_name="amazon",
        tos_template=(
            "**Amazon Gift Card Terms:**\n"
            "> • Gift cards must be **legitimate and unused**\n"
            "> • You will be asked to **provide the gift card code** after claiming\n"
            "> • Screenshot of the gift card **balance confirmation** required\n"
            "> • Fraudulent or stolen gift cards will result in a **permanent ban**"
        ),
        risk_level="high",
        min_amount=10.00
    ),
    "steam_gc": PaymentMethod(
        value="steam_gc",
        display_name="Steam Gift Card",
        category="giftcard",
        emoji_fallback="🎮",
        emoji_name="steam",
        tos_template=(
            "**Steam Gift Card Terms:**\n"
            "> • Gift cards must be **legitimate and unused**\n"
            "> • You will provide the **gift card code** after claiming\n"
            "> • Screenshot of the gift card required\n"
            "> • Fraudulent or stolen gift cards will result in a **permanent ban**"
        ),
        risk_level="high",
        min_amount=10.00
    ),

    # Bank Transfer
    "bank_transfer": PaymentMethod(
        value="bank_transfer",
        display_name="Bank Transfer",
        category="fiat",
        emoji_fallback="🏦",
        emoji_name="bank",
        tos_template=(
            "**Bank Transfer Terms:**\n"
            "> • Transfers must be from **your own bank account**\n"
            "> • Provide your **account details** for verification\n"
            "> • Bank transfers can take **1-3 business days**\n"
            "> • Upload **proof of transfer** after sending\n"
            "> • Any **chargebacks or disputes** will result in a **permanent ban**"
        ),
        risk_level="low"
    ),

    # Other
    "other_fiat": PaymentMethod(
        value="other_fiat",
        display_name="Other Fiat Method",
        category="fiat",
        emoji_fallback="💵",
        tos_template=(
            "**Other Payment Method Terms:**\n"
            "> • Discuss payment method details with your exchanger\n"
            "> • Provide **screenshots and proof** of payment after sending\n"
            "> • Any **disputes or chargebacks** will result in a **permanent ban**"
        ),
        risk_level="medium"
    ),
}

# Crypto assets
CRYPTO_ASSETS: Dict[str, PaymentMethod] = {
    "bitcoin": PaymentMethod(
        value="bitcoin",
        display_name="Bitcoin (BTC)",
        category="crypto",
        emoji_fallback="₿",
        emoji_name="bitcoin",
        tos_template=(
            "**Bitcoin Terms:**\n"
            "> • Transactions require **1+ network confirmations**\n"
            "> • Network fees vary based on congestion\n"
            "> • Double-check wallet addresses before sending\n"
            "> • Bitcoin transactions are **irreversible** once confirmed"
        ),
        risk_level="low",
        min_amount=10.00
    ),
    "ethereum": PaymentMethod(
        value="ethereum",
        display_name="Ethereum (ETH)",
        category="crypto",
        emoji_fallback="Ξ",
        emoji_name="eth",
        tos_template=(
            "**Ethereum Terms:**\n"
            "> • Transactions require **12+ network confirmations**\n"
            "> • Gas fees can be high during network congestion\n"
            "> • Double-check wallet addresses before sending\n"
            "> • Ethereum transactions are **irreversible** once confirmed"
        ),
        risk_level="low",
        min_amount=10.00
    ),
    "litecoin": PaymentMethod(
        value="litecoin",
        display_name="Litecoin (LTC)",
        category="crypto",
        emoji_fallback="Ł",
        emoji_name="ltc",
        tos_template=(
            "**Litecoin Terms:**\n"
            "> • Transactions require **1+ network confirmations**\n"
            "> • Network fees are typically very low\n"
            "> • Double-check wallet addresses before sending\n"
            "> • Litecoin transactions are **irreversible** once confirmed"
        ),
        risk_level="low",
        min_amount=10.00
    ),
    "solana": PaymentMethod(
        value="solana",
        display_name="Solana (SOL)",
        category="crypto",
        emoji_fallback="◎",
        emoji_name="sol",
        tos_template=(
            "**Solana Terms:**\n"
            "> • Transactions require **1+ network confirmations**\n"
            "> • Network fees are extremely low (~$0.0001)\n"
            "> • Double-check wallet addresses before sending\n"
            "> • Solana transactions are **irreversible** once confirmed"
        ),
        risk_level="low",
        min_amount=5.00
    ),
    "usdt_sol": PaymentMethod(
        value="usdt_sol",
        display_name="USDT (Solana)",
        category="crypto",
        emoji_fallback="₮",
        emoji_name="usdt",
        tos_template=(
            "**USDT (Solana) Terms:**\n"
            "> • This is **USDT on the Solana network**\n"
            "> • Transactions require **1+ network confirmations**\n"
            "> • Network fees are extremely low (~$0.0001)\n"
            "> • **Ensure your wallet supports Solana USDT** before sending\n"
            "> • Sending to wrong network will result in **permanent loss of funds**"
        ),
        risk_level="low",
        min_amount=5.00
    ),
    "usdt_eth": PaymentMethod(
        value="usdt_eth",
        display_name="USDT (Ethereum)",
        category="crypto",
        emoji_fallback="₮",
        emoji_name="usdt",
        tos_template=(
            "**USDT (Ethereum) Terms:**\n"
            "> • This is **USDT on the Ethereum network (ERC-20)**\n"
            "> • Transactions require **12+ network confirmations**\n"
            "> • Gas fees can be high ($5-50 depending on network congestion)\n"
            "> • **Ensure your wallet supports Ethereum USDT** before sending\n"
            "> • Sending to wrong network will result in **permanent loss of funds**"
        ),
        risk_level="low",
        min_amount=10.00
    ),
    "usdc_sol": PaymentMethod(
        value="usdc_sol",
        display_name="USDC (Solana)",
        category="crypto",
        emoji_fallback="$",
        emoji_name="usdc",
        tos_template=(
            "**USDC (Solana) Terms:**\n"
            "> • This is **USDC on the Solana network**\n"
            "> • Transactions require **1+ network confirmations**\n"
            "> • Network fees are extremely low (~$0.0001)\n"
            "> • **Ensure your wallet supports Solana USDC** before sending\n"
            "> • Sending to wrong network will result in **permanent loss of funds**"
        ),
        risk_level="low",
        min_amount=5.00
    ),
    "usdc_eth": PaymentMethod(
        value="usdc_eth",
        display_name="USDC (Ethereum)",
        category="crypto",
        emoji_fallback="$",
        emoji_name="usdc",
        tos_template=(
            "**USDC (Ethereum) Terms:**\n"
            "> • This is **USDC on the Ethereum network (ERC-20)**\n"
            "> • Transactions require **12+ network confirmations**\n"
            "> • Gas fees can be high ($5-50 depending on network congestion)\n"
            "> • **Ensure your wallet supports Ethereum USDC** before sending\n"
            "> • Sending to wrong network will result in **permanent loss of funds**"
        ),
        risk_level="low",
        min_amount=10.00
    ),
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_payment_method(value: str) -> Optional[PaymentMethod]:
    """Get payment method by value"""
    return PAYMENT_METHODS.get(value)


def get_crypto_asset(value: str) -> Optional[PaymentMethod]:
    """Get crypto asset by value"""
    return CRYPTO_ASSETS.get(value)


def format_payment_method_display(value: str, crypto_value: Optional[str] = None) -> str:
    """Format payment method for display"""
    if value == "crypto" and crypto_value:
        asset = get_crypto_asset(crypto_value)
        return asset.display_name if asset else crypto_value.upper()

    method = get_payment_method(value)
    if method:
        return method.display_name

    asset = get_crypto_asset(value)
    if asset:
        return asset.display_name

    return value.replace("_", " ").title()


def get_payment_methods_for_selection(config_emojis: Optional[Dict] = None) -> List[Dict]:
    """Get payment methods formatted for Discord selection"""
    methods = []

    # Add crypto option
    methods.append({
        "label": "Crypto",
        "value": "crypto",
        "description": "Bitcoin, Ethereum, Solana, USDT, USDC, etc.",
        "emoji": config_emojis.get("crypto") if config_emojis else "🟠"
    })

    # Add fiat methods
    for key, method in PAYMENT_METHODS.items():
        if method.category == "fiat":
            emoji = config_emojis.get(method.emoji_name) if config_emojis and method.emoji_name else method.emoji_fallback
            methods.append({
                "label": method.display_name,
                "value": method.value,
                "description": f"{method.category.title()} payment method",
                "emoji": emoji
            })

    # Add gift cards
    for key, method in PAYMENT_METHODS.items():
        if method.category == "giftcard":
            emoji = config_emojis.get(method.emoji_name) if config_emojis and method.emoji_name else method.emoji_fallback
            methods.append({
                "label": method.display_name,
                "value": method.value,
                "description": f"Min ${method.min_amount:.0f}",
                "emoji": emoji
            })

    return methods


def get_crypto_assets_for_selection(config_emojis: Optional[Dict] = None) -> List[Dict]:
    """Get crypto assets formatted for Discord selection"""
    assets = []

    for key, asset in CRYPTO_ASSETS.items():
        emoji = config_emojis.get(asset.emoji_name) if config_emojis and asset.emoji_name else asset.emoji_fallback
        assets.append({
            "label": asset.display_name,
            "value": asset.value,
            "description": f"Min ${asset.min_amount:.0f}",
            "emoji": emoji
        })

    return assets


def get_tos_for_method(method_value: str, crypto_value: Optional[str] = None) -> str:
    """Get TOS template for payment method"""
    if method_value == "crypto" and crypto_value:
        asset = get_crypto_asset(crypto_value)
        return asset.tos_template if asset and asset.tos_template else "No specific terms for this cryptocurrency."

    method = get_payment_method(method_value)
    if method and method.tos_template:
        return method.tos_template

    asset = get_crypto_asset(method_value)
    if asset and asset.tos_template:
        return asset.tos_template

    return "No specific terms for this payment method. Follow general exchange guidelines."
