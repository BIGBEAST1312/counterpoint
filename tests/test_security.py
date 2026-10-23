# Sign-in security tests | Built by Hetank Patel, owned by no feature
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
"""Passwords and sign-in tokens are never stored as they are typed."""
from app.auth.models import ROLES
from app.auth.security import hash_password, new_token, token_hash, verify_password


def test_password_is_salted_and_hashed():
    first, second = hash_password("counterpoint"), hash_password("counterpoint")
    assert first != second                    # a random salt each time
    assert "counterpoint" not in first        # the password itself is never stored
    assert verify_password("counterpoint", first) and verify_password("counterpoint", second)


def test_wrong_password_or_damaged_hash_is_refused():
    stored = hash_password("counterpoint")
    assert not verify_password("Counterpoint", stored)
    assert not verify_password("counterpoint", "not-a-real-hash")


def test_sign_in_token_is_stored_as_a_hash():
    token = new_token()
    assert token_hash(token) == token_hash(token) and token_hash(token) != token and len(token_hash(token)) == 64
    assert new_token() != token


def test_three_roles():
    assert ROLES == ("assistant", "lead", "supervisor")
