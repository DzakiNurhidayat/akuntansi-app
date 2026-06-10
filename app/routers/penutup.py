"""Jurnal Penutup — auto-generate dari NSD periode aktif.

Urutan (per CLAUDE.md):
  1. Pendapatan → Ikhtisar Laba Rugi (akun 313)
  2. Ikhtisar Laba Rugi → Beban
  3. Ikhtisar Laba Rugi ↔ Modal  (sesuai laba/rugi)
  4. Modal → Prive (drawing)

Tersimpan sebagai Transaksi.jenis='penutup'. Bisa di-regenerate
(transaksi 'penutup' periode terkait dihapus lalu dibuat ulang).
"""
import calendar
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Akun, JurnalEntry, Periode, Transaksi
from app.templates_env import templates

router = APIRouter(prefix="/penutup", tags=["penutup"])

# Kode akun khusus untuk jurnal penutup
KODE_IKHTISAR = "313"   # Ikhtisar Laba Rugi
KODE_MODAL    = "311"   # Modal Pemilik
KODE_PRIVE    = "312"   # Prive (drawing)

# Jenis transaksi yang membentuk NSD (Neraca Saldo setelah Disesuaikan)
JENIS_NSD = ["umum", "penyesuaian"]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _periode_aktif(db: Session, request: Request) -> Periode | None:
    """Periode dari query param, fallback ke yang terbaru."""
    try:
        pid = int(request.query_params.get("periode_id", 0))
    except ValueError:
        pid = 0
    if pid:
        p = db.query(Periode).filter(Periode.id == pid).first()
        if p:
            return p
    return (
        db.query(Periode)
        .order_by(Periode.tahun.desc(), Periode.bulan.desc())
        .first()
    )


def _saldo_nsd(db: Session, periode_id: int, kode_akun: str) -> Decimal:
    """Saldo NSD akun (debet−kredit) = saldo_awal + Δ(umum + penyesuaian).

    Hasilnya tetap dalam basis "debet positif" — caller harus convert berdasar saldo_normal.
    """
    from app.models import SaldoAwal
    sa = (
        db.query(SaldoAwal)
        .filter(SaldoAwal.periode_id == periode_id, SaldoAwal.kode_akun == kode_akun)
        .first()
    )
    awal_dr = Decimal("0")
    if sa:
        akun = db.query(Akun).filter(Akun.kode_akun == kode_akun).first()
        if akun:
            v = Decimal(str(sa.saldo))
            awal_dr = v if akun.saldo_normal == "debet" else -v

    r = (
        db.query(
            func.coalesce(func.sum(JurnalEntry.debet),  0).label("d"),
            func.coalesce(func.sum(JurnalEntry.kredit), 0).label("k"),
        )
        .join(Transaksi)
        .filter(
            JurnalEntry.kode_akun == kode_akun,
            Transaksi.periode_id == periode_id,
            Transaksi.jenis.in_(JENIS_NSD),
        )
        .first()
    )
    return awal_dr + Decimal(str(r.d)) - Decimal(str(r.k))


def _build_closing_entries(db: Session, periode: Periode) -> list[dict]:
    """Hitung 4 transaksi penutup berdasarkan NSD periode aktif.

    Return list of dicts:
      {tanggal, keterangan, jenis, entries: [{kode_akun, akun, debet, kredit, urutan}]}
    Transaksi dengan total nol akan diskip.
    """
    last_day = calendar.monthrange(periode.tahun, periode.bulan)[1]
    tgl = date(periode.tahun, periode.bulan, last_day)

    akun_map = {a.kode_akun: a for a in db.query(Akun).all()}
    akun_ikhtisar = akun_map.get(KODE_IKHTISAR)
    akun_modal    = akun_map.get(KODE_MODAL)
    akun_prive    = akun_map.get(KODE_PRIVE)

    # NSD per akun
    pendapatan_saldo = []  # list (akun, saldo_positif_kredit)
    beban_saldo      = []  # list (akun, saldo_positif_debet)

    for kode, akun in sorted(akun_map.items()):
        if akun.jenis_akun == "pendapatan":
            saldo = -_saldo_nsd(db, periode.id, kode)  # saldo normal kredit
            if saldo > 0:
                pendapatan_saldo.append((akun, saldo))
        elif akun.jenis_akun == "beban":
            saldo = _saldo_nsd(db, periode.id, kode)
            if saldo > 0:
                beban_saldo.append((akun, saldo))

    total_pendapatan = sum((s for _, s in pendapatan_saldo), Decimal("0"))
    total_beban      = sum((s for _, s in beban_saldo),      Decimal("0"))
    net = total_pendapatan - total_beban  # >0 laba, <0 rugi

    prive_saldo = _saldo_nsd(db, periode.id, KODE_PRIVE) if akun_prive else Decimal("0")

    transaksi_list: list[dict] = []

    # ── 1. Tutup Pendapatan ──────────────────────────────────────────────────
    if pendapatan_saldo and akun_ikhtisar:
        entries = []
        u = 0
        for akun, saldo in pendapatan_saldo:
            entries.append({"kode_akun": akun.kode_akun, "akun": akun,
                            "debet": saldo, "kredit": Decimal("0"), "urutan": u})
            u += 1
        entries.append({"kode_akun": KODE_IKHTISAR, "akun": akun_ikhtisar,
                        "debet": Decimal("0"), "kredit": total_pendapatan, "urutan": u})
        transaksi_list.append({
            "tanggal": tgl, "jenis": "penutup",
            "keterangan": "Menutup akun pendapatan ke Ikhtisar Laba Rugi",
            "entries": entries,
        })

    # ── 2. Tutup Beban ───────────────────────────────────────────────────────
    if beban_saldo and akun_ikhtisar:
        entries = [{"kode_akun": KODE_IKHTISAR, "akun": akun_ikhtisar,
                    "debet": total_beban, "kredit": Decimal("0"), "urutan": 0}]
        u = 1
        for akun, saldo in beban_saldo:
            entries.append({"kode_akun": akun.kode_akun, "akun": akun,
                            "debet": Decimal("0"), "kredit": saldo, "urutan": u})
            u += 1
        transaksi_list.append({
            "tanggal": tgl, "jenis": "penutup",
            "keterangan": "Menutup akun beban ke Ikhtisar Laba Rugi",
            "entries": entries,
        })

    # ── 3. Tutup Ikhtisar Laba Rugi ke Modal ─────────────────────────────────
    if net != 0 and akun_ikhtisar and akun_modal:
        if net > 0:
            # Laba: Ikhtisar L/R (D) → Modal (K)
            entries = [
                {"kode_akun": KODE_IKHTISAR, "akun": akun_ikhtisar,
                 "debet": net, "kredit": Decimal("0"), "urutan": 0},
                {"kode_akun": KODE_MODAL, "akun": akun_modal,
                 "debet": Decimal("0"), "kredit": net, "urutan": 1},
            ]
            ket = "Menutup Ikhtisar Laba Rugi (laba) ke Modal"
        else:
            rugi = -net
            # Rugi: Modal (D) → Ikhtisar L/R (K)
            entries = [
                {"kode_akun": KODE_MODAL, "akun": akun_modal,
                 "debet": rugi, "kredit": Decimal("0"), "urutan": 0},
                {"kode_akun": KODE_IKHTISAR, "akun": akun_ikhtisar,
                 "debet": Decimal("0"), "kredit": rugi, "urutan": 1},
            ]
            ket = "Menutup Ikhtisar Laba Rugi (rugi) ke Modal"
        transaksi_list.append({
            "tanggal": tgl, "jenis": "penutup",
            "keterangan": ket, "entries": entries,
        })

    # ── 4. Tutup Prive ke Modal ──────────────────────────────────────────────
    if prive_saldo > 0 and akun_modal and akun_prive:
        entries = [
            {"kode_akun": KODE_MODAL, "akun": akun_modal,
             "debet": prive_saldo, "kredit": Decimal("0"), "urutan": 0},
            {"kode_akun": KODE_PRIVE, "akun": akun_prive,
             "debet": Decimal("0"), "kredit": prive_saldo, "urutan": 1},
        ]
        transaksi_list.append({
            "tanggal": tgl, "jenis": "penutup",
            "keterangan": f"Menutup {akun_prive.nama_akun} ke Modal",
            "entries": entries,
        })

    return transaksi_list


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("")
def view_penutup(request: Request, db: Session = Depends(get_db)):
    periode = _periode_aktif(db, request)
    periodes = (
        db.query(Periode)
        .order_by(Periode.tahun.desc(), Periode.bulan.desc())
        .all()
    )

    preview = _build_closing_entries(db, periode) if periode else []

    # Transaksi penutup yang sudah tersimpan
    saved = []
    if periode:
        saved_trx = (
            db.query(Transaksi)
            .filter(Transaksi.periode_id == periode.id, Transaksi.jenis == "penutup")
            .order_by(Transaksi.id)
            .all()
        )
        for t in saved_trx:
            saved.append({
                "tanggal": t.tanggal,
                "keterangan": t.keterangan or "",
                "entries": [{
                    "akun": e.akun,
                    "kode_akun": e.kode_akun,
                    "debet": float(e.debet),
                    "kredit": float(e.kredit),
                } for e in t.entries],
            })

    # Periode berikutnya (kalau ada) — untuk shortcut setelah tutup
    next_periode = None
    if periode:
        from app.services.periode_service import _bulan_tahun_berikutnya
        nb, nt = _bulan_tahun_berikutnya(periode.bulan, periode.tahun)
        next_periode = (
            db.query(Periode)
            .filter(Periode.nama_perusahaan == periode.nama_perusahaan,
                    Periode.tahun == nt, Periode.bulan == nb)
            .first()
        )

    return templates.TemplateResponse("penutup.html", {
        "request": request,
        "periode": periode,
        "periodes": periodes,
        "preview": preview,
        "saved": saved,
        "has_saved": bool(saved),
        "is_closed": bool(periode and periode.is_closed),
        "next_periode": next_periode,
        "msg": request.query_params.get("msg"),
        "msg_type": request.query_params.get("type", "success"),
    })


@router.post("/generate")
def generate_penutup(request: Request, db: Session = Depends(get_db)):
    """Buat ulang transaksi 'penutup' untuk periode aktif."""
    # periode_id bisa dari form atau query
    periode = _periode_aktif(db, request)
    if not periode:
        return RedirectResponse("/penutup?msg=Periode+tidak+ditemukan&type=error", status_code=303)

    # Hapus penutup lama untuk periode ini
    old = (
        db.query(Transaksi)
        .filter(Transaksi.periode_id == periode.id, Transaksi.jenis == "penutup")
        .all()
    )
    for t in old:
        db.delete(t)
    db.flush()

    # Generate baru
    transaksi_list = _build_closing_entries(db, periode)
    if not transaksi_list:
        db.commit()
        return RedirectResponse(
            f"/penutup?periode_id={periode.id}"
            "&msg=Tidak+ada+saldo+nominal+untuk+ditutup&type=error",
            status_code=303,
        )

    for trx_data in transaksi_list:
        t = Transaksi(
            periode_id=periode.id,
            tanggal=trx_data["tanggal"],
            keterangan=trx_data["keterangan"],
            jenis="penutup",
        )
        db.add(t)
        db.flush()
        for e in trx_data["entries"]:
            db.add(JurnalEntry(
                transaksi_id=t.id,
                kode_akun=e["kode_akun"],
                debet=e["debet"],
                kredit=e["kredit"],
                urutan=e["urutan"],
            ))
    db.commit()

    n = len(transaksi_list)
    return RedirectResponse(
        f"/penutup?periode_id={periode.id}"
        f"&msg={n}+transaksi+penutup+berhasil+digenerate&type=success",
        status_code=303,
    )


@router.post("/tutup-periode")
def tutup_periode_route(request: Request, db: Session = Depends(get_db)):
    """Tutup periode aktif → lock + carry-forward + buka periode N+1 + pembalik auto."""
    from app.services.periode_service import tutup_periode

    periode = _periode_aktif(db, request)
    if not periode:
        return RedirectResponse("/penutup?msg=Periode+tidak+ditemukan&type=error", status_code=303)

    try:
        next_p, n_carry, n_pembalik = tutup_periode(db, periode, buat_pembalik=True)
        db.commit()
    except ValueError as e:
        db.rollback()
        return RedirectResponse(
            f"/penutup?periode_id={periode.id}&msg={str(e).replace(' ', '+')}&type=error",
            status_code=303,
        )

    msg = (f"Periode+{periode.bulan}/{periode.tahun}+ditutup.+"
           f"{n_carry}+saldo+awal+dibawa+ke+periode+baru,+{n_pembalik}+jurnal+pembalik+dibuat.")
    return RedirectResponse(
        f"/penutup?periode_id={next_p.id}&msg={msg}&type=success",
        status_code=303,
    )


@router.post("/resync")
def resync_route(request: Request, db: Session = Depends(get_db)):
    """Resync tutup buku: regenerate jurnal penutup + saldo_awal periode
    berikutnya + jurnal pembalik. Dipakai setelah edit transaksi di periode
    yang sudah ditutup, supaya snapshot di periode berikutnya tetap sinkron.
    """
    from app.services.periode_service import (
        get_or_create_next_periode,
        regenerate_pembalik,
        snapshot_saldo_awal,
    )

    periode = _periode_aktif(db, request)
    if not periode:
        return RedirectResponse("/penutup?msg=Periode+tidak+ditemukan&type=error", 303)
    if not periode.is_closed:
        return RedirectResponse(
            f"/penutup?periode_id={periode.id}"
            "&msg=Periode+belum+ditutup.+Tidak+perlu+resync.&type=error",
            303,
        )

    # 1. Regenerate jurnal penutup berdasarkan NSD saat ini
    old_penutup = (
        db.query(Transaksi)
        .filter(Transaksi.periode_id == periode.id, Transaksi.jenis == "penutup")
        .all()
    )
    for t in old_penutup:
        db.delete(t)
    db.flush()

    trx_list = _build_closing_entries(db, periode)
    for trx_data in trx_list:
        t = Transaksi(
            periode_id=periode.id,
            tanggal=trx_data["tanggal"],
            keterangan=trx_data["keterangan"],
            jenis="penutup",
        )
        db.add(t)
        db.flush()
        for e in trx_data["entries"]:
            db.add(JurnalEntry(
                transaksi_id=t.id,
                kode_akun=e["kode_akun"],
                debet=e["debet"],
                kredit=e["kredit"],
                urutan=e["urutan"],
            ))
    db.flush()

    # 2. Snapshot saldo_awal ke periode berikutnya
    next_p = get_or_create_next_periode(db, periode)
    n_carry = snapshot_saldo_awal(db, periode, next_p)

    # 3. Regenerate jurnal pembalik di periode berikutnya
    n_pembalik = regenerate_pembalik(db, periode, next_p)

    db.commit()
    msg = (
        f"Resync+selesai:+{len(trx_list)}+penutup+regenerated,+"
        f"{n_carry}+saldo+awal+disinkron,+{n_pembalik}+pembalik+digenerate."
    )
    return RedirectResponse(
        f"/penutup?periode_id={periode.id}&msg={msg}&type=success",
        status_code=303,
    )


@router.post("/buka-periode")
def buka_periode_route(request: Request, db: Session = Depends(get_db)):
    """Batalkan tutup periode aktif (kalau memungkinkan)."""
    from app.services.periode_service import buka_periode

    periode = _periode_aktif(db, request)
    if not periode:
        return RedirectResponse("/penutup?msg=Periode+tidak+ditemukan&type=error", status_code=303)

    try:
        n_pembalik = buka_periode(db, periode)
        db.commit()
    except ValueError as e:
        db.rollback()
        return RedirectResponse(
            f"/penutup?periode_id={periode.id}&msg={str(e).replace(' ', '+')}&type=error",
            status_code=303,
        )

    return RedirectResponse(
        f"/penutup?periode_id={periode.id}"
        f"&msg=Periode+dibuka+kembali.+{n_pembalik}+jurnal+pembalik+dihapus.&type=success",
        status_code=303,
    )


@router.post("/hapus")
def hapus_penutup(request: Request, db: Session = Depends(get_db)):
    """Hapus seluruh transaksi 'penutup' untuk periode aktif."""
    periode = _periode_aktif(db, request)
    if not periode:
        return RedirectResponse("/penutup?msg=Periode+tidak+ditemukan&type=error", status_code=303)

    old = (
        db.query(Transaksi)
        .filter(Transaksi.periode_id == periode.id, Transaksi.jenis == "penutup")
        .all()
    )
    n = len(old)
    for t in old:
        db.delete(t)
    db.commit()
    return RedirectResponse(
        f"/penutup?periode_id={periode.id}"
        f"&msg={n}+transaksi+penutup+dihapus&type=success",
        status_code=303,
    )
