"""Helper otorisasi: cek admin, ambil daftar akun yang user boleh pakai."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Akun, User, UserAkun

# Akun sistem — tidak boleh dipakai siapa pun di UI input
SYSTEM_AKUN = {"313"}  # Ikhtisar Laba Rugi (clearing untuk jurnal penutup)


def is_admin(user: Optional[User]) -> bool:
    return bool(user and user.is_admin)


def allowed_akun_kode(db: Session, user: Optional[User]) -> set[str]:
    """Return set kode_akun yang boleh dipakai user di form input transaksi.

      • Admin     → semua akun aktif (kecuali system)
      • Non-admin → akun yang di-assign ke dia + semua akun is_universal=True
      • None      → kosong
    """
    if not user:
        return set()

    base = db.query(Akun.kode_akun).filter(
        Akun.is_active.is_(True),
        ~Akun.kode_akun.in_(SYSTEM_AKUN),
    )

    if user.is_admin:
        return {k for (k,) in base.all()}

    universal_kode = {
        k for (k,) in base.filter(Akun.is_universal.is_(True)).all()
    }
    assigned = {
        ua.kode_akun
        for ua in db.query(UserAkun).filter(UserAkun.user_id == user.id).all()
    }
    return universal_kode | assigned


def user_assigned_kode(db: Session, user: User) -> set[str]:
    """Akun yang di-assign langsung ke user (tidak termasuk universal). Untuk
    halaman admin assignment, supaya checkbox yang sudah di-assign ter-tick."""
    return {
        ua.kode_akun
        for ua in db.query(UserAkun).filter(UserAkun.user_id == user.id).all()
    }
