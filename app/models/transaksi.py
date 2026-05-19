from sqlalchemy import Column, Integer, String, Date, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Transaksi(Base):
    __tablename__ = "transaksi"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    periode_id = Column(Integer, ForeignKey("periode.id"), nullable=False)
    tanggal = Column(Date, nullable=False)
    keterangan = Column(Text)
    jenis = Column(String(20), nullable=False, default="umum")
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    periode = relationship("Periode", back_populates="transaksi")
    entries = relationship("JurnalEntry", back_populates="transaksi", cascade="all, delete-orphan", order_by="JurnalEntry.urutan")
    
    __table_args__ = (
        CheckConstraint(
            "jenis IN ('umum', 'penyesuaian', 'penutup', 'pembalik')",
            name="check_jenis_transaksi"
        ),
    )
    
    def __repr__(self):
        return f"<Transaksi {self.id} - {self.tanggal} - {self.keterangan[:30]}>"