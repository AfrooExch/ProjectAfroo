"""
Cache Service - Redis-based caching for performance optimization
Provides caching for frequently accessed data to reduce database queries
"""

from typing import Optional, Any
from datetime import timedelta
import json
import logging
import pickle

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class CacheService:
    """Service for Redis caching operations"""

    # Cache key prefixes
    PREFIX_USER = "user:"
    PREFIX_BALANCE = "balance:"
    PREFIX_EXCHANGE_RATE = "rate:"
    PREFIX_TOS = "tos:"
    PREFIX_REPUTATION = "reputation:"
    PREFIX_ANALYTICS = "analytics:"
    PREFIX_SESSION = "session:"

    # Default TTLs (in seconds)
    TTL_SHORT = 300  # 5 minutes
    TTL_MEDIUM = 1800  # 30 minutes
    TTL_LONG = 3600  # 1 hour
    TTL_DAY = 86400  # 24 hours

    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        try:
            redis = get_redis()
            if not redis:
                return None

            value = await redis.get(key)
            if value:
                try:
                    # Try JSON first
                    return json.loads(value)
                except json.JSONDecodeError:
                    # Fall back to pickle for complex objects
                    try:
                        return pickle.loads(value)
                    except:
                        return value.decode() if isinstance(value, bytes) else value

            return None

        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None

    @staticmethod
    async def set(
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            Success status
        """
        try:
            redis = get_redis()
            if not redis:
                return False

            # Serialize value
            try:
                serialized = json.dumps(value)
            except (TypeError, ValueError):
                # Use pickle for non-JSON-serializable objects
                serialized = pickle.dumps(value)

            # Set with TTL
            if ttl:
                await redis.setex(key, ttl, serialized)
            else:
                await redis.set(key, serialized)

            return True

        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            return False

    @staticmethod
    async def delete(key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            Success status
        """
        try:
            redis = get_redis()
            if not redis:
                return False

            await redis.delete(key)
            return True

        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            return False

    @staticmethod
    async def delete_pattern(pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        try:
            redis = get_redis()
            if not redis:
                return 0

            # Get all matching keys
            keys = await redis.keys(pattern)

            if not keys:
                return 0

            # Delete all keys
            await redis.delete(*keys)
            return len(keys)

        except Exception as e:
            logger.warning(f"Cache delete pattern failed for {pattern}: {e}")
            return 0

    @staticmethod
    async def exists(key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        try:
            redis = get_redis()
            if not redis:
                return False

            return await redis.exists(key) > 0

        except Exception as e:
            logger.warning(f"Cache exists check failed for {key}: {e}")
            return False

    # Convenience methods for common cache patterns

    @staticmethod
    async def cache_user_data(user_id: str, user_data: dict, ttl: int = TTL_MEDIUM):
        """Cache user data"""
        key = f"{CacheService.PREFIX_USER}{user_id}"
        return await CacheService.set(key, user_data, ttl)

    @staticmethod
    async def get_cached_user_data(user_id: str) -> Optional[dict]:
        """Get cached user data"""
        key = f"{CacheService.PREFIX_USER}{user_id}"
        return await CacheService.get(key)

    @staticmethod
    async def invalidate_user_cache(user_id: str):
        """Invalidate all user-related cache"""
        pattern = f"{CacheService.PREFIX_USER}{user_id}*"
        return await CacheService.delete_pattern(pattern)

    @staticmethod
    async def cache_balance(user_id: str, asset: str, balance_data: dict, ttl: int = TTL_SHORT):
        """Cache balance data"""
        key = f"{CacheService.PREFIX_BALANCE}{user_id}:{asset}"
        return await CacheService.set(key, balance_data, ttl)

    @staticmethod
    async def get_cached_balance(user_id: str, asset: str) -> Optional[dict]:
        """Get cached balance"""
        key = f"{CacheService.PREFIX_BALANCE}{user_id}:{asset}"
        return await CacheService.get(key)

    @staticmethod
    async def invalidate_balance_cache(user_id: str, asset: Optional[str] = None):
        """Invalidate balance cache"""
        if asset:
            key = f"{CacheService.PREFIX_BALANCE}{user_id}:{asset}"
            return await CacheService.delete(key)
        else:
            pattern = f"{CacheService.PREFIX_BALANCE}{user_id}:*"
            return await CacheService.delete_pattern(pattern)

    @staticmethod
    async def cache_exchange_rate(from_asset: str, to_asset: str, rate: float, ttl: int = TTL_SHORT):
        """Cache exchange rate"""
        key = f"{CacheService.PREFIX_EXCHANGE_RATE}{from_asset}:{to_asset}"
        return await CacheService.set(key, rate, ttl)

    @staticmethod
    async def get_cached_exchange_rate(from_asset: str, to_asset: str) -> Optional[float]:
        """Get cached exchange rate"""
        key = f"{CacheService.PREFIX_EXCHANGE_RATE}{from_asset}:{to_asset}"
        return await CacheService.get(key)

    @staticmethod
    async def cache_reputation(user_id: str, reputation_data: dict, ttl: int = TTL_LONG):
        """Cache reputation data"""
        key = f"{CacheService.PREFIX_REPUTATION}{user_id}"
        return await CacheService.set(key, reputation_data, ttl)

    @staticmethod
    async def get_cached_reputation(user_id: str) -> Optional[dict]:
        """Get cached reputation"""
        key = f"{CacheService.PREFIX_REPUTATION}{user_id}"
        return await CacheService.get(key)

    @staticmethod
    async def invalidate_reputation_cache(user_id: str):
        """Invalidate reputation cache"""
        key = f"{CacheService.PREFIX_REPUTATION}{user_id}"
        return await CacheService.delete(key)

    @staticmethod
    async def cache_analytics(metric: str, data: Any, ttl: int = TTL_MEDIUM):
        """Cache analytics data"""
        key = f"{CacheService.PREFIX_ANALYTICS}{metric}"
        return await CacheService.set(key, data, ttl)

    @staticmethod
    async def get_cached_analytics(metric: str) -> Optional[Any]:
        """Get cached analytics"""
        key = f"{CacheService.PREFIX_ANALYTICS}{metric}"
        return await CacheService.get(key)

    @staticmethod
    async def cache_tos(category: str, tos_data: dict, ttl: int = TTL_DAY):
        """Cache TOS data"""
        key = f"{CacheService.PREFIX_TOS}{category}"
        return await CacheService.set(key, tos_data, ttl)

    @staticmethod
    async def get_cached_tos(category: str) -> Optional[dict]:
        """Get cached TOS"""
        key = f"{CacheService.PREFIX_TOS}{category}"
        return await CacheService.get(key)

    @staticmethod
    async def invalidate_tos_cache():
        """Invalidate all TOS cache"""
        pattern = f"{CacheService.PREFIX_TOS}*"
        return await CacheService.delete_pattern(pattern)

    @staticmethod
    async def get_cache_stats() -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        try:
            redis = get_redis()
            if not redis:
                return {"error": "Redis not available"}

            info = await redis.info()

            return {
                "connected": True,
                "used_memory": info.get("used_memory_human"),
                "total_keys": await redis.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) /
                    (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
                    * 100
                )
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}


# Decorator for caching function results
def cached(
    key_prefix: str,
    ttl: int = CacheService.TTL_MEDIUM,
    key_func=None
):
    """
    Decorator for caching function results.

    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds
        key_func: Optional function to generate cache key from args

    Example:
        @cached("user_profile", ttl=3600)
        async def get_user_profile(user_id: str):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = f"{key_prefix}:{key_func(*args, **kwargs)}"
            else:
                # Use first arg as key
                cache_key = f"{key_prefix}:{args[0] if args else ''}"

            # Try cache first
            cached_value = await CacheService.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await CacheService.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


# Cache warming - preload frequently accessed data
async def warm_cache():
    """
    Warm cache with frequently accessed data.
    Called on application startup.
    """
    try:
        logger.info("Warming cache...")

        # Preload active TOS
        from app.services.tos_service import TOSService
        all_tos = await TOSService.get_all_active_tos()
        for category, tos_data in all_tos.items():
            await CacheService.cache_tos(category, tos_data)

        # Preload platform analytics
        from app.services.analytics_service import AnalyticsService
        overview = await AnalyticsService.get_platform_overview()
        await CacheService.cache_analytics("platform_overview", overview)

        logger.info("Cache warmed successfully")

    except Exception as e:
        logger.error(f"Failed to warm cache: {e}", exc_info=True)


# Cache invalidation helpers
async def invalidate_user_related_cache(user_id: str):
    """Invalidate all cache related to a user"""
    await CacheService.invalidate_user_cache(user_id)
    await CacheService.invalidate_balance_cache(user_id)
    await CacheService.invalidate_reputation_cache(user_id)


async def clear_all_cache():
    """Clear all application cache"""
    try:
        redis = get_redis()
        if redis:
            await redis.flushdb()
            logger.info("All cache cleared")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return False
