"""
Tatum API Service - Blockchain Operations
Full integration with Tatum API for wallet generation, transactions, and monitoring
"""

import httpx
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


def redact_sensitive_fields(data: Dict) -> Dict:
    """
    Redact sensitive fields from data before logging.
    SECURITY: Never log private keys, secrets, or mnemonics!

    Args:
        data: Dictionary that may contain sensitive fields

    Returns:
        Sanitized copy with sensitive fields redacted
    """
    if not isinstance(data, dict):
        return data

    sensitive_keys = ["privateKey", "private_key", "fromPrivateKey", "secret", "mnemonic", "fromSecret"]
    sanitized = data.copy()

    for key in sensitive_keys:
        if key in sanitized:
            sanitized[key] = "***REDACTED***"

    # Recursively redact nested dicts and lists
    for key, value in sanitized.items():
        if isinstance(value, dict):
            sanitized[key] = redact_sensitive_fields(value)
        elif isinstance(value, list):
            sanitized[key] = [redact_sensitive_fields(item) if isinstance(item, dict) else item for item in value]

    return sanitized


async def try_solana_rpc_with_fallback(client: httpx.AsyncClient, payload: Dict) -> Dict:
    """
    Try multiple free Solana RPC endpoints with fallback on rate limit (429)

    Args:
        client: HTTPX async client
        payload: JSON-RPC payload

    Returns:
        JSON-RPC response

    Raises:
        Exception if all RPCs fail
    """
    # Free Solana RPC endpoints (no auth required)
    rpc_endpoints = [
        "https://api.mainnet-beta.solana.com",  # Official (has rate limits)
        "https://rpc.ankr.com/solana",  # Ankr free tier
        "https://solana-api.projectserum.com",  # Serum/OpenBook
        "https://solana.public-rpc.com",  # Public RPC
    ]

    last_error = None

    for rpc_url in rpc_endpoints:
        try:
            response = await client.post(rpc_url, json=payload, timeout=10.0)

            # If rate limited, try next endpoint
            if response.status_code == 429:
                logger.warning(f"Solana RPC rate limited: {rpc_url}, trying next...")
                last_error = f"Rate limited on {rpc_url}"
                continue

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.warning(f"Solana RPC {rpc_url} failed: {e}, trying next...")
            last_error = str(e)
            continue

    # All RPCs failed
    error_msg = f"All Solana RPCs failed. Last error: {last_error}"
    logger.error(error_msg)
    raise Exception(error_msg)


class TatumService:
    """
    Service for interacting with Tatum API for blockchain operations.

    Supports: BTC, ETH, LTC, SOL, and SPL tokens (USDT/USDC on Solana/Ethereum)
    """

    BASE_URL = "https://api.tatum.io/v3"

    BLOCKCHAIN_ENDPOINTS = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "LTC": "litecoin",
        "SOL": "solana",
        "XRP": "xrp",
        "BNB": "bsc",  # Fixed: BSC (Binance Smart Chain), not BNB Beacon Chain
        "TRX": "tron",
        "MATIC": "polygon",
        "AVAX": "avalanche",  # Fixed: was "avax", correct is "avalanche"
        "DOGE": "dogecoin",
        "USDT-ETH": "ethereum/erc20",
        "USDC-ETH": "ethereum/erc20",
        "USDT-SOL": "solana/spl",
        "USDC-SOL": "solana/spl"
    }

    # Token contract addresses
    TOKEN_CONTRACTS = {
        "USDT-ETH": "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT on Ethereum
        "USDC-ETH": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC on Ethereum
        "USDT-SOL": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT on Solana
        "USDC-SOL": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"   # USDC on Solana
    }

    @staticmethod
    def _get_headers() -> Dict[str, str]:
        """Get Tatum API headers"""
        return {
            "x-api-key": settings.TATUM_API_KEY,
            "Content-Type": "application/json"
        }

    @staticmethod
    async def generate_wallet(blockchain: str) -> Dict[str, str]:
        """
        Generate new wallet for specified blockchain.

        Args:
            blockchain: Asset code (BTC, ETH, SOL, etc.)

        Returns:
            Dict with address and private_key
        """
        try:
            asset = blockchain.upper()

            # For SPL/ERC20 tokens, use parent chain for wallet generation
            if asset in ["USDC-SOL", "USDT-SOL", "USDC-ETH", "USDT-ETH"]:
                base_chain = "solana" if "SOL" in asset else "ethereum"
                logger.info(f"Token wallet {asset}: using {base_chain} generation")
                endpoint = base_chain
            else:
                endpoint = TatumService.BLOCKCHAIN_ENDPOINTS.get(asset)

            if not endpoint:
                raise ValueError(f"Unsupported blockchain: {blockchain}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: Generate wallet (get mnemonic/xpub)
                # XRP uses /account endpoint instead of /wallet
                if asset == "XRP":
                    wallet_url = f"{TatumService.BASE_URL}/{endpoint}/account"
                else:
                    wallet_url = f"{TatumService.BASE_URL}/{endpoint}/wallet"

                response = await client.get(wallet_url, headers=TatumService._get_headers())
                response.raise_for_status()

                wallet_data = response.json()

                # Debug: Log response for XRP, BNB, AVAX
                if asset in ["XRP", "BNB", "AVAX"]:
                    logger.info(f"[DEBUG] {asset} wallet response: {wallet_data}")

                # Step 2: Generate private key from mnemonic
                if asset in ["BTC", "LTC", "ETH", "DOGE", "TRX", "MATIC", "BNB", "AVAX"] or "ETH" in asset:
                    # Bitcoin-based, Ethereum, DOGE, TRX, MATIC, and Ethereum tokens (use mnemonic/xpub pattern)
                    mnemonic = wallet_data["mnemonic"]
                    xpub = wallet_data["xpub"]

                    # Get private key
                    privkey_url = f"{TatumService.BASE_URL}/{endpoint}/wallet/priv"
                    privkey_payload = {
                        "index": 0,
                        "mnemonic": mnemonic
                    }

                    priv_response = await client.post(
                        privkey_url,
                        headers=TatumService._get_headers(),
                        json=privkey_payload
                    )
                    priv_response.raise_for_status()

                    privkey_data = priv_response.json()
                    private_key = privkey_data["key"]

                    # Get address
                    address_url = f"{TatumService.BASE_URL}/{endpoint}/address/{xpub}/0"
                    addr_response = await client.get(
                        address_url,
                        headers=TatumService._get_headers()
                    )
                    addr_response.raise_for_status()

                    address_data = addr_response.json()
                    address = address_data["address"]

                else:
                    # SOL, XRP (direct wallet generation)
                    # XRP uses 'secret' instead of 'privateKey'
                    address = wallet_data.get("address")
                    private_key = wallet_data.get("privateKey") or wallet_data.get("secret")

                    if not address or not private_key:
                        raise ValueError(f"Invalid wallet data for {asset}: missing address or privateKey/secret")

                logger.info(f"Generated wallet for {blockchain}: {address[:10]}...")

                return {
                    "address": address,
                    "private_key": private_key
                }

        except Exception as e:
            logger.error(f"Failed to generate {blockchain} wallet: {e}", exc_info=True)
            raise

    @staticmethod
    async def get_balance(blockchain: str, address: str) -> Dict[str, float]:
        """
        Get balance for an address.

        Args:
            blockchain: Asset code (BTC, ETH, SOL, USDT-ETH, etc.)
            address: Wallet address

        Returns:
            Dict with total, confirmed, unconfirmed balances
        """
        try:
            asset = blockchain.upper()

            async with httpx.AsyncClient(timeout=30.0) as client:
                if asset in ["BTC", "LTC", "DOGE"]:
                    # Bitcoin-based UTXO chains: Get UTXO balance
                    endpoint = TatumService.BLOCKCHAIN_ENDPOINTS.get(asset)
                    balance_url = f"{TatumService.BASE_URL}/{endpoint}/address/balance/{address}"

                    response = await client.get(balance_url, headers=TatumService._get_headers())
                    response.raise_for_status()

                    data = response.json()

                    incoming = float(data.get("incoming", 0))
                    outgoing = float(data.get("outgoing", 0))
                    incoming_pending = float(data.get("incomingPending", 0))
                    outgoing_pending = float(data.get("outgoingPending", 0))

                    confirmed = max(0.0, incoming - outgoing)
                    unconfirmed = max(0.0, incoming_pending - outgoing_pending)
                    total = confirmed + unconfirmed

                    return {
                        "total": total,
                        "confirmed": confirmed,
                        "unconfirmed": unconfirmed
                    }

                elif asset == "ETH":
                    # Ethereum native balance
                    balance_url = f"{TatumService.BASE_URL}/ethereum/account/balance/{address}"

                    response = await client.get(balance_url, headers=TatumService._get_headers())
                    response.raise_for_status()

                    data = response.json()
                    # Tatum already returns balance in ETH, not Wei
                    balance_eth = float(data.get("balance", 0))

                    return {
                        "total": balance_eth,
                        "confirmed": balance_eth,
                        "unconfirmed": 0.0
                    }

                elif asset == "SOL":
                    # Solana native balance
                    balance_url = f"{TatumService.BASE_URL}/solana/account/balance/{address}"

                    response = await client.get(balance_url, headers=TatumService._get_headers())
                    response.raise_for_status()

                    data = response.json()
                    # Tatum already returns balance in SOL, not lamports
                    balance_sol = float(data.get("balance", 0))

                    return {
                        "total": balance_sol,
                        "confirmed": balance_sol,
                        "unconfirmed": 0.0
                    }

                elif asset in ["XRP", "BNB", "TRX", "MATIC", "AVAX"]:
                    # Other blockchain native balances (account-based)
                    endpoint = TatumService.BLOCKCHAIN_ENDPOINTS.get(asset)

                    # XRP and TRX use account endpoint instead of balance endpoint
                    if asset == "XRP":
                        balance_url = f"{TatumService.BASE_URL}/{endpoint}/account/{address}"
                        response = await client.get(balance_url, headers=TatumService._get_headers())

                        if response.status_code == 404:
                            logger.warning(f"XRP address {address[:10]}... not found (404)")
                            return {"total": 0.0, "confirmed": 0.0, "unconfirmed": 0.0, "not_activated": True}

                        response.raise_for_status()
                        data = response.json()
                        balance_drops = float(data.get("account_data", {}).get("Balance", 0))
                        balance_xrp = balance_drops / 1e6  # Convert drops to XRP

                        return {"total": balance_xrp, "confirmed": balance_xrp, "unconfirmed": 0.0}

                    elif asset == "TRX":
                        balance_url = f"{TatumService.BASE_URL}/{endpoint}/account/{address}"
                        response = await client.get(balance_url, headers=TatumService._get_headers())

                        if response.status_code == 404:
                            logger.warning(f"TRX address {address[:10]}... not found (404)")
                            return {"total": 0.0, "confirmed": 0.0, "unconfirmed": 0.0, "not_activated": True}

                        response.raise_for_status()
                        data = response.json()
                        balance_sun = float(data.get("balance", 0))
                        balance_trx = balance_sun / 1e6  # Convert SUN to TRX

                        return {"total": balance_trx, "confirmed": balance_trx, "unconfirmed": 0.0}

                    else:
                        # BNB, MATIC, AVAX, DOGE use /account/balance endpoint
                        balance_url = f"{TatumService.BASE_URL}/{endpoint}/account/balance/{address}"
                        response = await client.get(balance_url, headers=TatumService._get_headers())

                        if response.status_code == 404:
                            logger.warning(f"{asset} address {address[:10]}... not activated on network (404)")
                            return {"total": 0.0, "confirmed": 0.0, "unconfirmed": 0.0, "not_activated": True}

                        response.raise_for_status()
                        data = response.json()
                        balance = float(data.get("balance", 0))

                        return {"total": balance, "confirmed": balance, "unconfirmed": 0.0}

                elif asset in ["USDT-ETH", "USDC-ETH"]:
                    # ERC-20 token balance
                    contract_address = TatumService.TOKEN_CONTRACTS.get(asset)
                    balance_url = f"{TatumService.BASE_URL}/ethereum/account/balance/erc20/{address}"

                    params = {"contractAddress": contract_address}

                    response = await client.get(
                        balance_url,
                        headers=TatumService._get_headers(),
                        params=params
                    )
                    response.raise_for_status()

                    data = response.json()
                    balance = float(data.get("balance", 0)) / 1e6  # USDT/USDC have 6 decimals

                    return {
                        "total": balance,
                        "confirmed": balance,
                        "unconfirmed": 0.0
                    }

                elif asset in ["USDT-SOL", "USDC-SOL"]:
                    # SPL token balance - Query Solana RPC directly (Tatum's SPL API is unreliable)
                    token_mint = TatumService.TOKEN_CONTRACTS.get(asset)

                    # Use Solana RPC with fallback for rate limit protection
                    payload = {
                        'jsonrpc': '2.0',
                        'id': 1,
                        'method': 'getTokenAccountsByOwner',
                        'params': [
                            address,
                            {'mint': token_mint},
                            {'encoding': 'jsonParsed'}
                        ]
                    }

                    data = await try_solana_rpc_with_fallback(client, payload)

                    # Check if token account exists
                    if 'result' not in data or not data['result'].get('value'):
                        logger.info(f"No {asset} token account found for {address[:10]}...")
                        return {
                            "total": 0.0,
                            "confirmed": 0.0,
                            "unconfirmed": 0.0
                        }

                    # Extract balance from first token account
                    token_account = data['result']['value'][0]
                    token_info = token_account['account']['data']['parsed']['info']
                    balance = float(token_info['tokenAmount']['uiAmount'] or 0)

                    logger.info(f"{asset} balance for {address[:10]}...: {balance}")

                    return {
                        "total": balance,
                        "confirmed": balance,
                        "unconfirmed": 0.0
                    }

                else:
                    raise ValueError(f"Unsupported asset for balance: {asset}")

        except Exception as e:
            logger.error(f"Failed to get balance for {blockchain} {address[:10]}...: {e}", exc_info=True)
            raise

    @staticmethod
    async def send_transaction(
        blockchain: str,
        from_address: str,
        private_key: str,
        to_address: str,
        amount: float
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send transaction on blockchain.

        Args:
            blockchain: Asset code (BTC, ETH, SOL, etc.)
            from_address: Sender address
            private_key: Sender private key
            to_address: Recipient address
            amount: Amount to send

        Returns:
            Tuple of (success, message, tx_hash)

        Security:
            CRITICAL: private_key parameter contains sensitive data!
            - NEVER log the private_key or any payload containing it
            - NEVER print/debug payloads in this function
            - Use redact_sensitive_fields() if logging is needed
            - Private keys must be zeroed from memory after use
        """
        try:
            asset = blockchain.upper()

            async with httpx.AsyncClient(timeout=60.0) as client:
                if asset in ["BTC", "LTC", "DOGE"]:
                    # Bitcoin-based UTXO transaction
                    endpoint = TatumService.BLOCKCHAIN_ENDPOINTS.get(asset)
                    tx_url = f"{TatumService.BASE_URL}/{endpoint}/transaction"

                    # Round amount to 8 decimals
                    rounded_amount = round(float(amount), 8)

                    # Let Tatum auto-calculate optimal fee for BTC/LTC/DOGE
                    # Auto-fee is more reliable and adapts to network conditions
                    # NOTE: For auto-fee, do NOT provide fee or changeAddress (Tatum requires both or neither)
                    # SECURITY: payload contains private_key - NEVER log payload!
                    payload = {
                        "fromAddress": [{"address": from_address, "privateKey": private_key}],
                        "to": [{"address": to_address, "value": rounded_amount}]
                    }
                    logger.info(f"Sending {asset} transaction: {rounded_amount} {asset} (Tatum auto-fee) to {to_address[:10]}...")

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )

                    # Log response for debugging
                    if response.status_code != 200:
                        logger.error(f"Tatum {asset} transaction failed: {response.status_code} - {response.text}")

                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} {blockchain} to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                elif asset == "ETH":
                    # Ethereum native transaction
                    tx_url = f"{TatumService.BASE_URL}/ethereum/transaction"

                    # Tatum expects amount in ETH (as decimal string), NOT wei
                    # Let Tatum auto-calculate gas (same approach as ERC-20 tokens)
                    rounded_amount = round(amount, 18)
                    amount_str = f"{rounded_amount:.18f}".rstrip('0').rstrip('.')

                    payload = {
                        "to": to_address,
                        "amount": amount_str,  # ETH as decimal string, not wei
                        "currency": "ETH",
                        "fromPrivateKey": private_key
                    }

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} ETH to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                elif asset == "SOL":
                    # Solana native transaction
                    tx_url = f"{TatumService.BASE_URL}/solana/transaction"

                    # Solana supports max 9 decimal places (lamports)
                    rounded_amount = round(float(amount), 9)
                    amount_str = f"{rounded_amount:.9f}".rstrip('0').rstrip('.')

                    payload = {
                        "from": from_address,
                        "to": to_address,
                        "amount": amount_str,
                        "fromPrivateKey": private_key
                    }

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} SOL to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                elif asset in ["USDT-ETH", "USDC-ETH"]:
                    # ERC-20 token transfer - use universal token endpoint
                    tx_url = f"{TatumService.BASE_URL}/blockchain/token/transaction"

                    contract_address = TatumService.TOKEN_CONTRACTS.get(asset)
                    # Amount should be decimal value, not raw units
                    rounded_amount = round(amount, 6)
                    amount_str = str(rounded_amount)

                    # Let Tatum handle gas automatically (V3 approach)
                    # Omitting fee params - Tatum will calculate gas dynamically
                    payload = {
                        "to": to_address,
                        "amount": amount_str,  # Decimal value like "9.934504"
                        "chain": "ETH",
                        "fromPrivateKey": private_key,
                        "contractAddress": contract_address,
                        "digits": 6
                    }

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} {asset} to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                elif asset in ["USDT-SOL", "USDC-SOL"]:
                    # SPL token transfer - use universal token endpoint (REVERTED to working Tatum API)
                    tx_url = f"{TatumService.BASE_URL}/blockchain/token/transaction"

                    token_address = TatumService.TOKEN_CONTRACTS.get(asset)
                    # Amount should be decimal value, not raw units
                    rounded_amount = round(amount, 6)
                    amount_str = str(rounded_amount)

                    payload = {
                        "from": from_address,  # SOL requires explicit from address
                        "to": to_address,
                        "amount": amount_str,  # Decimal value like "10.544373"
                        "chain": "SOL",
                        "fromPrivateKey": private_key,
                        "contractAddress": token_address,  # SPL token mint address
                        "digits": 6
                    }

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} {asset} to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                elif asset == "BNB":
                    # BNB on BSC (EVM-compatible, use ETH-like payload structure)
                    tx_url = f"{TatumService.BASE_URL}/bsc/transaction"

                    payload = {
                        "to": to_address,
                        "amount": str(amount),
                        "currency": "BSC",  # Tatum uses "BSC" not "BNB"
                        "fromPrivateKey": private_key
                    }

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} BNB to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                elif asset == "XRP":
                    # XRP uses different parameter names
                    tx_url = f"{TatumService.BASE_URL}/xrp/transaction"

                    # XRP expects amount with max 6 decimal places (standard XRP precision)
                    rounded_amount = round(float(amount), 6)

                    payload = {
                        "fromAccount": from_address,  # XRP requires explicit from address
                        "to": to_address,
                        "amount": str(rounded_amount),  # XRP amount as string with max 6 decimals
                        "fromSecret": private_key  # XRP uses "fromSecret" not "fromPrivateKey"
                    }

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} XRP to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                elif asset in ["TRX", "MATIC", "AVAX"]:
                    # Other blockchain transactions (account-based)
                    endpoint = TatumService.BLOCKCHAIN_ENDPOINTS.get(asset)
                    tx_url = f"{TatumService.BASE_URL}/{endpoint}/transaction"

                    payload = {
                        "fromPrivateKey": private_key,
                        "to": to_address,
                        "amount": str(amount)
                    }

                    # Add currency field for MATIC and AVAX
                    if asset in ["MATIC", "AVAX"]:
                        payload["currency"] = asset

                    response = await client.post(
                        tx_url,
                        headers=TatumService._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()

                    data = response.json()
                    tx_hash = data.get("txId")

                    logger.info(f"Sent {amount} {asset} to {to_address[:10]}... TX: {tx_hash}")
                    return True, "Transaction broadcast successfully", tx_hash

                else:
                    return False, f"Unsupported asset for transactions: {asset}", None

        except httpx.HTTPStatusError as e:
            # Extract detailed error from Tatum response
            try:
                error_detail = e.response.json()
                error_message = error_detail.get("message", error_detail.get("errorCode", e.response.text))
            except:
                error_message = e.response.text

            # Special handling for 403 errors
            if e.response.status_code == 403:
                logger.error(f"Tatum API 403 Forbidden for {blockchain}: {error_message}")
                return False, (
                    f"Blockchain transaction service temporarily unavailable for {blockchain}. "
                    "This may be due to API credit limits or permissions. Please contact support."
                ), None

            # Other HTTP errors
            error_msg = f"HTTP error sending {blockchain} transaction: {e.response.status_code}"
            logger.error(f"{error_msg} - Response: {error_message}")
            return False, f"{error_msg}: {error_message}", None
        except Exception as e:
            error_msg = f"Failed to send {blockchain} transaction: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None

    @staticmethod
    async def create_webhook_subscription(
        blockchain: str,
        address: str,
        webhook_url: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create webhook subscription for address monitoring.

        Args:
            blockchain: Asset code (BTC, ETH, SOL, etc.)
            address: Address to monitor
            webhook_url: URL to receive webhooks

        Returns:
            Tuple of (success, message, subscription_id)
        """
        try:
            asset = blockchain.upper()

            # Map asset to chain
            if asset in ["BTC"]:
                chain = "BTC"
            elif asset in ["ETH", "USDT-ETH", "USDC-ETH"]:
                chain = "ETH"
            elif asset in ["LTC"]:
                chain = "LTC"
            elif asset in ["SOL", "USDT-SOL", "USDC-SOL"]:
                chain = "SOL"
            elif asset in ["XRP"]:
                chain = "XRP"
            elif asset in ["BNB"]:
                chain = "BSC"  # Binance Smart Chain
            elif asset in ["TRX"]:
                chain = "TRON"
            elif asset in ["MATIC"]:
                chain = "MATIC"
            elif asset in ["AVAX"]:
                chain = "AVAX"
            elif asset in ["DOGE"]:
                chain = "DOGE"
            else:
                return False, f"Unsupported asset for monitoring: {asset}", None

            async with httpx.AsyncClient(timeout=30.0) as client:
                subscription_url = f"{TatumService.BASE_URL}/subscription"

                payload = {
                    "type": "ADDRESS_TRANSACTION",
                    "attr": {
                        "address": address,
                        "chain": chain,
                        "url": webhook_url
                    }
                }

                response = await client.post(
                    subscription_url,
                    headers=TatumService._get_headers(),
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                subscription_id = data.get("id")

                logger.info(f"Created webhook subscription for {blockchain} {address[:10]}... ID: {subscription_id}")
                return True, "Subscription created successfully", subscription_id

        except Exception as e:
            error_msg = f"Failed to create webhook subscription: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None

    @staticmethod
    async def delete_webhook_subscription(subscription_id: str) -> bool:
        """
        Delete webhook subscription.

        Args:
            subscription_id: Subscription ID to delete

        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                delete_url = f"{TatumService.BASE_URL}/subscription/{subscription_id}"

                response = await client.delete(
                    delete_url,
                    headers=TatumService._get_headers()
                )
                response.raise_for_status()

                logger.info(f"Deleted webhook subscription: {subscription_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete webhook subscription {subscription_id}: {e}", exc_info=True)
            return False

    @staticmethod
    def validate_address(blockchain: str, address: str) -> bool:
        """
        Validate blockchain address format.

        Args:
            blockchain: Asset code
            address: Address to validate

        Returns:
            True if valid
        """
        if not address or not isinstance(address, str):
            return False

        asset = blockchain.upper()

        if asset in ["BTC", "LTC", "DOGE"]:
            # Bitcoin/Litecoin/Dogecoin addresses
            return (
                address.startswith(("1", "3", "bc1", "m", "n", "2", "tb1", "D", "A", "9")) and
                26 <= len(address) <= 62
            )
        elif asset in ["ETH", "USDT-ETH", "USDC-ETH", "BNB", "MATIC"]:
            # Ethereum and EVM-compatible addresses
            return address.startswith("0x") and len(address) == 42
        elif asset in ["SOL", "USDT-SOL", "USDC-SOL"]:
            # Solana addresses
            return 32 <= len(address) <= 44
        elif asset == "XRP":
            # XRP addresses
            return (address.startswith("r") and 25 <= len(address) <= 35)
        elif asset == "TRX":
            # Tron addresses
            return address.startswith("T") and len(address) == 34
        elif asset == "AVAX":
            # Avalanche addresses (X-Chain or C-Chain)
            return (address.startswith(("X-", "C-", "P-", "0x")) and
                   (len(address) >= 42 if address.startswith("0x") else len(address) >= 40))
        else:
            logger.warning(f"Unknown blockchain for validation: {asset}")
            return False

    @staticmethod
    def get_explorer_url(blockchain: str, tx_hash: str) -> str:
        """
        Get blockchain explorer URL for transaction.

        Args:
            blockchain: Asset code (BTC, ETH, SOL, etc.)
            tx_hash: Transaction hash

        Returns:
            URL to view transaction on blockchain explorer
        """
        asset = blockchain.upper()

        explorers = {
            "BTC": f"https://blockstream.info/tx/{tx_hash}",
            "LTC": f"https://blockchair.com/litecoin/transaction/{tx_hash}",
            "ETH": f"https://etherscan.io/tx/{tx_hash}",
            "SOL": f"https://solscan.io/tx/{tx_hash}",
            "XRP": f"https://xrpscan.com/tx/{tx_hash}",
            "BNB": f"https://bscscan.com/tx/{tx_hash}",
            "TRX": f"https://tronscan.org/#/transaction/{tx_hash}",
            "MATIC": f"https://polygonscan.com/tx/{tx_hash}",
            "AVAX": f"https://snowtrace.io/tx/{tx_hash}",
            "DOGE": f"https://blockchair.com/dogecoin/transaction/{tx_hash}",
            "USDT-ETH": f"https://etherscan.io/tx/{tx_hash}",
            "USDC-ETH": f"https://etherscan.io/tx/{tx_hash}",
            "USDT-SOL": f"https://solscan.io/tx/{tx_hash}",
            "USDC-SOL": f"https://solscan.io/tx/{tx_hash}"
        }

        return explorers.get(asset, f"https://blockchain.com/search?search={tx_hash}")
