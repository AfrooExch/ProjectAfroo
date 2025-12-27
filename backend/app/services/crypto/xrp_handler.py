"""XRP (Ripple) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class XRPHandler(BaseCryptoHandler):
    """XRP cryptocurrency handler"""

    def get_chain(self) -> str:
        return "XRP"

    def get_required_confirmations(self) -> int:
        return 1  # XRP is instant

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate XRP address format
        if not address.startswith("r"):
            raise ValueError("Invalid XRP address format")

        if not (25 <= len(address) <= 35):
            raise ValueError("Invalid XRP address length")

        return address

    def get_decimals(self) -> int:
        return 6

    def get_min_withdrawal(self) -> float:
        return 1.0  # 1 XRP minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://xrpscan.com/tx/{tx_hash}"
