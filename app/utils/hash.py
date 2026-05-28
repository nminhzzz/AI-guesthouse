from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password is required")

    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password quá dài (bcrypt max 72 bytes)")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
