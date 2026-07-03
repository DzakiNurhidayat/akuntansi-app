from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Akun(Base):
    """Akun Chart of Accounts. Bisa berupa:
      • akun detail (is_kategori=False) — leaf, bisa dipakai di transaksi
      • kategori (is_kategori=True)     — grouping, tidak bisa dipakai di transaksi

    Hierarki: akun detail boleh punya parent kategori (mis. Kas 111 → kategori 11
    Harta Lancar). Kategori boleh nested (parent_kode → kategori lain).
    """
    __tablename__ = "akun"

    kode_akun = Column(String(10), primary_key=True)
    nama_akun = Column(String(100), nullable=False)
    nama_akun_en = Column(String(100))
    jenis_akun = Column(String(20), nullable=False)  # FK string ke jenis_akun.kode
    saldo_normal = Column(String(10), nullable=False)
    is_kontra = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    # Universal: bisa dipakai semua user tanpa perlu di-assign (mis. Kas)
    is_universal = Column(Boolean, default=False, nullable=False)
    # Kategori: TIDAK bisa dipilih di transaksi, hanya untuk grouping/neraca
    is_kategori = Column(Boolean, default=False, nullable=False)
    # Self-FK: parent kategori (NULL untuk top-level kategori atau akun tanpa kategori)
    parent_kode = Column(String(10), ForeignKey("akun.kode_akun"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    parent = relationship("Akun", remote_side="Akun.kode_akun", backref="children")

    __table_args__ = (
        CheckConstraint(
            "saldo_normal IN ('debet', 'kredit')",
            name="check_saldo_normal",
        ),
    )

    def __repr__(self):
        return f"<Akun {self.kode_akun} - {self.nama_akun}>"