"""Avalanche (AVAX) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class AVAXHandler(BaseCryptoHandler):
    """Avalanche cryptocurrency handler"""

    def get_chain(self) -> str:
        return "AVAX"

    def get_required_confirmations(self) -> int:
        return 1  # AVAX is very fast

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate AVAX address format (can be X-Chain, C-Chain, or P-Chain)
        if address.startswith("0x"):
            # C-Chain (EVM-compatible)
            if len(address) != 42:
                raise ValueError("Invalid Avalanche C-Chain address length")
        elif address.startswith(("X-", "P-", "C-")):
            # X-Chain or P-Chain
            if len(address) < 40:
                raise ValueError("Invalid Avalanche address length")
        else:
            raise ValueError("Invalid Avalanche address format")

        return address

    def get_decimals(self) -> int:
        return 18

    def get_min_withdrawal(self) -> float:
        return 0.01  # 0.01 AVAX minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://snowtrace.io/tx/{tx_hash}"
