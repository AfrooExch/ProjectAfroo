"""
Stats Tracking Service - Centralized user statistics tracking
Updates user_statistics collection when activities complete
"""

import logging
from typing import Optional
from datetime import datetime
from bson import ObjectId

from app.core.database import get_db_collection, get_users_collection

logger = logging.getLogger(__name__)


class StatsTrackingService:
    """Service for tracking user statistics across all platform activities"""

    # Constants
    MIN_REPUTATION = 100
    MAX_REPUTATION = 1000

    @staticmethod
    async def _add_reputation(user_id: str, amount: int = 2):
        """
        Add reputation to user with cap at MAX_REPUTATION.

        Args:
            user_id: User's MongoDB ObjectId as string
            amount: Amount of reputation to add (default: 2)
        """
        try:
            users = get_users_collection()

            # Get current reputation
            user = await users.find_one({"_id": ObjectId(user_id)})
            if not user:
                return

            current_rep = user.get("reputation_score", StatsTrackingService.MIN_REPUTATION)
            new_rep = min(current_rep + amount, StatsTrackingService.MAX_REPUTATION)

            # Only update if there's a change
            if new_rep != current_rep:
                await users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"reputation_score": new_rep}}
                )

                logger.debug(f"Updated reputation for user {user_id}: {current_rep} -> {new_rep}")

        except Exception as e:
            logger.error(f"Failed to add reputation to user {user_id}: {e}", exc_info=True)

    @staticmethod
    async def track_exchange_completion(
        client_id: str,
        exchanger_id: Optional[str],
        amount_usd: float,
        fee_amount_usd: float = 0.0,
        ticket_id: Optional[str] = None
    ):
        """
        Track completed exchange for both client and exchanger.

        Args:
            client_id: User ID of client (creator)
            exchanger_id: User ID of exchanger (Optional)
            amount_usd: Exchange value in USD
            fee_amount_usd: Fee amount paid by exchanger in USD
            ticket_id: Associated ticket ID if applicable
        """
        try:
            user_statistics = await get_db_collection("user_statistics")
            users = get_users_collection()

            # Update client stats - CLIENT GETS +2 REP PER EXCHANGE
            await user_statistics.update_one(
                {"user_id": ObjectId(client_id)},
                {
                    "$inc": {
                        "client_total_exchanges": 1,
                        "client_completed_exchanges": 1,
                        "client_exchange_volume_usd": amount_usd
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            # Award +2 reputation to client (capped at 1000)
            await StatsTrackingService._add_reputation(client_id, 2)

            # Check and award volume milestone roles to client
            await StatsTrackingService.check_exchange_volume_milestones(client_id)

            # Update exchanger stats if provided
            if exchanger_id:
                # Calculate profit (exchanger keeps amount - fee)
                exchanger_profit = amount_usd - fee_amount_usd if fee_amount_usd > 0 else 0

                await user_statistics.update_one(
                    {"user_id": ObjectId(exchanger_id)},
                    {
                        "$inc": {
                            "exchanger_total_completed": 1,
                            "exchanger_total_fees_paid_usd": fee_amount_usd,
                            "exchanger_total_profit_usd": exchanger_profit,
                            "exchanger_exchange_volume_usd": amount_usd
                        },
                        "$set": {"updated_at": datetime.utcnow()}
                    },
                    upsert=True
                )

                # Award +2 reputation to exchanger for completing ticket (capped at 1000)
                await StatsTrackingService._add_reputation(exchanger_id, 2)

                # If exchange came from ticket, count ticket completion
                if ticket_id:
                    await StatsTrackingService.track_exchanger_ticket_completion(
                        exchanger_id,
                        ticket_id,
                        "exchange"
                    )

            logger.info(f"Tracked exchange completion: client={client_id}, exchanger={exchanger_id}, amount=${amount_usd}, fee=${fee_amount_usd}")

        except Exception as e:
            logger.error(f"Failed to track exchange completion: {e}", exc_info=True)

    @staticmethod
    async def track_swap_completion(user_id: str, from_amount: float, to_amount: float, from_asset: str, to_asset: str, amount_usd: float = 0):
        """
        Track completed swap - NO REPUTATION AWARDED.

        Args:
            user_id: User ID who made the swap
            from_amount: Amount swapped from
            to_amount: Amount received
            from_asset: Source asset
            to_asset: Destination asset
            amount_usd: Swap value in USD
        """
        try:
            user_statistics = await get_db_collection("user_statistics")

            await user_statistics.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "swap_total_made": 1,
                        "swap_total_completed": 1,
                        "swap_total_volume_usd": amount_usd
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            # NO REPUTATION FOR SWAPS
            logger.info(f"Tracked swap completion: user={user_id}, {from_amount} {from_asset} -> {to_amount} {to_asset}, value=${amount_usd}")

        except Exception as e:
            logger.error(f"Failed to track swap completion: {e}", exc_info=True)

    @staticmethod
    async def track_automm_completion(buyer_id: str, seller_id: str, amount_usd: float):
        """
        Track completed AutoMM escrow deal - BOTH GET +2 REP.

        Args:
            buyer_id: Buyer user ID
            seller_id: Seller user ID
            amount_usd: Deal value in USD
        """
        try:
            user_statistics = await get_db_collection("user_statistics")
            users = get_users_collection()

            # Update buyer stats
            await user_statistics.update_one(
                {"user_id": ObjectId(buyer_id)},
                {
                    "$inc": {
                        "automm_total_created": 1,
                        "automm_total_completed": 1,
                        "automm_total_volume_usd": amount_usd
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            # Update seller stats
            await user_statistics.update_one(
                {"user_id": ObjectId(seller_id)},
                {
                    "$inc": {
                        "automm_total_created": 1,
                        "automm_total_completed": 1,
                        "automm_total_volume_usd": amount_usd
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            # +2 reputation for both parties (capped at 1000)
            await StatsTrackingService._add_reputation(buyer_id, 2)
            await StatsTrackingService._add_reputation(seller_id, 2)

            logger.info(f"Tracked AutoMM completion: buyer={buyer_id}, seller={seller_id}, amount=${amount_usd}")

        except Exception as e:
            logger.error(f"Failed to track AutoMM completion: {e}", exc_info=True)

    @staticmethod
    async def track_wallet_transaction(user_id: str, transaction_type: str, amount_usd: float, asset: str):
        """
        Track wallet transaction (deposit/withdrawal) - NO REPUTATION.

        Args:
            user_id: User ID
            transaction_type: "deposit" or "withdrawal"
            amount_usd: Transaction value in USD
            asset: Cryptocurrency asset
        """
        try:
            user_statistics = await get_db_collection("user_statistics")

            inc_fields = {}

            if transaction_type == "deposit":
                inc_fields["wallet_total_deposited_usd"] = amount_usd
            elif transaction_type == "withdrawal":
                inc_fields["wallet_total_withdrawn_usd"] = amount_usd

            await user_statistics.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$inc": inc_fields,
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            # NO REPUTATION FOR WALLET TRANSACTIONS
            logger.info(f"Tracked wallet transaction: user={user_id}, type={transaction_type}, amount=${amount_usd}")

        except Exception as e:
            logger.error(f"Failed to track wallet transaction: {e}", exc_info=True)

    @staticmethod
    async def track_ticket_completion(user_id: str, ticket_type: str):
        """
        Track ticket completion.

        Args:
            user_id: User who created the ticket
            ticket_type: Type of ticket (exchange, support, etc.)
        """
        try:
            user_statistics = await get_db_collection("user_statistics")

            await user_statistics.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "total_tickets": 1,
                        "completed_tickets": 1
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            logger.info(f"Tracked ticket completion: user={user_id}, type={ticket_type}")

        except Exception as e:
            logger.error(f"Failed to track ticket completion: {e}", exc_info=True)

    @staticmethod
    async def track_exchanger_ticket_completion(exchanger_id: str, ticket_id: str, ticket_type: str):
        """
        Track exchanger completing tickets - reputation already awarded in exchange completion.
        ONLY FOR EXCHANGERS - tracks their ticket fulfillment stats.

        Args:
            exchanger_id: Exchanger user ID
            ticket_id: Ticket ID
            ticket_type: Type of ticket
        """
        try:
            user_statistics = await get_db_collection("user_statistics")

            # Update exchanger-specific ticket stats (reputation already given in track_exchange_completion)
            await user_statistics.update_one(
                {"user_id": ObjectId(exchanger_id)},
                {
                    "$inc": {
                        "exchanger_tickets_completed": 1
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            logger.info(f"Tracked exchanger ticket completion: exchanger={exchanger_id}, ticket={ticket_id}")

        except Exception as e:
            logger.error(f"Failed to track exchanger ticket completion: {e}", exc_info=True)

    @staticmethod
    async def track_exchanger_ticket_claim(exchanger_id: str, ticket_id: str):
        """
        Track when exchanger claims a ticket.

        Args:
            exchanger_id: Exchanger user ID
            ticket_id: Ticket ID being claimed
        """
        try:
            user_statistics = await get_db_collection("user_statistics")

            await user_statistics.update_one(
                {"user_id": ObjectId(exchanger_id)},
                {
                    "$inc": {
                        "exchanger_tickets_claimed": 1
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            logger.info(f"Tracked exchanger ticket claim: exchanger={exchanger_id}, ticket={ticket_id}")

        except Exception as e:
            logger.error(f"Failed to track exchanger ticket claim: {e}", exc_info=True)

    @staticmethod
    async def track_exchange_cancel(user_id: str, amount_usd: float):
        """
        Track cancelled exchange - NO REPUTATION.

        Args:
            user_id: User who cancelled
            amount_usd: Exchange value
        """
        try:
            user_statistics = await get_db_collection("user_statistics")

            await user_statistics.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "client_total_exchanges": 1,
                        "client_cancelled_exchanges": 1
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            logger.info(f"Tracked exchange cancellation: user={user_id}, amount=${amount_usd}")

        except Exception as e:
            logger.error(f"Failed to track exchange cancellation: {e}", exc_info=True)

    @staticmethod
    async def track_swap_failure(user_id: str):
        """
        Track failed swap - NO REPUTATION.

        Args:
            user_id: User whose swap failed
        """
        try:
            user_statistics = await get_db_collection("user_statistics")

            await user_statistics.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "swap_total_made": 1,
                        "swap_total_failed": 1
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )

            logger.info(f"Tracked swap failure: user={user_id}")

        except Exception as e:
            logger.error(f"Failed to track swap failure: {e}", exc_info=True)

    @staticmethod
    async def check_exchange_volume_milestones(user_id: str):
        """
        Check and award volume milestone roles to user based on total exchange volume.

        Milestones: $500, $2,500, $5,000, $10,000, $25,000, $50,000

        Args:
            user_id: User ID to check milestones for
        """
        try:
            user_statistics = await get_db_collection("user_statistics")
            users = get_users_collection()

            stats = await user_statistics.find_one({"user_id": ObjectId(user_id)})
            if not stats:
                return

            total_volume = stats.get("client_exchange_volume_usd", 0)

            # Define milestone roles
            milestones = [
                (500, "ExchangeTrader-500"),
                (2500, "ExchangeTrader-2.5K"),
                (5000, "ExchangeTrader-5K"),
                (10000, "ExchangeTrader-10K"),
                (25000, "ExchangeTrader-25K"),
                (50000, "ExchangeTrader-50K")
            ]

            # Get user's current roles
            user = await users.find_one({"_id": ObjectId(user_id)})
            if not user:
                return

            current_roles = user.get("roles", [])

            # Check which milestone roles they should have
            roles_to_add = []
            for threshold, role_name in milestones:
                if total_volume >= threshold and role_name not in current_roles:
                    roles_to_add.append(role_name)

            # Add new roles if any
            if roles_to_add:
                await users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$addToSet": {"roles": {"$each": roles_to_add}}}
                )
                logger.info(f"Awarded milestone roles to user {user_id}: {roles_to_add}")

        except Exception as e:
            logger.error(f"Failed to check exchange volume milestones: {e}", exc_info=True)

    @staticmethod
    async def get_user_stats(user_id: str) -> dict:
        """
        Get comprehensive user statistics.

        Args:
            user_id: User ID

        Returns:
            Dict with all user stats
        """
        try:
            user_statistics = await get_db_collection("user_statistics")
            stats = await user_statistics.find_one({"user_id": ObjectId(user_id)})

            if not stats:
                # Compute stats on-the-fly from tickets collection
                logger.info(f"No user_statistics found for user {user_id}, computing from tickets")
                tickets = await get_db_collection("tickets")

                # Get user's Discord ID for lookups
                users = get_users_collection()
                user = await users.find_one({"_id": ObjectId(user_id)})
                if not user:
                    logger.warning(f"User {user_id} not found")
                    return {}

                discord_id = user.get("discord_id")

                # Aggregate client exchange stats
                client_pipeline = [
                    {"$match": {"customer_id": discord_id}},
                    {"$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "volume": {"$sum": "$amount_usd"}
                    }}
                ]
                client_results = await tickets.aggregate(client_pipeline).to_list(None)

                client_total = 0
                client_completed = 0
                client_cancelled = 0
                client_volume = 0.0

                for result in client_results:
                    count = result.get("count", 0)
                    volume = result.get("volume", 0.0)
                    status = result.get("_id")

                    client_total += count
                    if status == "completed":
                        client_completed += count
                        client_volume += volume
                    elif status in ["cancelled", "failed"]:
                        client_cancelled += count

                # Aggregate exchanger stats
                exchanger_pipeline = [
                    {"$match": {"exchanger_id": discord_id, "status": "completed"}},
                    {"$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "volume": {"$sum": "$amount_usd"}
                    }}
                ]
                exchanger_results = await tickets.aggregate(exchanger_pipeline).to_list(None)

                exchanger_completed = 0
                exchanger_volume = 0.0

                if exchanger_results:
                    exchanger_completed = exchanger_results[0].get("count", 0)
                    exchanger_volume = exchanger_results[0].get("volume", 0.0)

                logger.info(f"Computed stats for user {discord_id}: {client_total} client exchanges, {exchanger_completed} exchanger exchanges")

                return {
                    # Client Exchange Stats
                    "client_total_exchanges": client_total,
                    "client_completed_exchanges": client_completed,
                    "client_cancelled_exchanges": client_cancelled,
                    "client_exchange_volume_usd": client_volume,

                    # Exchanger Stats
                    "exchanger_total_completed": exchanger_completed,
                    "exchanger_total_claimed": exchanger_completed,  # Same as completed for now
                    "exchanger_total_fees_paid_usd": 0.0,  # Not tracking fees in tickets
                    "exchanger_total_profit_usd": 0.0,  # Not tracking profit in tickets
                    "exchanger_exchange_volume_usd": exchanger_volume,
                    "exchanger_tickets_completed": exchanger_completed,

                    # Swap Stats (not implemented yet)
                    "swap_total_made": 0,
                    "swap_total_completed": 0,
                    "swap_total_failed": 0,
                    "swap_total_volume_usd": 0.0,

                    # AutoMM Stats (not implemented yet)
                    "automm_total_created": 0,
                    "automm_total_completed": 0,
                    "automm_total_volume_usd": 0.0,

                    # Wallet Stats (not implemented yet)
                    "wallet_total_deposited_usd": 0.0,
                    "wallet_total_withdrawn_usd": 0.0
                }

            # Serialize ObjectId fields to strings
            if "_id" in stats:
                stats["_id"] = str(stats["_id"])
            if "user_id" in stats:
                stats["user_id"] = str(stats["user_id"])

            return stats

        except Exception as e:
            logger.error(f"Failed to get user stats: {e}", exc_info=True)
            return {}
