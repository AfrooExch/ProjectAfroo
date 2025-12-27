"""
Reputation Service - User ratings, reviews, and leaderboards
Tracks exchanger and client performance, ratings, and statistics
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
from decimal import Decimal
import logging

from app.core.database import get_db_collection

logger = logging.getLogger(__name__)


class ReputationService:
    """Service for reputation and leaderboard management"""

    # Rating scale (1-5 stars)
    MIN_RATING = 1
    MAX_RATING = 5

    # Leaderboard categories
    LEADERBOARD_TYPES = [
        "top_exchangers",
        "top_clients",
        "most_active",
        "highest_volume"
    ]

    @staticmethod
    async def submit_rating(
        ticket_id: str,
        rater_id: str,
        rated_id: str,
        rating: int,
        review: Optional[str] = None,
        rater_role: str = "client"  # "client" or "exchanger"
    ) -> Tuple[bool, str]:
        """
        Submit rating for completed ticket.

        Args:
            ticket_id: Ticket ID
            rater_id: User submitting rating
            rated_id: User being rated
            rating: Rating value (1-5)
            review: Optional review text
            rater_role: Role of rater (client or exchanger)

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate rating
            if not (ReputationService.MIN_RATING <= rating <= ReputationService.MAX_RATING):
                return False, f"Rating must be between {ReputationService.MIN_RATING} and {ReputationService.MAX_RATING}"

            # Check if ticket exists and is completed
            tickets_db = await get_db_collection("tickets")
            ticket = await tickets_db.find_one({"_id": ObjectId(ticket_id)})

            if not ticket:
                return False, "Ticket not found"

            if ticket["status"] != "completed":
                return False, "Can only rate completed tickets"

            # Verify rater is part of the ticket
            if rater_role == "client":
                if str(ticket["client_id"]) != rater_id:
                    return False, "Not authorized to rate this ticket"
                if str(ticket["exchanger_id"]) != rated_id:
                    return False, "Invalid rated user"
            else:  # exchanger
                if str(ticket["exchanger_id"]) != rater_id:
                    return False, "Not authorized to rate this ticket"
                if str(ticket["client_id"]) != rated_id:
                    return False, "Invalid rated user"

            # Check if rating already submitted
            ratings_db = await get_db_collection("reputation_ratings")
            existing = await ratings_db.find_one({
                "ticket_id": ObjectId(ticket_id),
                "rater_id": ObjectId(rater_id),
                "rated_id": ObjectId(rated_id)
            })

            if existing:
                return False, "Rating already submitted for this ticket"

            # Create rating record
            rating_dict = {
                "ticket_id": ObjectId(ticket_id),
                "rater_id": ObjectId(rater_id),
                "rated_id": ObjectId(rated_id),
                "rater_role": rater_role,
                "rated_role": "exchanger" if rater_role == "client" else "client",
                "rating": rating,
                "review": review,
                "created_at": datetime.utcnow()
            }

            await ratings_db.insert_one(rating_dict)

            # Update user statistics
            await ReputationService._update_user_stats(rated_id)

            logger.info(
                f"Rating submitted: {rater_role} {rater_id} rated "
                f"user {rated_id} {rating}/5 on ticket {ticket_id}"
            )

            return True, "Rating submitted successfully"

        except Exception as e:
            logger.error(f"Failed to submit rating: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def get_user_reputation(user_id: str) -> Dict:
        """
        Get user reputation summary.

        Args:
            user_id: User ID

        Returns:
            Dict with reputation data
        """
        try:
            ratings_db = await get_db_collection("reputation_ratings")

            # Get all ratings received by user
            cursor = ratings_db.find({"rated_id": ObjectId(user_id)})
            ratings = await cursor.to_list(length=10000)

            if not ratings:
                return {
                    "user_id": user_id,
                    "average_rating": 0.0,
                    "total_ratings": 0,
                    "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                    "recent_reviews": []
                }

            # Calculate statistics
            total_ratings = len(ratings)
            total_score = sum(r["rating"] for r in ratings)
            average_rating = total_score / total_ratings

            # Rating distribution
            distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for rating in ratings:
                distribution[rating["rating"]] += 1

            # Get recent reviews (with text)
            recent_reviews = [
                {
                    "rating": r["rating"],
                    "review": r.get("review"),
                    "rater_role": r["rater_role"],
                    "created_at": r["created_at"]
                }
                for r in sorted(ratings, key=lambda x: x["created_at"], reverse=True)[:10]
                if r.get("review")
            ]

            return {
                "user_id": user_id,
                "average_rating": round(average_rating, 2),
                "total_ratings": total_ratings,
                "rating_distribution": distribution,
                "recent_reviews": recent_reviews
            }

        except Exception as e:
            logger.error(f"Failed to get user reputation: {e}", exc_info=True)
            return {
                "user_id": user_id,
                "average_rating": 0.0,
                "total_ratings": 0,
                "error": str(e)
            }

    @staticmethod
    async def get_user_statistics(user_id: str) -> Dict:
        """
        Get user activity statistics.

        Args:
            user_id: User ID

        Returns:
            Dict with user stats
        """
        try:
            stats_db = await get_db_collection("user_statistics")

            stats = await stats_db.find_one({"user_id": ObjectId(user_id)})

            if not stats:
                # Calculate stats if not cached
                stats = await ReputationService._calculate_user_stats(user_id)

            # Serialize ObjectId
            if stats:
                stats["_id"] = str(stats.get("_id", ""))
                stats["user_id"] = str(stats["user_id"])

            return stats or {
                "user_id": user_id,
                "total_exchanges": 0,
                "completed_exchanges": 0,
                "total_volume_usd": 0.0,
                "average_completion_time_hours": 0.0,
                "success_rate": 0.0
            }

        except Exception as e:
            logger.error(f"Failed to get user statistics: {e}", exc_info=True)
            return {"user_id": user_id, "error": str(e)}

    @staticmethod
    async def get_leaderboard(
        category: str = "top_exchangers",
        time_period: str = "all_time",  # all_time, monthly, weekly
        limit: int = 50
    ) -> List[Dict]:
        """
        Get leaderboard for specified category.

        Args:
            category: Leaderboard type (top_exchangers, top_clients, etc.)
            time_period: Time period filter
            limit: Maximum entries

        Returns:
            List of leaderboard entries
        """
        try:
            if category not in ReputationService.LEADERBOARD_TYPES:
                raise ValueError(f"Invalid category: {category}")

            stats_db = await get_db_collection("user_statistics")
            users_db = await get_db_collection("users")

            # Build query based on time period
            query = {}
            if time_period == "monthly":
                cutoff = datetime.utcnow() - timedelta(days=30)
                query["last_active"] = {"$gte": cutoff}
            elif time_period == "weekly":
                cutoff = datetime.utcnow() - timedelta(days=7)
                query["last_active"] = {"$gte": cutoff}

            # Sort based on category
            sort_field = {
                "top_exchangers": "exchanger_rating",
                "top_clients": "client_rating",
                "most_active": "completed_exchanges",
                "highest_volume": "total_volume_usd"
            }.get(category, "exchanger_rating")

            # Get top users
            cursor = stats_db.find(query).sort(sort_field, -1).limit(limit)
            stats_list = await cursor.to_list(length=limit)

            # Enrich with user data
            leaderboard = []
            for idx, stats in enumerate(stats_list, 1):
                user = await users_db.find_one({"_id": stats["user_id"]})
                if user:
                    leaderboard.append({
                        "rank": idx,
                        "user_id": str(stats["user_id"]),
                        "username": user.get("username", "Unknown"),
                        "discord_username": user.get("discord_username"),
                        "average_rating": stats.get("exchanger_rating" if "exchanger" in category else "client_rating", 0.0),
                        "total_exchanges": stats.get("completed_exchanges", 0),
                        "total_volume_usd": stats.get("total_volume_usd", 0.0),
                        "success_rate": stats.get("success_rate", 0.0),
                        "join_date": user.get("created_at")
                    })

            return leaderboard

        except Exception as e:
            logger.error(f"Failed to get leaderboard: {e}", exc_info=True)
            return []

    @staticmethod
    async def _update_user_stats(user_id: str):
        """
        Update cached user statistics.
        Called after rating submission or ticket completion.

        Args:
            user_id: User ID
        """
        try:
            stats = await ReputationService._calculate_user_stats(user_id)

            stats_db = await get_db_collection("user_statistics")

            await stats_db.update_one(
                {"user_id": ObjectId(user_id)},
                {"$set": stats},
                upsert=True
            )

        except Exception as e:
            logger.error(f"Failed to update user stats: {e}", exc_info=True)

    @staticmethod
    async def _calculate_user_stats(user_id: str) -> Dict:
        """
        Calculate comprehensive user statistics from tickets, swaps, wallets, and ratings.

        Args:
            user_id: User ID

        Returns:
            Dict with calculated stats
        """
        try:
            tickets_db = await get_db_collection("tickets")
            ratings_db = await get_db_collection("reputation_ratings")
            swaps_db = await get_db_collection("afroo_swaps")
            wallets_db = await get_db_collection("wallets")
            vouches_db = await get_db_collection("vouches")

            user_oid = ObjectId(user_id)

            # ===== EXCHANGE STATISTICS =====
            # Get tickets where user was exchanger
            exchanger_tickets = await tickets_db.find({
                "exchanger_id": user_oid
            }).to_list(length=10000)

            # Get tickets where user was client
            client_tickets = await tickets_db.find({
                "client_id": user_oid
            }).to_list(length=10000)

            # Get ratings as exchanger
            exchanger_ratings = await ratings_db.find({
                "rated_id": user_oid,
                "rated_role": "exchanger"
            }).to_list(length=10000)

            # Get ratings as client
            client_ratings = await ratings_db.find({
                "rated_id": user_oid,
                "rated_role": "client"
            }).to_list(length=10000)

            # Calculate exchanger stats
            exchanger_completed = [t for t in exchanger_tickets if t["status"] == "completed"]
            exchanger_rating = (
                sum(r["rating"] for r in exchanger_ratings) / len(exchanger_ratings)
                if exchanger_ratings else 0.0
            )

            # Calculate client stats
            client_completed = [t for t in client_tickets if t["status"] == "completed"]
            client_rating = (
                sum(r["rating"] for r in client_ratings) / len(client_ratings)
                if client_ratings else 0.0
            )

            # Calculate total volume (from completed tickets)
            total_volume_usd = sum(
                t.get("amount_usd", 0.0)
                for t in exchanger_completed + client_completed
            )

            # Calculate completion times for exchange tickets
            completion_times = []
            for ticket in exchanger_completed + client_completed:
                if ticket.get("completed_at") and ticket.get("created_at"):
                    delta = ticket["completed_at"] - ticket["created_at"]
                    completion_times.append(delta.total_seconds() / 3600)  # hours

            avg_completion_time = (
                sum(completion_times) / len(completion_times)
                if completion_times else 0.0
            )

            # Calculate success rate for exchanges
            total_tickets = len(exchanger_tickets) + len(client_tickets)
            completed_tickets = len(exchanger_completed) + len(client_completed)
            failed_tickets = total_tickets - completed_tickets
            success_rate = (completed_tickets / total_tickets * 100) if total_tickets > 0 else 0.0

            # ===== SWAP STATISTICS =====
            # Get all swaps for user
            all_swaps = await swaps_db.find({"user_id": user_oid}).to_list(length=10000)
            completed_swaps = [s for s in all_swaps if s.get("status") == "completed"]

            total_swaps = len(all_swaps)

            # Calculate swap completion times
            swap_completion_times = []
            for swap in completed_swaps:
                if swap.get("completed_at") and swap.get("created_at"):
                    delta = swap["completed_at"] - swap["created_at"]
                    swap_completion_times.append(delta.total_seconds() / 60)  # minutes

            avg_swap_time = (
                sum(swap_completion_times) / len(swap_completion_times)
                if swap_completion_times else 0.0
            )

            fastest_swap = min(swap_completion_times) if swap_completion_times else 0.0

            # ===== WALLET STATISTICS =====
            # Count user's wallets
            wallet_count = await wallets_db.count_documents({"user_id": user_oid})

            # Count withdrawals (transactions with type = 'withdrawal')
            transactions_db = await get_db_collection("transactions")
            withdrawal_count = await transactions_db.count_documents({
                "user_id": user_oid,
                "transaction_type": "withdrawal",
                "status": "completed"
            })

            # ===== REPUTATION STATISTICS =====
            # Count vouches
            vouch_count = await vouches_db.count_documents({"vouched_user_id": user_oid})

            # Count warnings (assuming warnings collection exists)
            try:
                warnings_db = await get_db_collection("warnings")
                warning_count = await warnings_db.count_documents({"user_id": user_oid})
            except:
                warning_count = 0

            return {
                "user_id": user_oid,
                # Exchange statistics
                "exchanger_rating": round(exchanger_rating, 2),
                "client_rating": round(client_rating, 2),
                "exchanger_total_ratings": len(exchanger_ratings),
                "client_total_ratings": len(client_ratings),
                "total_exchanges": total_tickets,
                "completed_exchanges": completed_tickets,
                "total_completed_trades": completed_tickets,  # Alias for dashboard
                "successful_trades": completed_tickets,  # Alias for dashboard
                "failed_trades": failed_tickets,
                "total_volume_usd": round(total_volume_usd, 2),
                "average_completion_time_hours": round(avg_completion_time, 2),
                "success_rate": round(success_rate, 2),
                # Swap statistics
                "total_swaps": total_swaps,
                "completed_swaps": len(completed_swaps),
                "avg_completion_time_minutes": round(avg_swap_time, 2),
                "fastest_completion_minutes": round(fastest_swap, 2),
                # Wallet statistics
                "total_wallets": wallet_count,
                "total_withdrawals": withdrawal_count,
                # Reputation statistics
                "total_vouches": vouch_count,
                "warnings": warning_count,
                # Metadata
                "last_active": datetime.utcnow(),
                "last_calculated": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"Failed to calculate user stats: {e}", exc_info=True)
            return {
                "user_id": ObjectId(user_id),
                "error": str(e)
            }

    @staticmethod
    async def get_trust_score(user_id: str) -> Dict:
        """
        Calculate trust score based on multiple factors.

        Trust score considers:
        - Average rating
        - Number of completed exchanges
        - Success rate
        - Account age
        - Total volume

        Args:
            user_id: User ID

        Returns:
            Dict with trust score and breakdown
        """
        try:
            # Get user stats
            stats = await ReputationService.get_user_statistics(user_id)
            reputation = await ReputationService.get_user_reputation(user_id)

            # Get user account age
            users_db = await get_db_collection("users")
            user = await users_db.find_one({"_id": ObjectId(user_id)})

            if not user:
                return {"user_id": user_id, "trust_score": 0, "error": "User not found"}

            account_age_days = (datetime.utcnow() - user["created_at"]).days

            # Calculate trust score components (0-100 scale)
            rating_score = (reputation["average_rating"] / 5.0) * 30  # Max 30 points
            experience_score = min(stats.get("completed_exchanges", 0) / 100 * 25, 25)  # Max 25 points
            success_score = (stats.get("success_rate", 0) / 100) * 20  # Max 20 points
            volume_score = min(stats.get("total_volume_usd", 0) / 100000 * 15, 15)  # Max 15 points
            age_score = min(account_age_days / 365 * 10, 10)  # Max 10 points

            total_score = rating_score + experience_score + success_score + volume_score + age_score

            return {
                "user_id": user_id,
                "trust_score": round(total_score, 1),
                "breakdown": {
                    "rating_score": round(rating_score, 1),
                    "experience_score": round(experience_score, 1),
                    "success_score": round(success_score, 1),
                    "volume_score": round(volume_score, 1),
                    "age_score": round(age_score, 1)
                },
                "level": ReputationService._get_trust_level(total_score),
                "calculated_at": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"Failed to calculate trust score: {e}", exc_info=True)
            return {"user_id": user_id, "trust_score": 0, "error": str(e)}

    @staticmethod
    def _get_trust_level(score: float) -> str:
        """Get trust level name from score"""
        if score >= 90:
            return "Elite"
        elif score >= 75:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Fair"
        elif score >= 20:
            return "New"
        else:
            return "Untrusted"


# Background task to recalculate all user stats
async def recalculate_all_stats():
    """
    Recalculate statistics for all active users.
    Should be called daily by background task scheduler.
    """
    try:
        users_db = await get_db_collection("users")

        # Get all users active in last 90 days
        cutoff = datetime.utcnow() - timedelta(days=90)
        cursor = users_db.find({"last_activity": {"$gte": cutoff}})
        users = await cursor.to_list(length=10000)

        updated_count = 0
        for user in users:
            await ReputationService._update_user_stats(str(user["_id"]))
            updated_count += 1

        logger.info(f"Recalculated stats for {updated_count} users")

        return {"updated": updated_count}

    except Exception as e:
        logger.error(f"Failed to recalculate stats: {e}", exc_info=True)
        return {"error": str(e)}
