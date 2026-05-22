"""Tests for db/auth.py — user lookup and session creation."""


def test_verify_password_correct():
    from db.auth import hash_password, verify_password
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_verify_password_wrong():
    from db.auth import hash_password, verify_password
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_hash_password_produces_bcrypt_prefix():
    from db.auth import hash_password
    hashed = hash_password("anypassword")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_build_session_dict():
    from db.auth import _build_session
    row = {"id": "uuid1", "org_id": "org1", "role": "owner", "email": "a@b.com"}
    session = _build_session(row)
    assert session["user_id"] == "uuid1"
    assert session["org_id"] == "org1"
    assert session["role"] == "owner"
    assert session["email"] == "a@b.com"
