"""
MongoDB database connection and configuration
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# MongoDB client
client: AsyncIOMotorClient = None
db = None


async def connect_to_mongo():
    """Connect to MongoDB with optimized connection pooling"""
    global client, db
    try:
        # Connect using MONGODB_URL from environment
        client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=30000,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            retryWrites=True,
            retryReads=True
        )
        db = client[settings.DATABASE_NAME]
        # Test connection
        await client.admin.command('ping')
        logger.info("✅ Connected to MongoDB with connection pool (maxPoolSize=50, minPoolSize=10)")
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        logger.info("✅ Closed MongoDB connection")


def get_database():
    """Get database instance"""
    return db


# Collection references
def get_users_collection():
    return db.users


def get_wallets_collection():
    return db.wallets


def get_exchanges_collection():
    return db.exchanges


def get_tickets_collection():
    return db.tickets


def get_partners_collection():
    return db.partners


def get_exchangers_collection():
    return db.exchangers


def get_blockchain_transactions_collection():
    return db.blockchain_transactions


def get_audit_logs_collection():
    return db.audit_logs


def get_counters_collection():
    return db.counters


def get_swaps_collection():
    return db.afroo_swaps


def get_transactions_collection():
    return db.transactions


# V3 Core System Collections
async def get_db_collection(collection_name: str):
    """Get collection by name"""
    return db[collection_name]


async def create_indexes():
    """Create all necessary database indexes"""
    logger.info("Creating database indexes...")

    # Users indexes
    await db.users.create_index([("discord_id", ASCENDING)], unique=True)
    # Note: Email is stored from Discord OAuth but NOT used for email notifications
    # Email index removed since we don't send emails or query by email
    await db.users.create_index([("partner_id", ASCENDING)])
    await db.users.create_index([("status", ASCENDING)])
    await db.users.create_index([("created_at", DESCENDING)])

    # Wallets indexes (V4 system - NEW)
    await db.wallets.create_index([("user_id", ASCENDING), ("currency", ASCENDING)], unique=True)
    # Address index is NOT unique - multiple currencies can share same address (e.g., ETH tokens, SOL tokens)
    await db.wallets.create_index([("address", ASCENDING)])
    await db.wallets.create_index([("currency", ASCENDING)])
    await db.wallets.create_index([("created_at", DESCENDING)])

    # Balances indexes (V4 system - NEW)
    await db.balances.create_index([("user_id", ASCENDING), ("currency", ASCENDING)], unique=True)
    await db.balances.create_index([("currency", ASCENDING)])
    await db.balances.create_index([("last_synced", DESCENDING)])
    await db.balances.create_index([("sync_status", ASCENDING)])

    # Transactions indexes (V4 system - NEW)
    await db.transactions.create_index([("tx_id", ASCENDING)], unique=True)
    await db.transactions.create_index([("user_id", ASCENDING)])
    await db.transactions.create_index([("currency", ASCENDING)])
    await db.transactions.create_index([("type", ASCENDING)])
    await db.transactions.create_index([("status", ASCENDING)])
    await db.transactions.create_index([("blockchain_tx_hash", ASCENDING)])
    await db.transactions.create_index([("user_id", ASCENDING), ("currency", ASCENDING)])
    await db.transactions.create_index([("created_at", DESCENDING)])

    # Profit Holds indexes (V4 system - NEW)
    await db.profit_holds.create_index([("transaction_id", ASCENDING)])
    await db.profit_holds.create_index([("currency", ASCENDING)])
    await db.profit_holds.create_index([("status", ASCENDING)])
    await db.profit_holds.create_index([("batch_id", ASCENDING)])
    await db.profit_holds.create_index([("created_at", DESCENDING)])

    # Profit Batches indexes (V4 system - NEW)
    await db.profit_batches.create_index([("batch_id", ASCENDING)], unique=True)
    await db.profit_batches.create_index([("currency", ASCENDING)])
    await db.profit_batches.create_index([("status", ASCENDING)])
    await db.profit_batches.create_index([("created_at", DESCENDING)])

    # Webhook Logs indexes (V4 system - NEW)
    await db.webhook_logs.create_index([("webhook_id", ASCENDING)])
    await db.webhook_logs.create_index([("currency", ASCENDING)])
    await db.webhook_logs.create_index([("address", ASCENDING)])
    await db.webhook_logs.create_index([("tx_hash", ASCENDING)])
    await db.webhook_logs.create_index([("processed", ASCENDING)])
    await db.webhook_logs.create_index([("created_at", DESCENDING)])
    # TTL index to auto-delete old webhook logs after 30 days
    await db.webhook_logs.create_index(
        [("created_at", ASCENDING)],
        expireAfterSeconds=2592000  # 30 days
    )

    # Exchanges indexes
    await db.exchanges.create_index([("creator_id", ASCENDING)])
    await db.exchanges.create_index([("exchanger_id", ASCENDING)])
    await db.exchanges.create_index([("status", ASCENDING)])
    await db.exchanges.create_index([("partner_id", ASCENDING)])
    await db.exchanges.create_index([("created_at", DESCENDING)])
    await db.exchanges.create_index([("status", ASCENDING), ("created_at", DESCENDING)])

    # Tickets indexes
    await db.tickets.create_index([("ticket_number", ASCENDING)], unique=True)
    await db.tickets.create_index([("user_id", ASCENDING)])
    await db.tickets.create_index([("status", ASCENDING)])
    await db.tickets.create_index([("assigned_to", ASCENDING)])
    await db.tickets.create_index([("type", ASCENDING)])
    await db.tickets.create_index([("created_at", DESCENDING)])

    # Partners indexes
    await db.partners.create_index([("discord_guild_id", ASCENDING)], unique=True)
    await db.partners.create_index([("slug", ASCENDING)], unique=True)
    await db.partners.create_index([("status", ASCENDING)])

    # Exchangers indexes
    await db.exchangers.create_index(
        [("user_id", ASCENDING), ("partner_id", ASCENDING)],
        unique=True,
        sparse=True
    )
    await db.exchangers.create_index([("status", ASCENDING)])

    # Audit logs indexes
    await db.audit_logs.create_index([("user_id", ASCENDING)])
    await db.audit_logs.create_index([("resource_type", ASCENDING), ("resource_id", ASCENDING)])
    await db.audit_logs.create_index([("created_at", DESCENDING)])
    # TTL index for auto-deletion after 7 years
    await db.audit_logs.create_index(
        [("created_at", ASCENDING)],
        expireAfterSeconds=220752000
    )

    # Exchanger deposits indexes (V4 system with holds)
    await db.exchanger_deposits.create_index([("user_id", ASCENDING), ("currency", ASCENDING)], unique=True)
    await db.exchanger_deposits.create_index([("wallet_address", ASCENDING)])
    await db.exchanger_deposits.create_index([("created_at", DESCENDING)])

    # Ticket holds indexes (V3 system)
    await db.ticket_holds.create_index([("ticket_id", ASCENDING)])
    await db.ticket_holds.create_index([("user_id", ASCENDING)])
    await db.ticket_holds.create_index([("status", ASCENDING)])
    await db.ticket_holds.create_index([("asset", ASCENDING)])
    await db.ticket_holds.create_index([("created_at", DESCENDING)])

    # Platform fees indexes (V3 system)
    await db.platform_fees.create_index([("user_id", ASCENDING)])
    await db.platform_fees.create_index([("transaction_id", ASCENDING)])
    await db.platform_fees.create_index([("asset", ASCENDING)])
    await db.platform_fees.create_index([("collected", ASCENDING)])
    await db.platform_fees.create_index([("month", ASCENDING)])
    await db.platform_fees.create_index([("year", ASCENDING)])
    await db.platform_fees.create_index([("created_at", DESCENDING)])

    # Server fees indexes (V4 system)
    await db.server_fees.create_index([("ticket_id", ASCENDING)])
    await db.server_fees.create_index([("exchanger_id", ASCENDING)])
    await db.server_fees.create_index([("status", ASCENDING)])
    await db.server_fees.create_index([("asset", ASCENDING)])
    await db.server_fees.create_index([("created_at", DESCENDING)])

    # Afroo Wallets indexes (V4 system)
    await db.afroo_wallets.create_index([("user_id", ASCENDING), ("asset", ASCENDING)], unique=True)
    await db.afroo_wallets.create_index([("status", ASCENDING)])
    await db.afroo_wallets.create_index([("created_at", DESCENDING)])

    # Afroo Wallet Transactions indexes (V4 system)
    await db.afroo_wallet_transactions.create_index([("user_id", ASCENDING)])
    await db.afroo_wallet_transactions.create_index([("asset", ASCENDING)])
    await db.afroo_wallet_transactions.create_index([("type", ASCENDING)])
    await db.afroo_wallet_transactions.create_index([("created_at", DESCENDING)])

    # Afroo Swaps indexes (V4 system)
    await db.afroo_swaps.create_index([("user_id", ASCENDING)])
    await db.afroo_swaps.create_index([("status", ASCENDING)])
    await db.afroo_swaps.create_index([("from_asset", ASCENDING)])
    await db.afroo_swaps.create_index([("to_asset", ASCENDING)])
    await db.afroo_swaps.create_index([("created_at", DESCENDING)])

    # Blockchain Transactions indexes
    await db.blockchain_transactions.create_index([("tx_hash", ASCENDING)], unique=True)
    await db.blockchain_transactions.create_index([("user_id", ASCENDING)])
    await db.blockchain_transactions.create_index([("asset", ASCENDING)])
    await db.blockchain_transactions.create_index([("status", ASCENDING)])
    await db.blockchain_transactions.create_index([("created_at", DESCENDING)])

    # Withdrawals indexes (V4 system)
    await db.withdrawals.create_index([("user_id", ASCENDING)])
    await db.withdrawals.create_index([("status", ASCENDING)])
    await db.withdrawals.create_index([("asset", ASCENDING)])
    await db.withdrawals.create_index([("tx_hash", ASCENDING)])
    await db.withdrawals.create_index([("created_at", DESCENDING)])

    # Payouts indexes (V4 system)
    await db.payouts.create_index([("ticket_id", ASCENDING)])
    await db.payouts.create_index([("exchanger_id", ASCENDING)])
    await db.payouts.create_index([("client_id", ASCENDING)])
    await db.payouts.create_index([("status", ASCENDING)])
    await db.payouts.create_index([("tx_hash", ASCENDING)])
    await db.payouts.create_index([("created_at", DESCENDING)])

    # Reputation Ratings indexes (V4 system)
    await db.reputation_ratings.create_index([("ticket_id", ASCENDING)], unique=True)
    await db.reputation_ratings.create_index([("rater_id", ASCENDING)])
    await db.reputation_ratings.create_index([("rated_id", ASCENDING)])
    await db.reputation_ratings.create_index([("rating", ASCENDING)])
    await db.reputation_ratings.create_index([("created_at", DESCENDING)])

    # User Statistics indexes (V4 system)
    await db.user_statistics.create_index([("user_id", ASCENDING)], unique=True)
    await db.user_statistics.create_index([("trust_score", DESCENDING)])
    await db.user_statistics.create_index([("total_volume_usd", DESCENDING)])
    await db.user_statistics.create_index([("updated_at", DESCENDING)])

    # TOS Versions indexes (V4 system)
    await db.tos_versions.create_index([("category", ASCENDING), ("version", ASCENDING)], unique=True)
    await db.tos_versions.create_index([("category", ASCENDING), ("active", ASCENDING)])
    await db.tos_versions.create_index([("effective_date", DESCENDING)])
    await db.tos_versions.create_index([("created_at", DESCENDING)])

    # TOS Agreements indexes (V4 system)
    await db.tos_agreements.create_index([("user_id", ASCENDING), ("tos_id", ASCENDING)])
    await db.tos_agreements.create_index([("user_id", ASCENDING)])
    await db.tos_agreements.create_index([("tos_id", ASCENDING)])
    await db.tos_agreements.create_index([("agreed_at", DESCENDING)])

    # Tatum Subscriptions indexes (V4 system)
    await db.tatum_subscriptions.create_index([("subscription_id", ASCENDING)], unique=True)
    await db.tatum_subscriptions.create_index([("address", ASCENDING)])
    await db.tatum_subscriptions.create_index([("blockchain", ASCENDING)])
    await db.tatum_subscriptions.create_index([("status", ASCENDING)])

    # Balance Sync Records indexes (V4 system)
    await db.balance_sync_records.create_index([("user_id", ASCENDING)])
    await db.balance_sync_records.create_index([("asset", ASCENDING)])
    await db.balance_sync_records.create_index([("has_drift", ASCENDING)])
    await db.balance_sync_records.create_index([("synced_at", DESCENDING)])

    # Exchanger Applications indexes (V4 system)
    await db.exchanger_applications.create_index([("user_id", ASCENDING)])
    await db.exchanger_applications.create_index([("status", ASCENDING)])
    await db.exchanger_applications.create_index([("submitted_at", DESCENDING)])
    await db.exchanger_applications.create_index([("reviewed_by", ASCENDING)])

    # Key Reveals indexes (V4 system - security)
    await db.key_reveals.create_index([("user_id", ASCENDING)])
    await db.key_reveals.create_index([("asset", ASCENDING)])
    await db.key_reveals.create_index([("revealed_at", DESCENDING)])
    # TTL index to auto-delete old reveals after 7 days
    await db.key_reveals.create_index(
        [("revealed_at", ASCENDING)],
        expireAfterSeconds=604800  # 7 days
    )

    # Security Logs indexes (V4 system - audit trail)
    await db.security_logs.create_index([("user_id", ASCENDING)])
    await db.security_logs.create_index([("event_type", ASCENDING)])
    await db.security_logs.create_index([("severity", ASCENDING)])
    await db.security_logs.create_index([("timestamp", DESCENDING)])
    # TTL index to auto-delete old logs after 90 days
    await db.security_logs.create_index(
        [("timestamp", ASCENDING)],
        expireAfterSeconds=7776000  # 90 days
    )

    # User Achievements indexes (V4 system - milestones)
    await db.user_achievements.create_index([("user_id", ASCENDING)])
    await db.user_achievements.create_index([("achievement_type", ASCENDING)])
    await db.user_achievements.create_index([("tier_id", ASCENDING)])
    await db.user_achievements.create_index([("earned_at", DESCENDING)])

    # Pending Discord Role Grants indexes (V4 system - milestone roles)
    await db.pending_discord_role_grants.create_index([("user_id", ASCENDING)])
    await db.pending_discord_role_grants.create_index([("status", ASCENDING)])
    await db.pending_discord_role_grants.create_index([("created_at", ASCENDING)])

    # User Notifications indexes (V4 system)
    await db.user_notifications.create_index([("user_id", ASCENDING)])
    await db.user_notifications.create_index([("read", ASCENDING)])
    await db.user_notifications.create_index([("created_at", DESCENDING)])

    # Admin Wallets indexes (V4 system - fee collection)
    await db.admin_wallets.create_index([("asset", ASCENDING)])
    await db.admin_wallets.create_index([("active", ASCENDING)])

    logger.info("✅ All indexes created successfully")


async def get_next_sequence(collection_name: str) -> int:
    """Get next sequence number for auto-increment fields"""
    result = await db.counters.find_one_and_update(
        {"_id": collection_name},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=True
    )
    return result["sequence_value"]
