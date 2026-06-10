from sqlalchemy import Column, ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import relationship

from app.database import Base


class UserAkun(Base):
    """Many-to-many: user ↔ akun. Menentukan akun apa yang user boleh pakai
    saat input transaksi. Admin tidak butuh row di sini (full access).

    Akun dengan is_universal=True juga bisa dipakai semua user tanpa perlu
    row di tabel ini.
    """
    __tablename__ = "user_akun"

    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    kode_akun = Column(String(10), ForeignKey("akun.kode_akun", ondelete="CASCADE"), nullable=False)

    user = relationship("User")
    akun = relationship("Akun")

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "kode_akun", name="pk_user_akun"),
    )

    def __repr__(self):
        return f"<UserAkun u={self.user_id} a={self.kode_akun}>"
