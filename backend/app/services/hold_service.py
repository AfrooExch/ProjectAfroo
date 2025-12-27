"""
Hold Service - Fund locking/escrow for tickets
Manages locking and releasing exchanger funds during exchanges
V4 System - Uses exchanger_deposits with held/fee_reserved fields
"""

from typing import Optional, Dict, List
from datetime import datetime
from decimal import Decimal
from bson import ObjectId
import logging

from app.core.database import get_db_collection, get_audit_logs_collection

logger = logging.getLogger(__name__)


class HoldService:
    """Service for hold/escrow operations"""

    @staticmethod
    async def create_multi_currency_hold(
        ticket_id: str,
        user_id: str,
        amount_usd: Decimal
    ) -> List[dict]:
        """
        Create multi-currency hold - automatically lock funds from ANY available deposits (V4 System).

        Automatically uses whatever deposits are available to reach the required USD amount.
        Example: Need $10 → Use $3 BTC + $4 ETH + $3 LTC

        Steps:
        1. Calculate total needed (ticket amount + server fee)
        2. Get all deposits and calculate available USD value
        3. Allocate funds from available deposits to reach total
        4. Create hold records for each currency used
        5. Update deposits: increment held and fee_reserved

        Args:
            ticket_id: Ticket MongoDB _id
            user_id: Discord user ID (string, not ObjectId!)
            amount_usd: Ticket amount in USD (Decimal)

        Returns:
            List of hold records created
        """
        deposits_db = await get_db_collection("exchanger_deposits")
        holds_db = await get_db_collection("ticket_holds")
        from app.services.price_service import price_service

        # 1. Calculate server fee (2% of ticket, min $0.50) - comes FROM the ticket amount
        # Exchanger only needs the ticket amount available, fee is taken from it
        server_fee_usd = max(amount_usd * Decimal("0.02"), Decimal("0.50"))
        total_needed_usd = amount_usd  # NOT amount + fee! Fee comes from the amount.

        logger.info(f"Creating multi-currency hold: ticket=${amount_usd} (server fee=${server_fee_usd} reserved from this)")

        # 2. Get all deposits and calculate available USD value
        deposits = await deposits_db.find({"user_id": user_id}).to_list(length=100)

        if not deposits:
            raise ValueError(
                f"Insufficient funds: You need to deposit at least ${total_needed_usd:.2f} USD worth of cryptocurrency to claim this ticket. "
                f"Visit the deposit panel to add funds."
            )

        # Calculate available USD value for each deposit
        available_deposits = []
        for deposit in deposits:
            currency = deposit["currency"]
            balance = Decimal(deposit.get("balance", "0"))
            held = Decimal(deposit.get("held", "0"))
            fee_reserved = Decimal(deposit.get("fee_reserved", "0"))
            available_crypto = balance - held - fee_reserved

            if available_crypto <= 0:
                continue

            # Get USD value
            price_usd = await price_service.get_price_usd(currency)
            if not price_usd:
                logger.warning(f"Cannot get price for {currency}, skipping")
                continue

            available_usd = available_crypto * price_usd

            available_deposits.append({
                "currency": currency,
                "available_crypto": available_crypto,
                "available_usd": available_usd,
                "price_usd": price_usd,
                "deposit": deposit
            })

        # Sort by available USD (descending) - use largest deposits first
        available_deposits.sort(key=lambda x: x["available_usd"], reverse=True)

        # Calculate total available
        total_available_usd = sum(d["available_usd"] for d in available_deposits)

        logger.info(f"User has ${total_available_usd:.2f} available across {len(available_deposits)} currencies")

        if total_available_usd < total_needed_usd:
            raise ValueError(
                f"Insufficient balance. Need ${total_needed_usd:.2f} USD "
                f"(includes ${server_fee_usd:.2f} server fee), "
                f"but only ${total_available_usd:.2f} USD available across all deposits"
            )

        # 3. Allocate funds from available deposits
        # Important: Fee comes FROM the ticket amount, not added on top
        # For $10 ticket: hold $9.50 + reserve $0.50 fee = $10 total
        hold_records = []
        ticket_after_fee_usd = amount_usd - server_fee_usd  # $10 - $0.50 = $9.50
        remaining_ticket_usd = ticket_after_fee_usd
        remaining_fee_usd = server_fee_usd

        for deposit_info in available_deposits:
            if remaining_ticket_usd <= 0 and remaining_fee_usd <= 0:
                break

            currency = deposit_info["currency"]
            available_crypto = deposit_info["available_crypto"]
            available_usd = deposit_info["available_usd"]
            price_usd = deposit_info["price_usd"]

            # Calculate how much to take from this deposit (max = ticket_after_fee + fee)
            needed_usd = remaining_ticket_usd + remaining_fee_usd
            take_usd = min(needed_usd, available_usd)

            # Calculate ticket and fee portions
            if remaining_ticket_usd > 0:
                ticket_portion_usd = min(remaining_ticket_usd, take_usd)
                remaining_ticket_usd -= ticket_portion_usd
            else:
                ticket_portion_usd = Decimal("0")

            if remaining_fee_usd > 0:
                fee_portion_usd = min(remaining_fee_usd, take_usd - ticket_portion_usd)
                remaining_fee_usd -= fee_portion_usd
            else:
                fee_portion_usd = Decimal("0")

            # Convert USD amounts to crypto
            ticket_portion_crypto = ticket_portion_usd / price_usd
            fee_portion_crypto = fee_portion_usd / price_usd

            # 4. Create hold record
            hold_dict = {
                "ticket_id": ObjectId(ticket_id),
                "user_id": user_id,
                "currency": currency,
                "amount_usd": str(ticket_portion_usd),
                "crypto_held": str(ticket_portion_crypto),
                "server_fee_usd": str(fee_portion_usd),
                "server_fee_crypto": str(fee_portion_crypto),
                "price_at_hold": str(price_usd),
                "status": "active",
                "created_at": datetime.utcnow(),
                "released_at": None,
                "refunded_at": None
            }

            result = await holds_db.insert_one(hold_dict)
            hold_dict["_id"] = result.inserted_id
            hold_records.append(hold_dict)

            # 5. Update deposit (lock funds)
            current_held = Decimal(deposit_info["deposit"].get("held", "0"))
            current_fee_reserved = Decimal(deposit_info["deposit"].get("fee_reserved", "0"))

            new_held = current_held + ticket_portion_crypto
            new_fee_reserved = current_fee_reserved + fee_portion_crypto

            await deposits_db.update_one(
                {"user_id": user_id, "currency": currency},
                {
                    "$set": {
                        "held": str(new_held),
                        "fee_reserved": str(new_fee_reserved),
                        "last_synced": datetime.utcnow()
                    }
                }
            )

            logger.info(
                f"Allocated from {currency}: ${ticket_portion_usd:.2f} ticket + ${fee_portion_usd:.2f} fee "
                f"= {ticket_portion_crypto + fee_portion_crypto:.8f} {currency}"
            )

        # Log action
        await HoldService.log_action(
            user_id,
            "hold.created_multi",
            {
                "ticket_id": ticket_id,
                "amount_usd": str(amount_usd),
                "server_fee_usd": str(server_fee_usd),
                "currencies_used": [h["currency"] for h in hold_records],
                "hold_count": len(hold_records)
            }
        )

        logger.info(
            f"Multi-currency hold created: ticket={ticket_id} user={user_id} "
            f"amount=${amount_usd} fee=${server_fee_usd} currencies={len(hold_records)}"
        )

        return hold_records

    @staticmethod
    async def create_hold(
        ticket_id: str,
        user_id: str,
        currency: str,
        amount_usd: Decimal
    ) -> dict:
        """
        Create hold - lock funds for ticket from SPECIFIC currency (V4 System).
        DEPRECATED: Use create_multi_currency_hold instead for auto-allocation.

        Steps:
        1. Calculate server fee (2% of ticket, min $0.50)
        2. Check available balance (must have ticket amount + server fee available)
        3. Create hold record
        4. Update deposit: increment held (ticket amount) and fee_reserved (server fee)

        Args:
            ticket_id: Ticket MongoDB _id
            user_id: Discord user ID (string, not ObjectId!)
            currency: Currency code (BTC, ETH, etc.)
            amount_usd: Ticket amount in USD (Decimal)
        """
        deposits_db = await get_db_collection("exchanger_deposits")

        # 1. Calculate server fee (2%, min $0.50)
        server_fee_usd = max(amount_usd * Decimal("0.02"), Decimal("0.50"))
        total_needed_usd = amount_usd + server_fee_usd

        # 2. Get deposit and check available balance
        deposit = await deposits_db.find_one({
            "user_id": user_id,
            "currency": currency
        })

        if not deposit:
            raise ValueError(f"No {currency} deposit found for user {user_id}")

        # Calculate available (balance - held - fee_reserved)
        balance = Decimal(deposit.get("balance", "0"))
        held = Decimal(deposit.get("held", "0"))
        fee_reserved = Decimal(deposit.get("fee_reserved", "0"))
        available_crypto = balance - held - fee_reserved

        # Get USD value of available crypto
        from app.services.price_service import price_service
        price_usd = await price_service.get_price_usd(currency)

        if not price_usd:
            raise ValueError(f"Cannot get price for {currency}")

        available_usd = available_crypto * price_usd

        if available_usd < total_needed_usd:
            raise ValueError(
                f"Insufficient balance. Need ${total_needed_usd:.2f} USD "
                f"(${amount_usd:.2f} ticket + ${server_fee_usd:.2f} fee), "
                f"but only ${available_usd:.2f} USD available in {currency}"
            )

        # Calculate crypto amounts to lock
        crypto_amount_for_ticket = amount_usd / price_usd
        crypto_amount_for_fee = server_fee_usd / price_usd

        # 3. Create hold record
        holds_db = await get_db_collection("ticket_holds")

        hold_dict = {
            "ticket_id": ObjectId(ticket_id),
            "user_id": user_id,  # Store as string (Discord ID)
            "currency": currency,
            "amount_usd": str(amount_usd),
            "crypto_held": str(crypto_amount_for_ticket),
            "server_fee_usd": str(server_fee_usd),
            "server_fee_crypto": str(crypto_amount_for_fee),
            "price_at_hold": str(price_usd),
            "status": "active",
            "created_at": datetime.utcnow(),
            "released_at": None,
            "refunded_at": None
        }

        result = await holds_db.insert_one(hold_dict)
        hold_dict["_id"] = result.inserted_id

        # 4. Update deposit (lock funds)
        new_held = held + crypto_amount_for_ticket
        new_fee_reserved = fee_reserved + crypto_amount_for_fee

        await deposits_db.update_one(
            {"user_id": user_id, "currency": currency},
            {
                "$set": {
                    "held": str(new_held),
                    "fee_reserved": str(new_fee_reserved),
                    "last_synced": datetime.utcnow()
                }
            }
        )

        # Log
        await HoldService.log_action(
            user_id,
            "hold.created",
            {
                "ticket_id": ticket_id,
                "currency": currency,
                "amount_usd": str(amount_usd),
                "crypto_held": str(crypto_amount_for_ticket),
                "server_fee_usd": str(server_fee_usd),
                "server_fee_crypto": str(crypto_amount_for_fee)
            }
        )

        logger.info(
            f"Hold created: ticket={ticket_id} user={user_id} currency={currency} "
            f"amount=${amount_usd} fee=${server_fee_usd}"
        )

        return hold_dict

    @staticmethod
    async def release_hold(
        hold_id: str,
        deduct_funds: bool = True
    ) -> dict:
        """
        Release hold - complete ticket (V4 System).

        Steps:
        1. Get hold record
        2. Unlock held amount and fee_reserved
        3. Deduct ticket amount + fee from balance (if deduct_funds=True)
        4. Auto-collect server fee to admin wallet
        5. Mark hold as released

        Args:
            hold_id: Hold MongoDB _id
            deduct_funds: If True, deduct from balance (completion). If False, just unlock (cancel/refund)
        """
        holds_db = await get_db_collection("ticket_holds")
        deposits_db = await get_db_collection("exchanger_deposits")

        # 1. Get hold
        hold = await holds_db.find_one({"_id": ObjectId(hold_id)})

        if not hold:
            raise ValueError(f"Hold {hold_id} not found")

        if hold["status"] != "active":
            raise ValueError(f"Hold {hold_id} is not active (status: {hold['status']})")

        user_id = hold["user_id"]
        currency = hold["currency"]
        crypto_held = Decimal(hold["crypto_held"])
        server_fee_crypto = Decimal(hold["server_fee_crypto"])
        server_fee_usd = Decimal(hold["server_fee_usd"])

        # 2. Get current deposit
        logger.debug(f"[HOLD RELEASE DEBUG] Looking for deposit: user_id={user_id} (type={type(user_id).__name__}) currency={currency}")

        deposit = await deposits_db.find_one({
            "user_id": user_id,
            "currency": currency
        })

        if not deposit:
            logger.error(f"[HOLD RELEASE ERROR] Deposit not found for user {user_id} currency {currency}")
            raise ValueError(f"Deposit not found for user {user_id} currency {currency}")

        balance = Decimal(deposit.get("balance", "0"))
        held = Decimal(deposit.get("held", "0"))
        fee_reserved = Decimal(deposit.get("fee_reserved", "0"))

        logger.debug(f"[HOLD RELEASE DEBUG] Current deposit values: balance={balance} held={held} fee_reserved={fee_reserved}")
        logger.debug(f"[HOLD RELEASE DEBUG] Hold values: crypto_held={crypto_held} server_fee_crypto={server_fee_crypto}")

        # 3. Calculate new values with safeguards against negative amounts
        new_held = max(Decimal("0"), held - crypto_held)
        new_fee_reserved = max(Decimal("0"), fee_reserved - server_fee_crypto)

        if deduct_funds:
            # Completion: Deduct ticket amount + fee from balance
            new_balance = max(Decimal("0"), balance - crypto_held - server_fee_crypto)
        else:
            # Cancel/Refund: Just unlock, don't deduct
            new_balance = balance

        # Validation: Warn if values would have gone negative
        if held < crypto_held:
            logger.warning(f"[HOLD RELEASE WARNING] held ({held}) < crypto_held ({crypto_held}), clamped to 0")
        if fee_reserved < server_fee_crypto:
            logger.warning(f"[HOLD RELEASE WARNING] fee_reserved ({fee_reserved}) < server_fee_crypto ({server_fee_crypto}), clamped to 0")
        if deduct_funds and balance < (crypto_held + server_fee_crypto):
            logger.warning(f"[HOLD RELEASE WARNING] balance ({balance}) < total_deduction ({crypto_held + server_fee_crypto}), clamped to 0")

        logger.debug(f"[HOLD RELEASE DEBUG] New values: balance={new_balance} held={new_held} fee_reserved={new_fee_reserved}")

        # Update deposit
        update_result = await deposits_db.update_one(
            {"user_id": user_id, "currency": currency},
            {
                "$set": {
                    "balance": str(new_balance),
                    "held": str(new_held),
                    "fee_reserved": str(new_fee_reserved),
                    "last_synced": datetime.utcnow()
                }
            }
        )

        logger.debug(f"[HOLD RELEASE DEBUG] Update result: matched={update_result.matched_count} modified={update_result.modified_count}")

        if update_result.matched_count == 0:
            logger.error(f"[HOLD RELEASE ERROR] Update did not match any documents! user_id={user_id} currency={currency}")
        elif update_result.modified_count == 0:
            logger.warning(f"[HOLD RELEASE WARNING] Update matched but did not modify any documents (values may be the same)")

        # Verify update
        updated_deposit = await deposits_db.find_one({"user_id": user_id, "currency": currency})
        if updated_deposit:
            logger.debug(f"[HOLD RELEASE DEBUG] Verified updated values: balance={updated_deposit.get('balance')} held={updated_deposit.get('held')} fee_reserved={updated_deposit.get('fee_reserved')}")
        else:
            logger.error(f"[HOLD RELEASE ERROR] Could not find deposit after update!")

        # 4. Auto-collect server fee to admin wallet (if completing ticket)
        if deduct_funds and server_fee_crypto > 0:
            await HoldService._collect_fee_to_admin(
                currency=currency,
                amount_crypto=server_fee_crypto,
                amount_usd=server_fee_usd,
                ticket_id=str(hold["ticket_id"]),
                exchanger_id=user_id
            )

        # 5. Mark hold as released
        await holds_db.update_one(
            {"_id": ObjectId(hold_id)},
            {
                "$set": {
                    "status": "released" if deduct_funds else "refunded",
                    "released_at": datetime.utcnow() if deduct_funds else None,
                    "refunded_at": None if deduct_funds else datetime.utcnow()
                }
            }
        )

        # Log
        action = "hold.released" if deduct_funds else "hold.refunded"
        await HoldService.log_action(
            user_id,
            action,
            {
                "hold_id": hold_id,
                "ticket_id": str(hold["ticket_id"]),
                "currency": currency,
                "crypto_held": str(crypto_held),
                "server_fee_crypto": str(server_fee_crypto),
                "server_fee_usd": str(server_fee_usd),
                "deducted": deduct_funds
            }
        )

        logger.info(
            f"Hold {'released' if deduct_funds else 'refunded'}: hold={hold_id} "
            f"ticket={hold['ticket_id']} currency={currency} "
            f"held={crypto_held} fee={server_fee_crypto}"
        )

        return hold

    @staticmethod
    async def refund_hold(hold_id: str) -> dict:
        """
        Refund hold - cancel/unclaim ticket, unlock funds (no deduction).
        Just calls release_hold with deduct_funds=False
        """
        return await HoldService.release_hold(hold_id, deduct_funds=False)

    @staticmethod
    async def _collect_fee_to_admin(
        currency: str,
        amount_crypto: Decimal,
        amount_usd: Decimal,
        ticket_id: str,
        exchanger_id: str
    ):
        """
        Auto-collect server fee to admin wallet.

        Steps:
        1. Get or create admin deposit for this currency
        2. Add fee to admin's balance
        3. Record fee collection for tracking
        """
        from app.core.config import settings

        deposits_db = await get_db_collection("exchanger_deposits")
        server_fees_db = await get_db_collection("server_fees")

        # 1. Get or create admin deposit
        admin_user_id = "admin"
        admin_deposit = await deposits_db.find_one({
            "user_id": admin_user_id,
            "currency": currency
        })

        if not admin_deposit:
            # Create admin deposit if it doesn't exist
            try:
                admin_wallet_address = settings.get_admin_wallet(currency)
            except ValueError:
                logger.warning(f"No admin wallet configured for {currency}, fee not collected")
                return

            admin_deposit = {
                "user_id": admin_user_id,
                "currency": currency,
                "address": admin_wallet_address,
                "balance": "0",
                "held": "0",
                "fee_reserved": "0",
                "total_deposited": "0",
                "total_withdrawn": "0",
                "created_at": datetime.utcnow(),
                "last_synced": datetime.utcnow()
            }
            await deposits_db.insert_one(admin_deposit)
            current_balance = Decimal("0")
        else:
            current_balance = Decimal(admin_deposit.get("balance", "0"))

        # 2. Add fee to admin balance
        new_admin_balance = current_balance + amount_crypto
        await deposits_db.update_one(
            {"user_id": admin_user_id, "currency": currency},
            {
                "$set": {
                    "balance": str(new_admin_balance),
                    "last_synced": datetime.utcnow()
                }
            }
        )

        # 3. Record fee collection
        fee_record = {
            "ticket_id": ObjectId(ticket_id),
            "exchanger_id": exchanger_id,
            "currency": currency,
            "amount_crypto": str(amount_crypto),
            "amount_usd": str(amount_usd),
            "status": "collected",
            "collected_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }

        await server_fees_db.insert_one(fee_record)

        logger.info(
            f"Server fee collected to admin wallet: ticket={ticket_id} exchanger={exchanger_id} "
            f"currency={currency} amount={amount_crypto} (${amount_usd}) "
            f"admin_balance={new_admin_balance}"
        )

    @staticmethod
    async def get_active_holds(user_id: str) -> List[dict]:
        """Get active holds for user (V4 - user_id is Discord ID string)"""
        holds_db = await get_db_collection("ticket_holds")

        cursor = holds_db.find({
            "user_id": user_id,  # String Discord ID
            "status": "active"
        }).sort("created_at", -1)

        return await cursor.to_list(length=100)

    @staticmethod
    async def get_holds_by_ticket(ticket_id: str) -> List[dict]:
        """Get all holds for a ticket (multi-currency support)"""
        holds_db = await get_db_collection("ticket_holds")

        cursor = holds_db.find({"ticket_id": ObjectId(ticket_id)})
        return await cursor.to_list(length=100)

    @staticmethod
    async def get_hold_by_ticket(ticket_id: str) -> Optional[dict]:
        """Get hold by ticket ID (legacy - returns first hold only)"""
        holds = await HoldService.get_holds_by_ticket(ticket_id)
        return holds[0] if holds else None

    @staticmethod
    async def release_all_holds_for_ticket(
        ticket_id: str,
        deduct_funds: bool = True
    ) -> List[dict]:
        """
        Release ALL holds for a ticket (multi-currency support).

        Args:
            ticket_id: Ticket MongoDB _id
            deduct_funds: If True, deduct from balance (completion). If False, just unlock (cancel/refund)

        Returns:
            List of released hold records
        """
        holds = await HoldService.get_holds_by_ticket(ticket_id)

        if not holds:
            raise ValueError(f"No holds found for ticket {ticket_id}")

        released_holds = []
        for hold in holds:
            if hold["status"] == "active":
                released_hold = await HoldService.release_hold(str(hold["_id"]), deduct_funds)
                released_holds.append(released_hold)

        logger.info(f"Released {len(released_holds)} holds for ticket {ticket_id}")
        return released_holds

    @staticmethod
    async def log_action(user_id: str, action: str, details: dict):
        """Log hold action (V4 - user_id is Discord ID string)"""
        audit_logs = get_audit_logs_collection()

        # Try to convert Discord ID string to MongoDB ObjectId by looking up user
        from app.core.database import get_users_collection
        users = get_users_collection()
        user = await users.find_one({"discord_id": user_id})

        user_object_id = user["_id"] if user else None

        await audit_logs.insert_one({
            "user_id": user_object_id if user_object_id else user_id,  # Store ObjectId if found, else string
            "discord_id": user_id,  # Always store Discord ID for reference
            "actor_type": "system",
            "action": action,
            "resource_type": "hold",
            "resource_id": user_object_id if user_object_id else user_id,
            "details": details,
            "created_at": datetime.utcnow()
        })
