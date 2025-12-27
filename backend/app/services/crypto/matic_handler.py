"""Polygon (MATIC) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class MATICHandler(BaseCryptoHandler):
    """Polygon cryptocurrency handler"""

    def get_chain(self) -> str:
        return "MATIC"

    def get_required_confirmations(self) -> int:
        return 128  # Polygon requires many confirmations

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate MATIC address format (EVM-compatible)
        if not address.startswith("0x"):
            raise ValueError("Invalid Polygon address format")

        if len(address) != 42:
            raise ValueError("Invalid Polygon address length")

        return address.lower()

    def get_decimals(self) -> int:
        return 18

    def get_min_withdrawal(self) -> float:
        return 0.1  # 0.1 MATIC minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://polygonscan.com/tx/{tx_hash}"
