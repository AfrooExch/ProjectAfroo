"""
Base crypto handler - defines interface for all currency handlers
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseCryptoHandler(ABC):
    """Base class for cryptocurrency handlers"""

    @abstractmethod
    def get_chain(self) -> str:
        """
        Get Tatum chain identifier

        Returns:
            Chain identifier for Tatum API
        """
        pass

    @abstractmethod
    def get_required_confirmations(self) -> int:
        """
        Get number of confirmations required for deposits

        Returns:
            Number of confirmations needed
        """
        pass

    @abstractmethod
    def format_address(self, address: str) -> str:
        """
        Validate and format address

        Args:
            address: Wallet address to validate

        Returns:
            Formatted address

        Raises:
            ValueError: If address is invalid
        """
        pass

    def get_token_contract(self) -> Optional[str]:
        """
        Get token contract address (for ERC-20/SPL tokens)

        Returns:
            Contract address or None for native currencies
        """
        return None

    def is_token(self) -> bool:
        """Check if this is a token (vs native currency)"""
        return self.get_token_contract() is not None

    def get_decimals(self) -> int:
        """
        Get number of decimals for this currency

        Returns:
            Number of decimal places
        """
        return 8  # Default for most cryptocurrencies

    def get_min_withdrawal(self) -> float:
        """
        Get minimum withdrawal amount

        Returns:
            Minimum amount that can be withdrawn
        """
        return 0.00001  # Default minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        """
        Get blockchain explorer URL for transaction

        Args:
            tx_hash: Transaction hash

        Returns:
            URL to view transaction on explorer
        """
        return f"https://blockchain.info/tx/{tx_hash}"  # Override in subclasses
