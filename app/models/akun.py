from sqlalchemy import Column, String, Boolean, DateTime, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class Akun(Base):
    __tablename__ = "akun"
    
    kode_akun = Column(String(10), primary_key=True)
    nama_akun = Column(String(100), nullable=False)
    nama_akun_en = Column(String(100))
    jenis_akun = Column(String(20), nullable=False)
    saldo_normal = Column(String(10), nullable=False)
    is_kontra = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "jenis_akun IN ('aset', 'kewajiban', 'modal', 'pendapatan', 'beban')",
            name="check_jenis_akun"
        ),
        CheckConstraint(
            "saldo_normal IN ('debet', 'kredit')",
            name="check_saldo_normal"
        ),
    )
    
    def __repr__(self):
        return f"<Akun {self.kode_akun} - {self.nama_akun}>"