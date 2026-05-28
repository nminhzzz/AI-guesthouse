from app.mysql.base import Base
from app.mysql.session import engine

# Import models so SQLAlchemy can register metadata before create_all.
from app.mysql.models import user_model  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
