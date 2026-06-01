"""Shared slowapi rate limiter instance.

Import this module wherever rate limiting is needed:
  - app.py: wire into app.state and exception handler
  - auth/endpoints/login.py: apply @limiter.limit("10/minute")
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
