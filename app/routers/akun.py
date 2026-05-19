from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Akun, JurnalEntry
from app.templates_env import templates

router = APIRouter(prefix="/akun", tags=["akun"])

JENIS_CHOICES = ["aset", "kewajiban", "modal", "pendapatan", "beban"]
SALDO_DEFAULT = {
    "aset": "debet",
    "kewajiban": "kredit",
    "modal": "kredit",
    "pendapatan": "kredit",
    "beban": "debet",
}


KODE_TERSEMBUNYI = {"313"}  # Ikhtisar Laba Rugi — dipakai sistem, tidak ditampilkan


@router.get("")
def list_akun(request: Request, db: Session = Depends(get_db)):
    akun_list = (
        db.query(Akun)
        .filter(~Akun.kode_akun.in_(KODE_TERSEMBUNYI))
        .order_by(Akun.kode_akun)
        .all()
    )
    msg = request.query_params.get("msg")
    msg_type = request.query_params.get("type", "success")
    return templates.TemplateResponse("akun/list.html", {
        "request": request,
        "akun_list": akun_list,
        "jenis_choices": JENIS_CHOICES,
        "msg": msg,
        "msg_type": msg_type,
    })


@router.get("/tambah")
def form_tambah(request: Request):
    return templates.TemplateResponse("akun/form.html", {
        "request": request,
        "akun": None,
        "jenis_choices": JENIS_CHOICES,
        "saldo_default": SALDO_DEFAULT,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "error"),
    })


@router.post("/tambah")
def simpan_tambah(
    request: Request,
    db: Session = Depends(get_db),
    kode_akun: str = Form(...),
    nama_akun: str = Form(...),
    nama_akun_en: str = Form(""),
    jenis_akun: str = Form(...),
    saldo_normal: str = Form(...),
    is_kontra: bool = Form(False),
    is_active: bool = Form(False),
):
    kode_akun = kode_akun.strip()
    nama_akun = nama_akun.strip()

    if jenis_akun not in JENIS_CHOICES or saldo_normal not in ("debet", "kredit"):
        return RedirectResponse(
            f"/akun/tambah?msg=Data+tidak+valid&type=error", status_code=303
        )

    existing = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
    if existing:
        return RedirectResponse(
            f"/akun/tambah?msg=Kode+akun+{kode_akun}+sudah+digunakan&type=error",
            status_code=303,
        )

    akun = Akun(
        kode_akun=kode_akun,
        nama_akun=nama_akun,
        nama_akun_en=nama_akun_en.strip() or None,
        jenis_akun=jenis_akun,
        saldo_normal=saldo_normal,
        is_kontra=is_kontra,
        is_active=is_active,
    )
    db.add(akun)
    db.commit()
    return RedirectResponse(
        f"/akun?msg=Akun+{kode_akun}+-+{nama_akun}+berhasil+ditambahkan&type=success",
        status_code=303,
    )


@router.get("/{kode_akun}/edit")
def form_edit(kode_akun: str, request: Request, db: Session = Depends(get_db)):
    akun = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
    if not akun:
        return RedirectResponse("/akun?msg=Akun+tidak+ditemukan&type=error", status_code=303)
    return templates.TemplateResponse("akun/form.html", {
        "request": request,
        "akun": akun,
        "jenis_choices": JENIS_CHOICES,
        "saldo_default": SALDO_DEFAULT,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "error"),
    })


@router.post("/{kode_akun}/edit")
def simpan_edit(
    kode_akun: str,
    db: Session = Depends(get_db),
    nama_akun: str = Form(...),
    nama_akun_en: str = Form(""),
    jenis_akun: str = Form(...),
    saldo_normal: str = Form(...),
    is_kontra: bool = Form(False),
    is_active: bool = Form(False),
):
    akun = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
    if not akun:
        return RedirectResponse("/akun?msg=Akun+tidak+ditemukan&type=error", status_code=303)

    if jenis_akun not in JENIS_CHOICES or saldo_normal not in ("debet", "kredit"):
        return RedirectResponse(
            f"/akun/{kode_akun}/edit?msg=Data+tidak+valid&type=error", status_code=303
        )

    akun.nama_akun = nama_akun.strip()
    akun.nama_akun_en = nama_akun_en.strip() or None
    akun.jenis_akun = jenis_akun
    akun.saldo_normal = saldo_normal
    akun.is_kontra = is_kontra
    akun.is_active = is_active
    db.commit()
    return RedirectResponse(
        f"/akun?msg=Akun+{kode_akun}+berhasil+diperbarui&type=success", status_code=303
    )


@router.post("/{kode_akun}/hapus")
def hapus_akun(kode_akun: str, db: Session = Depends(get_db)):
    akun = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
    if not akun:
        return RedirectResponse("/akun?msg=Akun+tidak+ditemukan&type=error", status_code=303)

    dipakai = db.query(JurnalEntry).filter(JurnalEntry.kode_akun == kode_akun).first()
    if dipakai:
        return RedirectResponse(
            f"/akun?msg=Akun+{kode_akun}+tidak+bisa+dihapus+karena+sudah+dipakai+di+jurnal&type=error",
            status_code=303,
        )

    db.delete(akun)
    db.commit()
    return RedirectResponse(
        f"/akun?msg=Akun+{kode_akun}+berhasil+dihapus&type=success", status_code=303
    )
