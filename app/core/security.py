from fastapi.security import OAuth2PasswordBearer

# Chỉ định endpoint login để Swagger UI (docs) có thể gửi request lấy token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
