"""Password hashing (bcrypt).

bcrypt only uses the first 72 bytes of a password, so longer passwords are rejected
up front instead of being silently truncated.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import bcrypt

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

# bcrypt is deliberately slow (~0.25 s). It runs on its own small pool so that it never blocks the
# event loop, never competes with image processing for threads, and a burst of logins cannot run
# more than this many hashes at once.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bcrypt")

# Pre-computed hash used to keep login timing constant when the user does not exist.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt()).decode()


def validate_password_strength(password: str) -> None:
    """Raise ValueError if the password does not meet the policy."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time-ish verification; always performs one bcrypt check."""
    encoded = password.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        encoded = encoded[:MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(encoded, (password_hash or _DUMMY_HASH).encode()) and password_hash is not None
    except ValueError:
        return False


async def hash_password_async(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_executor, hash_password, password)


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    return await asyncio.get_running_loop().run_in_executor(_executor, verify_password, password, password_hash)
