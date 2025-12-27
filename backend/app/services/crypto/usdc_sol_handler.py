"""USDC on Solana (USDC-SOL) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class USDCSOLHandler(BaseCryptoHandler):
    """USDC on Solana token handler"""

    def get_chain(self) -> str:
        return "SOL"

    def get_required_confirmations(self) -> int:
        return 1  # Solana is fast

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate Solana address format
        if not (32 <= len(address) <= 44):
            raise ValueError("Invalid Solana address length")

        return address

    def get_token_contract(self) -> str:
        return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC on Solana

    def get_decimals(self) -> int:
        return 6  # USDC has 6 decimals

    def get_min_withdrawal(self) -> float:
        return 1.0  # $1 minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://explorer.solana.com/tx/{tx_hash}"
