from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mysql.models.user_model import User, UserRole
from app.mysql.schemas.token_schema import LoginRequest
from app.mysql.schemas.user_schema import UserCreate
from app.utils.hash import hash_password, verify_password

def get_user_by_email(db: Session, email: str | EmailStr) -> User | None:
    return db.scalars(
        select(User).where(User.email == str(email))
    ).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def authenticate_user(db: Session, payload: LoginRequest) -> User | None:
    user = get_user_by_email(db, payload.email)
    if not user:
        return None
    if not verify_password(payload.password, user.password):
        return None
    return user


def register_user(db: Session, payload: UserCreate) -> User:
    user = User(
        name=payload.name,
        email=str(payload.email),
        password=hash_password(payload.password),
        phone=payload.phone,
        avatar_url=payload.avatar_url,
        role=UserRole(payload.role.value),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
