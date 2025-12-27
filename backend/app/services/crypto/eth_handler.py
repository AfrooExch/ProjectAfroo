"""Ethereum (ETH) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class ETHHandler(BaseCryptoHandler):
    """Ethereum cryptocurrency handler"""

    def get_chain(self) -> str:
        return "ETH"

    def get_required_confirmations(self) -> int:
        return 12  # ETH requires 12 confirmations for safety

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate ETH address format
        if not address.startswith("0x"):
            raise ValueError("Invalid Ethereum address format")

        if len(address) != 42:
            raise ValueError("Invalid Ethereum address length")

        return address.lower()

    def get_decimals(self) -> int:
        return 18

    def get_min_withdrawal(self) -> float:
        return 0.0005  # 0.0005 ETH minimum (~$1.50 at current prices)

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://etherscan.io/tx/{tx_hash}"
