"""
Analytics Service - Platform statistics and insights
Provides comprehensive analytics for admins, exchangers, and clients
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.core.database import get_db_collection

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for platform analytics and statistics"""

    @staticmethod
    async def get_platform_overview(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get overall platform statistics.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dict with platform metrics
        """
        try:
            # Default to last 30 days if not specified
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            tickets_db = await get_db_collection("tickets")
            users_db = await get_db_collection("users")
            swaps_db = await get_db_collection("afroo_swaps")
            withdrawals_db = await get_db_collection("withdrawals")

            # Total users
            total_users = await users_db.count_documents({})
            new_users = await users_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            })

            # Active users (users with activity in period)
            active_user_ids = set()

            # Get active users from tickets
            active_tickets = await tickets_db.find({
                "created_at": {"$gte": start_date, "$lte": end_date}
            }).to_list(length=10000)

            for ticket in active_tickets:
                active_user_ids.add(str(ticket.get("client_id", "")))
                active_user_ids.add(str(ticket.get("exchanger_id", "")))

            active_users = len([uid for uid in active_user_ids if uid])

            # Ticket statistics
            total_tickets = await tickets_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            })

            completed_tickets = await tickets_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "completed"
            })

            cancelled_tickets = await tickets_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "cancelled"
            })

            # Calculate total volume from completed tickets
            completed_ticket_list = await tickets_db.find({
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "completed"
            }).to_list(length=10000)

            total_volume_usd = sum(
                t.get("amount_usd", 0.0) for t in completed_ticket_list
            )

            # Swap statistics
            total_swaps = await swaps_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            })

            completed_swaps = await swaps_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "completed"
            })

            # Withdrawal statistics
            total_withdrawals = await withdrawals_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            })

            completed_withdrawals = await withdrawals_db.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "completed"
            })

            # Calculate success rates
            ticket_success_rate = (
                (completed_tickets / total_tickets * 100)
                if total_tickets > 0 else 0.0
            )

            swap_success_rate = (
                (completed_swaps / total_swaps * 100)
                if total_swaps > 0 else 0.0
            )

            return {
                "period": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "days": (end_date - start_date).days
                },
                "users": {
                    "total": total_users,
                    "new": new_users,
                    "active": active_users
                },
                "tickets": {
                    "total": total_tickets,
                    "completed": completed_tickets,
                    "cancelled": cancelled_tickets,
                    "success_rate": round(ticket_success_rate, 2),
                    "total_volume_usd": round(total_volume_usd, 2)
                },
                "swaps": {
                    "total": total_swaps,
                    "completed": completed_swaps,
                    "success_rate": round(swap_success_rate, 2)
                },
                "withdrawals": {
                    "total": total_withdrawals,
                    "completed": completed_withdrawals
                }
            }

        except Exception as e:
            logger.error(f"Failed to get platform overview: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    async def get_revenue_stats(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get platform revenue statistics.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Dict with revenue metrics
        """
        try:
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            fees_db = await get_db_collection("fee_collection")

            # Get all fees in period
            cursor = fees_db.find({
                "created_at": {"$gte": start_date, "$lte": end_date}
            })

            fees = await cursor.to_list(length=100000)

            # Group by transaction type
            revenue_by_type = {}
            total_revenue_usd = 0.0

            for fee in fees:
                tx_type = fee.get("transaction_type", "unknown")
                amount_usd = fee.get("amount_usd", 0.0)

                if tx_type not in revenue_by_type:
                    revenue_by_type[tx_type] = {
                        "count": 0,
                        "total_usd": 0.0
                    }

                revenue_by_type[tx_type]["count"] += 1
                revenue_by_type[tx_type]["total_usd"] += amount_usd
                total_revenue_usd += amount_usd

            # Calculate daily average
            days = max((end_date - start_date).days, 1)
            daily_average = total_revenue_usd / days

            return {
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "total_revenue_usd": round(total_revenue_usd, 2),
                "daily_average_usd": round(daily_average, 2),
                "total_transactions": len(fees),
                "revenue_by_type": {
                    k: {
                        "count": v["count"],
                        "total_usd": round(v["total_usd"], 2)
                    }
                    for k, v in revenue_by_type.items()
                }
            }

        except Exception as e:
            logger.error(f"Failed to get revenue stats: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    async def get_asset_distribution() -> Dict:
        """
        Get distribution of assets across platform.

        Returns:
            Dict with asset distribution
        """
        try:
            deposits_db = await get_db_collection("exchanger_deposits")
            wallets_db = await get_db_collection("afroo_wallets")

            # Aggregate by asset
            asset_totals = {}

            # Exchanger deposits
            cursor = deposits_db.find({})
            deposits = await cursor.to_list(length=100000)

            for deposit in deposits:
                asset = deposit["asset"]
                balance = deposit.get("balance_units", 0.0)

                if asset not in asset_totals:
                    asset_totals[asset] = {
                        "exchanger_deposits": 0.0,
                        "afroo_wallets": 0.0,
                        "total": 0.0
                    }

                asset_totals[asset]["exchanger_deposits"] += balance

            # Afroo wallets
            cursor = wallets_db.find({})
            wallets = await cursor.to_list(length=100000)

            for wallet in wallets:
                asset = wallet["asset"]
                balance = wallet.get("balance_units", 0.0)

                if asset not in asset_totals:
                    asset_totals[asset] = {
                        "exchanger_deposits": 0.0,
                        "afroo_wallets": 0.0,
                        "total": 0.0
                    }

                asset_totals[asset]["afroo_wallets"] += balance

            # Calculate totals
            for asset in asset_totals:
                asset_totals[asset]["total"] = (
                    asset_totals[asset]["exchanger_deposits"] +
                    asset_totals[asset]["afroo_wallets"]
                )

            return {
                "asset_distribution": asset_totals,
                "total_assets": len(asset_totals)
            }

        except Exception as e:
            logger.error(f"Failed to get asset distribution: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    async def get_user_analytics(user_id: str) -> Dict:
        """
        Get detailed analytics for specific user.

        Args:
            user_id: User ID

        Returns:
            Dict with user analytics
        """
        try:
            tickets_db = await get_db_collection("tickets")
            swaps_db = await get_db_collection("afroo_swaps")
            withdrawals_db = await get_db_collection("withdrawals")

            user_oid = ObjectId(user_id)

            # Tickets as exchanger
            exchanger_tickets = await tickets_db.find({
                "exchanger_id": user_oid
            }).to_list(length=10000)

            # Tickets as client
            client_tickets = await tickets_db.find({
                "client_id": user_oid
            }).to_list(length=10000)

            # Swaps
            swaps = await swaps_db.find({
                "user_id": user_oid
            }).to_list(length=10000)

            # Withdrawals
            withdrawals = await withdrawals_db.find({
                "user_id": user_oid
            }).to_list(length=10000)

            # Calculate metrics
            return {
                "user_id": user_id,
                "exchanger_stats": {
                    "total_tickets": len(exchanger_tickets),
                    "completed": len([t for t in exchanger_tickets if t["status"] == "completed"]),
                    "total_volume_usd": sum(t.get("amount_usd", 0.0) for t in exchanger_tickets if t["status"] == "completed")
                },
                "client_stats": {
                    "total_tickets": len(client_tickets),
                    "completed": len([t for t in client_tickets if t["status"] == "completed"]),
                    "total_volume_usd": sum(t.get("amount_usd", 0.0) for t in client_tickets if t["status"] == "completed")
                },
                "swap_stats": {
                    "total_swaps": len(swaps),
                    "completed": len([s for s in swaps if s["status"] == "completed"])
                },
                "withdrawal_stats": {
                    "total_withdrawals": len(withdrawals),
                    "completed": len([w for w in withdrawals if w["status"] == "completed"])
                }
            }

        except Exception as e:
            logger.error(f"Failed to get user analytics: {e}", exc_info=True)
            return {"user_id": user_id, "error": str(e)}

    @staticmethod
    async def get_time_series_data(
        metric: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "daily"  # daily, weekly, monthly
    ) -> List[Dict]:
        """
        Get time series data for metric.

        Args:
            metric: Metric to track (tickets, swaps, revenue, etc.)
            start_date: Start date
            end_date: End date
            interval: Time interval

        Returns:
            List of time series data points
        """
        try:
            if interval == "daily":
                delta = timedelta(days=1)
            elif interval == "weekly":
                delta = timedelta(weeks=1)
            elif interval == "monthly":
                delta = timedelta(days=30)
            else:
                delta = timedelta(days=1)

            tickets_db = await get_db_collection("tickets")
            fees_db = await get_db_collection("fee_collection")

            time_series = []
            current_date = start_date

            while current_date <= end_date:
                next_date = current_date + delta

                if metric == "tickets":
                    count = await tickets_db.count_documents({
                        "created_at": {"$gte": current_date, "$lt": next_date}
                    })
                    value = count

                elif metric == "revenue":
                    cursor = fees_db.find({
                        "created_at": {"$gte": current_date, "$lt": next_date}
                    })
                    fees = await cursor.to_list(length=100000)
                    value = sum(f.get("amount_usd", 0.0) for f in fees)

                else:
                    value = 0

                time_series.append({
                    "date": current_date,
                    "value": value
                })

                current_date = next_date

            return time_series

        except Exception as e:
            logger.error(f"Failed to get time series data: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_exchanger_rankings(limit: int = 50) -> List[Dict]:
        """
        Get top exchangers by various metrics.

        Args:
            limit: Number of results

        Returns:
            List of exchanger rankings
        """
        try:
            stats_db = await get_db_collection("user_statistics")
            users_db = await get_db_collection("users")

            # Get exchangers sorted by rating
            cursor = stats_db.find({
                "exchanger_total_ratings": {"$gt": 0}
            }).sort("exchanger_rating", -1).limit(limit)

            stats_list = await cursor.to_list(length=limit)

            rankings = []
            for idx, stats in enumerate(stats_list, 1):
                user = await users_db.find_one({"_id": stats["user_id"]})
                if user:
                    rankings.append({
                        "rank": idx,
                        "user_id": str(stats["user_id"]),
                        "username": user.get("username"),
                        "rating": stats.get("exchanger_rating", 0.0),
                        "total_exchanges": stats.get("completed_exchanges", 0),
                        "total_volume_usd": stats.get("total_volume_usd", 0.0)
                    })

            return rankings

        except Exception as e:
            logger.error(f"Failed to get exchanger rankings: {e}", exc_info=True)
            return []


# Cache analytics data
_analytics_cache = {}
_cache_ttl = {}


async def get_cached_platform_overview() -> Dict:
    """
    Get platform overview with caching (5 min TTL).
    """
    cache_key = "platform_overview"
    now = datetime.utcnow()

    # Check cache
    if cache_key in _analytics_cache:
        if cache_key in _cache_ttl and _cache_ttl[cache_key] > now:
            return _analytics_cache[cache_key]

    # Fetch fresh data
    data = await AnalyticsService.get_platform_overview()

    # Cache for 5 minutes
    _analytics_cache[cache_key] = data
    _cache_ttl[cache_key] = now + timedelta(minutes=5)

    return data
