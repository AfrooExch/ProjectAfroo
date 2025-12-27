"""Tron (TRX) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class TRXHandler(BaseCryptoHandler):
    """Tron cryptocurrency handler"""

    def get_chain(self) -> str:
        return "TRON"

    def get_required_confirmations(self) -> int:
        return 19  # Tron requires 19 confirmations

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate TRX address format
        if not address.startswith("T"):
            raise ValueError("Invalid Tron address format")

        if len(address) != 34:
            raise ValueError("Invalid Tron address length")

        return address

    def get_decimals(self) -> int:
        return 6

    def get_min_withdrawal(self) -> float:
        return 1.0  # 1 TRX minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://tronscan.org/#/transaction/{tx_hash}"
