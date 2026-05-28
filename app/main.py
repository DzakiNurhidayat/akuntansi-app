from decimal import Decimal

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, engine, Base
from app.models import Akun, Periode, Transaksi, JurnalEntry
from app.templates_env import templates
from app.routers import akun as akun_router
from app.routers import transaksi as transaksi_router
from app.routers import laporan as laporan_router

# Buat tabel saat app start (jika belum ada)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cleaning Service Accounting")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(akun_router.router)
app.include_router(transaksi_router.router)
app.include_router(laporan_router.router)

BULAN_NAMA = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

# Arah saldo natural per kelompok akun
_GROUP_DIR = {
    "aset": "debet", "beban": "debet",
    "kewajiban": "kredit", "modal": "kredit", "pendapatan": "kredit",
}
# Kode yang dikecualikan dari kalkulasi modal (akun sistem)
_EXCLUDE_KODE = {"313"}


def _hitung_stats(db: Session, periode_id: int) -> dict:
    stats = {g: Decimal("0") for g in _GROUP_DIR}
    for jenis, arah in _GROUP_DIR.items():
        row = (
            db.query(
                func.coalesce(func.sum(JurnalEntry.debet), 0).label("d"),
                func.coalesce(func.sum(JurnalEntry.kredit), 0).label("k"),
            )
            .join(Transaksi, JurnalEntry.transaksi_id == Transaksi.id)
            .join(Akun, JurnalEntry.kode_akun == Akun.kode_akun)
            .filter(
                Transaksi.periode_id == periode_id,
                Transaksi.jenis == "umum",
                Akun.jenis_akun == jenis,
                ~Akun.kode_akun.in_(_EXCLUDE_KODE),
            )
            .first()
        )
        d, k = Decimal(str(row.d)), Decimal(str(row.k))
        stats[jenis] = (d - k) if arah == "debet" else (k - d)
    return stats


@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    periodes = (
        db.query(Periode)
        .order_by(Periode.tahun.desc(), Periode.bulan.desc())
        .all()
    )

    # Periode yang dipilih: dari query param atau default ke yang terbaru
    try:
        selected_id = int(request.query_params.get("periode_id", 0))
    except ValueError:
        selected_id = 0

    aktif = next((p for p in periodes if p.id == selected_id), None) or (periodes[0] if periodes else None)

    stats = _hitung_stats(db, aktif.id) if aktif else {g: Decimal("0") for g in _GROUP_DIR}
    laba_rugi = stats["pendapatan"] - stats["beban"]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "periodes": periodes,
        "aktif": aktif,
        "bulan_nama": BULAN_NAMA,
        "stats": {k: float(v) for k, v in stats.items()},
        "laba_rugi": float(laba_rugi),
    })


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Aplikasi berjalan!"}
