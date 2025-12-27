"""USDT on Ethereum (USDT-ETH) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class USDTETHHandler(BaseCryptoHandler):
    """USDT on Ethereum token handler"""

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
        return "0xdac17f958d2ee523a2206206994597c13d831ec7"  # USDT on Ethereum

    def get_decimals(self) -> int:
        return 6  # USDT has 6 decimals

    def get_min_withdrawal(self) -> float:
        return 5.0  # $5 minimum (due to ETH gas fees)

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://etherscan.io/tx/{tx_hash}"
