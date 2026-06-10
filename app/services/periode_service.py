"""Helper terpusat untuk siklus periode: saldo awal, tutup periode, buka periode,
jurnal pembalik.

Dipakai oleh router penutup, laporan (untuk include saldo_awal), transaksi (lock guard).
"""
import calendar
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Akun, JurnalEntry, Periode, SaldoAwal, Transaksi

# Akun yang TIDAK dibawa ke periode berikutnya meskipun jenis_akun='modal'
# 312 Prive, 313 Ikhtisar L/R — sudah 0 setelah penutup
KODE_TIDAK_DIBAWA = {"312", "313"}

# Jenis transaksi yang menggerakkan saldo (umum + penyesuaian + penutup + pembalik)
JENIS_AKTIF = ["umum", "penyesuaian", "penutup", "pembalik"]


# ─── Saldo Awal ──────────────────────────────────────────────────────────────

def get_saldo_awal_dict(db: Session, periode_id: int) -> dict[str, Decimal]:
    """Return {kode_akun: saldo} dari tabel saldo_awal untuk periode."""
    rows = db.query(SaldoAwal).filter(SaldoAwal.periode_id == periode_id).all()
    return {r.kode_akun: Decimal(str(r.saldo)) for r in rows}


def saldo_awal_signed(db: Session, periode_id: int, kode_akun: str,
                       saldo_normal: str) -> Decimal:
    """Saldo awal akun dalam bentuk (D − K) ber-tanda.

    Saldo di tabel saldo_awal disimpan SELALU positif di sisi normal akun.
    Untuk akun debet-normal: nilai positif berarti debet → return +value
    Untuk akun kredit-normal: nilai positif berarti kredit → return −value
    """
    r = (
        db.query(SaldoAwal)
        .filter(SaldoAwal.periode_id == periode_id, SaldoAwal.kode_akun == kode_akun)
        .first()
    )
    if not r:
        return Decimal("0")
    v = Decimal(str(r.saldo))
    return v if saldo_normal == "debet" else -v


# ─── Hitung Saldo Akhir (untuk carry-forward) ────────────────────────────────

def saldo_akhir_signed(db: Session, periode_id: int, kode_akun: str,
                        saldo_normal: str) -> Decimal:
    """Saldo akhir = saldo awal + Δ semua transaksi (umum + penyesuaian + penutup + pembalik).

    Return SELALU positif di sisi normal akun (atau negatif kalau anomali).
    """
    awal = saldo_awal_signed(db, periode_id, kode_akun, saldo_normal)

    r = (
        db.query(
            func.coalesce(func.sum(JurnalEntry.debet), 0).label("d"),
            func.coalesce(func.sum(JurnalEntry.kredit), 0).label("k"),
        )
        .join(Transaksi)
        .filter(
            JurnalEntry.kode_akun == kode_akun,
            Transaksi.periode_id == periode_id,
            Transaksi.jenis.in_(JENIS_AKTIF),
        )
        .first()
    )
    d, k = Decimal(str(r.d)), Decimal(str(r.k))
    net_dr = awal + d - k  # bersih dalam basis Debet−Kredit
    return net_dr if saldo_normal == "debet" else -net_dr


# ─── Periode Berikutnya ──────────────────────────────────────────────────────

def _bulan_tahun_berikutnya(bulan: int, tahun: int) -> tuple[int, int]:
    if bulan == 12:
        return 1, tahun + 1
    return bulan + 1, tahun


def get_or_create_next_periode(db: Session, current: Periode) -> Periode:
    """Ambil atau buat Periode berikutnya (bulan+1) dengan nama_perusahaan sama."""
    nb, nt = _bulan_tahun_berikutnya(current.bulan, current.tahun)
    nxt = (
        db.query(Periode)
        .filter(
            Periode.nama_perusahaan == current.nama_perusahaan,
            Periode.tahun == nt,
            Periode.bulan == nb,
        )
        .first()
    )
    if nxt:
        return nxt

    nxt = Periode(
        nama_perusahaan=current.nama_perusahaan,
        tahun=nt,
        bulan=nb,
        is_closed=False,
    )
    db.add(nxt)
    db.flush()
    return nxt


# ─── Akrual Detection (untuk jurnal pembalik) ────────────────────────────────

def is_ajp_akrual(transaksi: Transaksi) -> bool:
    """AJP akrual = AJP yang dibalik di awal periode berikutnya.

    Pattern:
      • Accrued Expense:  Beban (D) / Kewajiban (K)
      • Accrued Revenue:  Aset non-kontra (D) / Pendapatan (K)

    Bukan akrual (tidak dibalik):
      • Beban Perlengkapan / Perlengkapan  (alokasi pemakaian)
      • Beban Penyusutan / Akum Penyusutan (alokasi penyusutan)
      • Sewa Dibayar Dimuka / Beban Sewa   (reklasifikasi deferral)
      • Pendapatan Sewa / Pendapatan Sewa DD (reklasifikasi deferral)
    """
    entries = list(transaksi.entries)
    if len(entries) != 2:
        return False

    d_entry = next((e for e in entries if e.debet > 0), None)
    k_entry = next((e for e in entries if e.kredit > 0), None)
    if not d_entry or not k_entry:
        return False

    d_jenis = d_entry.akun.jenis_akun
    k_jenis = k_entry.akun.jenis_akun

    # Accrued expense
    if d_jenis == "beban" and k_jenis == "kewajiban":
        return True
    # Accrued revenue
    if d_jenis == "aset" and not d_entry.akun.is_kontra and k_jenis == "pendapatan":
        return True
    return False


# ─── Tutup Periode ───────────────────────────────────────────────────────────

def snapshot_saldo_awal(db: Session, src: Periode, dst: Periode) -> int:
    """Hitung saldo akhir akun permanen di src lalu tulis sebagai saldo_awal di dst.

    Idempotent: hapus saldo_awal lama di dst dulu, baru insert baru.
    Return: jumlah baris saldo_awal yang ditulis.
    """
    db.query(SaldoAwal).filter(SaldoAwal.periode_id == dst.id).delete(
        synchronize_session=False
    )
    db.flush()

    akun_list = db.query(Akun).order_by(Akun.kode_akun).all()
    n = 0
    for a in akun_list:
        # Hanya akun riil/permanen
        if a.jenis_akun not in ("aset", "kewajiban", "modal"):
            continue
        if a.kode_akun in KODE_TIDAK_DIBAWA:
            continue
        saldo = saldo_akhir_signed(db, src.id, a.kode_akun, a.saldo_normal)
        if saldo != 0:
            db.add(SaldoAwal(periode_id=dst.id, kode_akun=a.kode_akun, saldo=saldo))
            n += 1
    db.flush()
    return n


def regenerate_pembalik(db: Session, src: Periode, dst: Periode) -> int:
    """Hapus pembalik lama di dst + auto-generate baru dari AJP akrual di src.

    Return: jumlah transaksi pembalik baru.
    """
    db.query(Transaksi).filter(
        Transaksi.periode_id == dst.id, Transaksi.jenis == "pembalik"
    ).delete(synchronize_session=False)
    db.flush()
    return _generate_pembalik(db, src, dst)


def tutup_periode(db: Session, periode: Periode, *,
                   buat_pembalik: bool = True) -> tuple[Periode, int, int]:
    """Tutup periode N + buka periode N+1.

    Aksi:
      1. Validasi transaksi penutup sudah ada
      2. Snapshot saldo_awal ke periode N+1 (replace yang lama)
      3. (Opsional) Auto-generate jurnal pembalik di periode N+1 dari AJP akrual N
      4. Set periode.is_closed = True

    Return: (next_periode, jumlah_saldo_awal, jumlah_pembalik)
    """
    if periode.is_closed:
        raise ValueError("Periode sudah ditutup.")

    has_penutup = (
        db.query(Transaksi)
        .filter(Transaksi.periode_id == periode.id, Transaksi.jenis == "penutup")
        .first()
    )
    if not has_penutup:
        raise ValueError(
            "Belum ada jurnal penutup. Klik 'Generate Jurnal Penutup' terlebih dahulu."
        )

    next_p = get_or_create_next_periode(db, periode)
    n_carry = snapshot_saldo_awal(db, periode, next_p)
    n_pembalik = regenerate_pembalik(db, periode, next_p) if buat_pembalik else 0

    periode.is_closed = True
    db.flush()
    return next_p, n_carry, n_pembalik


def _generate_pembalik(db: Session, src: Periode, dst: Periode) -> int:
    """Auto-generate jurnal pembalik dari AJP akrual periode src ke periode dst.

    Jurnal pembalik = membalikkan debet/kredit AJP akrual, ditanggali hari pertama
    periode dst. Disimpan sebagai Transaksi.jenis='pembalik'.

    Return jumlah transaksi pembalik yang dibuat.
    """
    ajp_list = (
        db.query(Transaksi)
        .filter(Transaksi.periode_id == src.id, Transaksi.jenis == "penyesuaian")
        .all()
    )
    tgl_pembalik = date(dst.tahun, dst.bulan, 1)
    n = 0
    for ajp in ajp_list:
        if not is_ajp_akrual(ajp):
            continue

        # Buat transaksi pembalik
        pembalik = Transaksi(
            periode_id=dst.id,
            tanggal=tgl_pembalik,
            keterangan=f"Pembalik: {ajp.keterangan or 'AJP #' + str(ajp.id)}",
            jenis="pembalik",
        )
        db.add(pembalik)
        db.flush()

        # Swap debet ↔ kredit pada setiap entry
        for u, e in enumerate(ajp.entries):
            db.add(JurnalEntry(
                transaksi_id=pembalik.id,
                kode_akun=e.kode_akun,
                debet=e.kredit,   # swap
                kredit=e.debet,   # swap
                urutan=u,
            ))
        n += 1
    return n


# ─── Buka Periode (un-close) ─────────────────────────────────────────────────

def buka_periode(db: Session, periode: Periode) -> int:
    """Batalkan tutup periode. Hanya boleh jika periode berikutnya BELUM punya
    transaksi non-pembalik (kalau sudah dipakai, koreksi periode lama berbahaya).

    Aksi:
      1. Validasi periode N+1 tidak punya transaksi umum/penyesuaian/penutup
      2. Hapus saldo_awal periode N+1
      3. Hapus pembalik periode N+1
      4. (Optional) Hapus periode N+1 jika ia kosong total
      5. Set periode.is_closed = False

    Return jumlah pembalik yang dihapus.
    """
    if not periode.is_closed:
        raise ValueError("Periode belum ditutup.")

    nb, nt = _bulan_tahun_berikutnya(periode.bulan, periode.tahun)
    next_p = (
        db.query(Periode)
        .filter(
            Periode.nama_perusahaan == periode.nama_perusahaan,
            Periode.tahun == nt, Periode.bulan == nb,
        )
        .first()
    )

    n_pembalik_dihapus = 0
    if next_p:
        # 1. Cek transaksi non-pembalik
        non_pembalik = (
            db.query(Transaksi)
            .filter(
                Transaksi.periode_id == next_p.id,
                Transaksi.jenis.in_(["umum", "penyesuaian", "penutup"]),
            )
            .count()
        )
        if non_pembalik > 0:
            raise ValueError(
                f"Periode berikutnya ({nb}/{nt}) sudah punya {non_pembalik} transaksi. "
                "Tidak bisa buka periode ini — hapus dulu transaksi di periode berikutnya."
            )

        # 2. Hapus saldo_awal periode N+1
        db.query(SaldoAwal).filter(SaldoAwal.periode_id == next_p.id).delete()

        # 3. Hapus pembalik periode N+1
        pembalik_list = (
            db.query(Transaksi)
            .filter(Transaksi.periode_id == next_p.id, Transaksi.jenis == "pembalik")
            .all()
        )
        n_pembalik_dihapus = len(pembalik_list)
        for t in pembalik_list:
            db.delete(t)
        db.flush()  # pastikan delete sudah commit ke session sebelum count

        # 4. Hapus periode N+1 jika kosong sama sekali
        sisa = db.query(Transaksi).filter(Transaksi.periode_id == next_p.id).count()
        if sisa == 0:
            db.delete(next_p)

    # 5. Unlock
    periode.is_closed = False
    db.flush()
    return n_pembalik_dihapus
