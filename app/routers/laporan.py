import calendar
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Akun, Periode, Transaksi, JurnalEntry
from app.templates_env import templates

router = APIRouter(prefix="/laporan", tags=["laporan"])

JENIS_LAPORAN = ["umum"]
PAGE_SIZE = 10  # transaksi per halaman Jurnal Umum


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _anchor(db: Session):
    latest = (
        db.query(Periode)
        .order_by(Periode.tahun.desc(), Periode.bulan.desc())
        .first()
    )
    return (latest.tahun, latest.bulan) if latest else (2008, 4)


def _month_add(year: int, month: int, delta: int):
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def _presets(anchor_year: int, anchor_month: int):
    last_day = calendar.monthrange(anchor_year, anchor_month)[1]
    end = date(anchor_year, anchor_month, last_day)

    def start(delta_months: int):
        y, m = _month_add(anchor_year, anchor_month, delta_months)
        return date(y, m, 1)

    return {
        "1bulan": (start(0), end),
        "3bulan": (start(-2), end),
        "6bulan": (start(-5), end),
        "1tahun": (date(anchor_year, 1, 1), date(anchor_year, 12, 31)),
    }


def _parse_filter(request: Request, db: Session):
    ay, am = _anchor(db)
    last_day = calendar.monthrange(ay, am)[1]
    default_dari = date(ay, am, 1)
    default_sampai = date(ay, am, last_day)

    def safe_date(param, fallback):
        raw = request.query_params.get(param)
        try:
            return date.fromisoformat(raw) if raw else fallback
        except ValueError:
            return fallback

    tgl_dari = safe_date("tgl_dari", default_dari)
    tgl_sampai = safe_date("tgl_sampai", default_sampai)
    presets = _presets(ay, am)
    return tgl_dari, tgl_sampai, presets


def _filter_ctx(tgl_dari, tgl_sampai, presets, base_url: str):
    def url(d_from, d_to):
        return f"{base_url}?tgl_dari={d_from}&tgl_sampai={d_to}"

    return {
        "tgl_dari": tgl_dari,
        "tgl_sampai": tgl_sampai,
        "preset_links": {
            "1 Bulan": url(*presets["1bulan"]),
            "3 Bulan": url(*presets["3bulan"]),
            "6 Bulan": url(*presets["6bulan"]),
            "1 Tahun": url(*presets["1tahun"]),
        },
        "preset_ranges": presets,
    }


def _build_ju_page_map(db: Session) -> dict:
    """
    Peta global: jurnal_entry.id → nomor halaman JU (JU1, JU2, dst.)
    Dihitung per TRANSAKSI (15 transaksi/halaman).
    Semua entry dalam satu transaksi mendapat nomor halaman yang sama.
    """
    # 1. Halaman per transaksi
    trx_ids = (
        db.query(Transaksi.id)
        .filter(Transaksi.jenis.in_(JENIS_LAPORAN))
        .order_by(Transaksi.tanggal, Transaksi.id)
        .all()
    )
    trx_page = {tid: (i // PAGE_SIZE) + 1 for i, (tid,) in enumerate(trx_ids)}

    # 2. Propagasi ke setiap entry
    entries = (
        db.query(JurnalEntry.id, JurnalEntry.transaksi_id)
        .join(Transaksi)
        .filter(Transaksi.jenis.in_(JENIS_LAPORAN))
        .all()
    )
    return {eid: trx_page.get(tid, 1) for eid, tid in entries}


# ─── Jurnal Umum ─────────────────────────────────────────────────────────────

@router.get("/jurnal-umum")
def jurnal_umum(request: Request, db: Session = Depends(get_db)):
    tgl_dari, tgl_sampai, presets = _parse_filter(request, db)
    page = max(1, int(request.query_params.get("page", 1) or 1))

    # Semua transaksi dalam filter (untuk total keseluruhan)
    all_transaksi = (
        db.query(Transaksi)
        .filter(
            Transaksi.tanggal >= tgl_dari,
            Transaksi.tanggal <= tgl_sampai,
            Transaksi.jenis.in_(JENIS_LAPORAN),
        )
        .order_by(Transaksi.tanggal, Transaksi.id)
        .all()
    )

    total_transaksi = len(all_transaksi)
    total_pages = max(1, (total_transaksi + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)

    # Transaksi untuk halaman ini (15 transaksi utuh, tidak terpotong)
    start = (page - 1) * PAGE_SIZE
    page_transaksi = all_transaksi[start: start + PAGE_SIZE]

    # Flatten entry transaksi halaman ini → baris tampilan
    rows = []
    for t in page_transaksi:
        entries = list(t.entries)
        for i, entry in enumerate(entries):
            rows.append({
                "tanggal": t.tanggal,
                "show_day": i == 0,
                "is_last": i == len(entries) - 1,
                "entry": entry,
            })

    # Tandai perubahan bulan (reset tiap halaman baru)
    last_my = None
    for row in rows:
        my = row["tanggal"].strftime("%m, %Y")
        row["show_my"] = my != last_my
        last_my = my

    grand_total = sum(float(e.debet) for t in all_transaksi for e in t.entries)
    page_debet  = sum(float(r["entry"].debet)  for r in rows)
    page_kredit = sum(float(r["entry"].kredit) for r in rows)

    return templates.TemplateResponse("laporan/jurnal_umum.html", {
        "request": request,
        "rows": rows,
        "page": page,
        "total_pages": total_pages,
        "total_transaksi": total_transaksi,
        "page_transaksi_count": len(page_transaksi),
        "grand_total": grand_total,
        "page_debet": page_debet,
        "page_kredit": page_kredit,
        **_filter_ctx(tgl_dari, tgl_sampai, presets, "/laporan/jurnal-umum"),
    })


# ─── Buku Besar ──────────────────────────────────────────────────────────────

@router.get("/buku-besar")
def buku_besar(request: Request, db: Session = Depends(get_db)):
    tgl_dari, tgl_sampai, presets = _parse_filter(request, db)

    # Peta entry → halaman JU (global, tanpa filter tanggal)
    ju_page_map = _build_ju_page_map(db)

    akun_list = db.query(Akun).order_by(Akun.kode_akun).all()

    ledger = []
    for akun in akun_list:
        entries = (
            db.query(JurnalEntry)
            .join(Transaksi)
            .filter(
                JurnalEntry.kode_akun == akun.kode_akun,
                Transaksi.tanggal >= tgl_dari,
                Transaksi.tanggal <= tgl_sampai,
                Transaksi.jenis.in_(JENIS_LAPORAN),
            )
            .order_by(Transaksi.tanggal, Transaksi.id, JurnalEntry.urutan)
            .all()
        )
        if not entries:
            continue

        saldo = Decimal("0")
        rows = []
        for e in entries:
            d = Decimal(str(e.debet))
            k = Decimal(str(e.kredit))
            saldo += (d - k) if akun.saldo_normal == "debet" else (k - d)
            ref_page = ju_page_map.get(e.id, 1)
            rows.append({
                "tanggal": e.transaksi.tanggal,
                "keterangan": e.transaksi.keterangan or "",
                "ref": f"JU{ref_page}",
                "ref_page": ref_page,
                "debet": float(d),
                "kredit": float(k),
                "saldo": float(saldo),
            })

        ledger.append({
            "akun": akun,
            "saldo_akhir": float(saldo),
            "rows": rows,
        })

    return templates.TemplateResponse("laporan/buku_besar.html", {
        "request": request,
        "ledger": ledger,
        **_filter_ctx(tgl_dari, tgl_sampai, presets, "/laporan/buku-besar"),
    })


# ─── Neraca Saldo ────────────────────────────────────────────────────────────

@router.get("/neraca-saldo")
def neraca_saldo(request: Request, db: Session = Depends(get_db)):
    tgl_dari, tgl_sampai, presets = _parse_filter(request, db)

    akun_list = db.query(Akun).order_by(Akun.kode_akun).all()

    rows = []
    sum_debet = Decimal("0")
    sum_kredit = Decimal("0")

    for akun in akun_list:
        result = (
            db.query(
                func.coalesce(func.sum(JurnalEntry.debet), 0).label("total_d"),
                func.coalesce(func.sum(JurnalEntry.kredit), 0).label("total_k"),
            )
            .join(Transaksi)
            .filter(
                JurnalEntry.kode_akun == akun.kode_akun,
                Transaksi.tanggal >= tgl_dari,
                Transaksi.tanggal <= tgl_sampai,
                Transaksi.jenis.in_(JENIS_LAPORAN),
            )
            .first()
        )

        total_d = Decimal(str(result.total_d))
        total_k = Decimal(str(result.total_k))

        if total_d == 0 and total_k == 0:
            continue

        if akun.saldo_normal == "debet":
            net = total_d - total_k
            col_debet = float(net) if net >= 0 else 0
            col_kredit = float(-net) if net < 0 else 0
        else:
            net = total_k - total_d
            col_kredit = float(net) if net >= 0 else 0
            col_debet = float(-net) if net < 0 else 0

        rows.append({"akun": akun, "debet": col_debet, "kredit": col_kredit})
        sum_debet += Decimal(str(col_debet))
        sum_kredit += Decimal(str(col_kredit))

    return templates.TemplateResponse("laporan/neraca_saldo.html", {
        "request": request,
        "rows": rows,
        "sum_debet": float(sum_debet),
        "sum_kredit": float(sum_kredit),
        "seimbang": sum_debet == sum_kredit,
        **_filter_ctx(tgl_dari, tgl_sampai, presets, "/laporan/neraca-saldo"),
    })


# ─── Download (placeholder) ──────────────────────────────────────────────────

@router.get("/jurnal-umum/download")
@router.get("/buku-besar/download")
@router.get("/neraca-saldo/download")
def download_placeholder():
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Fitur download PDF belum tersedia."}, status_code=501)
