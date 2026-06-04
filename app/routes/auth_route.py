from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.common.schemas.response_schema import ApiResponse
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.mysql.dependencies import get_db
from app.mysql.models.user_model import User
from app.mysql.schemas.token_schema import LoginRequest, TokenResponse
from app.mysql.schemas.user_schema import UserCreate, UserResponse
from app.services.auth_service import (
    authenticate_user,
    get_user_by_email,
    get_user_by_id,
    register_user,
)
from app.services.session_service import (
    clear_user_session,
    get_token_version,
    revoke_all_user_sessions,
    rotate_refresh_session,
    set_active_refresh_jti,
)
from app.services.token_blacklist_service import (
    blacklist_jti,
    blacklist_token,
    is_blacklisted,
)
from app.utils.csrf import generate_csrf_token, verify_csrf
from app.utils.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_ttl,
)
from app.utils.rate_limiter import (
    check_login_rate_limit,
    check_register_rate_limit,
    reset_login_rate_limit,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _cookie_kwargs(max_age: int) -> dict:
    return {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "max_age": max_age,
        "path": "/",
    }


def _set_auth_cookies(
    response: Response,
    refresh_token: str,
    csrf_token: str,
    refresh_ttl: int,
) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        **_cookie_kwargs(refresh_ttl),
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=refresh_ttl,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")


def _build_token_payload(user: User) -> dict[str, str]:
    return {
        "user_id": str(user.id),
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }


def _issue_tokens(user: User, response: Response) -> TokenResponse:
    token_version = get_token_version(str(user.id))
    payload = _build_token_payload(user)

    access_token, _, _ = create_access_token(payload, token_version)
    refresh_token, refresh_jti, refresh_ttl = create_refresh_token(payload, token_version)
    csrf_token = generate_csrf_token()

    set_active_refresh_jti(str(user.id), refresh_jti, refresh_ttl)
    _set_auth_cookies(response, refresh_token, csrf_token, refresh_ttl)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        csrf_token=csrf_token,
    )


@router.post("/register", response_model=ApiResponse[UserResponse], status_code=201)
def register(
    user: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    check_register_rate_limit(client_ip)

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
    check_login_rate_limit(client_ip, str(payload.email))

    user = authenticate_user(db, payload)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    token_data = _issue_tokens(user, response)
    reset_login_rate_limit(client_ip, str(payload.email))

    # Gắn user vào response để frontend không cần gọi /auth/me thêm
    token_data.user = UserResponse.model_validate(user)

    return ApiResponse.success(
        data=token_data,
        message="Login successful",
    )


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse.success(
        data=UserResponse.model_validate(current_user),
        message="User profile fetched successfully",
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
        payload = decode_token(refresh_token_value)
        user_id = payload.get("user_id") if payload else None
        if user_id:
            revoke_all_user_sessions(user_id)
        raise HTTPException(status_code=401, detail="Token revoked")

    payload = decode_token(refresh_token_value)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = payload.get("user_id")
    old_jti = payload.get("jti")
    token_version = payload.get("token_version")

    if not user_id or not old_jti or token_version is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    if int(token_version) != get_token_version(user_id):
        raise HTTPException(status_code=401, detail="Session expired, please login again")

    try:
        user = get_user_by_id(db, int(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token payload") from exc

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")

    token_payload = _build_token_payload(user)
    refresh_ttl = get_token_ttl(payload)

    try:
        new_refresh_token, new_refresh_jti, new_refresh_ttl = create_refresh_token(
            token_payload,
            int(token_version),
        )
        rotate_refresh_session(user_id, old_jti, new_refresh_jti, refresh_ttl or new_refresh_ttl)
    except ValueError as exc:
        if str(exc) == "refresh_token_reused":
            revoke_all_user_sessions(user_id, old_jti_ttl=refresh_ttl)
            raise HTTPException(
                status_code=401,
                detail="Refresh token reuse detected. Please login again.",
            ) from exc
        raise

    blacklist_token(refresh_token_value, refresh_ttl)

    new_access_token, _, _ = create_access_token(token_payload, int(token_version))
    csrf_token = generate_csrf_token()
    _set_auth_cookies(response, new_refresh_token, csrf_token, new_refresh_ttl)

    return ApiResponse.success(
        data=TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            csrf_token=csrf_token,
        ),
        message="Refresh token successful",
    )


@router.post("/logout")
def logout(request: Request, response: Response):
    refresh_token_value = request.cookies.get("refresh_token")
    auth_header = request.headers.get("Authorization", "")

    if refresh_token_value:
        payload = decode_token(refresh_token_value)
        if payload and payload.get("type") == "refresh":
            refresh_ttl = get_token_ttl(payload)
            blacklist_token(refresh_token_value, refresh_ttl)

            jti = payload.get("jti")
            user_id = payload.get("user_id")
            if jti:
                blacklist_jti(jti, refresh_ttl)
            if user_id:
                clear_user_session(user_id)

    if auth_header.startswith("Bearer "):
        access_token = auth_header.split(" ", 1)[1]
        access_payload = decode_token(access_token)
        if access_payload and access_payload.get("type") == "access":
            access_ttl = get_token_ttl(access_payload)
            blacklist_token(access_token, access_ttl)
            access_jti = access_payload.get("jti")
            if access_jti:
                blacklist_jti(access_jti, access_ttl)

    _clear_auth_cookies(response)
    return ApiResponse.success(message="Logout successful")
