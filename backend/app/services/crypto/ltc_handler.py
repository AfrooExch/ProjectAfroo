"""Litecoin (LTC) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class LTCHandler(BaseCryptoHandler):
    """Litecoin cryptocurrency handler"""

    def get_chain(self) -> str:
        return "LTC"

    def get_required_confirmations(self) -> int:
        return 6  # LTC requires 6 confirmations

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate LTC address format
        if not address.startswith(("L", "M", "3", "ltc1")):
            raise ValueError("Invalid Litecoin address format")

        if not (26 <= len(address) <= 62):
            raise ValueError("Invalid Litecoin address length")

        return address

    def get_decimals(self) -> int:
        return 8

    def get_min_withdrawal(self) -> float:
        return 0.001  # 0.001 LTC minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://blockchair.com/litecoin/transaction/{tx_hash}"
