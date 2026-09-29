from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

def hash_password(password: str) -> str:
    """Return an Argon2id password hash suitable for database storage."""
    if not password:
        raise ValueError("Password must not be empty")
    return _hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
