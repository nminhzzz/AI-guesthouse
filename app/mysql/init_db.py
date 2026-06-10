from app.mysql.base import Base
from app.mysql.database import engine, SessionLocal
from app.utils.hash import hash_password
import logging

logger = logging.getLogger(__name__)

# Import models so SQLAlchemy can register metadata before create_all.
from app.mysql.models.user_model import User, UserRole

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    
    # Tạo tài khoản admin mặc định nếu chưa có
    with SessionLocal() as db:
        admin_email = "admin@aiguesthouse.com"
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            try:
                admin_user = User(
                    name="Super Admin",
                    email=admin_email,
                    password=hash_password("admin123456"),
                    role=UserRole.admin,
                    is_verified=True,
                    is_active=True
                )
                db.add(admin_user)
                db.commit()
                logger.info(f"Đã tạo tài khoản admin mặc định: {admin_email}")
            except Exception as e:
                db.rollback()
                logger.error(f"Lỗi khi tạo admin mặc định: {e}")
        else:
            logger.info("Tài khoản admin đã tồn tại.")
