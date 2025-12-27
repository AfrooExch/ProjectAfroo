"""
Solana Direct Web3 Service - SPL Token Operations
Handles SPL token transfers with automatic ATA creation
"""

import logging
from typing import Tuple, Optional
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer as system_transfer
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.hash import Hash
from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
    transfer_checked,
    TransferCheckedParams,
)

logger = logging.getLogger(__name__)


class SolanaService:
    """Direct Solana blockchain service for SPL token operations"""

    # Mainnet RPC endpoints (will try in order with fallback on rate limit)
    RPC_ENDPOINTS = [
        "https://api.mainnet-beta.solana.com",  # Official (has rate limits)
        "https://rpc.ankr.com/solana",  # Ankr free tier
        "https://solana-api.projectserum.com",  # Serum/OpenBook
        "https://solana.public-rpc.com",  # Public RPC
    ]

    # Default to first endpoint
    RPC_URL = RPC_ENDPOINTS[0]

    @staticmethod
    async def _get_rpc_client() -> AsyncClient:
        """
        Get Solana RPC client with automatic fallback on errors
        Tries multiple free RPC endpoints if rate limited
        """
        # Try each RPC endpoint
        for rpc_url in SolanaService.RPC_ENDPOINTS:
            try:
                client = AsyncClient(rpc_url)
                # Test connection with a lightweight call
                await client.get_health()
                logger.info(f"Connected to Solana RPC: {rpc_url}")
                return client
            except Exception as e:
                logger.warning(f"Solana RPC {rpc_url} failed: {e}, trying next...")
                try:
                    await client.close()
                except:
                    pass
                continue

        # Fall back to first endpoint if all health checks fail
        logger.warning("All Solana RPC health checks failed, using first endpoint anyway")
        return AsyncClient(SolanaService.RPC_ENDPOINTS[0])

    # SPL Token contract addresses
    USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    USDT_MINT = Pubkey.from_string("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB")

    @staticmethod
    async def transfer_spl_token(
        from_private_key: str,
        to_address: str,
        amount: float,
        token_mint: str,
        decimals: int = 6,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Transfer SPL token with automatic ATA creation

        Args:
            from_private_key: Sender's private key (base58)
            to_address: Recipient's address
            amount: Amount to transfer
            token_mint: Token mint address (USDC-SOL or USDT-SOL)
            decimals: Token decimals (default 6)

        Returns:
            Tuple of (success, message, transaction_signature)
        """
        client = None
        try:
            # Parse keypair and addresses
            sender_keypair = Keypair.from_base58_string(from_private_key)
            sender_pubkey = sender_keypair.pubkey()
            recipient_pubkey = Pubkey.from_string(to_address)

            # Get mint pubkey
            if token_mint == "USDC-SOL":
                mint_pubkey = SolanaService.USDC_MINT
            elif token_mint == "USDT-SOL":
                mint_pubkey = SolanaService.USDT_MINT
            else:
                mint_pubkey = Pubkey.from_string(token_mint)

            logger.info(
                f"Transferring {amount} {token_mint} from {str(sender_pubkey)[:10]}... to {to_address[:10]}..."
            )

            # Connect to Solana with fallback
            client = await SolanaService._get_rpc_client()

            # Get associated token accounts
            sender_ata = get_associated_token_address(sender_pubkey, mint_pubkey)
            recipient_ata = get_associated_token_address(recipient_pubkey, mint_pubkey)

            logger.info(f"Sender ATA: {str(sender_ata)[:10]}...")
            logger.info(f"Recipient ATA: {str(recipient_ata)[:10]}...")

            # Check if recipient ATA exists
            try:
                ata_info = await client.get_account_info(recipient_ata, commitment=Confirmed)
                ata_exists = ata_info.value is not None
                logger.info(f"Recipient ATA exists: {ata_exists}")
            except Exception as e:
                logger.warning(f"Could not check ATA existence: {e}")
                ata_exists = False

            # Get recent blockhash
            recent_blockhash_resp = await client.get_latest_blockhash(commitment=Confirmed)
            recent_blockhash = recent_blockhash_resp.value.blockhash

            # Build instructions
            instructions = []

            # Create recipient ATA if it doesn't exist
            if not ata_exists:
                create_ata_ix = create_associated_token_account(
                    payer=sender_pubkey, owner=recipient_pubkey, mint=mint_pubkey
                )
                instructions.append(create_ata_ix)
                logger.info("Added instruction to create recipient ATA")

            # Transfer instruction
            transfer_amount = int(amount * (10**decimals))
            transfer_ix = transfer_checked(
                TransferCheckedParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=sender_ata,
                    mint=mint_pubkey,
                    dest=recipient_ata,
                    owner=sender_pubkey,
                    amount=transfer_amount,
                    decimals=decimals,
                )
            )
            instructions.append(transfer_ix)
            logger.info(f"Added transfer instruction for {transfer_amount} tokens ({amount} {token_mint})")

            # Create and sign transaction
            message = MessageV0.try_compile(
                payer=sender_pubkey,
                instructions=instructions,
                address_lookup_table_accounts=[],
                recent_blockhash=recent_blockhash,
            )
            transaction = VersionedTransaction(message, [sender_keypair])

            # Send transaction
            logger.info("Sending transaction to Solana network...")
            tx_opts = TxOpts(skip_preflight=False, preflight_commitment=Confirmed)
            tx_resp = await client.send_transaction(transaction, opts=tx_opts)
            signature = str(tx_resp.value)

            logger.info(f"{token_mint} transfer successful: {signature}")

            await client.close()
            return True, "Transaction broadcast successfully", signature

        except Exception as e:
            error_msg = f"Failed to transfer {token_mint}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if client:
                await client.close()

            return False, error_msg, None

    @staticmethod
    async def transfer_sol(
        from_private_key: str, to_address: str, amount: float
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Transfer native SOL

        Args:
            from_private_key: Sender's private key (base58)
            to_address: Recipient's address
            amount: Amount in SOL

        Returns:
            Tuple of (success, message, transaction_signature)
        """
        client = None
        try:
            # Parse keypair and addresses
            sender_keypair = Keypair.from_base58_string(from_private_key)
            sender_pubkey = sender_keypair.pubkey()
            recipient_pubkey = Pubkey.from_string(to_address)

            logger.info(f"Transferring {amount} SOL from {str(sender_pubkey)[:10]}... to {to_address[:10]}...")

            # Connect to Solana with fallback
            client = await SolanaService._get_rpc_client()

            # Get recent blockhash
            recent_blockhash_resp = await client.get_latest_blockhash(commitment=Confirmed)
            recent_blockhash = recent_blockhash_resp.value.blockhash

            # Create transfer instruction (amount in lamports)
            lamports = int(amount * 1_000_000_000)
            transfer_ix = system_transfer(
                TransferParams(from_pubkey=sender_pubkey, to_pubkey=recipient_pubkey, lamports=lamports)
            )

            # Create and sign transaction
            message = MessageV0.try_compile(
                payer=sender_pubkey,
                instructions=[transfer_ix],
                address_lookup_table_accounts=[],
                recent_blockhash=recent_blockhash,
            )
            transaction = VersionedTransaction(message, [sender_keypair])

            # Send transaction
            logger.info("Sending SOL transfer to Solana network...")
            tx_opts = TxOpts(skip_preflight=False, preflight_commitment=Confirmed)
            tx_resp = await client.send_transaction(transaction, opts=tx_opts)
            signature = str(tx_resp.value)

            logger.info(f"SOL transfer successful: {signature}")

            await client.close()
            return True, "Transaction broadcast successfully", signature

        except Exception as e:
            error_msg = f"Failed to transfer SOL: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if client:
                await client.close()

            return False, error_msg, None
