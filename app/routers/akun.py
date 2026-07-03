from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Akun, JenisAkun, JurnalEntry
from app.templates_env import templates

router = APIRouter(prefix="/akun", tags=["akun"])

KODE_TERSEMBUNYI = {"313"}  # Ikhtisar L/R — dipakai sistem, sembunyikan dari UI


def _jenis_options(db: Session):
    """Return list dict {kode, nama, saldo_normal_default} untuk dropdown jenis."""
    return [
        {
            "kode": j.kode,
            "nama": j.nama,
            "saldo_normal_default": j.saldo_normal_default,
        }
        for j in db.query(JenisAkun)
        .filter(JenisAkun.is_active.is_(True))
        .order_by(JenisAkun.urutan)
        .all()
    ]


def _kategori_options(db: Session, jenis_akun: str = None):
    """Return list dict {kode_akun, nama_akun, jenis_akun} untuk dropdown parent.

    Hanya akun is_kategori=True. Optionally filter berdasarkan jenis_akun.
    """
    q = db.query(Akun).filter(Akun.is_kategori.is_(True), Akun.is_active.is_(True))
    if jenis_akun:
        q = q.filter(Akun.jenis_akun == jenis_akun)
    return [
        {"kode_akun": a.kode_akun, "nama_akun": a.nama_akun, "jenis_akun": a.jenis_akun}
        for a in q.order_by(Akun.kode_akun).all()
    ]


# ─── List Akun + Jenis Akun ──────────────────────────────────────────────────
@router.get("")
def list_akun(request: Request, db: Session = Depends(get_db)):
    akun_list = (
        db.query(Akun)
        .filter(~Akun.kode_akun.in_(KODE_TERSEMBUNYI))
        .order_by(Akun.kode_akun)
        .all()
    )
    jenis_list = (
        db.query(JenisAkun).order_by(JenisAkun.urutan).all()
    )

    # Build dict jenis_kode → nama (untuk display)
    jenis_nama = {j.kode: j.nama for j in jenis_list}

    return templates.TemplateResponse("akun/list.html", {
        "request": request,
        "akun_list": akun_list,
        "jenis_list": jenis_list,
        "jenis_nama": jenis_nama,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "success"),
    })


# ─── Form Akun ───────────────────────────────────────────────────────────────
@router.get("/tambah")
def form_tambah(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("akun/form.html", {
        "request": request,
        "akun": None,
        "jenis_options": _jenis_options(db),
        "kategori_options": _kategori_options(db),
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "error"),
    })


@router.post("/tambah")
def simpan_tambah(
    db: Session = Depends(get_db),
    kode_akun: str = Form(...),
    nama_akun: str = Form(...),
    nama_akun_en: str = Form(""),
    jenis_akun: str = Form(...),
    saldo_normal: str = Form(...),
    is_kontra: bool = Form(False),
    is_active: bool = Form(False),
    is_kategori: bool = Form(False),
    parent_kode: str = Form(""),
):
    kode_akun = kode_akun.strip()
    nama_akun = nama_akun.strip()
    parent_kode = parent_kode.strip() or None

    # Kategori tidak boleh punya parent kategori (struktur flat 1 level)
    if is_kategori:
        parent_kode = None

    # Validasi jenis_akun harus ada di tabel JenisAkun
    jenis_valid = db.query(JenisAkun).filter(JenisAkun.kode == jenis_akun).first()
    if not jenis_valid or saldo_normal not in ("debet", "kredit"):
        return RedirectResponse(
            "/akun/tambah?msg=Data+tidak+valid&type=error", status_code=303,
        )

    if db.query(Akun).filter(Akun.kode_akun == kode_akun).first():
        return RedirectResponse(
            f"/akun/tambah?msg=Kode+akun+{kode_akun}+sudah+digunakan&type=error",
            status_code=303,
        )

    # Validasi parent_kode (harus is_kategori=True dan jenis_akun match)
    if parent_kode:
        parent = db.query(Akun).filter(Akun.kode_akun == parent_kode).first()
        if not parent or not parent.is_kategori or parent.jenis_akun != jenis_akun:
            return RedirectResponse(
                f"/akun/tambah?msg=Parent+kategori+tidak+valid&type=error",
                status_code=303,
            )

    db.add(Akun(
        kode_akun=kode_akun,
        nama_akun=nama_akun,
        nama_akun_en=nama_akun_en.strip() or None,
        jenis_akun=jenis_akun,
        saldo_normal=saldo_normal,
        is_kontra=is_kontra,
        is_active=is_active,
        is_kategori=is_kategori,
        parent_kode=parent_kode,
    ))
    db.commit()
    label = "Kategori" if is_kategori else "Akun"
    return RedirectResponse(
        f"/akun?msg={label}+{kode_akun}+-+{nama_akun}+berhasil+ditambahkan&type=success",
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
        "jenis_options": _jenis_options(db),
        "kategori_options": _kategori_options(db),
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
    is_kategori: bool = Form(False),
    parent_kode: str = Form(""),
):
    akun = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
    if not akun:
        return RedirectResponse("/akun?msg=Akun+tidak+ditemukan&type=error", status_code=303)

    parent_kode = parent_kode.strip() or None

    # Kategori tidak boleh punya parent kategori
    if is_kategori:
        parent_kode = None

    jenis_valid = db.query(JenisAkun).filter(JenisAkun.kode == jenis_akun).first()
    if not jenis_valid or saldo_normal not in ("debet", "kredit"):
        return RedirectResponse(
            f"/akun/{kode_akun}/edit?msg=Data+tidak+valid&type=error", status_code=303,
        )

    if parent_kode:
        if parent_kode == kode_akun:
            return RedirectResponse(
                f"/akun/{kode_akun}/edit?msg=Akun+tidak+bisa+jadi+parent+sendiri&type=error",
                status_code=303,
            )
        parent = db.query(Akun).filter(Akun.kode_akun == parent_kode).first()
        if not parent or not parent.is_kategori or parent.jenis_akun != jenis_akun:
            return RedirectResponse(
                f"/akun/{kode_akun}/edit?msg=Parent+kategori+tidak+valid&type=error",
                status_code=303,
            )

    akun.nama_akun = nama_akun.strip()
    akun.nama_akun_en = nama_akun_en.strip() or None
    akun.jenis_akun = jenis_akun
    akun.saldo_normal = saldo_normal
    akun.is_kontra = is_kontra
    akun.is_active = is_active
    akun.is_kategori = is_kategori
    akun.parent_kode = parent_kode
    db.commit()
    return RedirectResponse(
        f"/akun?msg=Akun+{kode_akun}+berhasil+diperbarui&type=success", status_code=303,
    )


@router.post("/{kode_akun}/hapus")
def hapus_akun(kode_akun: str, db: Session = Depends(get_db)):
    akun = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
    if not akun:
        return RedirectResponse("/akun?msg=Akun+tidak+ditemukan&type=error", status_code=303)

    if db.query(JurnalEntry).filter(JurnalEntry.kode_akun == kode_akun).first():
        return RedirectResponse(
            f"/akun?msg=Akun+{kode_akun}+tidak+bisa+dihapus+karena+sudah+dipakai+di+jurnal&type=error",
            status_code=303,
        )
    # Cek apakah jadi parent akun lain
    if db.query(Akun).filter(Akun.parent_kode == kode_akun).first():
        return RedirectResponse(
            f"/akun?msg=Kategori+{kode_akun}+tidak+bisa+dihapus+karena+jadi+parent+akun+lain&type=error",
            status_code=303,
        )

    db.delete(akun)
    db.commit()
    return RedirectResponse(
        f"/akun?msg=Akun+{kode_akun}+berhasil+dihapus&type=success", status_code=303,
    )


# ─── Jenis Akun CRUD ─────────────────────────────────────────────────────────
@router.post("/jenis/tambah")
def tambah_jenis(
    db: Session = Depends(get_db),
    kode: str = Form(...),
    nama: str = Form(...),
    saldo_normal_default: str = Form(...),
    urutan: int = Form(0),
):
    kode = kode.strip().lower()
    nama = nama.strip()
    if not kode or not nama or saldo_normal_default not in ("debet", "kredit"):
        return RedirectResponse("/akun?msg=Data+jenis+tidak+valid&type=error", 303)
    if db.query(JenisAkun).filter(JenisAkun.kode == kode).first():
        return RedirectResponse(f"/akun?msg=Kode+jenis+{kode}+sudah+ada&type=error", 303)
    db.add(JenisAkun(
        kode=kode, nama=nama,
        saldo_normal_default=saldo_normal_default,
        urutan=urutan, is_active=True,
    ))
    db.commit()
    return RedirectResponse(
        f"/akun?msg=Jenis+{nama}+berhasil+ditambahkan&type=success", 303,
    )


@router.post("/jenis/{jenis_id}/edit")
def edit_jenis(
    jenis_id: int,
    db: Session = Depends(get_db),
    nama: str = Form(...),
    saldo_normal_default: str = Form(...),
    urutan: int = Form(0),
    is_active: bool = Form(False),
):
    j = db.query(JenisAkun).filter(JenisAkun.id == jenis_id).first()
    if not j:
        return RedirectResponse("/akun?msg=Jenis+tidak+ditemukan&type=error", 303)
    if saldo_normal_default not in ("debet", "kredit"):
        return RedirectResponse("/akun?msg=Saldo+normal+tidak+valid&type=error", 303)
    j.nama = nama.strip()
    j.saldo_normal_default = saldo_normal_default
    j.urutan = urutan
    j.is_active = is_active
    db.commit()
    return RedirectResponse(f"/akun?msg=Jenis+{j.nama}+diperbarui&type=success", 303)


@router.post("/jenis/{jenis_id}/hapus")
def hapus_jenis(jenis_id: int, db: Session = Depends(get_db)):
    j = db.query(JenisAkun).filter(JenisAkun.id == jenis_id).first()
    if not j:
        return RedirectResponse("/akun?msg=Jenis+tidak+ditemukan&type=error", 303)
    # Cek apakah ada akun yang pakai jenis ini
    if db.query(Akun).filter(Akun.jenis_akun == j.kode).first():
        return RedirectResponse(
            f"/akun?msg=Jenis+{j.kode}+tidak+bisa+dihapus+karena+masih+ada+akun+yang+pakai&type=error",
            303,
        )
    db.delete(j)
    db.commit()
    return RedirectResponse(f"/akun?msg=Jenis+{j.kode}+dihapus&type=success", 303)
