"""
QR Code Generator Utility
Ported from V3, generates QR codes for cryptocurrency addresses

Supports:
- Bitcoin (BTC)
- Ethereum (ETH)
- Litecoin (LTC)
- Solana (SOL)
- Any ERC-20/SPL tokens (USDT, USDC, etc.)

Returns BytesIO object that can be sent as Discord file attachment
"""

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import qrcode library
try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    logger.warning("⚠️ QR code generation requires 'qrcode' package. Install with: pip install qrcode[pil]")


def generate_qr_code(
    address: str,
    asset: str = "CRYPTO",
    amount: Optional[float] = None,
    label: Optional[str] = None
) -> Optional[io.BytesIO]:
    """
    Generate QR code for cryptocurrency address

    Args:
        address: Crypto wallet address
        asset: Asset type (BTC, ETH, LTC, SOL, USDT, USDC, etc.)
        amount: Optional amount to include in QR code
        label: Optional label for the payment

    Returns:
        BytesIO object containing PNG image, or None if generation fails

    Example:
        ```python
        qr_buffer = generate_qr_code(
            address="bc1q...",
            asset="BTC",
            amount=0.001,
            label="Afroo Exchange"
        )

        if qr_buffer:
            file = discord.File(qr_buffer, filename="address_qr.png")
            await ctx.send(file=file)
        ```
    """
    if not QR_AVAILABLE:
        logger.error("QR code generation unavailable - qrcode package not installed")
        return None

    try:
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,  # Size of QR code (1 is smallest, 40 is largest)
            error_correction=ERROR_CORRECT_L,  # Error correction level
            box_size=10,  # Size of each box in pixels
            border=4,  # Border size in boxes
        )

        # Build URI based on asset type
        uri = _build_crypto_uri(address, asset.upper(), amount, label)

        # Add data and generate
        qr.add_data(uri)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to buffer
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        logger.debug(f"Generated QR code for {asset} address: {address[:8]}...")
        return img_buffer

    except Exception as e:
        logger.error(f"Failed to generate QR code for {address}: {e}")
        return None


def _build_crypto_uri(
    address: str,
    asset: str,
    amount: Optional[float] = None,
    label: Optional[str] = None
) -> str:
    """
    Build cryptocurrency payment URI

    Different cryptocurrencies use different URI formats:
    - Bitcoin: bitcoin:address?amount=0.001&label=Test
    - Ethereum: ethereum:address
    - Litecoin: litecoin:address
    - Solana: solana:address

    Args:
        address: Wallet address
        asset: Asset type
        amount: Optional amount
        label: Optional label

    Returns:
        Formatted URI string
    """
    # Determine URI scheme based on asset
    if asset in ["BTC", "BITCOIN"]:
        uri = f"bitcoin:{address}"
    elif asset in ["ETH", "ETHEREUM", "USDT", "USDC", "USDT-ETH", "USDC-ETH"]:
        uri = f"ethereum:{address}"
    elif asset in ["LTC", "LITECOIN"]:
        uri = f"litecoin:{address}"
    elif asset in ["SOL", "SOLANA", "USDT-SOL", "USDC-SOL"]:
        uri = f"solana:{address}"
    else:
        # Generic format for unknown assets
        uri = address

    # Add optional parameters
    params = []
    if amount is not None:
        params.append(f"amount={amount}")
    if label is not None:
        params.append(f"label={label}")

    if params:
        uri += "?" + "&".join(params)

    return uri


def generate_qr_for_btc(
    address: str,
    amount: Optional[float] = None,
    label: Optional[str] = None
) -> Optional[io.BytesIO]:
    """
    Generate QR code specifically for Bitcoin address

    Args:
        address: Bitcoin address (legacy, SegWit, or bech32)
        amount: Optional BTC amount
        label: Optional label

    Returns:
        BytesIO object with QR code image
    """
    return generate_qr_code(address, "BTC", amount, label)


def generate_qr_for_eth(
    address: str,
    label: Optional[str] = None
) -> Optional[io.BytesIO]:
    """
    Generate QR code specifically for Ethereum address

    Args:
        address: Ethereum address (0x...)
        label: Optional label

    Returns:
        BytesIO object with QR code image

    Note: Ethereum URIs don't typically include amount
    """
    return generate_qr_code(address, "ETH", None, label)


def generate_qr_for_ltc(
    address: str,
    amount: Optional[float] = None,
    label: Optional[str] = None
) -> Optional[io.BytesIO]:
    """
    Generate QR code specifically for Litecoin address

    Args:
        address: Litecoin address
        amount: Optional LTC amount
        label: Optional label

    Returns:
        BytesIO object with QR code image
    """
    return generate_qr_code(address, "LTC", amount, label)


def generate_qr_for_sol(
    address: str,
    amount: Optional[float] = None,
    label: Optional[str] = None
) -> Optional[io.BytesIO]:
    """
    Generate QR code specifically for Solana address

    Args:
        address: Solana address (base58)
        amount: Optional SOL amount
        label: Optional label

    Returns:
        BytesIO object with QR code image
    """
    return generate_qr_code(address, "SOL", amount, label)


def create_qr_discord_file(
    address: str,
    asset: str = "CRYPTO",
    amount: Optional[float] = None,
    label: Optional[str] = None,
    filename: Optional[str] = None
) -> Optional[object]:
    """
    Generate QR code and return as Discord File object ready to send

    Args:
        address: Crypto wallet address
        asset: Asset type
        amount: Optional amount
        label: Optional label
        filename: Custom filename (default: "address_qr.png")

    Returns:
        discord.File object or None if generation fails

    Example:
        ```python
        file = create_qr_discord_file(
            address="bc1q...",
            asset="BTC",
            filename="btc_deposit.png"
        )

        if file:
            await ctx.send("Scan this QR code to deposit:", file=file)
        ```
    """
    try:
        import discord
    except ImportError:
        logger.error("Discord library not available")
        return None

    # Generate QR code
    qr_buffer = generate_qr_code(address, asset, amount, label)
    if not qr_buffer:
        return None

    # Create Discord file
    if filename is None:
        filename = f"{asset.lower()}_address_qr.png"

    file = discord.File(qr_buffer, filename=filename)
    return file


# Export check function for other modules
def is_qr_available() -> bool:
    """
    Check if QR code generation is available

    Returns:
        True if qrcode library is installed, False otherwise
    """
    return QR_AVAILABLE
