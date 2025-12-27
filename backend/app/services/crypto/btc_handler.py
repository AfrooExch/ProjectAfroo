"""Bitcoin (BTC) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class BTCHandler(BaseCryptoHandler):
    """Bitcoin cryptocurrency handler"""

    def get_chain(self) -> str:
        return "BTC"

    def get_required_confirmations(self) -> int:
        return 2  # BTC requires 2 confirmations

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate BTC address format
        if not address.startswith(("1", "3", "bc1")):
            raise ValueError("Invalid Bitcoin address format")

        if not (26 <= len(address) <= 62):
            raise ValueError("Invalid Bitcoin address length")

        return address

    def get_decimals(self) -> int:
        return 8

    def get_min_withdrawal(self) -> float:
        return 0.00002  # 0.00002 BTC minimum (~$1.76 at current prices)

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://www.blockchain.com/btc/tx/{tx_hash}"
