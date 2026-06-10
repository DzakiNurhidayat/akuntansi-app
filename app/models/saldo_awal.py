from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class SaldoAwal(Base):
    """Saldo awal periode untuk akun permanen (carry-forward dari periode sebelumnya).

    Diisi otomatis saat 'Tutup Periode' di /penutup — menyimpan saldo akhir akun
    1xx (aset), 2xx (kewajiban), dan 311 (modal) periode N untuk dipakai sebagai
    opening balance di periode N+1.

    saldo > 0  → saldo di sisi normal akun
    saldo < 0  → saldo di sisi berlawanan (jarang, biasanya validasi error)
    """
    __tablename__ = "saldo_awal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    periode_id = Column(Integer, ForeignKey("periode.id", ondelete="CASCADE"), nullable=False)
    kode_akun = Column(String(10), ForeignKey("akun.kode_akun"), nullable=False)
    saldo = Column(Numeric(15, 2), default=0, nullable=False)

    periode = relationship("Periode")
    akun = relationship("Akun")

    __table_args__ = (
        UniqueConstraint("periode_id", "kode_akun", name="uq_saldo_awal"),
    )

    def __repr__(self):
        return f"<SaldoAwal p={self.periode_id} {self.kode_akun} = {self.saldo}>"
