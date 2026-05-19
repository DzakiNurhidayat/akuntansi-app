from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class JurnalEntry(Base):
    __tablename__ = "jurnal_entry"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaksi_id = Column(Integer, ForeignKey("transaksi.id", ondelete="CASCADE"), nullable=False)
    kode_akun = Column(String(10), ForeignKey("akun.kode_akun"), nullable=False)
    debet = Column(Numeric(15, 2), default=0)
    kredit = Column(Numeric(15, 2), default=0)
    urutan = Column(Integer, default=0)
    
    # Relationships
    transaksi = relationship("Transaksi", back_populates="entries")
    akun = relationship("Akun")
    
    __table_args__ = (
        CheckConstraint(
            "(debet > 0 AND kredit = 0) OR (debet = 0 AND kredit > 0)",
            name="check_debet_kredit"
        ),
    )
    
    def __repr__(self):
        return f"<JurnalEntry {self.kode_akun} D:{self.debet} K:{self.kredit}>"