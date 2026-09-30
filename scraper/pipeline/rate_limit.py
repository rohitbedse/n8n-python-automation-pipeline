"""
Rate Limiting Utilities
=======================
Provides rate limiting for polite scraping.
"""

import time
import threading
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 1.0
    burst_limit: int = 5
    cooldown_seconds: float = 0.0


class RateLimiter:
    """
    Token bucket rate limiter for polite scraping.
    
    Allows bursts up to burst_limit, then enforces requests_per_second rate.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = float(config.burst_limit)
        self.last_update = time.monotonic()
        self.lock = threading.Lock()
        self.total_requests = 0
        self.total_wait_time = 0.0
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(
            self.config.burst_limit,
            self.tokens + elapsed * self.config.requests_per_second
        )
        self.last_update = now
    
    def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, blocking until available.
        
        Returns:
            Time waited in seconds
        """
        waited = 0.0
        
        with self.lock:
            while True:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self.total_requests += 1
                    return waited
                
                # Calculate wait time
                needed = tokens - self.tokens
                wait_time = needed / self.config.requests_per_second
                
                # Release lock while waiting
                self.lock.release()
                time.sleep(wait_time)
                waited += wait_time
                self.total_wait_time += wait_time
                self.lock.acquire()
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without blocking.
        
        Returns:
            True if acquired, False otherwise
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                self.total_requests += 1
                return True
            
            return False
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        with self.lock:
            self._refill()
            return {
                "available_tokens": self.tokens,
                "total_requests": self.total_requests,
                "total_wait_time": self.total_wait_time,
                "config": {
                    "requests_per_second": self.config.requests_per_second,
                    "burst_limit": self.config.burst_limit,
                }
            }
    
    def reset(self) -> None:
        """Reset rate limiter state."""
        with self.lock:
            self.tokens = float(self.config.burst_limit)
            self.last_update = time.monotonic()
            self.total_requests = 0
            self.total_wait_time = 0.0


class DomainRateLimiter:
    """
    Rate limiter that tracks limits per domain.
    """
    
    def __init__(self, default_config: RateLimitConfig):
        self.default_config = default_config
        self.limiters: dict[str, RateLimiter] = {}
        self.lock = threading.Lock()
    
    def get_limiter(self, domain: str, config: Optional[RateLimitConfig] = None) -> RateLimiter:
        """Get or create a rate limiter for a domain."""
        with self.lock:
            if domain not in self.limiters:
                self.limiters[domain] = RateLimiter(config or self.default_config)
            return self.limiters[domain]
    
    def acquire(self, domain: str, tokens: int = 1, config: Optional[RateLimitConfig] = None) -> float:
        """Acquire tokens for a domain."""
        limiter = self.get_limiter(domain, config)
        return limiter.acquire(tokens)
    
    def get_all_stats(self) -> dict:
        """Get statistics for all domain limiters."""
        with self.lock:
            return {domain: limiter.get_stats() for domain, limiter in self.limiters.items()}


# Global domain rate limiter instance
_global_domain_limiter: Optional[DomainRateLimiter] = None


def get_global_domain_limiter() -> DomainRateLimiter:
    """Get or create the global domain rate limiter."""
    global _global_domain_limiter
    
    if _global_domain_limiter is None:
        from ..config.settings import PIPELINE_CONFIG
        
        default_config = RateLimitConfig(
            requests_per_second=1.0 / PIPELINE_CONFIG.get("delay_between_requests", 1.0),
            burst_limit=5,
        )
        _global_domain_limiter = DomainRateLimiter(default_config)
    
    return _global_domain_limiter


def rate_limit_request(domain: str, delay: float = 1.0) -> float:
    """
    Simple rate limiting function for a domain.
    
    Args:
        domain: Domain name
        delay: Minimum delay between requests in seconds
        
    Returns:
        Time waited in seconds
    """
    limiter = get_global_domain_limiter()
    config = RateLimitConfig(requests_per_second=1.0 / delay)
    return limiter.acquire(domain, config=config)