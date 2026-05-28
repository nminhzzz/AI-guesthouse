from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum
from datetime import datetime


# Role Enum
class UserRole(str, Enum):
    user = "user"
    owner = "owner"
    admin = "admin"


class RegisterRole(str, Enum):
    user = "user"
    owner = "owner"


# ===== Base =====
class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: UserRole = UserRole.user


# ===== Create (register) =====
class UserCreate(UserBase):
    role: RegisterRole = RegisterRole.user
    password: str  # chỉ nhập plain password khi đăng ký


# ===== Update =====
class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


# ===== Response =====
class UserResponse(UserBase):
    id: int
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True