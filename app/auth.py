import base64
import hashlib
import hmac
import secrets
from urllib.parse import urlparse

from app.models import AdminUser

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 310_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_{PBKDF2_ALGORITHM}$"
        f"{PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, rounds, salt_b64, digest_b64 = password_hash.split("$", 3)
        if scheme != f"pbkdf2_{PBKDF2_ALGORITHM}":
            return False
        iterations = int(rounds)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
    except Exception:
        return False

    calculated = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(calculated, expected)


def is_safe_next_path(next_path: str | None) -> bool:
    if not next_path:
        return False
    parsed = urlparse(next_path)
    if parsed.scheme or parsed.netloc:
        return False
    return next_path.startswith("/")


def authenticate_admin(username: str, password: str, admin_user: AdminUser | None) -> bool:
    if admin_user is None or not admin_user.is_active:
        return False
    valid_user = secrets.compare_digest(username, admin_user.username)
    valid_pass = verify_password(password, admin_user.password_hash)
    return valid_user and valid_pass
