from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import oauth2_scheme
from app.mysql.dependencies import get_db
from app.mysql.models.user_model import User, UserRole
from app.services.auth_service import get_user_by_id
from app.services.session_service import get_token_version
from app.services.token_blacklist_service import is_blacklisted, is_jti_blacklisted
from app.utils.jwt_handler import decode_token


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if is_blacklisted(token):
        raise credentials_exception

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    jti = payload.get("jti")
    if jti and is_jti_blacklisted(jti):
        raise credentials_exception

    user_id = payload.get("user_id")
    token_version = payload.get("token_version")
    if user_id is None or token_version is None:
        raise credentials_exception

    if int(token_version) != get_token_version(str(user_id)):
        raise credentials_exception

    try:
        user = get_user_by_id(db, int(user_id))
    except ValueError:
        raise credentials_exception

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    # Production thường nên check role thật sự.
    # Theo yêu cầu của bạn: chỉ cần token hợp lệ, không xét role.
    return current_user
