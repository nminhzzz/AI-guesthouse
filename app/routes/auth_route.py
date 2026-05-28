from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.common.schemas.response_schema import ApiResponse
from app.mysql.dependencies import get_db
from app.mysql.schemas.token_schema import LoginRequest, TokenResponse
from app.mysql.schemas.user_schema import UserCreate, UserResponse
from app.services.auth_service import (
    authenticate_user,
    get_user_by_email,
    get_user_by_id,
    register_user,
)
from app.services.token_blacklist_service import blacklist_token, is_blacklisted
from app.utils.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.utils.rate_limiter import check_rate_limit, reset_rate_limit

router = APIRouter(prefix="/auth", tags=["Auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


@router.post("/register", response_model=ApiResponse[UserResponse], status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    new_user = register_user(db, user)
    return ApiResponse.success(
        data=UserResponse.model_validate(new_user),
        message="User registered successfully",
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    user = authenticate_user(db, payload)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    token_payload = {
        "user_id": str(user.id),
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    _set_refresh_cookie(response, refresh_token)
    reset_rate_limit(client_ip)

    return ApiResponse.success(
        data=TokenResponse(access_token=access_token, token_type="bearer"),
        message="Login successful",
    )


@router.post("/refresh-token", response_model=ApiResponse[TokenResponse])
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    if is_blacklisted(refresh_token_value):
        raise HTTPException(status_code=401, detail="Token revoked")

    payload = decode_token(refresh_token_value)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user = get_user_by_id(db, int(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token payload") from exc

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")

    token_payload = {
        "user_id": str(user.id),
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }
    new_access_token = create_access_token(token_payload)
    new_refresh_token = create_refresh_token(token_payload)
    _set_refresh_cookie(response, new_refresh_token)

    return ApiResponse.success(
        data=TokenResponse(access_token=new_access_token, token_type="bearer"),
        message="Refresh token successful",
    )



@router.post("/logout")
def logout(
    request: Request,
    response: Response
):

    # 1. Lấy refresh token từ cookie
    refresh_token_value = request.cookies.get(
        "refresh_token"
    )

    if not refresh_token_value:
        response.delete_cookie(key="refresh_token", path="/")
        return ApiResponse.success(message="Logout successful")

    # 2. Decode token
    payload = decode_token(refresh_token_value)

    if payload is None:
        response.delete_cookie(key="refresh_token", path="/")
        return ApiResponse.success(message="Logout successful")

    # 3. Kiểm tra type
    if payload.get("type") != "refresh":
        response.delete_cookie(key="refresh_token", path="/")
        return ApiResponse.success(message="Logout successful")

    # 4. Tính thời gian còn lại của token
    exp = payload.get("exp")

    if exp:

        expires_in = int(
            exp - datetime.now(
                timezone.utc
            ).timestamp()
        )

        # Chỉ blacklist nếu token còn hạn
        if expires_in > 0:

            blacklist_token(
                refresh_token_value,
                expires_in
            )

    # 5. Xóa cookie
    response.delete_cookie(
        key="refresh_token",
        path="/"
    )

    # 6. Response
    return ApiResponse.success(
        message="Logout successful"
    )