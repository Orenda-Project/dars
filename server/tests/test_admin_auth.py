"""
F5.2 — admin auth primitives. Pure-Python: no DB.
"""
from dars.v2_api.admin_auth import (
    hash_api_key,
    hash_password,
    make_api_key,
    verify_password,
)


def test_hash_password_round_trip():
    h = hash_password("hunter2hunter2")
    assert verify_password("hunter2hunter2", h)
    assert not verify_password("wrong-password", h)


def test_hash_password_different_each_time():
    """bcrypt salt is random per hash."""
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_verify_password_handles_garbage_hash():
    assert not verify_password("any", "not-a-bcrypt-hash")
    assert not verify_password("any", "")


def test_make_api_key_shape():
    raw, hashed, prefix = make_api_key()
    assert raw.startswith("dk_live_")
    assert hashed == hash_api_key(raw)
    assert raw.startswith(prefix)
    assert len(prefix) == 12


def test_make_api_key_unique():
    a, _, _ = make_api_key()
    b, _, _ = make_api_key()
    assert a != b
