from pydantic import EmailStr
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.mysql.models.user_model import User, UserRole
from app.mysql.schemas.user_schema import (
    SortOrder,
    UserAdminCreate,
    UserAdminUpdate,
    UserCreate,
    UserSortField,
)
from app.utils.hash import hash_password
from app.utils.pagination import get_offset, get_total_pages


SORTABLE_COLUMNS = {
    "id": User.id,
    "name": User.name,
    "email": User.email,
    "role": User.role,
    "created_at": User.created_at,
    "updated_at": User.updated_at,
}


def get_user_by_email(db: Session, email: str | EmailStr) -> User | None:
    return db.scalars(
        select(User).where(User.email == str(email))
    ).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    is_verified: bool | None = None,
    sort_by: UserSortField = "created_at",
    sort_order: SortOrder = "desc",
) -> tuple[list[User], int]:
    query = select(User)

    if search:
        keyword = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(User.name).like(keyword),
                func.lower(User.email).like(keyword),
                func.lower(User.phone).like(keyword),
            )
        )

    if role is not None:
        query = query.where(User.role == role)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    if is_verified is not None:
        query = query.where(User.is_verified == is_verified)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    sort_column = SORTABLE_COLUMNS.get(sort_by, User.created_at)
    order_expr = asc(sort_column) if sort_order == "asc" else desc(sort_column)
    query = query.order_by(order_expr).offset(get_offset(page, page_size)).limit(page_size)

    users = list(db.scalars(query).all())
    return users, total


def create_user_admin(db: Session, payload: UserAdminCreate) -> User:
    user = User(
        name=payload.name,
        email=str(payload.email),
        password=hash_password(payload.password),
        phone=payload.phone,
        avatar_url=payload.avatar_url,
        role=UserRole(payload.role.value),
        is_verified=payload.is_verified,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
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


def update_user_admin(db: Session, user: User, payload: UserAdminUpdate) -> User:
    update_data = payload.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        user.email = str(update_data.pop("email"))

    if "password" in update_data and update_data["password"] is not None:
        user.password = hash_password(update_data.pop("password"))

    if "role" in update_data and update_data["role"] is not None:
        user.role = update_data.pop("role")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User, *, hard_delete: bool = False) -> None:
    if hard_delete:
        db.delete(user)
    else:
        user.is_active = False
    db.commit()


def build_paginated_result(
    items: list[User],
    total: int,
    page: int,
    page_size: int,
) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": get_total_pages(total, page_size),
    }
