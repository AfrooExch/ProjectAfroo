"""
Rate Limiter - Token bucket rate limiting using Redis
Prevents abuse and ensures fair API usage
"""

import time
from typing import Optional, Tuple
from functools import wraps
from fastapi import HTTPException, Request, status
import logging

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter using Redis"""

    def __init__(self):
        self.redis = None

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g., "user:123:api_general")
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        if not self.redis:
            self.redis = get_redis()

        current_time = int(time.time())
        window_start = current_time - window_seconds

        # Redis key for this rate limit
        redis_key = f"rate_limit:{key}"

        try:
            # Remove old requests outside window
            await self.redis.zremrangebyscore(redis_key, 0, window_start)

            # Count requests in current window
            request_count = await self.redis.zcard(redis_key)

            if request_count >= max_requests:
                # Get oldest request timestamp
                oldest = await self.redis.zrange(redis_key, 0, 0, withscores=True)
                if oldest:
                    retry_after = int(oldest[0][1]) + window_seconds - current_time
                    return False, max(0, retry_after)
                return False, window_seconds

            # Add current request
            await self.redis.zadd(redis_key, {str(current_time): current_time})

            # Set expiry on key
            await self.redis.expire(redis_key, window_seconds + 10)

            return True, None

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if Redis fails
            return True, None

    async def reset_rate_limit(self, key: str):
        """Reset rate limit for key"""
        if not self.redis:
            self.redis = get_redis()

        redis_key = f"rate_limit:{key}"
        await self.redis.delete(redis_key)


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(
    max_requests: int,
    window_seconds: int,
    key_func=None
):
    """
    Rate limit decorator for FastAPI routes.

    Args:
        max_requests: Maximum requests allowed
        window_seconds: Time window in seconds
        key_func: Optional function to generate custom key

    Example:
        @rate_limit(max_requests=10, window_seconds=60)
        async def my_endpoint(request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # No request object, skip rate limiting
                return await func(*args, **kwargs)

            # Generate rate limit key
            if key_func:
                key = key_func(request)
            else:
                # Default: use IP address
                client_ip = request.client.host if request.client else "unknown"
                endpoint = request.url.path
                key = f"{client_ip}:{endpoint}"

            # Check rate limit
            is_allowed, retry_after = await rate_limiter.check_rate_limit(
                key, max_requests, window_seconds
            )

            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)}
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def user_rate_limit(max_requests: int, window_seconds: int):
    """
    Rate limit decorator for authenticated routes.
    Uses user ID as key.

    Example:
        @user_rate_limit(max_requests=5, window_seconds=60)
        async def my_endpoint(request: Request, current_user: dict = Depends(...)):
            ...
    """
    def key_func(request: Request):
        # Extract user from request state (set by auth dependency)
        user = getattr(request.state, "user", None)
        if user:
            user_id = user.get("_id", "unknown")
            return f"user:{user_id}:{request.url.path}"
        # Fallback to IP
        return f"ip:{request.client.host}:{request.url.path}"

    return rate_limit(max_requests, window_seconds, key_func)
