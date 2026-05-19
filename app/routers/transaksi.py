from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from decimal import Decimal, InvalidOperation
from datetime import date

from app.database import get_db
from app.models import Akun, Periode, Transaksi, JurnalEntry
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

# Tanggal default: 1 April 2008 (bulan periode soal)
TANGGAL_DEFAULT = "2008-04-01"


def _akun_json(db: Session):
    akun_list = (
        db.query(Akun)
        .filter(Akun.is_active == True)
        .order_by(Akun.kode_akun)
        .all()
    )
    return [
        {"kode_akun": a.kode_akun, "nama_akun": a.nama_akun, "jenis_akun": a.jenis_akun}
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


def _validate_entries(entries, db: Session):
    errors = []
    if len(entries) < 2:
        errors.append("Minimal 2 baris entri jurnal.")
        return errors

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


def _form_ctx(db: Session, transaksi=None, errors=None, entries_data=None, form_data=None):
    return {
        "akun_json": _akun_json(db),
        "jenis_input": JENIS_INPUT,
        "jenis_label": JENIS_LABEL,
        "transaksi": transaksi,
        "errors": errors or [],
        "entries_data": entries_data,
        "form_data": form_data or {},
        "tanggal_default": TANGGAL_DEFAULT,
    }


# ─── List ────────────────────────────────────────────────────────────────────

@router.get("")
def list_transaksi(request: Request, db: Session = Depends(get_db)):
    jenis_filter = request.query_params.get("jenis", "")
    q = db.query(Transaksi)
    if jenis_filter in JENIS_SEMUA:
        q = q.filter(Transaksi.jenis == jenis_filter)
    else:
        # Default: hanya tampilkan umum dan penyesuaian (input manual)
        q = q.filter(Transaksi.jenis.in_(JENIS_INPUT))
    transaksi_list = q.order_by(Transaksi.tanggal, Transaksi.id).all()

    for t in transaksi_list:
        t._total = sum(float(e.debet) for e in t.entries)

    return templates.TemplateResponse("transaksi/list.html", {
        "request": request,
        "transaksi_list": transaksi_list,
        "jenis_input": JENIS_INPUT,
        "jenis_label": JENIS_LABEL,
        "jenis_filter": jenis_filter,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "success"),
    })


# ─── Tambah ──────────────────────────────────────────────────────────────────

@router.get("/tambah")
def form_tambah(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("transaksi/form.html", {
        "request": request,
        **_form_ctx(db),
    })


@router.post("/tambah")
async def simpan_tambah(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    entries = _parse_entries(form)
    errors = _validate_entries(entries, db)

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
        periode = _resolve_periode(tanggal, db)
        if not periode:
            errors.append(
                f"Tidak ada periode untuk bulan {tanggal.month}/{tanggal.year}. "
                "Pastikan periode sudah dibuat."
            )

    if errors:
        return templates.TemplateResponse("transaksi/form.html", {
            "request": request,
            **_form_ctx(db, errors=errors, entries_data=entries_data, form_data=dict(form)),
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
        **_form_ctx(db, transaksi=transaksi, entries_data=entries_json),
    })


@router.post("/{id}/edit")
async def simpan_edit(id: int, request: Request, db: Session = Depends(get_db)):
    transaksi = db.query(Transaksi).filter(Transaksi.id == id).first()
    if not transaksi:
        return RedirectResponse("/transaksi?msg=Transaksi+tidak+ditemukan&type=error", status_code=303)

    form = await request.form()
    entries = _parse_entries(form)
    errors = _validate_entries(entries, db)

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

    if errors:
        return templates.TemplateResponse("transaksi/form.html", {
            "request": request,
            **_form_ctx(db, transaksi=transaksi, errors=errors,
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
