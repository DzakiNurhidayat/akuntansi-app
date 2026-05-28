import calendar
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Akun, Periode, Transaksi, JurnalEntry
from app.templates_env import templates

router = APIRouter(prefix="/laporan", tags=["laporan"])

JENIS_LAPORAN = ["umum"]
PAGE_SIZE = 10  # transaksi per halaman Jurnal Umum

_BULAN_ID = [
    '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
]

def _fmt_tgl(d) -> str:
    return f"{d.day} {_BULAN_ID[d.month]} {d.year}"

def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
    fmt  = request.query_params.get("format", "")
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

    # ── PDF export ────────────────────────────────────────────────────────────
    if fmt == "pdf":
        from app.services.pdf import render_pdf
        periode_obj = (
            db.query(Periode)
            .order_by(Periode.tahun.desc(), Periode.bulan.desc())
            .first()
        )
        pdf_rows = []
        for t in all_transaksi:
            entries = list(t.entries)
            for i, e in enumerate(entries):
                pdf_rows.append({
                    "tanggal":    t.tanggal.strftime("%d/%m") if i == 0 else "",
                    "keterangan": (t.keterangan or "") if i == 0 else "",
                    "kode":       e.akun.kode_akun,
                    "akun":       e.akun.nama_akun,
                    "is_kredit":  e.kredit > 0,
                    "debet":      float(e.debet),
                    "kredit":     float(e.kredit),
                })
        pdf_bytes = render_pdf("jurnal_umum.html", {
            "landscape":       False,
            "nama_perusahaan": periode_obj.nama_perusahaan if periode_obj else "",
            "judul":           "Jurnal Umum",
            "periode_str":     f"Periode {_fmt_tgl(tgl_dari)} s/d {_fmt_tgl(tgl_sampai)}",
            "rows":            pdf_rows,
            "grand_total":     grand_total,
        })
        return _pdf_response(pdf_bytes, f"jurnal_umum_{tgl_dari}_{tgl_sampai}.pdf")

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
    fmt = request.query_params.get("format", "")

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

    if fmt == "pdf":
        from app.services.pdf import render_pdf
        periode_obj = (
            db.query(Periode)
            .order_by(Periode.tahun.desc(), Periode.bulan.desc())
            .first()
        )
        pdf_bytes = render_pdf("buku_besar.html", {
            "landscape":       False,
            "nama_perusahaan": periode_obj.nama_perusahaan if periode_obj else "",
            "judul":           "Buku Besar",
            "periode_str":     f"Periode {_fmt_tgl(tgl_dari)} s/d {_fmt_tgl(tgl_sampai)}",
            "ledger":          ledger,
        })
        return _pdf_response(pdf_bytes, f"buku_besar_{tgl_dari}_{tgl_sampai}.pdf")

    return templates.TemplateResponse("laporan/buku_besar.html", {
        "request": request,
        "ledger": ledger,
        **_filter_ctx(tgl_dari, tgl_sampai, presets, "/laporan/buku-besar"),
    })


# ─── Neraca Saldo ────────────────────────────────────────────────────────────

@router.get("/neraca-saldo")
def neraca_saldo(request: Request, db: Session = Depends(get_db)):
    tgl_dari, tgl_sampai, presets = _parse_filter(request, db)
    fmt = request.query_params.get("format", "")

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

    if fmt == "pdf":
        from app.services.pdf import render_pdf
        periode_obj = (
            db.query(Periode)
            .order_by(Periode.tahun.desc(), Periode.bulan.desc())
            .first()
        )
        pdf_bytes = render_pdf("neraca_saldo.html", {
            "landscape":       False,
            "nama_perusahaan": periode_obj.nama_perusahaan if periode_obj else "",
            "judul":           "Neraca Saldo",
            "periode_str":     f"Per {_fmt_tgl(tgl_sampai)}",
            "rows":            rows,
            "sum_debet":       float(sum_debet),
            "sum_kredit":      float(sum_kredit),
            "seimbang":        sum_debet == sum_kredit,
        })
        return _pdf_response(pdf_bytes, f"neraca_saldo_{tgl_sampai}.pdf")

    return templates.TemplateResponse("laporan/neraca_saldo.html", {
        "request": request,
        "rows": rows,
        "sum_debet": float(sum_debet),
        "sum_kredit": float(sum_kredit),
        "seimbang": sum_debet == sum_kredit,
        **_filter_ctx(tgl_dari, tgl_sampai, presets, "/laporan/neraca-saldo"),
    })


# ─── Worksheet (Kertas Kerja / Neraca Lajur) ─────────────────────────────────

@router.get("/worksheet")
def worksheet(request: Request, db: Session = Depends(get_db)):
    tgl_dari, tgl_sampai, presets = _parse_filter(request, db)
    fmt = request.query_params.get("format", "")

    akun_list = db.query(Akun).order_by(Akun.kode_akun).all()

    def raw_sums(kode, jenis_list):
        """Kembalikan (total_debet, total_kredit) mentah untuk akun & jenis tertentu."""
        r = (
            db.query(
                func.coalesce(func.sum(JurnalEntry.debet), 0).label("d"),
                func.coalesce(func.sum(JurnalEntry.kredit), 0).label("k"),
            )
            .join(Transaksi)
            .filter(
                JurnalEntry.kode_akun == kode,
                Transaksi.tanggal >= tgl_dari,
                Transaksi.tanggal <= tgl_sampai,
                Transaksi.jenis.in_(jenis_list),
            )
            .first()
        )
        return Decimal(str(r.d)), Decimal(str(r.k))

    def net_col(d_raw, k_raw, saldo_normal):
        """Kembalikan (col_d, col_k) saldo bersih sesuai saldo normal akun."""
        net = (d_raw - k_raw) if saldo_normal == "debet" else (k_raw - d_raw)
        if net > 0:
            return (float(net), 0.0) if saldo_normal == "debet" else (0.0, float(net))
        elif net < 0:
            return (0.0, float(-net)) if saldo_normal == "debet" else (float(-net), 0.0)
        return 0.0, 0.0

    rows = []
    for akun in akun_list:
        ns_d_raw,  ns_k_raw  = raw_sums(akun.kode_akun, ["umum"])
        ajp_d_raw, ajp_k_raw = raw_sums(akun.kode_akun, ["penyesuaian"])

        # Kolom NS — saldo bersih dari jurnal umum
        ns_d, ns_k = net_col(ns_d_raw, ns_k_raw, akun.saldo_normal)

        # Kolom AJP — jumlah mentah debet & kredit dari AJP
        ajp_d, ajp_k = float(ajp_d_raw), float(ajp_k_raw)

        # Kolom NSD — saldo bersih gabungan (NS + AJP)
        nsd_d, nsd_k = net_col(
            ns_d_raw + ajp_d_raw,
            ns_k_raw + ajp_k_raw,
            akun.saldo_normal,
        )

        # Laba Rugi vs Neraca — ambil dari NSD berdasarkan jenis akun
        if akun.jenis_akun in ("pendapatan", "beban"):
            lr_d, lr_k = nsd_d, nsd_k
            n_d,  n_k  = 0.0,  0.0
        else:
            lr_d, lr_k = 0.0,  0.0
            n_d,  n_k  = nsd_d, nsd_k

        # Lewati akun yang kosong di seluruh kolom
        if not any([ns_d, ns_k, ajp_d, ajp_k]):
            continue

        rows.append({
            "kode_akun": akun.kode_akun,
            "nama_akun": akun.nama_akun,
            "ns_d": ns_d, "ns_k": ns_k,
            "ajp_d": ajp_d, "ajp_k": ajp_k,
            "nsd_d": nsd_d, "nsd_k": nsd_k,
            "lr_d": lr_d, "lr_k": lr_k,
            "n_d": n_d, "n_k": n_k,
        })

    # ── Total per kolom ───────────────────────────────────────────────────────
    def tot(key):
        return sum(r[key] for r in rows)

    totals = {k: tot(k) for k in
              ["ns_d","ns_k","ajp_d","ajp_k","nsd_d","nsd_k","lr_d","lr_k","n_d","n_k"]}

    # ── Selisih Laba / Rugi ───────────────────────────────────────────────────
    lr_diff = totals["lr_k"] - totals["lr_d"]  # positif = laba, negatif = rugi

    if lr_diff > 0:       # Laba → masuk L/R Debet & Neraca Kredit
        selisih = {"label": "Laba", "lr_d": float(lr_diff),  "lr_k": 0.0,
                                    "n_d": 0.0,               "n_k": float(lr_diff)}
    elif lr_diff < 0:     # Rugi → masuk L/R Kredit & Neraca Debet
        rugi = float(-lr_diff)
        selisih = {"label": "Rugi", "lr_d": 0.0,   "lr_k": rugi,
                                    "n_d": rugi,    "n_k": 0.0}
    else:
        selisih = {"label": "", "lr_d": 0.0, "lr_k": 0.0, "n_d": 0.0, "n_k": 0.0}

    # ── Grand total (setelah selisih, harus balance) ──────────────────────────
    grand = {
        "lr_d": totals["lr_d"] + selisih["lr_d"],
        "lr_k": totals["lr_k"] + selisih["lr_k"],
        "n_d":  totals["n_d"]  + selisih["n_d"],
        "n_k":  totals["n_k"]  + selisih["n_k"],
    }

    if fmt == "pdf":
        from app.services.pdf import render_pdf
        periode_obj = (
            db.query(Periode)
            .order_by(Periode.tahun.desc(), Periode.bulan.desc())
            .first()
        )
        pdf_bytes = render_pdf("worksheet.html", {
            "landscape":       True,
            "nama_perusahaan": periode_obj.nama_perusahaan if periode_obj else "",
            "judul":           "Kertas Kerja (Neraca Lajur)",
            "periode_str":     f"Periode {_fmt_tgl(tgl_dari)} s/d {_fmt_tgl(tgl_sampai)}",
            "rows":            rows,
            "totals":          totals,
            "selisih":         selisih,
            "grand":           grand,
        })
        return _pdf_response(pdf_bytes, f"worksheet_{tgl_dari}_{tgl_sampai}.pdf")

    return templates.TemplateResponse("laporan/worksheet.html", {
        "request": request,
        "rows": rows,
        "totals": totals,
        "selisih": selisih,
        "grand": grand,
        **_filter_ctx(tgl_dari, tgl_sampai, presets, "/laporan/worksheet"),
    })


# ─── Laporan Keuangan ────────────────────────────────────────────────────────

@router.get("/keuangan")
def keuangan(request: Request, db: Session = Depends(get_db)):
    tgl_dari, tgl_sampai, presets = _parse_filter(request, db)
    tab = request.query_params.get("tab", "laba-rugi")

    periode = (
        db.query(Periode)
        .order_by(Periode.tahun.desc(), Periode.bulan.desc())
        .first()
    )

    akun_list = db.query(Akun).order_by(Akun.kode_akun).all()
    JENIS_ALL = ["umum", "penyesuaian"]

    def nsd_bal(kode, saldo_normal):
        """Saldo NSD (umum+penyesuaian), selalu >= 0 dari sisi saldo normal."""
        r = (
            db.query(
                func.coalesce(func.sum(JurnalEntry.debet), 0).label("d"),
                func.coalesce(func.sum(JurnalEntry.kredit), 0).label("k"),
            )
            .join(Transaksi)
            .filter(
                JurnalEntry.kode_akun == kode,
                Transaksi.tanggal >= tgl_dari,
                Transaksi.tanggal <= tgl_sampai,
                Transaksi.jenis.in_(JENIS_ALL),
            )
            .first()
        )
        d, k = Decimal(str(r.d)), Decimal(str(r.k))
        net = (d - k) if saldo_normal == "debet" else (k - d)
        return float(net) if net > 0 else 0.0

    balances: dict[str, tuple] = {}
    for a in akun_list:
        balances[a.kode_akun] = (a, nsd_bal(a.kode_akun, a.saldo_normal))

    # ── Laba Rugi ─────────────────────────────────────────────────────────────
    pendapatan_items = [
        (a, b) for _, (a, b) in balances.items()
        if a.jenis_akun == "pendapatan" and b > 0
    ]
    beban_items = [
        (a, b) for _, (a, b) in balances.items()
        if a.jenis_akun == "beban" and b > 0
    ]
    total_pendapatan = sum(b for _, b in pendapatan_items)
    total_beban      = sum(b for _, b in beban_items)
    net_lr = total_pendapatan - total_beban  # positif = laba, negatif = rugi

    laba_rugi = {
        "pendapatan_items": pendapatan_items,
        "beban_items":      beban_items,
        "total_pendapatan": total_pendapatan,
        "total_beban":      total_beban,
        "net":     abs(net_lr),
        "is_laba": net_lr >= 0,
    }

    # ── Ekuitas Pemilik ───────────────────────────────────────────────────────
    modal_awal = 0.0  # TODO: baca dari saldo_awal saat multi-bulan

    # Investasi baru: net kredit ke akun 311 dari jurnal umum periode ini
    r_311 = (
        db.query(
            func.coalesce(func.sum(JurnalEntry.debet),  0).label("d"),
            func.coalesce(func.sum(JurnalEntry.kredit), 0).label("k"),
        )
        .join(Transaksi)
        .filter(
            JurnalEntry.kode_akun == "311",
            Transaksi.tanggal >= tgl_dari,
            Transaksi.tanggal <= tgl_sampai,
            Transaksi.jenis == "umum",
        )
        .first()
    )
    modal_investasi = max(
        0.0,
        float(Decimal(str(r_311.k)) - Decimal(str(r_311.d)))
    )

    prive_bal  = balances.get("312", (None, 0.0))[1]
    akun_311   = balances.get("311", (None, 0.0))[0]
    akun_312   = balances.get("312", (None, 0.0))[0]
    nama_modal = akun_311.nama_akun if akun_311 else "Modal Pemilik"
    nama_prive = akun_312.nama_akun if akun_312 else "Prive"

    add_items:  list[tuple[str, float]] = []
    less_items: list[tuple[str, float]] = []

    if modal_investasi > 0:
        add_items.append(("Investasi Modal", modal_investasi))
    if net_lr > 0:
        add_items.append(("Net Income", net_lr))
    elif net_lr < 0:
        less_items.append(("Net Loss", abs(net_lr)))
    if prive_bal > 0:
        less_items.append((nama_prive, prive_bal))

    total_add   = sum(b for _, b in add_items)
    total_less  = sum(b for _, b in less_items)
    perubahan   = total_add - total_less
    modal_akhir = modal_awal + perubahan

    ekuitas = {
        "modal_awal":    modal_awal,
        "tgl_awal":      tgl_dari,
        "tgl_akhir":     tgl_sampai,
        "add_items":     add_items,
        "less_items":    less_items,
        "perubahan":     perubahan,
        "modal_akhir":   modal_akhir,
        "nama_modal":    nama_modal,
    }

    # ── Neraca ────────────────────────────────────────────────────────────────
    aset_lancar = [
        (a, b) for kode, (a, b) in balances.items()
        if a.jenis_akun == "aset" and kode.startswith("11") and b > 0
    ]
    aset_tl = [
        (a, b) for kode, (a, b) in balances.items()
        if a.jenis_akun == "aset" and kode.startswith("12") and b > 0
    ]
    kewajiban_items = [
        (a, b) for kode, (a, b) in balances.items()
        if a.jenis_akun == "kewajiban" and b > 0
    ]

    total_al   = (sum(b for a, b in aset_lancar if not a.is_kontra)
                - sum(b for a, b in aset_lancar if     a.is_kontra))
    total_atl  = (sum(b for a, b in aset_tl    if not a.is_kontra)
                - sum(b for a, b in aset_tl    if     a.is_kontra))
    total_aset = total_al + total_atl
    total_kwjbn = sum(b for _, b in kewajiban_items)
    total_km    = total_kwjbn + modal_akhir

    def _r(lbl, amt, rtype):
        return (lbl, amt, rtype)

    L: list = []
    R: list = []

    L.append(_r("Aset Lancar", None, "section"))
    for a, b in aset_lancar:
        L.append(_r(a.nama_akun, b, "item-kontra" if a.is_kontra else "item"))
    L.append(_r("Total Aset Lancar", total_al, "subtotal"))
    L.append(_r("", None, "spacer"))

    L.append(_r("Aset Tidak Lancar", None, "section"))
    for a, b in aset_tl:
        L.append(_r(a.nama_akun, b, "item-kontra" if a.is_kontra else "item"))
    L.append(_r("Total Aset Tidak Lancar", total_atl, "subtotal"))
    L.append(_r("", None, "spacer"))

    R.append(_r("Kewajiban Lancar", None, "section"))
    for a, b in kewajiban_items:
        R.append(_r(a.nama_akun, b, "item"))
    R.append(_r("Total Kewajiban", total_kwjbn, "subtotal"))
    R.append(_r("", None, "spacer"))

    R.append(_r("Modal", None, "section"))
    R.append(_r(nama_modal, modal_akhir, "item"))
    R.append(_r("", None, "spacer"))

    # Pad supaya baris Total sejajar
    mx = max(len(L), len(R))
    while len(L) < mx:
        L.append(_r("", None, "spacer"))
    while len(R) < mx:
        R.append(_r("", None, "spacer"))

    L.append(_r("Total Aset", total_aset, "total"))
    R.append(_r("Total Kewajiban + Modal", total_km, "total"))

    neraca = {
        "rows":      list(zip(L, R)),
        "total_aset": total_aset,
        "total_km":   total_km,
        "seimbang":   abs(total_aset - total_km) < 1.0,
    }

    fmt = request.query_params.get("format", "")
    if fmt == "pdf":
        from app.services.pdf import render_pdf
        nama_perus = periode.nama_perusahaan if periode else ""
        per_str    = f"Untuk Bulan yang Berakhir {_fmt_tgl(tgl_sampai)}"

        if tab == "laba-rugi":
            pdf_bytes = render_pdf("laba_rugi.html", {
                "landscape": False, "nama_perusahaan": nama_perus,
                "judul": "Laporan Laba Rugi", "periode_str": per_str,
                "lr": laba_rugi,
            })
            return _pdf_response(pdf_bytes, f"laba_rugi_{tgl_sampai}.pdf")

        elif tab == "ekuitas":
            pdf_bytes = render_pdf("ekuitas.html", {
                "landscape": False, "nama_perusahaan": nama_perus,
                "judul": "Laporan Ekuitas Pemilik", "periode_str": per_str,
                "ek": ekuitas,
            })
            return _pdf_response(pdf_bytes, f"ekuitas_{tgl_sampai}.pdf")

        else:  # neraca
            pdf_bytes = render_pdf("neraca.html", {
                "landscape": False, "nama_perusahaan": nama_perus,
                "judul": "Neraca", "periode_str": f"Per {_fmt_tgl(tgl_sampai)}",
                "nr": neraca,
            })
            return _pdf_response(pdf_bytes, f"neraca_{tgl_sampai}.pdf")

    return templates.TemplateResponse("laporan/keuangan.html", {
        "request": request,
        "tab":      tab,
        "periode":  periode,
        "laba_rugi": laba_rugi,
        "ekuitas":   ekuitas,
        "neraca":    neraca,
        "tgl_dari":    tgl_dari,
        "tgl_sampai":  tgl_sampai,
        "extra_hidden": {"tab": tab},
        **_filter_ctx(tgl_dari, tgl_sampai, presets, "/laporan/keuangan"),
    })


# ─── Download (placeholder) ──────────────────────────────────────────────────

@router.get("/jurnal-umum/download")
@router.get("/buku-besar/download")
@router.get("/neraca-saldo/download")
def download_placeholder():
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Fitur download PDF belum tersedia."}, status_code=501)
