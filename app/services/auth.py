"""Helper autentikasi: hash password, verifikasi, dependency current_user."""
import bcrypt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


# ─── Password hashing ────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash password plain → bcrypt string (utf-8)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Cek apakah plain password cocok dengan hash bcrypt."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ─── Session helpers ─────────────────────────────────────────────────────────

def login_user(request: Request, user: User) -> None:
    """Set session cookie agar user dianggap login."""
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["nama"] = user.nama
    request.session["is_admin"] = bool(user.is_admin)


def logout_user(request: Request) -> None:
    """Hapus session login."""
    request.session.clear()


# ─── Dependency: current_user ────────────────────────────────────────────────

def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Return User aktif (atau None kalau belum login).

    Digunakan sebagai dependency di route. Auth enforcement dilakukan oleh
    AuthMiddleware — dependency ini hanya mengambil user yang sudah login.
    """
    uid = request.session.get("user_id")
    if not uid:
        return None
    user = db.query(User).filter(User.id == uid, User.is_active.is_(True)).first()
    return user
