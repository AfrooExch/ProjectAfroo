"""
Wallet Service - Complete business logic for wallet operations
Manages wallet creation, deposits, withdrawals, fees, and profit handling
"""

from typing import Optional, List, Dict, Tuple
from datetime import datetime
from decimal import Decimal
from bson import ObjectId
import logging
import uuid

from app.core.config import settings
from app.core.encryption import get_encryption_service
from app.core.database import get_database
from app.models.wallet import (
    Wallet, Balance, Transaction, ProfitHold, ProfitBatch,
    is_valid_currency, SUPPORTED_CURRENCIES
)
from app.services.tatum_service import TatumService
from app.services.crypto import get_crypto_handler

logger = logging.getLogger(__name__)


class WalletService:
    """Complete wallet service with all operations"""

    def __init__(self):
        self.encryption = get_encryption_service()
        self.tatum = TatumService()

    async def create_wallet(self, user_id: str, currency: str) -> Dict:
        """
        Create new wallet for user

        Args:
            user_id: Discord user ID
            currency: Currency code (BTC, ETH, USDC-SOL, etc.)

        Returns:
            Wallet data with address

        Raises:
            ValueError: If currency unsupported or wallet exists
        """
        try:
            currency = currency.upper()

            # Validate currency
            if not is_valid_currency(currency):
                raise ValueError(f"Unsupported currency: {currency}")

            db = get_database()

            # Check if wallet already exists
            existing = await db.wallets.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if existing:
                raise ValueError(f"Wallet for {currency} already exists")

            # Get crypto handler
            handler = get_crypto_handler(currency)

            # TOKEN LOGIC: Use parent wallet address for tokens
            # ERC-20 tokens (USDC-ETH, USDT-ETH) use same address as ETH
            # SPL tokens (USDC-SOL, USDT-SOL) use same address as SOL
            parent_currency = None
            if currency in ["USDC-ETH", "USDT-ETH"]:
                parent_currency = "ETH"
            elif currency in ["USDC-SOL", "USDT-SOL"]:
                parent_currency = "SOL"

            if parent_currency:
                # Check if parent wallet exists
                parent_wallet = await db.wallets.find_one({
                    "user_id": user_id,
                    "currency": parent_currency
                })

                if parent_wallet:
                    # Use parent wallet's address and key
                    logger.info(f"Using existing {parent_currency} wallet for {currency}")
                    address = parent_wallet["address"]
                    encrypted_key = parent_wallet["encrypted_private_key"]
                else:
                    # Generate new wallet (parent doesn't exist yet)
                    logger.info(f"Generating new wallet for {currency} (parent {parent_currency} doesn't exist)")
                    wallet_data = await self.tatum.generate_wallet(parent_currency)  # Generate parent type
                    address = handler.format_address(wallet_data["address"])
                    encrypted_key = self.encryption.encrypt_private_key(wallet_data["private_key"])
            else:
                # Regular wallet generation (not a token)
                logger.info(f"Generating {currency} wallet for user {user_id}")
                wallet_data = await self.tatum.generate_wallet(currency)
                address = handler.format_address(wallet_data["address"])
                encrypted_key = self.encryption.encrypt_private_key(wallet_data["private_key"])

            # Create wallet document
            wallet = Wallet(
                user_id=user_id,
                currency=currency,
                address=address,
                encrypted_private_key=encrypted_key,
                derivation_index=0
            )

            # Insert wallet
            result = await db.wallets.insert_one(wallet.dict(by_alias=True, exclude={"id"}))
            wallet.id = result.inserted_id

            # Create balance record
            balance = Balance(
                user_id=user_id,
                currency=currency,
                available="0",
                locked="0",
                pending="0"
            )

            await db.balances.insert_one(balance.dict(by_alias=True, exclude={"id"}))

            # Subscribe to Tatum webhooks for deposits
            webhook_url = f"{settings.TATUM_WEBHOOK_BASE_URL}/api/v1/webhooks/tatum"
            success, msg, subscription_id = await self.tatum.create_webhook_subscription(
                currency, address, webhook_url
            )

            if not success:
                logger.warning(f"Failed to create webhook subscription: {msg}")

            logger.info(f"Created {currency} wallet {address[:10]}... for user {user_id}")

            return {
                "wallet_id": str(wallet.id),
                "address": address,
                "currency": currency,
                "balance": "0",
                "created_at": wallet.created_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to create wallet for {user_id}/{currency}: {e}", exc_info=True)
            raise

    async def get_wallet(self, user_id: str, currency: str) -> Optional[Dict]:
        """
        Get wallet for user and currency

        Args:
            user_id: Discord user ID
            currency: Currency code

        Returns:
            Wallet data or None if not found
        """
        try:
            currency = currency.upper()
            db = get_database()

            wallet = await db.wallets.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if not wallet:
                return None

            # Get balance
            balance = await db.balances.find_one({
                "user_id": user_id,
                "currency": currency
            })

            # Format balances properly (fix 0E-30 issue)
            def format_balance(value) -> str:
                """Format balance to avoid scientific notation"""
                if not value:
                    return "0"
                try:
                    decimal_val = Decimal(str(value))
                    # Remove trailing zeros and scientific notation
                    formatted = format(decimal_val, 'f')
                    # Remove trailing zeros after decimal point
                    if '.' in formatted:
                        formatted = formatted.rstrip('0').rstrip('.')
                    return formatted if formatted != '' else "0"
                except:
                    return str(value)

            return {
                "wallet_id": str(wallet["_id"]),
                "address": wallet["address"],
                "currency": wallet["currency"],
                "balance": format_balance(balance.get("available") if balance else "0"),
                "locked": format_balance(balance.get("locked") if balance else "0"),
                "pending": format_balance(balance.get("pending") if balance else "0"),
                "created_at": wallet["created_at"].isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get wallet for {user_id}/{currency}: {e}", exc_info=True)
            raise

    async def get_balance(self, user_id: str, currency: str) -> Decimal:
        """
        Get available balance for user

        Args:
            user_id: Discord user ID
            currency: Currency code

        Returns:
            Available balance as Decimal
        """
        try:
            currency = currency.upper()
            db = get_database()

            balance = await db.balances.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if not balance:
                logger.warning(f"No balance record found for {user_id}/{currency} in balances collection")
                return Decimal("0")

            available = balance.get("available", "0")
            logger.info(f"get_balance for {user_id}/{currency}: {available}")
            return Decimal(available)

        except Exception as e:
            logger.error(f"Failed to get balance for {user_id}/{currency}: {e}", exc_info=True)
            return Decimal("0")

    async def sync_balance(self, user_id: str, currency: str) -> Dict:
        """
        Sync balance with blockchain

        Args:
            user_id: Discord user ID
            currency: Currency code

        Returns:
            Updated balance data
        """
        try:
            currency = currency.upper()
            db = get_database()

            # Get wallet
            wallet = await db.wallets.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if not wallet:
                raise ValueError("Wallet not found")

            # Get blockchain balance
            balance_data = await self.tatum.get_balance(currency, wallet["address"])
            blockchain_balance = str(balance_data["confirmed"])

            # Get current balance before update
            current_balance_doc = await db.balances.find_one({
                "user_id": user_id,
                "currency": currency
            })

            old_balance = current_balance_doc.get("available", "0") if current_balance_doc else "0"

            # Update balance with blockchain data
            await db.balances.update_one(
                {"user_id": user_id, "currency": currency},
                {
                    "$set": {
                        "available": blockchain_balance,
                        "last_synced": datetime.utcnow(),
                        "sync_status": "synced"
                    }
                },
                upsert=True
            )

            logger.info(f"Synced {currency} balance for {user_id}: {old_balance} -> {blockchain_balance}")

            return {
                "currency": currency,
                "old_balance": old_balance,
                "blockchain_balance": blockchain_balance,
                "synced_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to sync balance for {user_id}/{currency}: {e}", exc_info=True)
            raise

    async def deposit_confirmed(
        self,
        user_id: str,
        currency: str,
        amount: str,
        tx_hash: str
    ) -> Dict:
        """
        Process confirmed deposit

        Args:
            user_id: Discord user ID
            currency: Currency code
            amount: Deposit amount (as string)
            tx_hash: Transaction hash

        Returns:
            Transaction data
        """
        try:
            currency = currency.upper()
            db = get_database()

            # Check if transaction already processed
            existing_tx = await db.transactions.find_one({
                "blockchain_tx_hash": tx_hash,
                "currency": currency
            })

            if existing_tx:
                logger.warning(f"Deposit {tx_hash} already processed")
                return {"status": "duplicate", "tx_id": str(existing_tx["_id"])}

            # Get wallet
            wallet = await db.wallets.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if not wallet:
                raise ValueError("Wallet not found")

            # Create transaction record
            tx_id = f"DEP-{uuid.uuid4().hex[:12].upper()}"
            handler = get_crypto_handler(currency)

            transaction = Transaction(
                tx_id=tx_id,
                user_id=user_id,
                currency=currency,
                type="deposit",
                amount=amount,
                to_address=wallet["address"],
                status="confirmed",
                confirmations=handler.get_required_confirmations(),
                required_confirmations=handler.get_required_confirmations(),
                blockchain_tx_hash=tx_hash,
                confirmed_at=datetime.utcnow()
            )

            result = await db.transactions.insert_one(
                transaction.dict(by_alias=True, exclude={"id"})
            )

            # Update balance - move from pending to available
            amount_decimal = Decimal(amount)

            # Get current balance
            deposit_balance_doc = await db.balances.find_one({"user_id": user_id, "currency": currency})
            if deposit_balance_doc:
                current_available = Decimal(str(deposit_balance_doc.get("available", "0")))
                current_pending = Decimal(str(deposit_balance_doc.get("pending", "0")))

                await db.balances.update_one(
                    {"user_id": user_id, "currency": currency},
                    {
                        "$set": {
                            "available": str(current_available + amount_decimal),
                            "pending": str(max(Decimal("0"), current_pending - amount_decimal)),  # Don't go negative
                            "last_synced": datetime.utcnow()
                        }
                    }
                )
            else:
                # Create new balance record if doesn't exist
                await db.balances.insert_one({
                    "user_id": user_id,
                    "currency": currency,
                    "available": str(amount_decimal),
                    "locked": "0",
                    "pending": "0",
                    "last_synced": datetime.utcnow()
                })

            logger.info(f"Deposit confirmed: {amount} {currency} for user {user_id}, tx {tx_hash}")

            # Track wallet deposit stats
            try:
                from app.services.stats_tracking_service import StatsTrackingService
                from app.services.price_service import PriceService

                # Convert to USD
                price_usd = await PriceService.get_price_usd(currency)
                amount_usd = float(amount_decimal * price_usd) if price_usd else 0

                await StatsTrackingService.track_wallet_transaction(
                    user_id=user_id,
                    transaction_type="deposit",
                    amount_usd=amount_usd,
                    asset=currency
                )
                logger.info(f"Tracked deposit stats: {user_id}, ${amount_usd:.2f} USD in {currency}")
            except Exception as stats_err:
                logger.error(f"Failed to track deposit stats: {stats_err}", exc_info=True)
                # Don't fail deposit if stats tracking fails

            return {
                "tx_id": tx_id,
                "amount": amount,
                "currency": currency,
                "status": "confirmed",
                "tx_hash": tx_hash
            }

        except Exception as e:
            logger.error(f"Failed to process deposit: {e}", exc_info=True)
            raise

    def _get_network_fee(self, currency: str) -> Decimal:
        """Get network fee for currency"""
        network_fees = {
            "BTC": Decimal("0.000005"),  # 500 satoshis (~$0.40 at current prices)
            "ETH": Decimal("0.001"),  # Tatum auto-calculates (typical ~$3)
            "USDC-ETH": Decimal("0.001"),  # Tatum auto-calculates
            "USDT-ETH": Decimal("0.001"),  # Tatum auto-calculates
            "SOL": Decimal("0.000005"),  # Tatum auto-calculates (minimal)
            "USDC-SOL": Decimal("0.000005"),  # Tatum auto-calculates
            "USDT-SOL": Decimal("0.000005"),  # Tatum auto-calculates
            "LTC": Decimal("0.001"),  # Increased from 0.0000025 to meet LTC network relay fee requirements (~$0.12)
            "XRP": Decimal("0.00001"),  # 10 drops (minimal, fixed)
            "BNB": Decimal("0.0005"),  # Tatum auto-calculates (~$0.30)
            "TRX": Decimal("1"),  # ~1 TRX fee
            "MATIC": Decimal("0.01"),  # Tatum auto-calculates (~$0.005)
            "AVAX": Decimal("0.001"),  # Tatum auto-calculates (~$0.04)
            "DOGE": Decimal("2")  # Tatum auto-calculates, estimate ~2 DOGE (~$0.80)
        }
        return network_fees.get(currency.upper(), Decimal("0.0001"))

    async def calculate_max_withdrawal(
        self,
        currency: str,
        available_balance: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        """
        Calculate maximum withdrawal amount from available balance

        Args:
            currency: Currency code
            available_balance: Available balance

        Returns:
            Tuple of (send_amount, network_fee, server_fee, total_deducted)
        """
        try:
            currency = currency.upper()

            # Get network fee
            network_fee = self._get_network_fee(currency)

            # Some blockchains require minimum reserves to keep accounts active
            reserve_amount = Decimal("0")
            if currency == "SOL":
                # SOL rent-exempt reserve
                reserve_amount = Decimal("0.001")
                logger.info(f"SOL withdrawal: keeping {reserve_amount} SOL rent-exempt reserve")
            elif currency == "XRP":
                # XRP wallet reserve requirement (1 XRP base reserve to keep wallet active)
                reserve_amount = Decimal("1")
                logger.info(f"XRP withdrawal: keeping {reserve_amount} XRP wallet reserve")

            # Check if balance covers network fee + reserve
            minimum_required = network_fee + reserve_amount
            if available_balance <= minimum_required:
                if reserve_amount > 0:
                    raise ValueError(f"Balance too low to cover network fee ({network_fee} {currency}) and rent-exempt reserve ({reserve_amount} {currency})")
                else:
                    raise ValueError(f"Balance too low to cover network fee ({network_fee} {currency})")

            # Calculate send amount after fees
            # Formula: send_amount = (available_balance - network_fee - reserve_amount) / (1 + fee_rate)
            # For SOL, we keep reserve_amount in the account (not deducted from user balance)
            fee_rate = Decimal(str(settings.SERVER_PROFIT_RATE)) / Decimal("100")
            withdrawable_balance = available_balance - reserve_amount
            send_amount = (withdrawable_balance - network_fee) / (Decimal("1") + fee_rate)

            # Round to 8 decimal places (crypto standard) to avoid dust errors
            send_amount = send_amount.quantize(Decimal("0.00000001"))

            # Calculate server fee
            server_fee = send_amount * fee_rate
            server_fee = server_fee.quantize(Decimal("0.00000001"))

            # For MAX withdrawal, ensure total_deducted equals withdrawable_balance exactly
            # to avoid creating dust change. Adjust server_fee to make the math work.
            # Note: reserve_amount stays in the wallet (not deducted from balance)
            total_deducted = withdrawable_balance

            # Recalculate server_fee to make total exact: server_fee = total - send - network_fee
            server_fee = total_deducted - send_amount - network_fee

            logger.info(f"Max withdrawal for {currency}: send={send_amount}, network_fee={network_fee}, server_fee={server_fee}, total={total_deducted}, balance={available_balance}, reserve={reserve_amount}")

            return send_amount, network_fee, server_fee, total_deducted

        except Exception as e:
            logger.error(f"Failed to calculate max withdrawal: {e}", exc_info=True)
            raise

    async def calculate_fees(
        self,
        currency: str,
        amount: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate withdrawal fees for a specific amount

        Args:
            currency: Currency code
            amount: Withdrawal amount (what user will receive)

        Returns:
            Tuple of (network_fee, server_fee, total_deducted)
        """
        try:
            currency = currency.upper()

            # Get network fee
            network_fee = self._get_network_fee(currency)

            # Calculate server fee (0.4% of amount)
            fee_rate = Decimal(str(settings.SERVER_PROFIT_RATE)) / Decimal("100")
            server_fee = amount * fee_rate

            # Ensure minimum fee
            min_fee_usd = Decimal(str(settings.MIN_PROFIT_USD))
            if server_fee < min_fee_usd / Decimal("100"):  # Convert to crypto estimate
                server_fee = min_fee_usd / Decimal("100")

            # Total deducted from user
            total_deducted = amount + network_fee + server_fee

            logger.info(f"Fee calculation for {currency}: amount={amount}, network_fee={network_fee}, server_fee={server_fee}, total={total_deducted}")

            return network_fee, server_fee, total_deducted

        except Exception as e:
            logger.error(f"Failed to calculate fees: {e}", exc_info=True)
            raise

    async def withdraw(
        self,
        user_id: str,
        currency: str,
        to_address: str,
        amount: Decimal,
        precomputed_network_fee: Optional[Decimal] = None,
        precomputed_server_fee: Optional[Decimal] = None,
        precomputed_total: Optional[Decimal] = None
    ) -> Dict:
        """
        Process withdrawal

        Args:
            user_id: Discord user ID
            currency: Currency code
            to_address: Destination address
            amount: Withdrawal amount (what recipient receives)
            precomputed_network_fee: Optional pre-calculated network fee (for max withdrawals)
            precomputed_server_fee: Optional pre-calculated server fee (for max withdrawals)
            precomputed_total: Optional pre-calculated total deducted (for max withdrawals)

        Returns:
            Transaction data

        Raises:
            ValueError: If insufficient balance or invalid params
        """
        try:
            currency = currency.upper()
            db = get_database()

            # Validate currency
            if not is_valid_currency(currency):
                raise ValueError(f"Unsupported currency: {currency}")

            # Get handler and validate address
            handler = get_crypto_handler(currency)
            to_address = handler.format_address(to_address)

            # Check minimum withdrawal
            if amount < Decimal(str(handler.get_min_withdrawal())):
                raise ValueError(f"Amount below minimum withdrawal ({handler.get_min_withdrawal()} {currency})")

            # Use precomputed fees if provided (for max withdrawals), otherwise calculate
            if precomputed_network_fee is not None and precomputed_server_fee is not None and precomputed_total is not None:
                network_fee = precomputed_network_fee
                server_fee = precomputed_server_fee
                total_deducted = precomputed_total
                logger.info(f"Using precomputed fees for {currency} withdrawal: network={network_fee}, server={server_fee}, total={total_deducted}")
            else:
                # Calculate fees normally
                network_fee, server_fee, total_deducted = await self.calculate_fees(currency, amount)

            # Check balance
            current_balance = await self.get_balance(user_id, currency)

            if current_balance < total_deducted:
                raise ValueError(f"Insufficient balance. Required: {total_deducted}, Available: {current_balance}")

            # Get wallet and decrypt private key
            wallet = await db.wallets.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if not wallet:
                raise ValueError("Wallet not found")

            private_key = self.encryption.decrypt_private_key(wallet["encrypted_private_key"])

            # Lock balance - get current balance and calculate new values
            balance_doc = await db.balances.find_one({"user_id": user_id, "currency": currency})
            if not balance_doc:
                raise ValueError("Balance record not found")

            # Convert strings to Decimal for calculation
            current_available = Decimal(str(balance_doc.get("available", "0")))
            current_locked = Decimal(str(balance_doc.get("locked", "0")))

            # Calculate new balances
            new_available = current_available - total_deducted
            new_locked = current_locked + total_deducted

            # Update with string values (MongoDB stores as strings)
            await db.balances.update_one(
                {"user_id": user_id, "currency": currency},
                {
                    "$set": {
                        "available": str(new_available),
                        "locked": str(new_locked)
                    }
                }
            )

            # Create transaction record
            tx_id = f"WTH-{uuid.uuid4().hex[:12].upper()}"

            transaction = Transaction(
                tx_id=tx_id,
                user_id=user_id,
                currency=currency,
                type="withdrawal",
                amount=str(amount),
                network_fee=str(network_fee),
                server_fee=str(server_fee),
                total_deducted=str(total_deducted),
                from_address=wallet["address"],
                to_address=to_address,
                status="pending"
            )

            result = await db.transactions.insert_one(
                transaction.dict(by_alias=True, exclude={"id"})
            )
            transaction.id = result.inserted_id

            # No gas transfer needed anymore - tokens use same wallet as parent!
            # ERC-20 tokens (USDC-ETH, USDT-ETH) use same address as ETH
            # SPL tokens (USDC-SOL, USDT-SOL) use same address as SOL

            # Send transaction via Tatum
            try:
                success, message, tx_hash = await self.tatum.send_transaction(
                    currency,
                    wallet["address"],
                    private_key,
                    to_address,
                    float(amount)
                )

                if not success:
                    # Rollback balance lock - restore previous values
                    rollback_balance_doc = await db.balances.find_one({"user_id": user_id, "currency": currency})
                    if rollback_balance_doc:
                        rollback_available = Decimal(str(rollback_balance_doc.get("available", "0")))
                        rollback_locked = Decimal(str(rollback_balance_doc.get("locked", "0")))

                        await db.balances.update_one(
                            {"user_id": user_id, "currency": currency},
                            {
                                "$set": {
                                    "available": str(rollback_available + total_deducted),
                                    "locked": str(rollback_locked - total_deducted)
                                }
                            }
                        )

                    # Update transaction status
                    await db.transactions.update_one(
                        {"_id": transaction.id},
                        {
                            "$set": {
                                "status": "failed",
                                "error_message": message,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )

                    raise Exception(f"Transaction failed: {message}")

                # Update transaction with hash
                await db.transactions.update_one(
                    {"_id": transaction.id},
                    {
                        "$set": {
                            "blockchain_tx_hash": tx_hash,
                            "status": "confirming",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                # Unlock balance (withdrawal is now on blockchain)
                unlock_balance_doc = await db.balances.find_one({"user_id": user_id, "currency": currency})
                if unlock_balance_doc:
                    unlock_locked = Decimal(str(unlock_balance_doc.get("locked", "0")))

                    await db.balances.update_one(
                        {"user_id": user_id, "currency": currency},
                        {
                            "$set": {"locked": str(unlock_locked - total_deducted)}
                        }
                    )

                # Process server profit
                await self.process_server_profit(str(transaction.id), server_fee, currency)

                logger.info(f"Withdrawal sent: {amount} {currency} to {to_address[:10]}..., tx {tx_hash}")

                # Track wallet withdrawal stats
                try:
                    from app.services.stats_tracking_service import StatsTrackingService
                    from app.services.price_service import PriceService

                    # Convert to USD
                    price_usd = await PriceService.get_price_usd(currency)
                    amount_usd = float(amount * price_usd) if price_usd else 0

                    await StatsTrackingService.track_wallet_transaction(
                        user_id=user_id,
                        transaction_type="withdrawal",
                        amount_usd=amount_usd,
                        asset=currency
                    )
                    logger.info(f"Tracked withdrawal stats: {user_id}, ${amount_usd:.2f} USD in {currency}")
                except Exception as stats_err:
                    logger.error(f"Failed to track withdrawal stats: {stats_err}", exc_info=True)
                    # Don't fail withdrawal if stats tracking fails

                return {
                    "tx_id": tx_id,
                    "amount": str(amount),
                    "network_fee": str(network_fee),
                    "server_fee": str(server_fee),
                    "total_deducted": str(total_deducted),
                    "to_address": to_address,
                    "tx_hash": tx_hash,
                    "status": "confirming",
                    "explorer_url": handler.get_explorer_url(tx_hash)
                }

            except Exception as e:
                logger.error(f"Withdrawal transaction failed: {e}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Failed to process withdrawal: {e}", exc_info=True)
            raise

    async def process_server_profit(
        self,
        transaction_id: str,
        amount: Decimal,
        currency: str
    ) -> None:
        """
        Process server profit fee - send to admin or hold if too small

        Args:
            transaction_id: Transaction ID that generated fee
            amount: Fee amount
            currency: Currency code
        """
        try:
            from app.services.price_service import price_service

            currency = currency.upper()
            db = get_database()

            # Check if amount meets minimum for immediate send
            min_profit = Decimal(str(settings.MIN_PROFIT_USD))

            # Convert to USD using real price service
            price_usd = await price_service.get_price_usd(currency)
            if price_usd is None:
                logger.warning(f"Could not get USD price for {currency}, holding profit for later")
                amount_usd = Decimal("0")  # Will be held
            else:
                amount_usd = amount * price_usd

            logger.info(f"Server profit: {amount} {currency} = ${amount_usd:.2f} USD (threshold: ${min_profit})")

            if amount_usd >= min_profit:
                # Send immediately to admin wallet
                admin_wallet = settings.get_admin_wallet(currency)

                # Get system wallet for this currency
                system_wallet = await db.wallets.find_one({
                    "user_id": "SYSTEM",
                    "currency": currency
                })

                if not system_wallet:
                    logger.error(f"No system wallet found for {currency} - cannot send profit. Creating profit hold instead.")
                    # Create hold instead
                    profit_hold = ProfitHold(
                        transaction_id=transaction_id,
                        user_id="system",
                        currency=currency,
                        amount=str(amount),
                        usd_value=str(amount_usd),
                        reason="no_system_wallet"
                    )
                    result = await db.profit_holds.insert_one(
                        profit_hold.dict(by_alias=True, exclude={"id"})
                    )
                    await db.transactions.update_one(
                        {"_id": ObjectId(transaction_id)},
                        {"$set": {"profit_hold_id": str(result.inserted_id)}}
                    )
                    return

                # Get system wallet private key
                system_private_key = self.encryption.decrypt_private_key(system_wallet["encrypted_private_key"])

                # Send profit to admin wallet
                try:
                    logger.info(f"Sending ${amount_usd:.2f} ({amount} {currency}) profit to admin {admin_wallet[:10]}...")

                    success, message, tx_hash = await self.tatum.send_transaction(
                        currency,
                        system_wallet["address"],
                        system_private_key,
                        admin_wallet,
                        float(amount)
                    )

                    if success:
                        logger.info(f"Profit sent to admin: {tx_hash}")
                        # Update transaction as profit sent
                        await db.transactions.update_one(
                            {"_id": ObjectId(transaction_id)},
                            {"$set": {
                                "profit_sent": True,
                                "profit_tx_hash": tx_hash,
                                "profit_sent_at": datetime.utcnow()
                            }}
                        )
                    else:
                        logger.error(f"Failed to send profit to admin: {message}")
                        # Create hold for failed send
                        profit_hold = ProfitHold(
                            transaction_id=transaction_id,
                            user_id="system",
                            currency=currency,
                            amount=str(amount),
                            usd_value=str(amount_usd),
                            reason=f"send_failed: {message}"
                        )
                        result = await db.profit_holds.insert_one(
                            profit_hold.dict(by_alias=True, exclude={"id"})
                        )
                        await db.transactions.update_one(
                            {"_id": ObjectId(transaction_id)},
                            {"$set": {"profit_hold_id": str(result.inserted_id)}}
                        )

                except Exception as send_error:
                    logger.error(f"Exception sending profit: {send_error}", exc_info=True)
                    # Create hold for exception
                    profit_hold = ProfitHold(
                        transaction_id=transaction_id,
                        user_id="system",
                        currency=currency,
                        amount=str(amount),
                        usd_value=str(amount_usd),
                        reason=f"exception: {str(send_error)}"
                    )
                    result = await db.profit_holds.insert_one(
                        profit_hold.dict(by_alias=True, exclude={"id"})
                    )
                    await db.transactions.update_one(
                        {"_id": ObjectId(transaction_id)},
                        {"$set": {"profit_hold_id": str(result.inserted_id)}}
                    )

            else:
                # Hold profit for batch processing (below minimum threshold)
                profit_hold = ProfitHold(
                    transaction_id=transaction_id,
                    user_id="system",
                    currency=currency,
                    amount=str(amount),
                    usd_value=str(amount_usd),
                    reason="below_minimum"
                )

                result = await db.profit_holds.insert_one(
                    profit_hold.dict(by_alias=True, exclude={"id"})
                )

                # Update transaction with hold reference
                await db.transactions.update_one(
                    {"_id": ObjectId(transaction_id)},
                    {"$set": {"profit_hold_id": str(result.inserted_id)}}
                )

                logger.info(f"Held ${amount_usd:.2f} ({amount} {currency}) profit for batch processing (below ${min_profit} threshold)")

        except Exception as e:
            logger.error(f"Failed to process server profit: {e}", exc_info=True)
            # Don't raise - profit processing shouldn't block withdrawal

    async def get_transactions(
        self,
        user_id: str,
        currency: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get transaction history for user (improved with USD values and fees)

        Args:
            user_id: Discord user ID
            currency: Optional currency filter
            limit: Max results
            offset: Pagination offset

        Returns:
            List of transactions with USD values
        """
        try:
            from app.services.price_service import price_service

            db = get_database()

            query = {"user_id": user_id}

            if currency:
                query["currency"] = currency.upper()

            cursor = db.transactions.find(query).sort("created_at", -1).skip(offset).limit(limit)

            def format_fee(value) -> str:
                """Format fee to avoid scientific notation"""
                if not value:
                    return None
                try:
                    decimal_val = Decimal(str(value))
                    formatted = format(decimal_val, 'f')
                    if '.' in formatted:
                        formatted = formatted.rstrip('0').rstrip('.')
                    return formatted if formatted != '' else "0"
                except:
                    return str(value)

            transactions = []
            async for tx in cursor:
                currency_code = tx["currency"]
                amount = tx["amount"]

                # Get USD value
                usd_value = await price_service.convert_to_usd(amount, currency_code)

                # Format transaction data
                tx_data = {
                    "tx_id": tx["tx_id"],
                    "type": tx["type"],
                    "currency": currency_code,
                    "amount": amount,
                    "usd_value": usd_value,
                    "status": tx["status"],
                    "tx_hash": tx.get("blockchain_tx_hash"),
                    "to_address": tx.get("to_address"),
                    "from_address": tx.get("from_address"),
                    "network_fee": format_fee(tx.get("network_fee")),
                    "server_fee": format_fee(tx.get("server_fee")),
                    "created_at": tx["created_at"].isoformat(),
                    "confirmations": tx.get("confirmations", 0)
                }

                transactions.append(tx_data)

            return transactions

        except Exception as e:
            logger.error(f"Failed to get transactions: {e}", exc_info=True)
            raise

    async def get_portfolio(self, user_id: str) -> List[Dict]:
        """
        Get all balances for user (portfolio view with USD values)

        Args:
            user_id: Discord user ID

        Returns:
            List of balances for all currencies with USD values
        """
        try:
            from app.services.price_service import price_service

            db = get_database()

            # Helper to format balance
            def format_balance(value) -> str:
                """Format balance to avoid scientific notation"""
                if not value:
                    return "0"
                try:
                    decimal_val = Decimal(str(value))
                    formatted = format(decimal_val, 'f')
                    if '.' in formatted:
                        formatted = formatted.rstrip('0').rstrip('.')
                    return formatted if formatted != '' else "0"
                except:
                    return str(value)

            # First, collect all balances with wallet addresses
            temp_balances = []
            currencies_to_fetch = []

            cursor = db.balances.find({"user_id": user_id})

            async for balance in cursor:
                currency = balance["currency"]

                # Skip unsupported currencies (e.g., old V3 codes)
                if not is_valid_currency(currency):
                    logger.warning(f"Skipping unsupported currency in portfolio: {currency} for user {user_id}")
                    continue

                # Get wallet address
                wallet = await db.wallets.find_one({
                    "user_id": user_id,
                    "currency": currency
                })

                if not wallet:
                    logger.warning(f"No wallet found for {user_id}/{currency}")
                    continue

                # Calculate total
                available = Decimal(str(balance["available"]))
                locked = Decimal(str(balance["locked"]))
                pending = Decimal(str(balance["pending"]))
                total = available + locked + pending

                temp_balances.append({
                    "currency": currency,
                    "address": wallet["address"],
                    "available": format_balance(balance["available"]),
                    "locked": format_balance(balance["locked"]),
                    "pending": format_balance(balance["pending"]),
                    "total": format_balance(total),
                    "total_decimal": total
                })
                currencies_to_fetch.append(currency)

            # Batch fetch all prices at once to avoid rate limiting
            prices = await price_service.get_prices_batch(currencies_to_fetch)

            # Now add USD values to balances
            balances = []
            for bal in temp_balances:
                currency = bal["currency"]
                price = prices.get(currency)

                if price is not None:
                    usd_value = bal["total_decimal"] * price
                    bal["usd_value"] = f"{usd_value:.2f}"
                else:
                    bal["usd_value"] = None

                # Remove temporary field
                del bal["total_decimal"]
                balances.append(bal)

            return balances

        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}", exc_info=True)
            raise



# Global service instance
_wallet_service = None


def get_wallet_service() -> WalletService:
    """Get singleton wallet service instance"""
    global _wallet_service

    if _wallet_service is None:
        _wallet_service = WalletService()

    return _wallet_service
