"""Manajemen User & Assignment Akun — admin only.

Akses sudah diproteksi oleh AuthMiddleware (path /admin/* hanya untuk admin).
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Akun, User, UserAkun
from app.services.auth import hash_password
from app.services.permissions import SYSTEM_AKUN, user_assigned_kode
from app.templates_env import templates

router = APIRouter(prefix="/admin", tags=["admin"])

JENIS_CHOICES = ["aset", "kewajiban", "modal", "pendapatan", "beban"]
JENIS_LABEL = {
    "aset": "Aset",
    "kewajiban": "Kewajiban",
    "modal": "Modal",
    "pendapatan": "Pendapatan",
    "beban": "Beban",
}


# ─── /admin → redirect ke /admin/users ───────────────────────────────────────
@router.get("")
def admin_root():
    return RedirectResponse("/admin/users", status_code=303)


# ─── List User ────────────────────────────────────────────────────────────────
@router.get("/users")
def list_users(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()

    # Hitung jumlah akun yang di-assign per user (untuk display di list)
    assigned_count: dict[int, int] = {}
    for u in users:
        assigned_count[u.id] = (
            db.query(UserAkun).filter(UserAkun.user_id == u.id).count()
        )

    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "users": users,
        "assigned_count": assigned_count,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "success"),
    })


# ─── Toggle is_active ────────────────────────────────────────────────────────
@router.post("/users/{user_id}/toggle-active")
def toggle_active(user_id: int, request: Request, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return RedirectResponse("/admin/users?msg=User+tidak+ditemukan&type=error", 303)

    # Cegah self-deactivate
    if u.id == request.session.get("user_id"):
        return RedirectResponse(
            "/admin/users?msg=Tidak+bisa+nonaktifkan+akun+sendiri&type=error", 303,
        )

    u.is_active = not u.is_active
    db.commit()
    label = "diaktifkan" if u.is_active else "dinonaktifkan"
    return RedirectResponse(f"/admin/users?msg={u.username}+{label}&type=success", 303)


# ─── Buat user baru ──────────────────────────────────────────────────────────
@router.post("/users/tambah")
def tambah_user(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    nama: str = Form(...),
    password: str = Form(...),
    is_admin: bool = Form(False),
):
    username = username.strip().lower()
    nama = nama.strip()
    if not username or not nama or not password:
        return RedirectResponse("/admin/users?msg=Semua+field+wajib+diisi&type=error", 303)

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return RedirectResponse(
            f"/admin/users?msg=Username+{username}+sudah+digunakan&type=error", 303,
        )

    db.add(User(
        username=username,
        nama=nama,
        password_hash=hash_password(password),
        is_active=True,
        is_admin=is_admin,
    ))
    db.commit()
    return RedirectResponse(
        f"/admin/users?msg=User+{username}+berhasil+dibuat&type=success", 303,
    )


# ─── Halaman assignment akun ke user ─────────────────────────────────────────
@router.get("/users/{user_id}/akun")
def manage_akun(user_id: int, request: Request, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return RedirectResponse("/admin/users?msg=User+tidak+ditemukan&type=error", 303)

    # Daftar akun (exclude sistem 313)
    akun_list = (
        db.query(Akun)
        .filter(~Akun.kode_akun.in_(SYSTEM_AKUN))
        .order_by(Akun.kode_akun)
        .all()
    )
    assigned = user_assigned_kode(db, u)

    return templates.TemplateResponse("admin/user_akun.html", {
        "request": request,
        "user_target": u,
        "akun_list": akun_list,
        "assigned": assigned,
        "jenis_choices": JENIS_CHOICES,
        "jenis_label": JENIS_LABEL,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "success"),
    })


# ─── Simpan assignment akun ──────────────────────────────────────────────────
@router.post("/users/{user_id}/akun")
async def save_akun_assignment(
    user_id: int, request: Request, db: Session = Depends(get_db)
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return RedirectResponse("/admin/users?msg=User+tidak+ditemukan&type=error", 303)

    form = await request.form()
    selected = set(form.getlist("akun"))  # list kode_akun yang di-check

    # Filter: hanya akun yang valid & bukan sistem
    valid_kode = {
        a.kode_akun for a in db.query(Akun).filter(~Akun.kode_akun.in_(SYSTEM_AKUN)).all()
    }
    selected &= valid_kode

    # Replace assignment: hapus semua, lalu insert baru
    db.query(UserAkun).filter(UserAkun.user_id == u.id).delete()
    db.flush()
    for kode in selected:
        db.add(UserAkun(user_id=u.id, kode_akun=kode))
    db.commit()

    return RedirectResponse(
        f"/admin/users/{user_id}/akun?msg={len(selected)}+akun+di-assign+ke+{u.username}&type=success",
        status_code=303,
    )


# ─── Toggle akun universal ───────────────────────────────────────────────────
@router.post("/akun/{kode_akun}/toggle-universal")
def toggle_universal(kode_akun: str, db: Session = Depends(get_db)):
    a = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
    if not a:
        return RedirectResponse("/akun?msg=Akun+tidak+ditemukan&type=error", 303)

    a.is_universal = not a.is_universal
    db.commit()
    label = "universal" if a.is_universal else "non-universal"
    return RedirectResponse(
        f"/akun?msg=Akun+{kode_akun}+sekarang+{label}&type=success", 303,
    )
