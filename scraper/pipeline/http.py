"""
HTTP Utilities with Retry and Exponential Backoff
==================================================
Provides robust HTTP fetching with configurable retry logic,
exponential backoff, and proper error handling.
"""

import time
import random
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config.settings import (
    RETRYABLE_STATUS_CODES,
    NON_RETRYABLE_STATUS_CODES,
)

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    attempts: int = 0


def create_session(
    user_agent: str,
    referer: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> requests.Session:
    """
    Create a configured requests session with retry strategy.
    
    Args:
        user_agent: User-Agent string to use
        referer: Optional Referer header
        extra_headers: Additional headers to include
        timeout: Default timeout in seconds
        
    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    
    headers = {"User-Agent": user_agent}
    if referer:
        headers["Referer"] = referer
    if extra_headers:
        headers.update(extra_headers)
    session.headers.update(headers)
    
    # Configure retry strategy for connection errors
    retry_strategy = Retry(
        total=0,  # We handle retries manually for more control
        connect=3,
        read=3,
        status=0,  # We handle status retries manually
        backoff_factor=0.5,
        raise_on_status=False,
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Store default timeout
    session.default_timeout = timeout
    
    return session


def _should_retry_status(status_code: int) -> bool:
    """Check if a status code should trigger a retry."""
    if status_code in RETRYABLE_STATUS_CODES:
        return True
    if status_code in NON_RETRYABLE_STATUS_CODES:
        return False
    # Retry on 5xx server errors by default
    return 500 <= status_code < 600


def _calculate_backoff(attempt: int, base: float = 2.0, max_backoff: float = 60.0, jitter: bool = True) -> float:
    """Calculate exponential backoff with optional jitter."""
    backoff = min(base * (2 ** (attempt - 1)), max_backoff)
    if jitter:
        backoff = backoff * (0.5 + random.random())  # 50-150% of calculated backoff
    return backoff


def fetch_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    max_retries: int = 3,
    timeout: Optional[int] = None,
    backoff_base: float = 2.0,
    backoff_max: float = 60.0,
    retryable_status_codes: Optional[set] = None,
    **kwargs
) -> FetchResult:
    """
    Fetch a URL with retry logic and exponential backoff.
    
    Args:
        session: requests.Session to use
        method: HTTP method (GET, POST, etc.)
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        backoff_base: Base backoff in seconds
        backoff_max: Maximum backoff in seconds
        retryable_status_codes: Additional status codes to retry
        **kwargs: Additional arguments passed to session.request()
        
    Returns:
        FetchResult with success status, data, or error
    """
    if timeout is None:
        timeout = getattr(session, 'default_timeout', 30)
    
    if retryable_status_codes is None:
        retryable_status_codes = RETRYABLE_STATUS_CODES
    
    last_exception = None
    last_status_code = None
    
    for attempt in range(1, max_retries + 1):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
            last_status_code = response.status_code
            
            if response.status_code == 200:
                return FetchResult(
                    success=True,
                    data=response,
                    status_code=response.status_code,
                    response_headers=dict(response.headers),
                    attempts=attempt,
                )
            
            # Check if we should retry this status code
            should_retry = (
                response.status_code in retryable_status_codes or
                (500 <= response.status_code < 600 and response.status_code not in NON_RETRYABLE_STATUS_CODES)
            )
            
            if not should_retry or attempt == max_retries:
                return FetchResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.reason}",
                    status_code=response.status_code,
                    response_headers=dict(response.headers),
                    attempts=attempt,
                )
            
            # Log retry
            logger.warning(
                f"HTTP {response.status_code} for {url}, "
                f"attempt {attempt}/{max_retries}, retrying..."
            )
            
        except requests.Timeout as e:
            last_exception = e
            logger.warning(f"Timeout fetching {url} (attempt {attempt}/{max_retries}): {e}")
            
        except requests.ConnectionError as e:
            last_exception = e
            logger.warning(f"Connection error for {url} (attempt {attempt}/{max_retries}): {e}")
            
        except requests.RequestException as e:
            last_exception = e
            logger.error(f"Request failed for {url} (attempt {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                break
        
        # Wait before retry (except on last attempt)
        if attempt < max_retries:
            backoff = _calculate_backoff(attempt, backoff_base, backoff_max)
            logger.debug(f"Backing off for {backoff:.1f}s before retry {attempt + 1}")
            time.sleep(backoff)
    
    # All retries exhausted
    error_msg = str(last_exception) if last_exception else f"Failed after {max_retries} attempts"
    if last_status_code:
        error_msg = f"HTTP {last_status_code}: {error_msg}"
    
    return FetchResult(
        success=False,
        error=error_msg,
        status_code=last_status_code,
        attempts=max_retries,
    )


def fetch_json_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    max_retries: int = 3,
    timeout: Optional[int] = None,
    backoff_base: float = 2.0,
    backoff_max: float = 60.0,
    **kwargs
) -> FetchResult:
    """
    Fetch JSON data with retry logic.
    
    Args:
        session: requests.Session to use
        method: HTTP method
        url: URL to fetch
        max_retries: Maximum retry attempts
        timeout: Request timeout
        backoff_base: Base backoff seconds
        backoff_max: Maximum backoff seconds
        **kwargs: Additional request arguments
        
    Returns:
        FetchResult with parsed JSON data or error
    """
    result = fetch_with_retry(
        session, method, url, max_retries, timeout, backoff_base, backoff_max, **kwargs
    )
    
    if not result.success:
        return result
    
    try:
        # Handle SWAYAM's prefixed JSON (")]}'")
        text = result.data.text
        if text.startswith(")]}'"):
            text = text[4:].strip()
        json_data = json.loads(text)
        result.data = json_data
    except json.JSONDecodeError as e:
        result.success = False
        result.error = f"Invalid JSON response: {e}"
    
    return result


def fetch_html_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = 3,
    timeout: Optional[int] = None,
    backoff_base: float = 2.0,
    backoff_max: float = 60.0,
    **kwargs
) -> FetchResult:
    """
    Fetch HTML content with retry logic.
    
    Args:
        session: requests.Session to use
        url: URL to fetch
        max_retries: Maximum retry attempts
        timeout: Request timeout
        backoff_base: Base backoff seconds
        backoff_max: Maximum backoff seconds
        **kwargs: Additional request arguments
        
    Returns:
        FetchResult with HTML text or error
    """
    result = fetch_with_retry(
        session, "GET", url, max_retries, timeout, backoff_base, backoff_max, **kwargs
    )
    
    if not result.success:
        return result
    
    result.data = result.data.text
    return result


import json