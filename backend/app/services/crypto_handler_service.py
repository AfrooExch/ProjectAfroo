"""
Crypto Handler Service - Blockchain operations via Tatum API
Handles wallet creation, balance checking, and transactions
Matches V3 implementation using Tatum API
"""

from typing import Optional, Dict, Tuple
from decimal import Decimal
import logging
import httpx

from app.core.config import settings
from app.core.security import encrypt_private_key, get_decrypted_private_key

logger = logging.getLogger(__name__)


class CryptoHandlerService:
    """Service for blockchain operations via Tatum"""

    # Blockchain mapping for Tatum API
    BLOCKCHAIN_MAP = {
        "BTC": "bitcoin",
        "LTC": "litecoin",
        "ETH": "ethereum",
        "SOL": "solana"
    }

    @staticmethod
    async def create_wallet(asset: str) -> Dict:
        """
        Create crypto wallet via Tatum API.
        Returns address and encrypted private key.

        Args:
            asset: Asset code (BTC, ETH, LTC, SOL)

        Returns:
            Dict with address and encrypted_private_key
        """
        try:
            blockchain = CryptoHandlerService.BLOCKCHAIN_MAP.get(asset)
            if not blockchain:
                raise ValueError(f"Unsupported asset: {asset}")

            async with httpx.AsyncClient() as client:
                headers = {
                    "x-api-key": settings.TATUM_API_KEY,
                    "Content-Type": "application/json"
                }

                # Generate wallet (mnemonic + xpub)
                wallet_url = f"{settings.TATUM_API_URL}/v3/{blockchain}/wallet"
                response = await client.get(wallet_url, headers=headers, timeout=30.0)

                if response.status_code != 200:
                    raise Exception(f"Failed to generate {asset} wallet: {response.status_code}")

                wallet_data = response.json()
                mnemonic = wallet_data["mnemonic"]
                xpub = wallet_data["xpub"]

                # Generate private key from mnemonic
                privkey_url = f"{settings.TATUM_API_URL}/v3/{blockchain}/wallet/priv"
                privkey_payload = {
                    "index": 0,
                    "mnemonic": mnemonic
                }

                response = await client.post(
                    privkey_url,
                    headers=headers,
                    json=privkey_payload,
                    timeout=30.0
                )

                if response.status_code != 200:
                    raise Exception(f"Failed to generate {asset} private key: {response.status_code}")

                privkey_data = response.json()
                private_key = privkey_data["key"]

                # Generate address from xpub
                address_url = f"{settings.TATUM_API_URL}/v3/{blockchain}/address/{xpub}/0"
                response = await client.get(address_url, headers=headers, timeout=30.0)

                if response.status_code != 200:
                    raise Exception(f"Failed to generate {asset} address: {response.status_code}")

                address_data = response.json()
                address = address_data["address"]

                # Encrypt private key before returning
                encrypted_private_key = encrypt_private_key(private_key)

                logger.info(f"Created {asset} wallet: {address}")

                return {
                    "asset": asset,
                    "address": address,
                    "encrypted_private_key": encrypted_private_key,
                    "xpub": xpub
                }

        except Exception as e:
            logger.error(f"Wallet creation failed for {asset}: {e}", exc_info=True)
            raise

    @staticmethod
    async def get_balance(asset: str, address: str) -> Dict:
        """
        Get balance for address via Tatum API.

        Args:
            asset: Asset code
            address: Blockchain address

        Returns:
            Dict with total, confirmed, unconfirmed balances
        """
        try:
            blockchain = CryptoHandlerService.BLOCKCHAIN_MAP.get(asset)
            if not blockchain:
                raise ValueError(f"Unsupported asset: {asset}")

            async with httpx.AsyncClient() as client:
                headers = {"x-api-key": settings.TATUM_API_KEY}

                url = f"{settings.TATUM_API_URL}/v3/{blockchain}/address/balance/{address}"
                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code != 200:
                    raise Exception(f"Failed to get {asset} balance: {response.status_code}")

                data = response.json()

                # Parse balance (format varies by blockchain)
                if asset == "BTC" or asset == "LTC":
                    incoming = float(data.get("incoming", 0))
                    outgoing = float(data.get("outgoing", 0))
                    incoming_pending = float(data.get("incomingPending", 0))
                    outgoing_pending = float(data.get("outgoingPending", 0))

                    confirmed = max(0.0, incoming - outgoing)
                    unconfirmed = max(0.0, incoming_pending - outgoing_pending)
                    total = confirmed + unconfirmed

                elif asset == "ETH":
                    balance = float(data.get("balance", 0))
                    confirmed = balance
                    unconfirmed = 0.0
                    total = balance

                elif asset == "SOL":
                    balance = float(data.get("balance", 0))
                    confirmed = balance
                    unconfirmed = 0.0
                    total = balance

                else:
                    total = float(data.get("balance", 0))
                    confirmed = total
                    unconfirmed = 0.0

                return {
                    "asset": asset,
                    "address": address,
                    "total": total,
                    "confirmed": confirmed,
                    "unconfirmed": unconfirmed
                }

        except Exception as e:
            logger.error(f"Balance check failed for {asset} {address}: {e}", exc_info=True)
            raise

    @staticmethod
    async def send_transaction(
        asset: str,
        from_address: str,
        to_address: str,
        amount: float,
        encrypted_private_key: str
    ) -> Tuple[bool, str]:
        """
        Send transaction via Tatum API.
        Follows V3 pattern - sends private key to Tatum for signing.

        Args:
            asset: Asset code
            from_address: Sender address
            to_address: Recipient address
            amount: Amount to send
            encrypted_private_key: Encrypted private key

        Returns:
            Tuple of (success, tx_hash or error_message)
        """
        try:
            blockchain = CryptoHandlerService.BLOCKCHAIN_MAP.get(asset)
            if not blockchain:
                return False, f"Unsupported asset: {asset}"

            # Decrypt private key
            private_key = get_decrypted_private_key(encrypted_private_key)

            async with httpx.AsyncClient() as client:
                headers = {
                    "x-api-key": settings.TATUM_API_KEY,
                    "Content-Type": "application/json"
                }

                # Build transaction payload
                if asset == "BTC":
                    # Bitcoin uses satoshis
                    satoshis = int(amount * 100_000_000)
                    payload = {
                        "fromAddress": [{
                            "address": from_address,
                            "privateKey": private_key
                        }],
                        "to": [{
                            "address": to_address,
                            "value": satoshis
                        }]
                    }

                elif asset == "LTC":
                    # Litecoin also uses satoshis
                    satoshis = int(amount * 100_000_000)
                    payload = {
                        "fromAddress": [{
                            "address": from_address,
                            "privateKey": private_key
                        }],
                        "to": [{
                            "address": to_address,
                            "value": satoshis
                        }]
                    }

                elif asset == "ETH":
                    payload = {
                        "fromPrivateKey": private_key,
                        "to": to_address,
                        "amount": str(amount),
                        "currency": "ETH"
                    }

                elif asset == "SOL":
                    payload = {
                        "fromPrivateKey": private_key,
                        "to": to_address,
                        "amount": str(amount)
                    }

                else:
                    return False, f"Transaction not implemented for {asset}"

                # Send transaction
                tx_url = f"{settings.TATUM_API_URL}/v3/{blockchain}/transaction"

                logger.info(
                    f"Sending {asset} transaction: {amount} "
                    f"from {from_address[:6]}... to {to_address[:6]}..."
                )

                response = await client.post(
                    tx_url,
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(
                        f"{asset} transaction failed: {response.status_code} - {error_text}"
                    )
                    return False, f"Transaction failed: {error_text}"

                tx_data = response.json()
                tx_hash = tx_data.get("txId")

                if not tx_hash:
                    return False, "No transaction hash returned"

                logger.info(f"{asset} transaction successful: {tx_hash}")

                return True, tx_hash

        except Exception as e:
            logger.error(f"Transaction failed for {asset}: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def get_transaction(asset: str, tx_hash: str) -> Optional[Dict]:
        """
        Get transaction details via Tatum API.

        Args:
            asset: Asset code
            tx_hash: Transaction hash

        Returns:
            Transaction data dict or None
        """
        try:
            blockchain = CryptoHandlerService.BLOCKCHAIN_MAP.get(asset)
            if not blockchain:
                return None

            # Map to Tatum chain format
            chain_map = {
                "BTC": "bitcoin-mainnet",
                "LTC": "litecoin-mainnet",
                "ETH": "ethereum-mainnet",
                "SOL": "solana-mainnet"
            }

            chain = chain_map.get(asset)
            if not chain:
                return None

            async with httpx.AsyncClient() as client:
                headers = {"x-api-key": settings.TATUM_API_KEY}

                url = f"{settings.TATUM_API_URL}/v3/blockchain/transaction/{chain}/{tx_hash}"
                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code != 200:
                    return None

                return response.json()

        except Exception as e:
            logger.error(f"Get transaction failed for {asset} {tx_hash}: {e}")
            return None


# Convenience functions
async def create_wallet(asset: str) -> Dict:
    """Create crypto wallet"""
    return await CryptoHandlerService.create_wallet(asset)


async def get_balance(asset: str, address: str) -> Dict:
    """Get wallet balance"""
    return await CryptoHandlerService.get_balance(asset, address)


async def send_transaction(
    asset: str,
    from_address: str,
    to_address: str,
    amount: float,
    encrypted_private_key: str
) -> Tuple[bool, str]:
    """Send blockchain transaction"""
    return await CryptoHandlerService.send_transaction(
        asset, from_address, to_address, amount, encrypted_private_key
    )
