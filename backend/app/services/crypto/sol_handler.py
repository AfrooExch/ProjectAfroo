"""Solana (SOL) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class SOLHandler(BaseCryptoHandler):
    """Solana cryptocurrency handler"""

    def get_chain(self) -> str:
        return "SOL"

    def get_required_confirmations(self) -> int:
        return 1  # SOL is fast, 1 confirmation is sufficient

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate SOL address format
        if not (32 <= len(address) <= 44):
            raise ValueError("Invalid Solana address length")

        return address

    def get_decimals(self) -> int:
        return 9  # Solana uses lamports (9 decimals)

    def get_min_withdrawal(self) -> float:
        return 0.01  # 0.01 SOL minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://explorer.solana.com/tx/{tx_hash}"
