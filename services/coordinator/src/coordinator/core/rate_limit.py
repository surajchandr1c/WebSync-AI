"""In-memory sliding-window rate limiter for sensitive authentication endpoints."""

import time
from collections import defaultdict, deque
from typing import Dict
from fastapi import Request, HTTPException, status
from coordinator.config import settings


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter."""

    def __init__(self):
        self._records: Dict[str, deque] = defaultdict(deque)

    def check(self, key: str, max_requests: int, window_seconds: int = 60) -> None:
        """Evaluate rate limit for a given identifier key. Raises HTTP 429 if exceeded."""
        if not settings.RATE_LIMIT_ENABLED:
            return

        now = time.time()
        window_start = now - window_seconds
        queue = self._records[key]

        # Purge timestamps outside the sliding window
        while queue and queue[0] < window_start:
            queue.popleft()

        if len(queue) >= max_requests:
            retry_after = int(window_seconds - (now - queue[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        queue.append(now)

    def clear(self) -> None:
        """Clear all stored rate limit history (useful for test resets)."""
        self._records.clear()


rate_limiter = SlidingWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    """Resolve client IP safely respecting forward headers if present."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


async def check_login_rate_limit(request: Request) -> None:
    """Dependency enforcing rate limits on user login."""
    client_ip = get_client_ip(request)
    rate_limiter.check(
        key=f"login:{client_ip}",
        max_requests=settings.RATE_LIMIT_LOGIN_PER_MINUTE,
        window_seconds=60,
    )


async def check_registration_rate_limit(request: Request) -> None:
    """Dependency enforcing rate limits on user and worker registration."""
    client_ip = get_client_ip(request)
    rate_limiter.check(
        key=f"register:{client_ip}",
        max_requests=settings.RATE_LIMIT_REGISTER_PER_MINUTE,
        window_seconds=60,
    )
