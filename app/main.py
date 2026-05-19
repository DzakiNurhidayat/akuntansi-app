from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from app.database import get_db, engine, Base
from app.models import Akun, Periode
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


@app.get("/")
def index():
    """Redirect ke Input Transaksi (Dashboard disembunyikan sementara)"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/transaksi", status_code=302)


@app.get("/api/health")
def health_check():
    """Endpoint untuk cek aplikasi berjalan"""
    return {"status": "ok", "message": "Aplikasi berjalan!"}