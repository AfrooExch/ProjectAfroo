"""
Exchanger Service - V4 with V4 Wallet Integration
Handles exchanger deposits, holds, fees, and claim limits
Supports all 14 cryptocurrencies
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from bson import ObjectId
from decimal import Decimal
import logging
import asyncio
from collections import defaultdict

from app.core.database import get_db_collection
from app.models.exchanger import (
    ExchangerDeposit,
    TicketHold,
    HoldAllocation,
    FeeReservation,
    FeeAllocation,
    ExchangerProfile
)
from app.services.price_service import price_service

logger = logging.getLogger(__name__)


# All 14 supported cryptocurrencies (from wallet system)
SUPPORTED_CURRENCIES = [
    "BTC", "LTC", "ETH", "SOL",
    "USDC-SOL", "USDC-ETH",
    "USDT-SOL", "USDT-ETH",
    "XRP", "BNB", "TRX",
    "MATIC", "AVAX", "DOGE"
]


class ExchangerService:
    """Service for exchanger operations with V4 wallet integration"""

    # Configuration
    CLAIM_LIMIT_MULTIPLIER = 1.0  # Can claim up to 1x deposit balance ($100 deposited = $100 claim limit)
    HOLD_MULTIPLIER = 1.0  # Hold 100% of ticket value

    # Per-user locks to prevent race conditions
    _user_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @staticmethod
    def _get_user_lock(user_id: str) -> asyncio.Lock:
        """Get lock for user to prevent race conditions"""
        return ExchangerService._user_locks[user_id]

    @staticmethod
    async def create_deposit_wallet(user_id: str, currency: str) -> ExchangerDeposit:
        """
        Create SEPARATE exchanger deposit wallet (NOT same as regular wallet)
        Generates brand new address and private key to prevent bypass

        Args:
            user_id: Discord user ID
            currency: Currency code (BTC, ETH, etc.)

        Returns:
            ExchangerDeposit
        """
        async with ExchangerService._get_user_lock(user_id):
            db = await get_db_collection("exchanger_deposits")

            # Check if already exists
            existing = await db.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if existing:
                return ExchangerDeposit(**existing)

            # Validate currency
            if currency.upper() not in SUPPORTED_CURRENCIES:
                raise ValueError(f"Currency {currency} not supported")

            # Generate BRAND NEW wallet (separate from V4 regular wallet)
            from app.services.tatum_service import TatumService
            from app.core.encryption import get_encryption_service
            encryption = get_encryption_service()

            tatum_service = TatumService()

            # TOKEN LOGIC: SPL/ERC-20 tokens share address with parent chain
            # USDC-SOL, USDT-SOL use same address as SOL (need SOL for gas)
            # USDC-ETH, USDT-ETH use same address as ETH (need ETH for gas)
            parent_currency = None
            if currency.upper() in ["USDC-ETH", "USDT-ETH"]:
                parent_currency = "ETH"
            elif currency.upper() in ["USDC-SOL", "USDT-SOL"]:
                parent_currency = "SOL"

            if parent_currency:
                # Check if parent wallet exists
                parent_deposit = await db.find_one({
                    "user_id": user_id,
                    "currency": parent_currency
                })

                if parent_deposit:
                    # Use parent wallet's address and key (tokens share address with parent)
                    logger.info(f"Using existing {parent_currency} exchanger wallet for {currency}")
                    wallet_address = parent_deposit["wallet_address"]
                    encrypted_private_key = parent_deposit["encrypted_private_key"]
                else:
                    # Generate new wallet for parent chain
                    logger.info(f"Generating new {parent_currency} wallet for {currency} token")
                    wallet_data = await tatum_service.generate_wallet(parent_currency)
                    wallet_address = wallet_data["address"]
                    private_key = wallet_data["private_key"]
                    encrypted_private_key = encryption.encrypt_private_key(private_key)
            else:
                # Generate new wallet with new private key (native coin)
                wallet_data = await tatum_service.generate_wallet(currency)
                wallet_address = wallet_data["address"]
                private_key = wallet_data["private_key"]
                encrypted_private_key = encryption.encrypt_private_key(private_key)

            # Create exchanger deposit record
            deposit = ExchangerDeposit(
                user_id=user_id,
                currency=currency,
                wallet_address=wallet_address,
                encrypted_private_key=encrypted_private_key,
                balance="0",
                unconfirmed_balance="0",
                held="0",
                fee_reserved="0"
            )

            deposit_dict = deposit.model_dump(by_alias=True, exclude_none=True)
            # Remove _id to let MongoDB generate it
            if "_id" in deposit_dict:
                del deposit_dict["_id"]
            result = await db.insert_one(deposit_dict)

            logger.info(f"Created SEPARATE exchanger deposit wallet: user={user_id} currency={currency} address={wallet_address}")
            logger.info(f"This wallet is SEPARATE from regular V4 wallet to prevent bypass!")

            # Fetch the inserted document to return proper ExchangerDeposit object
            inserted_deposit = await db.find_one({"_id": result.inserted_id})
            return ExchangerDeposit(**inserted_deposit)

    @staticmethod
    async def get_deposit(user_id: str, currency: str) -> Optional[ExchangerDeposit]:
        """Get exchanger deposit wallet"""
        db = await get_db_collection("exchanger_deposits")

        deposit_data = await db.find_one({
            "user_id": user_id,
            "currency": currency
        })

        if not deposit_data:
            return None

        return ExchangerDeposit(**deposit_data)

    @staticmethod
    async def list_deposits(user_id: str) -> List[ExchangerDeposit]:
        """List all deposit wallets for exchanger"""
        db = await get_db_collection("exchanger_deposits")

        cursor = db.find({"user_id": user_id, "is_active": True})
        deposits_data = await cursor.to_list(length=100)

        return [ExchangerDeposit(**d) for d in deposits_data]

    @staticmethod
    async def sync_deposit_balance(user_id: str, currency: str) -> ExchangerDeposit:
        """
        Sync deposit balance from V4 wallet system
        Updates balance, held, fee_reserved based on active holds/fees
        """
        async with ExchangerService._get_user_lock(user_id):
            db = await get_db_collection("exchanger_deposits")

            deposit_data = await db.find_one({
                "user_id": user_id,
                "currency": currency
            })

            if not deposit_data:
                raise ValueError(f"No {currency} deposit found for user {user_id}")

            # Get balance from blockchain using exchanger deposit's address
            from app.services.tatum_service import TatumService
            tatum_service = TatumService()

            wallet_address = deposit_data["wallet_address"]
            balance_result = await tatum_service.get_balance(currency, wallet_address)
            confirmed_balance = str(balance_result.get("confirmed", 0))
            unconfirmed_balance = str(balance_result.get("unconfirmed", 0))

            # Calculate held and fee_reserved from active holds (V4 multi-currency system)
            # Holds are stored directly in ticket_holds with crypto_held and server_fee_crypto
            holds_db = await get_db_collection("ticket_holds")

            # Aggregate held amounts (crypto_held field) for this user and currency
            held_pipeline = [
                {
                    "$match": {
                        "user_id": user_id,  # Discord ID string
                        "currency": currency,
                        "status": "active"
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_held": {"$sum": {"$toDecimal": "$crypto_held"}},
                        "total_fee": {"$sum": {"$toDecimal": "$server_fee_crypto"}}
                    }
                }
            ]

            result = await holds_db.aggregate(held_pipeline).to_list(length=1)

            if result:
                held_amount = str(result[0].get("total_held", 0))
                fee_reserved_amount = str(result[0].get("total_fee", 0))
            else:
                held_amount = "0"
                fee_reserved_amount = "0"

            # Calculate USD values
            balance_usd = None
            held_usd = None
            fee_reserved_usd = None

            try:
                price_usd = await price_service.get_price_usd(currency)
                if price_usd:
                    balance_usd = str(Decimal(confirmed_balance) * price_usd)
                    held_usd = str(Decimal(held_amount) * price_usd)
                    fee_reserved_usd = str(Decimal(fee_reserved_amount) * price_usd)
            except Exception as e:
                logger.warning(f"Failed to calculate USD values for {currency}: {e}")

            # Update deposit
            update_fields = {
                "balance": confirmed_balance,
                "unconfirmed_balance": unconfirmed_balance,
                "held": held_amount,
                "fee_reserved": fee_reserved_amount,
                "last_synced": datetime.utcnow()
            }

            # Add USD fields if calculated successfully
            if balance_usd is not None:
                update_fields["balance_usd"] = balance_usd
            if held_usd is not None:
                update_fields["held_usd"] = held_usd
            if fee_reserved_usd is not None:
                update_fields["fee_reserved_usd"] = fee_reserved_usd

            await db.update_one(
                {"user_id": user_id, "currency": currency},
                {"$set": update_fields}
            )

            # Get updated deposit
            updated_data = await db.find_one({"user_id": user_id, "currency": currency})
            return ExchangerDeposit(**updated_data)

    @staticmethod
    async def get_aggregate_balance_usd(user_id: str) -> Decimal:
        """Get total USD value of all deposit balances"""
        deposits = await ExchangerService.list_deposits(user_id)

        total_usd = Decimal("0")
        for deposit in deposits:
            balance = Decimal(deposit.balance)
            if balance > 0:
                price_usd = await price_service.get_price_usd(deposit.currency)
                if price_usd:
                    total_usd += balance * price_usd

        return total_usd

    @staticmethod
    async def get_total_held_usd(user_id: str) -> Decimal:
        """Get total USD value currently held across all deposits"""
        db = await get_db_collection("ticket_holds")

        # Sum all active holds for this exchanger
        pipeline = [
            {
                "$match": {
                    "exchanger_id": user_id,
                    "status": "active"
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": {"$toDecimal": "$hold_usd"}}
                }
            }
        ]

        result = await db.aggregate(pipeline).to_list(length=1)
        return Decimal(str(result[0]["total"])) if result else Decimal("0")

    @staticmethod
    async def get_total_fee_reserved_usd(user_id: str) -> Decimal:
        """Get total USD value of fee_reserved across all deposits"""
        deposits = await ExchangerService.list_deposits(user_id)

        total_fee_reserved_usd = Decimal("0")
        for deposit in deposits:
            fee_reserved = deposit.get_fee_reserved_decimal()
            if fee_reserved > 0:
                price_usd = await price_service.get_price_usd(deposit.currency)
                if price_usd:
                    total_fee_reserved_usd += fee_reserved * price_usd

        return total_fee_reserved_usd

    @staticmethod
    async def get_available_usd_for_holds(user_id: str) -> Decimal:
        """Get available USD that can be used for new holds"""
        deposits = await ExchangerService.list_deposits(user_id)

        total_available_usd = Decimal("0")
        for deposit in deposits:
            available = deposit.get_available_decimal()
            if available > 0:
                price_usd = await price_service.get_price_usd(deposit.currency)
                if price_usd:
                    total_available_usd += available * price_usd

        return total_available_usd

    @staticmethod
    async def can_claim_ticket(user_id: str, ticket_amount_usd: Decimal) -> Tuple[bool, str, Decimal]:
        """
        Check if exchanger can claim ticket based on deposit limits

        Returns:
            (can_claim, reason, available_to_claim_usd)
        """
        # Get total deposit balance
        total_deposit_usd = await ExchangerService.get_aggregate_balance_usd(user_id)

        # Calculate claim limit
        claim_limit_usd = total_deposit_usd * Decimal(str(ExchangerService.CLAIM_LIMIT_MULTIPLIER))

        # Get total already held
        total_held_usd = await ExchangerService.get_total_held_usd(user_id)

        # Check if enough available
        available_usd = await ExchangerService.get_available_usd_for_holds(user_id)

        if available_usd < ticket_amount_usd:
            return False, (
                f"Insufficient available balance. Need ${ticket_amount_usd:.2f} "
                f"but only ${available_usd:.2f} available"
            ), available_usd

        # Check claim limit
        new_total_held = total_held_usd + ticket_amount_usd
        if new_total_held > claim_limit_usd:
            remaining = claim_limit_usd - total_held_usd
            return False, (
                f"Would exceed claim limit (${new_total_held:.2f} > ${claim_limit_usd:.2f}). "
                f"Only ${remaining:.2f} available to claim."
            ), remaining

        return True, f"Can claim (${new_total_held:.2f} <= ${claim_limit_usd:.2f})", claim_limit_usd - new_total_held

    @staticmethod
    async def hold_funds_for_ticket(ticket_id: str, exchanger_id: str, ticket_amount_usd: Decimal) -> TicketHold:
        """
        Hold funds for active ticket
        Locks exchanger deposits proportionally across assets
        """
        async with ExchangerService._get_user_lock(exchanger_id):
            holds_db = await get_db_collection("ticket_holds")
            allocations_db = await get_db_collection("hold_allocations")

            # Calculate hold amount
            hold_amount_usd = ticket_amount_usd * Decimal(str(ExchangerService.HOLD_MULTIPLIER))

            # Get all deposits with available balance
            deposits = await ExchangerService.list_deposits(exchanger_id)

            asset_data = []
            total_available_usd = Decimal("0")

            for deposit in deposits:
                available = deposit.get_available_decimal()
                if available > 0:
                    price_usd = await price_service.get_price_usd(deposit.currency)
                    if price_usd:
                        available_usd = available * price_usd
                        asset_data.append({
                            "deposit": deposit,
                            "available": available,
                            "available_usd": available_usd,
                            "price_usd": price_usd
                        })
                        total_available_usd += available_usd

            if total_available_usd < hold_amount_usd:
                raise ValueError(
                    f"Insufficient funds: need ${hold_amount_usd:.2f} but only ${total_available_usd:.2f} available"
                )

            # Sort by available USD (largest first)
            asset_data.sort(key=lambda x: x["available_usd"], reverse=True)

            # Create hold
            hold = TicketHold(
                ticket_id=ticket_id,
                exchanger_id=exchanger_id,
                hold_usd=str(hold_amount_usd),
                status="active"
            )

            hold_dict = hold.model_dump(by_alias=True, exclude_none=True)
            result = await holds_db.insert_one(hold_dict)
            hold_id = result.inserted_id

            # Allocate hold across assets
            remaining_usd = hold_amount_usd
            deposits_db = await get_db_collection("exchanger_deposits")

            for asset_info in asset_data:
                if remaining_usd <= 0:
                    break

                deposit = asset_info["deposit"]
                available_usd = asset_info["available_usd"]
                price_usd = asset_info["price_usd"]

                # Calculate allocation
                allocate_usd = min(remaining_usd, available_usd)
                allocate_units = allocate_usd / price_usd

                # Create allocation record
                allocation = HoldAllocation(
                    hold_id=hold_id,
                    currency=deposit.currency,
                    amount=str(allocate_units),
                    usd_at_allocation=str(allocate_usd),
                    rate_usd_per_unit=str(price_usd)
                )

                alloc_dict = allocation.model_dump(by_alias=True, exclude_none=True)
                await allocations_db.insert_one(alloc_dict)

                # Update deposit held amount (atomic)
                prev_held = Decimal(deposit.held)
                new_held = prev_held + allocate_units

                update_result = await deposits_db.update_one(
                    {
                        "_id": deposit.id,
                        "balance": {"$gte": str(new_held)}  # Ensure sufficient balance
                    },
                    {"$set": {"held": str(new_held)}}
                )

                if update_result.modified_count == 0:
                    raise ValueError(f"Failed to hold funds for {deposit.currency} - race condition or insufficient balance")

                remaining_usd -= allocate_usd

                logger.info(
                    f"Allocated {allocate_units:.8f} {deposit.currency} "
                    f"(${allocate_usd:.2f}) for ticket {ticket_id}"
                )

            logger.info(f"Successfully held ${hold_amount_usd:.2f} for ticket {ticket_id}")

            return TicketHold(**{**hold_dict, "_id": hold_id})

    @staticmethod
    async def release_funds_for_ticket(ticket_id: str) -> bool:
        """
        Release held funds when ticket is completed/cancelled
        """
        holds_db = await get_db_collection("ticket_holds")
        allocations_db = await get_db_collection("hold_allocations")
        deposits_db = await get_db_collection("exchanger_deposits")

        # Find active hold
        hold_data = await holds_db.find_one({
            "ticket_id": ticket_id,
            "status": "active"
        })

        if not hold_data:
            logger.warning(f"No active hold found for ticket {ticket_id}")
            return False

        # Get allocations
        cursor = allocations_db.find({"hold_id": hold_data["_id"]})
        allocations = await cursor.to_list(length=None)

        # Release each allocation
        for allocation in allocations:
            # Get deposit
            deposit_data = await deposits_db.find_one({
                "user_id": hold_data["exchanger_id"],
                "currency": allocation["currency"]
            })

            if deposit_data:
                # Update held amount
                prev_held = Decimal(deposit_data.get("held", "0"))
                release_amount = Decimal(allocation["amount"])
                new_held = max(Decimal("0"), prev_held - release_amount)

                await deposits_db.update_one(
                    {"_id": deposit_data["_id"]},
                    {"$set": {"held": str(new_held)}}
                )

                logger.info(
                    f"Released {release_amount:.8f} {allocation['currency']} "
                    f"from hold for ticket {ticket_id}"
                )

        # Update hold status
        await holds_db.update_one(
            {"_id": hold_data["_id"]},
            {
                "$set": {
                    "status": "released",
                    "released_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"Released hold for ticket {ticket_id}")
        return True

    @staticmethod
    async def get_claim_limit_info(user_id: str) -> Dict:
        """Get claim limit information for exchanger"""
        total_deposit_usd = await ExchangerService.get_aggregate_balance_usd(user_id)
        total_held_usd = await ExchangerService.get_total_held_usd(user_id)
        total_fee_reserved_usd = await ExchangerService.get_total_fee_reserved_usd(user_id)

        claim_limit_usd = total_deposit_usd * Decimal(str(ExchangerService.CLAIM_LIMIT_MULTIPLIER))
        # Available = Claim Limit - Held - Fee Reserved
        available_to_claim_usd = max(Decimal("0"), claim_limit_usd - total_held_usd - total_fee_reserved_usd)

        return {
            "total_deposit_usd": str(total_deposit_usd),
            "total_held_usd": str(total_held_usd),
            "total_fee_reserved_usd": str(total_fee_reserved_usd),
            "claim_limit_usd": str(claim_limit_usd),
            "available_to_claim_usd": str(available_to_claim_usd),
            "claim_limit_multiplier": ExchangerService.CLAIM_LIMIT_MULTIPLIER
        }

    @staticmethod
    async def withdraw_exchanger_funds(
        user_id: str,
        currency: str,
        amount: str,
        to_address: str
    ) -> Tuple[bool, str, Optional[str], Dict]:
        """
        Withdraw exchanger funds - ONLY free funds (not held or fee_reserved)
        
        Args:
            user_id: Exchanger Discord ID
            currency: Currency code
            amount: Amount to withdraw ("max" or Decimal string)
            to_address: Destination address
            
        Returns:
            (success, message, tx_hash, transaction_data)
        """
        async with ExchangerService._get_user_lock(user_id):
            deposits_db = await get_db_collection("exchanger_deposits")
            transactions_db = await get_db_collection("exchanger_transactions")
            
            # Get deposit
            deposit_data = await deposits_db.find_one({
                "user_id": user_id,
                "currency": currency
            })
            
            if not deposit_data:
                return False, f"No {currency} deposit found", None, {}
            
            deposit = ExchangerDeposit(**deposit_data)

            # Calculate available (FREE funds only)
            balance = deposit.get_balance_decimal()
            held = deposit.get_held_decimal()
            fee_reserved = deposit.get_fee_reserved_decimal()
            available = deposit.get_available_decimal()

            logger.info(
                f"Withdraw check: user={user_id} currency={currency} "
                f"balance={balance} held={held} fee_reserved={fee_reserved} available={available}"
            )

            if available <= 0:
                return False, f"No available {currency} to withdraw (all funds are held or reserved)", None, {}
            
            # Handle "max" amount
            if amount.lower() == "max":
                withdraw_amount = available
            else:
                withdraw_amount = Decimal(amount)
            
            # Validate amount
            if withdraw_amount <= 0:
                return False, "Amount must be greater than 0", None, {}
            
            if withdraw_amount > available:
                return False, (
                    f"Cannot withdraw {withdraw_amount} {currency}. "
                    f"Only {available} {currency} available (rest is held/reserved)"
                ), None, {}
            
            # Calculate ONLY network fee
            # NOTE: Server fees (exchanger_fee) are already calculated and stored in fee_reserved
            # by the ticket system and fee service. We don't calculate them here!
            # Use same network fees as wallet service for consistency
            network_fees = {
                "BTC": Decimal("0.000005"),
                "ETH": Decimal("0.001"),
                "USDC-ETH": Decimal("0.001"),
                "USDT-ETH": Decimal("0.001"),
                "SOL": Decimal("0.000005"),
                "USDC-SOL": Decimal("0.000005"),
                "USDT-SOL": Decimal("0.000005"),
                "LTC": Decimal("0.001"),  # Increased from 0.0000025 to meet LTC network relay fee requirements
                "XRP": Decimal("0.00001"),
                "BNB": Decimal("0.0005"),
                "TRX": Decimal("1"),
                "MATIC": Decimal("0.01"),
                "AVAX": Decimal("0.001"),
                "DOGE": Decimal("2")
            }
            network_fee = network_fees.get(currency.upper(), Decimal("0.0001"))

            # Check if we have enough for network fee
            if withdraw_amount <= network_fee:
                return False, f"Amount too small. Network fee is {network_fee} {currency}", None, {}

            # Calculate send amount (what recipient actually gets)
            send_amount = withdraw_amount - network_fee
            
            # Get encrypted private key and decrypt
            from app.core.encryption import get_encryption_service
            encryption = get_encryption_service()
            encrypted_key = deposit_data.get("encrypted_private_key")

            if not encrypted_key:
                return False, "Wallet private key not found", None, {}

            # Try to decrypt the private key
            try:
                private_key = encryption.decrypt_private_key(encrypted_key)
            except Exception as decrypt_err:
                logger.error(
                    f"Failed to decrypt private key for {user_id}/{currency}: {decrypt_err}"
                )
                # Return special error tuple with status code indicator
                # Format: (success, message, tx_hash, transaction, is_system_error)
                return False, (
                    f"Unable to access wallet private key. Your {currency} exchanger wallet may have "
                    f"a corrupted encryption key. Please contact support with error code: DECRYPT_FAIL"
                ), None, {}, True  # True indicates system error, not user error

            # Initialize Tatum service
            from app.services.tatum_service import TatumService
            tatum_service = TatumService()

            # Send transaction (positional args: blockchain, from_address, private_key, to_address, amount)
            success, message, tx_hash = await tatum_service.send_transaction(
                currency,  # blockchain
                deposit.wallet_address,  # from_address
                private_key,  # private_key
                to_address,  # to_address
                float(send_amount)  # amount - what recipient receives after network fee
            )

            # Create transaction record
            transaction = {
                "user_id": user_id,
                "currency": currency,
                "type": "withdrawal",
                "amount": str(send_amount),  # Amount recipient receives
                "total_deducted": str(withdraw_amount),  # Total from balance
                "status": "confirmed" if success else "failed",
                "tx_hash": tx_hash,
                "to_address": to_address,
                "from_address": deposit.wallet_address,
                "network_fee": str(network_fee),
                "error_message": message if not success else None,
                "created_at": datetime.utcnow(),
                "confirmed_at": datetime.utcnow() if success else None
            }
            
            result = await transactions_db.insert_one(transaction)
            transaction["_id"] = result.inserted_id
            
            if success:
                # Update deposit balance
                new_balance = Decimal(deposit.balance) - withdraw_amount
                await deposits_db.update_one(
                    {"_id": deposit_data["_id"]},
                    {"$set": {"balance": str(new_balance)}}
                )

                logger.info(
                    f"Exchanger withdrawal: user={user_id} currency={currency} "
                    f"send={send_amount} network_fee={network_fee} total={withdraw_amount} tx={tx_hash}"
                )
            else:
                logger.error(f"Exchanger withdrawal failed: {message}")

            return success, message, tx_hash, transaction

    @staticmethod
    async def get_transaction_history(
        user_id: str,
        currency: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get exchanger transaction history
        
        Args:
            user_id: Exchanger Discord ID
            currency: Optional currency filter
            limit: Max transactions to return
            
        Returns:
            List of transactions
        """
        transactions_db = await get_db_collection("exchanger_transactions")
        
        query = {"user_id": user_id}
        if currency:
            query["currency"] = currency
        
        cursor = transactions_db.find(query).sort("created_at", -1).limit(limit)
        transactions = await cursor.to_list(length=limit)
        
        return transactions

    @staticmethod
    async def log_deposit(
        user_id: str,
        currency: str,
        amount: Decimal,
        tx_hash: str,
        from_address: str
    ):
        """Log deposit transaction"""
        transactions_db = await get_db_collection("exchanger_transactions")
        
        transaction = {
            "user_id": user_id,
            "currency": currency,
            "type": "deposit",
            "amount": str(amount),
            "status": "confirmed",
            "tx_hash": tx_hash,
            "from_address": from_address,
            "to_address": (await ExchangerService.get_deposit(user_id, currency)).wallet_address,
            "network_fee": "0",
            "exchanger_fee": "0",
            "created_at": datetime.utcnow(),
            "confirmed_at": datetime.utcnow()
        }
        
        await transactions_db.insert_one(transaction)
        logger.info(f"Logged exchanger deposit: user={user_id} currency={currency} amount={amount}")

    # ====================
    # Exchanger Preferences
    # ====================

    @staticmethod
    async def get_preferences(user_id: str) -> Dict:
        """
        Get exchanger preferences
        Creates default preferences if not found
        """
        prefs_db = await get_db_collection("exchanger_preferences")

        prefs = await prefs_db.find_one({"user_id": user_id})

        if not prefs:
            # Create default preferences
            default_prefs = {
                "user_id": user_id,
                "preferred_payment_methods": [],
                "preferred_currencies": [],
                "min_ticket_amount": None,
                "max_ticket_amount": None,
                "notifications_enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await prefs_db.insert_one(default_prefs)
            default_prefs["_id"] = result.inserted_id
            return default_prefs

        return prefs

    @staticmethod
    async def update_preferences(user_id: str, updates: Dict) -> Dict:
        """
        Update exchanger preferences

        Args:
            user_id: Exchanger Discord ID
            updates: Dictionary of fields to update

        Returns:
            Updated preferences
        """
        prefs_db = await get_db_collection("exchanger_preferences")

        # Ensure preferences exist
        await ExchangerService.get_preferences(user_id)

        # Add updated_at timestamp
        updates["updated_at"] = datetime.utcnow()

        # Update preferences
        await prefs_db.update_one(
            {"user_id": user_id},
            {"$set": updates}
        )

        # Return updated preferences
        return await ExchangerService.get_preferences(user_id)

    @staticmethod
    async def check_ticket_match_preferences(ticket: Dict, exchanger_id: str) -> bool:
        """
        Check if ticket matches exchanger's preferences
        Used for filtering notifications

        Args:
            ticket: Ticket dictionary
            exchanger_id: Exchanger Discord ID

        Returns:
            True if ticket matches preferences
        """
        prefs = await ExchangerService.get_preferences(exchanger_id)

        # If notifications disabled, don't match
        if not prefs.get("notifications_enabled", True):
            return False

        # Check payment method preferences
        preferred_methods = prefs.get("preferred_payment_methods", [])
        if preferred_methods:
            ticket_method = ticket.get("send_method") or ticket.get("receive_method")
            if ticket_method not in preferred_methods:
                return False

        # Check currency preferences
        preferred_currencies = prefs.get("preferred_currencies", [])
        if preferred_currencies:
            ticket_currency = ticket.get("send_crypto") or ticket.get("receive_crypto")
            if ticket_currency and ticket_currency not in preferred_currencies:
                return False

        # Check amount range
        ticket_amount = Decimal(str(ticket.get("amount_usd", 0)))

        min_amount = prefs.get("min_ticket_amount")
        if min_amount:
            if ticket_amount < Decimal(min_amount):
                return False

        max_amount = prefs.get("max_ticket_amount")
        if max_amount:
            if ticket_amount > Decimal(max_amount):
                return False

        return True

    # ====================
    # Exchanger Questions
    # ====================

    @staticmethod
    async def get_awaiting_claim_tickets(limit: int = 25) -> List[Dict]:
        """
        Get tickets that are awaiting_claim or open (unclaimed tickets)
        For use in Ask Question feature

        Args:
            limit: Maximum number of tickets to return

        Returns:
            List of ticket dictionaries
        """
        tickets_db = await get_db_collection("tickets")

        cursor = tickets_db.find({
            "status": {"$in": ["open", "awaiting_claim"]},  # Both open and awaiting_claim tickets
            "type": "exchange"  # Only exchange tickets can be asked questions on
        }).sort("created_at", -1).limit(limit)

        tickets = await cursor.to_list(length=limit)
        return tickets

    @staticmethod
    async def ask_question(
        exchanger_id: str,
        ticket_id: str,
        question_text: str,
        question_type: str = "preset",
        alt_payment_method: Optional[str] = None,
        alt_amount_usd: Optional[str] = None
    ) -> Dict:
        """
        Ask anonymous question on ticket

        Args:
            exchanger_id: Exchanger Discord ID
            ticket_id: Target ticket ID
            question_text: Question text
            question_type: preset, custom, alt_payment, alt_amount
            alt_payment_method: Alternative payment method (for alt_payment)
            alt_amount_usd: Alternative amount (for alt_amount)

        Returns:
            Question record
        """
        questions_db = await get_db_collection("exchanger_questions")
        tickets_db = await get_db_collection("tickets")

        # Verify ticket exists and is awaiting_claim or open
        ticket = await tickets_db.find_one({"ticket_id": ticket_id})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        if ticket.get("status") not in ["open", "awaiting_claim"]:
            raise ValueError(f"Ticket {ticket_id} is not available for questions (status: {ticket.get('status')})")

        # Format question text with alternatives
        full_question = question_text

        if question_type == "alt_payment" and alt_payment_method:
            full_question += f"\n\n**Alternative Payment Method:** {alt_payment_method}"

        if question_type == "alt_amount" and alt_amount_usd:
            full_question += f"\n\n**Alternative Amount:** ${alt_amount_usd} USD"

        # Create question record
        question = {
            "ticket_id": ticket_id,
            "exchanger_id": exchanger_id,
            "question_text": full_question,
            "question_type": question_type,
            "alt_payment_method": alt_payment_method,
            "alt_amount_usd": alt_amount_usd,
            "created_at": datetime.utcnow(),
            "posted_to_channel": False
        }

        result = await questions_db.insert_one(question)
        question["_id"] = result.inserted_id

        logger.info(f"Exchanger {exchanger_id} asked question on ticket {ticket_id}")

        return question

    @staticmethod
    async def get_ticket_questions(ticket_id: str) -> List[Dict]:
        """Get all questions for a ticket"""
        questions_db = await get_db_collection("exchanger_questions")

        cursor = questions_db.find({
            "ticket_id": ticket_id
        }).sort("created_at", 1)

        questions = await cursor.to_list(length=100)
        return questions

    @staticmethod
    async def mark_question_posted(question_id: ObjectId):
        """Mark question as posted to channel"""
        questions_db = await get_db_collection("exchanger_questions")

        await questions_db.update_one(
            {"_id": question_id},
            {"$set": {"posted_to_channel": True}}
        )

    # ====================
    # Premade Messages
    # ====================

    @staticmethod
    async def get_premades(user_id: str) -> List[Dict]:
        """Get all premade messages for exchanger"""
        profiles_db = await get_db_collection("exchanger_profiles")

        profile = await profiles_db.find_one({"user_id": user_id})

        if not profile or "premades" not in profile:
            return []

        return profile["premades"]

    @staticmethod
    async def create_premade(user_id: str, name: str, content: str) -> Dict:
        """Create a new premade message"""
        profiles_db = await get_db_collection("exchanger_profiles")

        # Get or create profile
        profile = await profiles_db.find_one({"user_id": user_id})

        if not profile:
            # Create new profile with premade
            profile = {
                "user_id": user_id,
                "username": "",  # Will be updated by bot
                "total_volume_usd": "0",
                "total_trades": 0,
                "rating": 0.0,
                "completion_rate": 0.0,
                "is_active": True,
                "is_verified": False,
                "premades": [],
                "created_at": datetime.utcnow()
            }
            await profiles_db.insert_one(profile)

        # Create premade
        premade = {
            "name": name,
            "content": content,
            "created_at": datetime.utcnow()
        }

        # Add to profile
        await profiles_db.update_one(
            {"user_id": user_id},
            {"$push": {"premades": premade}}
        )

        logger.info(f"Exchanger {user_id} created premade '{name}'")

        return premade

    @staticmethod
    async def delete_premade(user_id: str, name: str) -> bool:
        """Delete a premade message by name"""
        profiles_db = await get_db_collection("exchanger_profiles")

        result = await profiles_db.update_one(
            {"user_id": user_id},
            {"$pull": {"premades": {"name": name}}}
        )

        if result.modified_count > 0:
            logger.info(f"Exchanger {user_id} deleted premade '{name}'")
            return True

        return False
