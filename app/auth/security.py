# Shared infrastructure: staff sign-in | Built by Hetank Patel, owned by no feature
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
"""Password hashing and session tokens, using only Python's standard library.

PBKDF2 runs SHA-256 many times over the password plus a random salt, so guessing
passwords from a stolen database is slow. The stored format is
    pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>
"""
import hashlib
import hmac
import secrets

ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), hash_hex)  # constant-time compare


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
