import re
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from fastapi import Form
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRole(str, Enum):
    user = "user"
    owner = "owner"
    admin = "admin"


class RegisterRole(str, Enum):
    user = "user"
    owner = "owner"


def validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Mật khẩu phải chứa ít nhất một chữ viết hoa")
    if not re.search(r"[a-z]", v):
        raise ValueError("Mật khẩu phải chứa ít nhất một chữ viết thường")
    if not re.search(r"\d", v):
        raise ValueError("Mật khẩu phải chứa ít nhất một chữ số")
    return v


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=20)
    avatar_url: Optional[str] = None
    role: UserRole = UserRole.user


class UserCreate(UserBase):
    role: RegisterRole = RegisterRole.user
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserAdminCreate(UserBase):
    password: str
    is_verified: bool = False
    is_active: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @classmethod
    def as_form(
        cls,
        name: str = Form(...),
        email: EmailStr = Form(...),
        password: str = Form(...),
        phone: Optional[str] = Form(None),
        avatar_url: Optional[str] = Form(None),
        role: UserRole = Form(UserRole.user),
        is_verified: bool = Form(False),
        is_active: bool = Form(True),
    ) -> "UserAdminCreate":
        return cls(
            name=name,
            email=email,
            password=password,
            phone=phone,
            avatar_url=avatar_url,
            role=role,
            is_verified=is_verified,
            is_active=is_active,
        )


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    avatar_url: Optional[str] = None


class UserAdminUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    avatar_url: Optional[str] = None
    role: Optional[UserRole] = None
    is_verified: Optional[bool] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_password_strength(v)

    @classmethod
    def as_form(
        cls,
        name: Optional[str] = Form(None),
        email: Optional[EmailStr] = Form(None),
        phone: Optional[str] = Form(None),
        avatar_url: Optional[str] = Form(None),
        role: Optional[UserRole] = Form(None),
        is_verified: Optional[bool] = Form(None),
        is_active: Optional[bool] = Form(None),
        password: Optional[str] = Form(None),
    ) -> "UserAdminUpdate":
        # Chỉ đưa vào fields thực sự được gửi để model_dump(exclude_unset=True) hoạt động đúng
        fields: dict = {}
        if name is not None: fields["name"] = name
        if email is not None: fields["email"] = email
        if phone is not None: fields["phone"] = phone
        if avatar_url is not None: fields["avatar_url"] = avatar_url
        if role is not None: fields["role"] = role
        if is_verified is not None: fields["is_verified"] = is_verified
        if is_active is not None: fields["is_active"] = is_active
        if password is not None: fields["password"] = password
        return cls(**fields)


class UserResponse(UserBase):
    id: int
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


UserSortField = Literal["id", "name", "email", "role", "created_at", "updated_at"]
SortOrder = Literal["asc", "desc"]
