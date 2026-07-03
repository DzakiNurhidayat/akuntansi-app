import calendar
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Akun, Periode, Transaksi, JurnalEntry, User
from app.templates_env import templates

router = APIRouter(prefix="/transaksi", tags=["transaksi"])

# Hanya umum dan penyesuaian yang bisa diinput manual
JENIS_INPUT = ["umum", "penyesuaian"]
JENIS_LABEL = {
    "umum": "Jurnal Umum",
    "penyesuaian": "Penyesuaian",
    "penutup": "Penutup",
    "pembalik": "Pembalik",
}
JENIS_SEMUA = list(JENIS_LABEL.keys())

# Tanggal default fallback (kalau belum ada periode sama sekali)
TANGGAL_DEFAULT = "2008-04-01"

BULAN_NAMA = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def _latest_periode(db: Session):
    """Periode dengan (tahun, bulan) terbesar — periode tempat input wajib jatuh."""
    return (
        db.query(Periode)
        .order_by(Periode.tahun.desc(), Periode.bulan.desc())
        .first()
    )


def _periode_range(p: "Periode") -> tuple[date, date]:
    """Return (first_day, last_day) periode."""
    last = calendar.monthrange(p.tahun, p.bulan)[1]
    return date(p.tahun, p.bulan, 1), date(p.tahun, p.bulan, last)


def _akun_json(db: Session, request: Request):
    """Return list akun yang BOLEH dipakai user yang sedang login.

      • Admin → semua akun aktif (kecuali system)
      • Non-admin → akun yang di-assign + universal (kecuali system)
    """
    from app.services.auth import get_current_user
    from app.services.permissions import allowed_akun_kode

    # Ambil current user (manual karena ini bukan dependency)
    uid = request.session.get("user_id") if hasattr(request, "session") else None
    user = db.query(User).filter(User.id == uid).first() if uid else None

    allowed = allowed_akun_kode(db, user) if user else set()

    from sqlalchemy.orm import joinedload
    akun_list = (
        db.query(Akun)
        .options(joinedload(Akun.parent))  # eager-load parent supaya tidak N+1
        .filter(
            Akun.is_active == True,
            Akun.is_kategori == False,                        # kategori tidak boleh dipakai di transaksi
            Akun.kode_akun.in_(allowed) if allowed else False,
        )
        .order_by(Akun.kode_akun)
        .all()
    )
    return [
        {
            "kode_akun": a.kode_akun,
            "nama_akun": a.nama_akun,
            "jenis_akun": a.jenis_akun,
            "is_universal": bool(a.is_universal),
            "parent_kode": a.parent_kode,
            "parent_nama": a.parent.nama_akun if a.parent else None,
        }
        for a in akun_list
    ]


def _parse_entries(form):
    kode_list = form.getlist("kode_akun")
    debet_list = form.getlist("debet")
    kredit_list = form.getlist("kredit")
    entries = []
    for i, (kode, d_raw, k_raw) in enumerate(zip(kode_list, debet_list, kredit_list)):
        try:
            d = Decimal(d_raw.replace(",", "") if d_raw else "0")
            k = Decimal(k_raw.replace(",", "") if k_raw else "0")
        except InvalidOperation:
            d, k = Decimal("0"), Decimal("0")
        if d == 0 and k == 0:
            continue
        entries.append({"kode_akun": kode, "debet": d, "kredit": k, "urutan": i})
    return entries


def _validate_entries(entries, db: Session, request: Request = None):
    """Validasi entri jurnal. Kalau request ada, sekaligus cek izin akses akun
    berdasarkan user yang login (non-admin hanya boleh pakai akun yang
    di-assign + universal)."""
    errors = []
    if len(entries) < 2:
        errors.append("Minimal 2 baris entri jurnal.")
        return errors

    # Cek izin akses akun (kalau request tersedia)
    allowed = None
    if request is not None:
        from app.services.permissions import allowed_akun_kode
        uid = request.session.get("user_id")
        user = db.query(User).filter(User.id == uid).first() if uid else None
        if user and not user.is_admin:
            allowed = allowed_akun_kode(db, user)

    total_d = Decimal("0")
    total_k = Decimal("0")
    for e in entries:
        if not e["kode_akun"]:
            errors.append("Semua baris harus memiliki akun.")
            break
        if e["debet"] > 0 and e["kredit"] > 0:
            errors.append(f"Akun {e['kode_akun']}: debet dan kredit tidak boleh keduanya diisi.")
        if e["debet"] < 0 or e["kredit"] < 0:
            errors.append(f"Akun {e['kode_akun']}: nilai tidak boleh negatif.")
        if not db.query(Akun).filter(Akun.kode_akun == e["kode_akun"]).first():
            errors.append(f"Akun {e['kode_akun']} tidak ditemukan.")
        elif allowed is not None and e["kode_akun"] not in allowed:
            errors.append(
                f"Anda tidak punya akses ke akun {e['kode_akun']}. "
                "Hubungi administrator untuk assignment."
            )
        total_d += e["debet"]
        total_k += e["kredit"]

    if not errors and total_d != total_k:
        selisih = abs(total_d - total_k)
        errors.append(
            f"Total debet harus sama dengan total kredit "
            f"(selisih Rp {int(selisih):,})".replace(",", ".")
        )
    return errors


def _resolve_periode(tanggal: date, db: Session):
    """Cari periode berdasarkan bulan/tahun dari tanggal."""
    return db.query(Periode).filter(
        Periode.tahun == tanggal.year,
        Periode.bulan == tanggal.month,
    ).first()


def _is_periode_locked(transaksi: Transaksi) -> bool:
    """True jika periode transaksi sudah ditutup (is_closed)."""
    return bool(transaksi.periode and transaksi.periode.is_closed)


def _form_ctx(db: Session, request: Request, transaksi=None, errors=None, entries_data=None, form_data=None):
    latest = _latest_periode(db)
    if latest:
        first_day, last_day = _periode_range(latest)
        tgl_default = first_day.isoformat()
        tgl_min = first_day.isoformat()
        tgl_max = last_day.isoformat()
        periode_locked = latest.is_closed
    else:
        tgl_default = TANGGAL_DEFAULT
        tgl_min = tgl_max = ""
        periode_locked = False

    # Untuk edit, batasi ke periode transaksi (boleh selama periode tidak locked)
    if transaksi:
        t_first, t_last = _periode_range(transaksi.periode) if transaksi.periode else (None, None)
        if t_first and t_last:
            tgl_min = t_first.isoformat()
            tgl_max = t_last.isoformat()

    return {
        "akun_json": _akun_json(db, request),
        "jenis_input": JENIS_INPUT,
        "jenis_label": JENIS_LABEL,
        "transaksi": transaksi,
        "errors": errors or [],
        "entries_data": entries_data,
        "form_data": form_data or {},
        "tanggal_default": tgl_default,
        "tanggal_min": tgl_min,
        "tanggal_max": tgl_max,
        "latest_periode": latest,
        "periode_locked": periode_locked,
    }


# ─── List ────────────────────────────────────────────────────────────────────

@router.get("")
def list_transaksi(request: Request, db: Session = Depends(get_db)):
    jenis_filter = request.query_params.get("jenis", "")

    # Filter periode — default ke periode aktif (paling baru)
    periodes = (
        db.query(Periode)
        .order_by(Periode.tahun.desc(), Periode.bulan.desc())
        .all()
    )
    try:
        periode_filter = int(request.query_params.get("periode_id", 0))
    except ValueError:
        periode_filter = 0

    # Validasi: periode_filter harus ada di list, kalau tidak default ke 0 (Semua)
    valid_ids = {p.id for p in periodes}
    if periode_filter and periode_filter not in valid_ids:
        periode_filter = 0

    q = db.query(Transaksi)
    if jenis_filter in JENIS_SEMUA:
        q = q.filter(Transaksi.jenis == jenis_filter)
    else:
        # Default: hanya tampilkan umum dan penyesuaian (input manual)
        q = q.filter(Transaksi.jenis.in_(JENIS_INPUT))
    if periode_filter:
        q = q.filter(Transaksi.periode_id == periode_filter)
    transaksi_list = q.order_by(Transaksi.tanggal, Transaksi.id).all()

    for t in transaksi_list:
        t._total = sum(float(e.debet) for e in t.entries)

    return templates.TemplateResponse("transaksi/list.html", {
        "request": request,
        "transaksi_list": transaksi_list,
        "jenis_input": JENIS_INPUT,
        "jenis_label": JENIS_LABEL,
        "jenis_filter": jenis_filter,
        "periodes": periodes,
        "periode_filter": periode_filter,
        "bulan_nama": BULAN_NAMA,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "success"),
    })


# ─── Tambah ──────────────────────────────────────────────────────────────────

@router.get("/tambah")
def form_tambah(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("transaksi/form.html", {
        "request": request,
        **_form_ctx(db, request),
    })


@router.post("/tambah")
async def simpan_tambah(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    entries = _parse_entries(form)
    errors = _validate_entries(entries, db, request)

    entries_data = [
        {"kode_akun": e["kode_akun"], "debet": float(e["debet"]), "kredit": float(e["kredit"])}
        for e in entries
    ]

    # Resolve tanggal dan periode
    tanggal_raw = form.get("tanggal", "")
    try:
        tanggal = date.fromisoformat(tanggal_raw)
    except (ValueError, TypeError):
        errors.insert(0, "Format tanggal tidak valid.")
        tanggal = None

    if tanggal and not errors:
        latest = _latest_periode(db)
        periode = _resolve_periode(tanggal, db)
        if not latest:
            errors.append("Belum ada periode. Jalankan seed_data.py terlebih dahulu.")
        elif not periode or periode.id != latest.id:
            first_day, last_day = _periode_range(latest)
            errors.append(
                f"Tanggal harus berada di periode aktif "
                f"({first_day.strftime('%d/%m/%Y')} – {last_day.strftime('%d/%m/%Y')}). "
                f"Transaksi tidak bisa diinput di periode sebelumnya yang sudah lewat."
            )

    if errors:
        return templates.TemplateResponse("transaksi/form.html", {
            "request": request,
            **_form_ctx(db, request, errors=errors, entries_data=entries_data, form_data=dict(form)),
        }, status_code=400)

    jenis = form.get("jenis", "umum")
    if jenis not in JENIS_INPUT:
        jenis = "umum"

    transaksi = Transaksi(
        periode_id=periode.id,
        tanggal=tanggal,
        keterangan=form.get("keterangan", "").strip(),
        jenis=jenis,
    )
    db.add(transaksi)
    db.flush()

    for e in entries:
        db.add(JurnalEntry(
            transaksi_id=transaksi.id,
            kode_akun=e["kode_akun"],
            debet=e["debet"],
            kredit=e["kredit"],
            urutan=e["urutan"],
        ))
    db.commit()

    return RedirectResponse(
        f"/transaksi?msg=Transaksi+{tanggal}+berhasil+disimpan&type=success",
        status_code=303,
    )


# ─── Edit ────────────────────────────────────────────────────────────────────

@router.get("/{id}/edit")
def form_edit(id: int, request: Request, db: Session = Depends(get_db)):
    transaksi = db.query(Transaksi).filter(Transaksi.id == id).first()
    if not transaksi:
        return RedirectResponse("/transaksi?msg=Transaksi+tidak+ditemukan&type=error", status_code=303)

    entries_json = [
        {"kode_akun": e.kode_akun, "debet": float(e.debet), "kredit": float(e.kredit)}
        for e in transaksi.entries
    ]
    return templates.TemplateResponse("transaksi/form.html", {
        "request": request,
        **_form_ctx(db, request, transaksi=transaksi, entries_data=entries_json),
    })


@router.post("/{id}/edit")
async def simpan_edit(id: int, request: Request, db: Session = Depends(get_db)):
    transaksi = db.query(Transaksi).filter(Transaksi.id == id).first()
    if not transaksi:
        return RedirectResponse("/transaksi?msg=Transaksi+tidak+ditemukan&type=error", status_code=303)

    form = await request.form()
    entries = _parse_entries(form)
    errors = _validate_entries(entries, db, request)

    entries_data = [
        {"kode_akun": e["kode_akun"], "debet": float(e["debet"]), "kredit": float(e["kredit"])}
        for e in entries
    ]

    tanggal_raw = form.get("tanggal", "")
    try:
        tanggal = date.fromisoformat(tanggal_raw)
    except (ValueError, TypeError):
        errors.insert(0, "Format tanggal tidak valid.")
        tanggal = None

    if tanggal and not errors:
        periode = _resolve_periode(tanggal, db)
        if not periode:
            errors.append(
                f"Tidak ada periode untuk bulan {tanggal.month}/{tanggal.year}."
            )
        elif periode.id != transaksi.periode_id:
            first, last = _periode_range(transaksi.periode)
            errors.append(
                f"Tanggal harus tetap di periode asli transaksi "
                f"({first.strftime('%d/%m/%Y')} – {last.strftime('%d/%m/%Y')})."
            )

    if errors:
        return templates.TemplateResponse("transaksi/form.html", {
            "request": request,
            **_form_ctx(db, request, transaksi=transaksi, errors=errors,
                        entries_data=entries_data, form_data=dict(form)),
        }, status_code=400)

    jenis = form.get("jenis", transaksi.jenis)
    if jenis not in JENIS_INPUT:
        jenis = transaksi.jenis

    transaksi.tanggal = tanggal
    transaksi.periode_id = periode.id
    transaksi.keterangan = form.get("keterangan", "").strip()
    transaksi.jenis = jenis

    db.query(JurnalEntry).filter(JurnalEntry.transaksi_id == id).delete()
    for e in entries:
        db.add(JurnalEntry(
            transaksi_id=id,
            kode_akun=e["kode_akun"],
            debet=e["debet"],
            kredit=e["kredit"],
            urutan=e["urutan"],
        ))
    db.commit()

    return RedirectResponse(
        f"/transaksi?msg=Transaksi+%23{id}+berhasil+diperbarui&type=success",
        status_code=303,
    )


# ─── Hapus ───────────────────────────────────────────────────────────────────

@router.post("/{id}/hapus")
def hapus_transaksi(id: int, db: Session = Depends(get_db)):
    transaksi = db.query(Transaksi).filter(Transaksi.id == id).first()
    if not transaksi:
        return RedirectResponse("/transaksi?msg=Transaksi+tidak+ditemukan&type=error", status_code=303)

    if transaksi.jenis in ("penutup", "pembalik"):
        return RedirectResponse(
            f"/transaksi?msg=Transaksi+jenis+{transaksi.jenis}+tidak+bisa+dihapus+manual&type=error",
            status_code=303,
        )

    db.delete(transaksi)
    db.commit()
    return RedirectResponse(
        f"/transaksi?msg=Transaksi+%23{id}+berhasil+dihapus&type=success",
        status_code=303,
    )
