"""
Redis connection and cache utilities
"""

import redis.asyncio as redis
import json
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis client
redis_client: redis.Redis = None


async def connect_to_redis():
    """Connect to Redis with optimized connection pooling"""
    global redis_client
    try:
        # Create connection pool with optimal settings
        pool = redis.ConnectionPool(
            host="afroo-redis-prod",
            port=6379,
            password=settings.REDIS_PASSWORD,
            db=0,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )

        # Create Redis client with connection pool
        redis_client = redis.Redis(connection_pool=pool)
        await redis_client.ping()
        logger.info("✅ Connected to Redis with connection pool (max_connections=50)")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise


async def close_redis_connection():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("✅ Closed Redis connection")


def get_redis():
    """Get Redis client instance"""
    return redis_client


# Redis key patterns
class RedisKeys:
    """Redis key naming patterns"""

    # Session management
    SESSION = "session:{token}"
    USER_SESSION = "user:{discord_id}:sessions"

    # Caching
    USER_CACHE = "cache:user:{discord_id}"
    WALLET_BALANCE = "cache:wallet:{address}:balance"
    EXCHANGE_RATE = "cache:rate:{from_currency}:{to_currency}"
    PARTNER_BRANDING = "cache:partner:{slug}:branding"

    # Rate limiting
    RATE_LIMIT = "ratelimit:{identifier}:{window}"

    # Real-time data
    ACTIVE_EXCHANGES = "realtime:exchanges:active"
    ONLINE_USERS = "realtime:users:online"

    # Queues
    NOTIFICATION_QUEUE = "queue:notifications"
    BLOCKCHAIN_MONITOR_QUEUE = "queue:blockchain:monitor"

    # Locks
    WALLET_LOCK = "lock:wallet:{wallet_id}"
    EXCHANGE_LOCK = "lock:exchange:{exchange_id}"


class CacheService:
    """Cache service utilities"""

    @staticmethod
    async def get(key: str) -> Optional[str]:
        """Get value from cache"""
        return await redis_client.get(key)

    @staticmethod
    async def set(key: str, value: str, ttl: int = 300):
        """Set value in cache with TTL"""
        await redis_client.setex(key, ttl, value)

    @staticmethod
    async def delete(key: str):
        """Delete key from cache"""
        await redis_client.delete(key)

    @staticmethod
    async def get_json(key: str) -> Optional[dict]:
        """Get JSON value from cache"""
        data = await redis_client.get(key)
        return json.loads(data) if data else None

    @staticmethod
    async def set_json(key: str, value: dict, ttl: int = 300):
        """Set JSON value in cache"""
        await redis_client.setex(key, ttl, json.dumps(value))


class SessionService:
    """Session management"""

    @staticmethod
    async def store_refresh_token(token: str, discord_id: str, ttl: int = 2592000):
        """Store refresh token (30 days)"""
        key = RedisKeys.SESSION.format(token=token)
        await redis_client.setex(key, ttl, discord_id)

        # Add to user's session set
        user_sessions_key = RedisKeys.USER_SESSION.format(discord_id=discord_id)
        await redis_client.sadd(user_sessions_key, token)

    @staticmethod
    async def get_refresh_token(token: str) -> Optional[str]:
        """Get discord_id from refresh token"""
        key = RedisKeys.SESSION.format(token=token)
        return await redis_client.get(key)

    @staticmethod
    async def verify_refresh_token(token: str, discord_id: str) -> bool:
        """Verify refresh token belongs to user"""
        key = RedisKeys.SESSION.format(token=token)
        stored_discord_id = await redis_client.get(key)
        return stored_discord_id == discord_id

    @staticmethod
    async def delete_refresh_token(token: str):
        """Delete refresh token"""
        key = RedisKeys.SESSION.format(token=token)
        discord_id = await redis_client.get(key)

        if discord_id:
            user_sessions_key = RedisKeys.USER_SESSION.format(discord_id=discord_id)
            await redis_client.srem(user_sessions_key, token)

        await redis_client.delete(key)

    @staticmethod
    async def delete_all_user_sessions(discord_id: str):
        """Delete all sessions for a user"""
        user_sessions_key = RedisKeys.USER_SESSION.format(discord_id=discord_id)
        tokens = await redis_client.smembers(user_sessions_key)

        for token in tokens:
            key = RedisKeys.SESSION.format(token=token)
            await redis_client.delete(key)

        await redis_client.delete(user_sessions_key)


class RateLimiter:
    """Rate limiting utilities"""

    @staticmethod
    async def check_rate_limit(
        identifier: str,
        max_requests: int = 100,
        window: int = 60
    ) -> bool:
        """Check if request is within rate limit"""
        key = RedisKeys.RATE_LIMIT.format(identifier=identifier, window=window)

        # Increment counter
        count = await redis_client.incr(key)

        # Set expiry on first request
        if count == 1:
            await redis_client.expire(key, window)

        return count <= max_requests

    @staticmethod
    async def get_remaining(identifier: str, max_requests: int = 100, window: int = 60) -> int:
        """Get remaining requests in current window"""
        key = RedisKeys.RATE_LIMIT.format(identifier=identifier, window=window)
        count = await redis_client.get(key)
        current = int(count) if count else 0
        return max(0, max_requests - current)
