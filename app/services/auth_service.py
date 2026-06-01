from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.mysql.models.user_model import User
from app.mysql.schemas.token_schema import LoginRequest
from app.mysql.schemas.user_schema import UserCreate
from app.services.user_service import (
    get_user_by_email,
    get_user_by_id,
    register_user,
)
from app.utils.hash import verify_password

__all__ = [
    "authenticate_user",
    "get_user_by_email",
    "get_user_by_id",
    "register_user",
]


def authenticate_user(db: Session, payload: LoginRequest) -> User | None:
    user = get_user_by_email(db, payload.email)
    if not user:
        return None
    if not verify_password(payload.password, user.password):
        return None
    return user
