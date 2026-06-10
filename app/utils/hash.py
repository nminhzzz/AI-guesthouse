import bcrypt

def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password is required")

    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password quá dài (bcrypt max 72 bytes)")

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False
