from pydantic import BaseModel, EmailStr


# ── Trả về sau khi login thành công ───────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    csrf_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Dữ liệu bên trong JWT (payload) ──────────────────────────
class TokenData(BaseModel):
    user_id: str
    role: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str