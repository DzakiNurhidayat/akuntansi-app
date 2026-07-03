from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class JenisAkun(Base):
    """Klasifikasi tingkat tertinggi akun: Harta, Utang, Modal, Pendapatan, Beban.

    Awalnya 5 jenis standar di-seed; admin bisa tambah jenis baru (mis. untuk
    akun 6xx). `kode` dipakai oleh Akun.jenis_akun sebagai referensi (string).
    """
    __tablename__ = "jenis_akun"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Kode internal yang dipakai di Akun.jenis_akun (mis. "aset", "kewajiban")
    kode = Column(String(20), unique=True, nullable=False, index=True)
    # Nama tampilan (mis. "Harta", "Utang")
    nama = Column(String(50), nullable=False)
    saldo_normal_default = Column(String(10), nullable=False)
    urutan = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "saldo_normal_default IN ('debet', 'kredit')",
            name="check_jenis_saldo_normal",
        ),
    )

    def __repr__(self):
        return f"<JenisAkun {self.kode} - {self.nama}>"
