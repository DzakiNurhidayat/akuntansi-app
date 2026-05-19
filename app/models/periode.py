from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Periode(Base):
    __tablename__ = "periode"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nama_perusahaan = Column(String(100), nullable=False)
    tahun = Column(Integer, nullable=False)
    bulan = Column(Integer, nullable=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship ke transaksi
    transaksi = relationship("Transaksi", back_populates="periode", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('nama_perusahaan', 'tahun', 'bulan', name='uq_periode'),
        CheckConstraint('bulan BETWEEN 1 AND 12', name='check_bulan'),
    )
    
    def __repr__(self):
        return f"<Periode {self.nama_perusahaan} {self.bulan}/{self.tahun}>"