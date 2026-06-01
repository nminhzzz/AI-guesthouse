import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    MYSQL_HOST = os.getenv("MYSQL_HOST")
    MYSQL_PORT = os.getenv("MYSQL_PORT")
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_DB = os.getenv("MYSQL_DB")

    MONGO_URL = os.getenv("MONGO_URL")
    MONGO_DB = os.getenv("MONGO_DB")

    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = os.getenv("REDIS_PORT")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax")

    LOGIN_RATE_LIMIT: int = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
    LOGIN_RATE_WINDOW_SECONDS: int = int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", str(15 * 60)))
    REGISTER_RATE_LIMIT: int = int(os.getenv("REGISTER_RATE_LIMIT", "10"))
    REGISTER_RATE_WINDOW_SECONDS: int = int(os.getenv("REGISTER_RATE_WINDOW_SECONDS", str(60 * 60)))

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


settings = Settings()

if not settings.SECRET_KEY:
    if settings.is_production:
        raise ValueError("SECRET_KEY is required in production")
    settings.SECRET_KEY = "dev-only-change-me"
