"""
Resilient HTTP layer built on requests.

A single shared Session (connection pooling + consistent headers), plus a
`fetch` helper with retries, exponential-ish backoff, and a polite delay.
Every failure is logged; on total failure `fetch` returns None so callers
can degrade gracefully instead of crashing.
"""

import time

import requests
from bs4 import BeautifulSoup

from config import (
    MAX_RETRIES,
    POLITE_DELAY,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF,
    USER_AGENT,
)
from core.logger import get_logger

log = get_logger("http")

_session = None


def get_session():
    """Lazily create and return the shared requests Session."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})
    return _session


def fetch(url, params=None):
    """
    GET a URL with retries + backoff.

    Returns the requests.Response on success, or None if every attempt failed.
    """
    session = get_session()
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.debug("GET %s (attempt %d/%d)", url, attempt, MAX_RETRIES)
            resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            time.sleep(POLITE_DELAY)
            return resp
        except requests.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            # 4xx (e.g. 404 Not Found) won't fix itself — fail fast, no retry.
            if status is not None and 400 <= status < 500:
                log.error("Client error %s for %s — not retrying", status, url)
                return None
            wait = RETRY_BACKOFF * attempt
            log.warning("Server error (%s) for %s — retrying in %.1fs", exc, url, wait)
            time.sleep(wait)
        except requests.RequestException as exc:
            last_error = exc
            wait = RETRY_BACKOFF * attempt
            log.warning(
                "Fetch failed (%s) for %s — retrying in %.1fs", exc, url, wait
            )
            time.sleep(wait)

    log.error("Giving up on %s after %d attempts: %s", url, MAX_RETRIES, last_error)
    return None


def fetch_soup(url, params=None, parser="lxml"):
    """Fetch a URL and return a parsed BeautifulSoup, or None on failure."""
    resp = fetch(url, params=params)
    if resp is None:
        return None
    try:
        return BeautifulSoup(resp.text, parser)
    except Exception as exc:  # pragma: no cover - parser edge cases
        log.error("Failed to parse HTML from %s: %s", url, exc)
        return None


def fetch_json(url, params=None):
    """Fetch a URL and return parsed JSON, or None on failure."""
    resp = fetch(url, params=params)
    if resp is None:
        return None
    try:
        return resp.json()
    except ValueError as exc:
        log.error("Invalid JSON from %s: %s", url, exc)
        return None
