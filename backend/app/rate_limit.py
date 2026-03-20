"""
Shared rate limiter instance for slowapi.

Used in main.py (middleware) and auth/router.py (login endpoint).
"""

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    HAS_SLOWAPI = True
except ImportError:
    limiter = None
    HAS_SLOWAPI = False
