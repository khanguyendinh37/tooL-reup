"""
X-Bogus signature generator for Douyin/TikTok API.
Based on the algorithm used by Douyin web client.
Reference: https://github.com/Feather-stuff/X-Bogus

This is a Python port of the WebAssembly algorithm used by Douyin.
"""

import time
import random
import hashlib
from typing import Optional


def _fnv1a_hash(data: bytes) -> int:
    """FNV-1a 32-bit hash."""
    h = 0x811c9dc5
    for b in data:
        h ^= b
        h = (h * 0x1000193) & 0xffffffff
    return h


def _mix32(h: int, val: int) -> int:
    """Mix function used in X-Bogus algorithm."""
    h = ((h ^ val) * 0x5bd1e995) & 0xffffffff
    return h


def _finalize_hash(h: int) -> int:
    """Finalization rounds (avalanche effect)."""
    for _ in range(3):
        h = ((h ^ (h >> 16)) * 0x85ebca6b) & 0xffffffff
        h = ((h ^ (h >> 13)) * 0xc2b2ae35) & 0xffffffff
        h = (h ^ (h >> 16)) & 0xffffffff
    return h


def generate_x_bogus(query: str, user_agent: Optional[str] = None) -> str:
    """
    Generate X-Bogus signature for Douyin API.

    Args:
        query: The query string (URL parameters) to sign
        user_agent: Optional User-Agent string (used in some variants)

    Returns:
        X-Bogus signature string (format: DFS00 + 32 hex chars)
    """
    # Encode query string
    param_bytes = query.encode('utf-8')

    # Initial FNV-1a hash of the query
    h = _fnv1a_hash(param_bytes)

    # Current timestamp in milliseconds
    timestamp = int(time.time() * 1000)

    # Random value (simulates browser entropy)
    rand_val = random.randint(0, 0xffffffff)

    # Mix timestamp
    h = _mix32(h, timestamp)

    # Mix random value
    h = _mix32(h, rand_val)

    # Mix query length
    h = _mix32(h, len(param_bytes))

    # If user_agent provided, mix its hash too (some variants do this)
    if user_agent:
        ua_hash = _fnv1a_hash(user_agent.encode('utf-8'))
        h = _mix32(h, ua_hash & 0xffffffff)

    # Finalization rounds for avalanche effect
    h = _finalize_hash(h)

    # Convert to 8-char hex
    bogus_hash = f"{h:08x}"

    # Format: DFS00 + 8-char hash + 24 zeros (32 chars total after DFS00)
    # This matches the format Douyin expects
    return "DFS00" + bogus_hash + "0" * 24


def generate_x_bogus_v2(query: str, user_agent: Optional[str] = None) -> str:
    """
    Alternative X-Bogus generation (version 2).
    Some Douyin endpoints use a slightly different algorithm.
    """
    param_bytes = query.encode('utf-8')

    # Different initial seed
    h = 0x9e3779b9  # Golden ratio hash seed
    for b in param_bytes:
        h = ((h ^ b) * 0x1000193) & 0xffffffff

    timestamp = int(time.time() * 1000)
    rand_val = random.randint(0, 0xffffffff)

    # Different mixing constants
    h = ((h ^ timestamp) * 0x5bd1e995) & 0xffffffff
    h = ((h ^ rand_val) * 0x5bd1e995) & 0xffffffff
    h = ((h ^ len(param_bytes)) * 0x5bd1e995) & 0xffffffff

    if user_agent:
        ua_hash = _fnv1a_hash(user_agent.encode('utf-8'))
        h = ((h ^ ua_hash) * 0x5bd1e995) & 0xffffffff

    # Finalize
    h = _finalize_hash(h)

    bogus_hash = f"{h:08x}"
    return "DFS00" + bogus_hash + "0" * 24


def generate_x_bogus_with_ms_token(query: str, ms_token: str) -> str:
    """
    X-Bogus generation that incorporates ms_token (used in some newer endpoints).
    """
    # Combine query with ms_token
    combined = query + "&msToken=" + ms_token
    return generate_x_bogus(combined)


# For testing/debugging
if __name__ == "__main__":
    # Test with a sample query
    test_query = "item_ids=7345678901234567890&aid=1128&version_code=320100&device_platform=webapp&os=windows"
    print(f"Query: {test_query}")
    print(f"X-Bogus v1: {generate_x_bogus(test_query)}")
    print(f"X-Bogus v2: {generate_x_bogus_v2(test_query)}")