"""Dogecoin (DOGE) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class DOGEHandler(BaseCryptoHandler):
    """Dogecoin cryptocurrency handler"""

    def get_chain(self) -> str:
        return "DOGE"

    def get_required_confirmations(self) -> int:
        return 6  # DOGE requires 6 confirmations

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate DOGE address format
        if not address.startswith(("D", "A", "9")):
            raise ValueError("Invalid Dogecoin address format")

        if not (26 <= len(address) <= 34):
            raise ValueError("Invalid Dogecoin address length")

        return address

    def get_decimals(self) -> int:
        return 8

    def get_min_withdrawal(self) -> float:
        return 1.0  # 1 DOGE minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://dogechain.info/tx/{tx_hash}"
