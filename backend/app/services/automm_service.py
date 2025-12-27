"""
AutoMM P2P Escrow Service
Secure peer-to-peer cryptocurrency escrow with temporary wallets
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
from bson import ObjectId

from app.core.database import get_database
from app.services.tatum_service import TatumService
from app.core.security import encrypt_private_key, get_decrypted_private_key

logger = logging.getLogger(__name__)


def serialize_escrow(escrow: Dict) -> Dict:
    """
    Serialize escrow document for JSON response.

    Converts ObjectId and datetime objects to strings.
    """
    if not escrow:
        return escrow

    # Create a deep copy to avoid modifying original
    import copy
    result = copy.deepcopy(escrow)

    # Convert _id
    if "_id" in result:
        result["_id"] = str(result["_id"])

    # Convert all datetime fields
    datetime_fields = ["created_at", "updated_at", "released_at", "completed_at", "disputed_at", "cancelled_at"]
    for field in datetime_fields:
        if field in result and isinstance(result[field], datetime):
            result[field] = result[field].isoformat()

    # Convert datetime in events array
    if "events" in result and isinstance(result["events"], list):
        for event in result["events"]:
            if "timestamp" in event and isinstance(event["timestamp"], datetime):
                event["timestamp"] = event["timestamp"].isoformat()
            # Also convert any ObjectIds in event data
            if "data" in event and isinstance(event["data"], dict):
                for key, value in list(event["data"].items()):
                    if isinstance(value, ObjectId):
                        event["data"][key] = str(value)
                    elif isinstance(value, datetime):
                        event["data"][key] = value.isoformat()

    # Remove sensitive encrypted keys
    result.pop("encrypted_key", None)
    result.pop("party1_encrypted_key", None)
    result.pop("party2_encrypted_key", None)

    return result


class AutoMMService:
    """Service for AutoMM P2P escrow operations"""

    @staticmethod
    async def create_buyer_escrow(
        buyer_id: str,
        seller_id: str,
        amount: float,
        crypto: str,
        service_description: str,
        channel_id: str
    ) -> Dict:
        """
        Create buyer-protection escrow with single wallet for buyer to deposit.

        Args:
            buyer_id: Discord ID of buyer
            seller_id: Discord ID of seller
            amount: Amount buyer will pay
            crypto: Cryptocurrency (BTC, ETH, etc.)
            service_description: What buyer is purchasing
            channel_id: Discord channel ID

        Returns:
            Dict with escrow_id and deposit_address
        """
        try:
            logger.info(f"Creating buyer escrow: {buyer_id} -> {seller_id} | {amount} {crypto}")

            # Generate temporary wallet for buyer deposit
            deposit_wallet = await TatumService.generate_wallet(crypto)

            # Encrypt private key
            encrypted_key = encrypt_private_key(deposit_wallet["private_key"])

            # Create escrow document
            escrow_data = {
                "type": "buyer_protection",
                "buyer_id": buyer_id,
                "seller_id": seller_id,
                "amount": amount,
                "crypto": crypto.upper(),
                "service_description": service_description,
                "deposit_address": deposit_wallet["address"],
                "encrypted_key": encrypted_key,
                "balance": 0.0,
                "status": "awaiting_deposit",  # awaiting_deposit, deposit_confirmed, released, completed, disputed
                "deposit_status": "not_received",  # not_received, pending_confirmation, confirmed
                "channel_id": channel_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "events": [
                    {
                        "type": "created",
                        "timestamp": datetime.utcnow(),
                        "data": {
                            "buyer_id": buyer_id,
                            "seller_id": seller_id,
                            "amount": amount,
                            "crypto": crypto,
                            "service": service_description
                        }
                    }
                ]
            }

            db = get_database()
            result = await db.automm_escrow.insert_one(escrow_data)
            escrow_id = str(result.inserted_id)

            # Generate MM ID from last 8 chars of ObjectId
            mm_id = escrow_id[-8:].upper()

            # Update with MM ID
            await db.automm_escrow.update_one(
                {"_id": result.inserted_id},
                {"$set": {"mm_id": mm_id}}
            )

            logger.info(f"Created buyer escrow {escrow_id} (MM #{mm_id}): Deposit address {deposit_wallet['address']}")

            return {
                "escrow_id": escrow_id,
                "mm_id": mm_id,
                "deposit_address": deposit_wallet["address"]
            }

        except Exception as e:
            logger.error(f"Error creating buyer escrow: {e}", exc_info=True)
            raise

    @staticmethod
    async def check_deposit(escrow_id: str) -> Dict:
        """
        Check if buyer has deposited funds.

        Args:
            escrow_id: Escrow ID

        Returns:
            Dict with status and balance
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            # Check balance
            balance_data = await TatumService.get_balance(
                escrow["crypto"],
                escrow["deposit_address"]
            )
            balance = float(balance_data.get("confirmed", 0))
            pending = float(balance_data.get("unconfirmed", 0))

            # Determine status and confirmations
            # If Tatum reports it as "confirmed", it means it has met minimum confirmations
            # Tatum's get_balance returns confirmed/unconfirmed, not exact confirmation count
            if balance > 0:
                status = "confirmed"
                # If balance is confirmed, assume it has 3+ confirmations (Tatum's threshold)
                confirmations = 3
            elif pending > 0:
                status = "pending_confirmation"
                # Still pending, not enough confirmations yet
                confirmations = 1
            else:
                status = "not_received"
                confirmations = 0

            # Update database
            await db.automm_escrow.update_one(
                {"_id": ObjectId(escrow_id)},
                {
                    "$set": {
                        "balance": balance,
                        "deposit_status": status,
                        "confirmations": confirmations,
                        "updated_at": datetime.utcnow()
                    },
                    "$push": {
                        "events": {
                            "type": "deposit_check",
                            "timestamp": datetime.utcnow(),
                            "data": {
                                "status": status,
                                "balance": balance,
                                "confirmations": confirmations
                            }
                        }
                    }
                }
            )

            logger.info(f"Escrow {escrow_id}: Deposit status {status} ({balance} {escrow['crypto']}, {confirmations} confirmations)")

            # Return only simple data types
            return {
                "status": str(status),
                "balance": float(balance),
                "confirmations": int(confirmations)
            }

        except Exception as e:
            logger.error(f"Error checking deposit for escrow {escrow_id}: {e}", exc_info=True)
            raise

    @staticmethod
    async def release_funds(escrow_id: str, seller_address: str) -> Dict:
        """
        Release funds from escrow to seller's wallet.

        Args:
            escrow_id: Escrow ID
            seller_address: Seller's wallet address to receive funds

        Returns:
            Dict with tx_hash and tx_url
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            if escrow.get("status") == "released":
                raise ValueError(f"Escrow {escrow_id} already released")

            if escrow.get("deposit_status") != "confirmed":
                raise ValueError("Deposit not confirmed yet")

            # Calculate amount to send (subtract fee for UTXO coins)
            send_amount = escrow.get("balance", 0)
            crypto = escrow.get("crypto", "").upper()

            # For UTXO-based coins (BTC, LTC, DOGE), subtract estimated fee
            if crypto in ["BTC", "LTC", "DOGE"]:
                # LTC uses 5 sat/byte, ~250 bytes = 0.0000125 LTC fee
                if crypto == "LTC":
                    estimated_fee = 0.0000125
                elif crypto == "DOGE":
                    estimated_fee = 0.01  # DOGE has higher fees
                else:  # BTC
                    estimated_fee = 0.00001  # Will be auto-calculated by Tatum

                send_amount = round(escrow.get("balance", 0) - estimated_fee, 8)

                if send_amount <= 0:
                    raise ValueError(f"Balance too low to cover fees ({escrow.get('balance', 0)} {crypto})")

                logger.info(f"Escrow {escrow_id}: Sending {send_amount} {crypto} (balance {escrow.get('balance', 0)}, fee ~{estimated_fee})")

            # Send transaction
            success, msg, tx_hash = await TatumService.send_transaction(
                blockchain=crypto,
                from_address=escrow.get("deposit_address", ""),
                private_key=get_decrypted_private_key(escrow.get("encrypted_key", "")),
                to_address=seller_address,
                amount=send_amount
            )

            if not success:
                raise Exception(f"Failed to send transaction: {msg}")

            # Build explorer URL
            tx_url = TatumService.get_explorer_url(escrow.get("crypto", crypto), tx_hash)

            # Update database
            await db.automm_escrow.update_one(
                {"_id": ObjectId(escrow_id)},
                {
                    "$set": {
                        "status": "released",
                        "seller_address": seller_address,
                        "tx_hash": tx_hash,
                        "released_at": datetime.utcnow()
                    },
                    "$push": {
                        "events": {
                            "type": "released",
                            "timestamp": datetime.utcnow(),
                            "data": {
                                "seller_address": seller_address,
                                "tx_hash": tx_hash,
                                "amount": escrow.get("balance", 0)
                            }
                        }
                    }
                }
            )

            logger.info(f"Escrow {escrow_id}: Released {send_amount} {crypto} to {seller_address} | TX: {tx_hash}")

            # Return only simple data types - no ObjectIds or complex objects
            return {
                "tx_hash": str(tx_hash) if tx_hash else "",
                "tx_url": str(tx_url) if tx_url else "",
                "amount": str(send_amount),  # Amount actually sent (after fees)
                "crypto": str(crypto)
            }

        except Exception as e:
            logger.error(f"Error releasing funds for escrow {escrow_id}: {e}", exc_info=True)
            raise

    @staticmethod
    async def complete_escrow_transaction(escrow_id: str) -> Dict:
        """
        Mark escrow as completed (seller confirms receipt).

        Args:
            escrow_id: Escrow ID

        Returns:
            Success dict
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            if escrow.get("status") != "released":
                raise ValueError("Funds must be released before completing")

            # Track AutoMM completion stats
            from app.services.stats_tracking_service import StatsTrackingService
            from app.services.price_service import PriceService

            # Get exact crypto USD value for stats
            balance = escrow.get("balance", 0)
            crypto = escrow.get("crypto", "BTC")

            # Fetch real-time price
            price_usd = await PriceService.get_price_usd(crypto)
            amount_usd = float(balance * price_usd) if price_usd else 0

            await StatsTrackingService.track_automm_completion(
                buyer_id=escrow.get("buyer_id"),
                seller_id=escrow.get("seller_id"),
                amount_usd=amount_usd
            )

            # Mark as completed
            await db.automm_escrow.update_one(
                {"_id": ObjectId(escrow_id)},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow()
                    },
                    "$push": {
                        "events": {
                            "type": "completed",
                            "timestamp": datetime.utcnow()
                        }
                    }
                }
            )

            logger.info(f"Escrow {escrow_id}: Completed")

            return {"success": True}

        except Exception as e:
            logger.error(f"Error completing escrow {escrow_id}: {e}", exc_info=True)
            raise

    @staticmethod
    async def request_cancel(escrow_id: str, user_id: str) -> Dict:
        """
        Request to cancel escrow. Tracks which parties have approved.

        Both buyer and seller must approve before refund can be processed.

        Args:
            escrow_id: Escrow ID
            user_id: Discord user ID requesting cancel

        Returns:
            Success dict with cancel_approved_by list
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            if escrow.get("status") in ["completed", "cancelled"]:
                raise ValueError(f"Cannot cancel escrow with status: {escrow.get('status')}")

            # Get current cancel approvals
            cancel_approved_by = escrow.get("cancel_approved_by", [])

            # Add user_id to approval list if not already there
            if user_id not in cancel_approved_by:
                cancel_approved_by.append(user_id)

                await db.automm_escrow.update_one(
                    {"_id": ObjectId(escrow_id)},
                    {
                        "$set": {
                            "cancel_approved_by": cancel_approved_by
                        },
                        "$push": {
                            "events": {
                                "type": "cancel_requested",
                                "timestamp": datetime.utcnow(),
                                "data": {
                                    "user_id": user_id
                                }
                            }
                        }
                    }
                )

                logger.info(f"Escrow {escrow_id}: Cancel approved by {user_id}")

            return {
                "cancel_approved_by": cancel_approved_by,
                "both_approved": len(cancel_approved_by) >= 2
            }

        except Exception as e:
            logger.error(f"Error requesting cancel for escrow {escrow_id}: {e}", exc_info=True)
            raise

    @staticmethod
    async def process_refund(escrow_id: str, buyer_address: str) -> Dict:
        """
        Process refund to buyer after both parties agree to cancel.

        Returns funds from escrow wallet to buyer's wallet.

        Args:
            escrow_id: Escrow ID
            buyer_address: Buyer's wallet address for refund

        Returns:
            Dict with tx_hash and tx_url
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            # Check both parties approved cancel
            cancel_approved_by = escrow.get("cancel_approved_by", [])
            buyer_id = escrow.get("buyer_id")
            seller_id = escrow.get("seller_id")

            if buyer_id not in cancel_approved_by or seller_id not in cancel_approved_by:
                raise ValueError("Both parties must approve cancellation before refund")

            if escrow.get("status") == "cancelled":
                raise ValueError(f"Escrow {escrow_id} already cancelled")

            # Calculate amount to send (subtract fee for UTXO coins)
            send_amount = escrow.get("balance", 0)
            crypto = escrow.get("crypto", "").upper()

            # For UTXO-based coins (BTC, LTC, DOGE), subtract estimated fee
            if crypto in ["BTC", "LTC", "DOGE"]:
                if crypto == "LTC":
                    estimated_fee = 0.0000125
                elif crypto == "DOGE":
                    estimated_fee = 0.01
                else:  # BTC
                    estimated_fee = 0.00001

                send_amount = round(escrow.get("balance", 0) - estimated_fee, 8)

                if send_amount <= 0:
                    raise ValueError(f"Balance too low to cover fees ({escrow.get('balance', 0)} {crypto})")

                logger.info(f"Escrow {escrow_id}: Refunding {send_amount} {crypto} (balance {escrow.get('balance', 0)}, fee ~{estimated_fee})")

            # Send refund transaction
            success, msg, tx_hash = await TatumService.send_transaction(
                blockchain=crypto,
                from_address=escrow.get("deposit_address", ""),
                private_key=get_decrypted_private_key(escrow.get("encrypted_key", "")),
                to_address=buyer_address,
                amount=send_amount
            )

            if not success:
                raise Exception(f"Failed to send refund: {msg}")

            # Build explorer URL
            tx_url = TatumService.get_explorer_url(escrow.get("crypto", crypto), tx_hash)

            # Update database
            await db.automm_escrow.update_one(
                {"_id": ObjectId(escrow_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "refund_address": buyer_address,
                        "refund_tx_hash": tx_hash,
                        "cancelled_at": datetime.utcnow()
                    },
                    "$push": {
                        "events": {
                            "type": "refunded",
                            "timestamp": datetime.utcnow(),
                            "data": {
                                "buyer_address": buyer_address,
                                "tx_hash": tx_hash,
                                "amount": send_amount
                            }
                        }
                    }
                }
            )

            logger.info(f"Escrow {escrow_id}: Refunded {send_amount} {crypto} to {buyer_address} | TX: {tx_hash}")

            return {
                "tx_hash": str(tx_hash) if tx_hash else "",
                "tx_url": str(tx_url) if tx_url else "",
                "amount": str(send_amount),
                "crypto": str(crypto)
            }

        except Exception as e:
            logger.error(f"Error processing refund for escrow {escrow_id}: {e}", exc_info=True)
            raise

    @staticmethod
    async def create_escrow(
        party1_id: str,
        party1_crypto: str,
        party2_id: str,
        party2_crypto: str,
        channel_id: str
    ) -> Dict:
        """
        Create P2P escrow trade with temporary wallets for both parties.

        Args:
            party1_id: Discord ID of party 1
            party1_crypto: Cryptocurrency party 1 is sending (e.g., "BTC", "USDC-SOL")
            party2_id: Discord ID of party 2
            party2_crypto: Cryptocurrency party 2 is sending
            channel_id: Discord channel ID for this trade

        Returns:
            Dict with escrow_id, party1_address, party2_address
        """
        try:
            logger.info(f"Creating P2P escrow: {party1_id} ({party1_crypto}) <-> {party2_id} ({party2_crypto})")

            # Generate temporary wallets for both parties
            party1_wallet = await TatumService.generate_wallet(party1_crypto)
            party2_wallet = await TatumService.generate_wallet(party2_crypto)

            # Encrypt private keys
            party1_encrypted_key = encrypt_private_key(party1_wallet["private_key"])
            party2_encrypted_key = encrypt_private_key(party2_wallet["private_key"])

            # Create escrow document
            escrow_data = {
                "party1_id": party1_id,
                "party1_crypto": party1_crypto.upper(),
                "party1_address": party1_wallet["address"],
                "party1_encrypted_key": party1_encrypted_key,
                "party1_balance": 0.0,
                "party1_confirmed": False,
                "party1_status": "not_received",  # not_received, pending_confirmation, confirmed
                "party2_id": party2_id,
                "party2_crypto": party2_crypto.upper(),
                "party2_address": party2_wallet["address"],
                "party2_encrypted_key": party2_encrypted_key,
                "party2_balance": 0.0,
                "party2_confirmed": False,
                "party2_status": "not_received",
                "channel_id": channel_id,
                "status": "awaiting_funds",  # awaiting_funds, funds_received, completed, cancelled, disputed
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "events": [
                    {
                        "type": "created",
                        "timestamp": datetime.utcnow(),
                        "data": {
                            "party1_id": party1_id,
                            "party1_crypto": party1_crypto,
                            "party2_id": party2_id,
                            "party2_crypto": party2_crypto
                        }
                    }
                ]
            }

            db = get_database()
            result = await db.automm_escrow.insert_one(escrow_data)
            escrow_id = str(result.inserted_id)

            logger.info(f"Created P2P escrow {escrow_id}: Party1 {party1_wallet['address']}, Party2 {party2_wallet['address']}")

            return {
                "escrow_id": escrow_id,
                "party1_address": party1_wallet["address"],
                "party2_address": party2_wallet["address"]
            }

        except Exception as e:
            logger.error(f"Error creating P2P escrow: {e}", exc_info=True)
            raise

    @staticmethod
    async def check_blockchain_status(escrow_id: str) -> Dict:
        """
        Check blockchain status for both parties' escrow wallets.

        Args:
            escrow_id: Escrow ID

        Returns:
            Dict with party1_status, party2_status, party1_balance, party2_balance
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            # Check party 1's balance
            party1_balance_data = await TatumService.get_balance(
                escrow["party1_crypto"],
                escrow["party1_address"]
            )
            party1_balance = float(party1_balance_data.get("confirmed", 0))
            party1_pending = float(party1_balance_data.get("unconfirmed", 0))

            # Check party 2's balance
            party2_balance_data = await TatumService.get_balance(
                escrow["party2_crypto"],
                escrow["party2_address"]
            )
            party2_balance = float(party2_balance_data.get("confirmed", 0))
            party2_pending = float(party2_balance_data.get("unconfirmed", 0))

            # Determine status for party 1
            if party1_balance > 0:
                party1_status = "confirmed"
            elif party1_pending > 0:
                party1_status = "pending_confirmation"
            else:
                party1_status = "not_received"

            # Determine status for party 2
            if party2_balance > 0:
                party2_status = "confirmed"
            elif party2_pending > 0:
                party2_status = "pending_confirmation"
            else:
                party2_status = "not_received"

            # Update database
            await db.automm_escrow.update_one(
                {"_id": ObjectId(escrow_id)},
                {
                    "$set": {
                        "party1_balance": party1_balance,
                        "party1_status": party1_status,
                        "party2_balance": party2_balance,
                        "party2_status": party2_status,
                        "updated_at": datetime.utcnow()
                    },
                    "$push": {
                        "events": {
                            "type": "blockchain_check",
                            "timestamp": datetime.utcnow(),
                            "data": {
                                "party1_status": party1_status,
                                "party1_balance": party1_balance,
                                "party2_status": party2_status,
                                "party2_balance": party2_balance
                            }
                        }
                    }
                }
            )

            logger.info(f"Escrow {escrow_id}: Party1 {party1_status} ({party1_balance}), Party2 {party2_status} ({party2_balance})")

            return {
                "party1_status": party1_status,
                "party1_balance": party1_balance,
                "party2_status": party2_status,
                "party2_balance": party2_balance
            }

        except Exception as e:
            logger.error(f"Error checking blockchain status for escrow {escrow_id}: {e}", exc_info=True)
            raise

    @staticmethod
    async def complete_escrow(
        escrow_id: str,
        party1_destination: Optional[str] = None,
        party2_destination: Optional[str] = None
    ) -> Dict:
        """
        Complete escrow trade by releasing funds to both parties.

        If destination addresses are not provided, funds stay in escrow wallets
        (for manual withdrawal by parties).

        Args:
            escrow_id: Escrow ID
            party1_destination: Optional destination address for party 1 to receive party2's crypto
            party2_destination: Optional destination address for party 2 to receive party1's crypto

        Returns:
            Dict with success status and transaction hashes
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            if escrow["status"] == "completed":
                raise ValueError(f"Escrow {escrow_id} already completed")

            # Verify both parties have confirmed funds
            if escrow["party1_status"] != "confirmed" or escrow["party2_status"] != "confirmed":
                raise ValueError("Both parties must have confirmed funds before completing escrow")

            result = {
                "success": True,
                "party1_tx": None,
                "party2_tx": None,
                "message": "Escrow completed. Funds released."
            }

            # If destination addresses provided, send funds
            if party1_destination and party2_destination:
                # Send party2's crypto to party1's destination
                success1, msg1, tx_hash1 = await TatumService.send_transaction(
                    blockchain=escrow["party2_crypto"],
                    from_address=escrow["party2_address"],
                    private_key=get_decrypted_private_key(escrow["party2_encrypted_key"]),
                    to_address=party1_destination,
                    amount=escrow["party2_balance"]
                )

                if not success1:
                    raise Exception(f"Failed to send party2's crypto to party1: {msg1}")

                # Send party1's crypto to party2's destination
                success2, msg2, tx_hash2 = await TatumService.send_transaction(
                    blockchain=escrow["party1_crypto"],
                    from_address=escrow["party1_address"],
                    private_key=get_decrypted_private_key(escrow["party1_encrypted_key"]),
                    to_address=party2_destination,
                    amount=escrow["party1_balance"]
                )

                if not success2:
                    raise Exception(f"Failed to send party1's crypto to party2: {msg2}")

                result["party1_tx"] = tx_hash1
                result["party2_tx"] = tx_hash2

            # Mark escrow as completed
            await db.automm_escrow.update_one(
                {"_id": ObjectId(escrow_id)},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow(),
                        "party1_destination": party1_destination,
                        "party2_destination": party2_destination,
                        "party1_tx_hash": result["party1_tx"],
                        "party2_tx_hash": result["party2_tx"]
                    },
                    "$push": {
                        "events": {
                            "type": "completed",
                            "timestamp": datetime.utcnow(),
                            "data": {
                                "party1_tx": result["party1_tx"],
                                "party2_tx": result["party2_tx"]
                            }
                        }
                    }
                }
            )

            logger.info(f"Escrow {escrow_id} completed successfully")

            return result

        except Exception as e:
            logger.error(f"Error completing escrow {escrow_id}: {e}", exc_info=True)
            raise

    @staticmethod
    async def get_escrow(escrow_id: str) -> Dict:
        """
        Get escrow details.

        Args:
            escrow_id: Escrow ID

        Returns:
            Escrow document (serialized for JSON)
        """
        try:
            db = get_database()
            escrow = await db.automm_escrow.find_one({"_id": ObjectId(escrow_id)})

            if not escrow:
                raise ValueError(f"Escrow {escrow_id} not found")

            return serialize_escrow(escrow)

        except Exception as e:
            logger.error(f"Error getting escrow {escrow_id}: {e}", exc_info=True)
            raise
