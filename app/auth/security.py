import hashlib
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _bcrypt_safe_secret(password: str) -> str:
    b = password.encode("utf-8")
    if len(b) <= 72:
        return password
    # bcrypt hard limit: pre-hash long passwords deterministically
    return hashlib.sha256(b).hexdigest()


def hash_password(password: str) -> str:
    return _pwd.hash(_bcrypt_safe_secret(password))


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(_bcrypt_safe_secret(password), password_hash)
