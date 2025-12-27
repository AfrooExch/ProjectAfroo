"""USDC on Ethereum (USDC-ETH) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class USDCETHHandler(BaseCryptoHandler):
    """USDC on Ethereum token handler"""

    def get_chain(self) -> str:
        return "ETH"

    def get_required_confirmations(self) -> int:
        return 12  # Ethereum confirmations

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate Ethereum address format
        if not address.startswith("0x"):
            raise ValueError("Invalid Ethereum address format")

        if len(address) != 42:
            raise ValueError("Invalid Ethereum address length")

        return address.lower()

    def get_token_contract(self) -> str:
        return "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC on Ethereum

    def get_decimals(self) -> int:
        return 6  # USDC has 6 decimals

    def get_min_withdrawal(self) -> float:
        return 5.0  # $5 minimum (due to ETH gas fees)

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://etherscan.io/tx/{tx_hash}"
