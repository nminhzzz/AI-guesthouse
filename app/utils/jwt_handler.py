from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from typing import Optional
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
ALGORITHM = "HS256"

# Thời gian hết hạn
ACCESS_TOKEN_EXPIRE_MINUTES = 15     # 1 ngày
REFRESH_TOKEN_EXPIRE_DAYS = 7              # 7 ngày


def create_access_token(data: dict) -> str:
    """
    Tạo Access Token
    """
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # thêm thời gian hết hạn + loại token
    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def create_refresh_token(data: dict) -> str:
    """
    Tạo Refresh Token
    """
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


from typing import Optional

def decode_token(token: str) -> Optional[dict]:
    """
    Decode JWT token
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload

    except JWTError:
        return None

def verify_token_type(token: str, expected_type: str) -> Optional[dict]:
    """
    Kiểm tra token có đúng loại không
    expected_type:
        - access
        - refresh
    """
    payload = decode_token(token)

    if payload is None:
        return None

    token_type = payload.get("type")

    if token_type != expected_type:
        return None

    return payload