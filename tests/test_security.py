import os
os.environ.setdefault("AUTH_SECRET_KEY", "test-only-secret-32-bytes-long-minimum-!")

from datetime import timedelta

from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_token, decode_token

def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)
    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)

def test_token_round_trip_and_type_check() -> None:
    token = create_token(subject="user-123", token_type="access", lifetime=timedelta(minutes=5))
    assert decode_token(token, "access") == "user-123"
    assert decode_token(token, "refresh") is None
