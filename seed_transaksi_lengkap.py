"""Seeder Transaksi LENGKAP — Jurnal Umum + Jurnal Penyesuaian (April 2008).

Run: python seed_transaksi_lengkap.py

Prasyarat: jalankan `python seed_utama.py` terlebih dahulu.

Akan SKIP kalau sudah ada transaksi umum atau penyesuaian di periode April 2008.
Jalankan `python reset_transaksi.py` dulu jika ingin re-seed.

Berisi:
  • 13 Jurnal Umum (sama dengan seed_transaksi_umum.py)
  • 6 Jurnal Penyesuaian (sesuai data soal per 30 April 2008):
      1. Beban perlengkapan (sisa fisik Rp 8.547.200)
      2. Penyusutan peralatan (garis lurus 2 tahun)
      3. Reklas Beban Sewa → Sewa Dibayar Dimuka (5 bulan belum expired)
      4. Accrued Revenue (piutang jasa Rp 1.000.000)
      5. Reklas Pendapatan Sewa Mesin → Pendapatan Diterima Dimuka (2/3 belum earned)
      6. Accrued Expense gaji (Rp 1.215.400)
"""
import sys

from app.database import SessionLocal
from app.models import Akun, Periode, Transaksi
from seed_transaksi_umum import JURNAL_UMUM, make_trx


# ── Definisi Jurnal Penyesuaian (AJP) per 30 April 2008 ──────────────────────
JURNAL_PENYESUAIAN = [
    # AJP 1: Beban perlengkapan
    # Saldo perlengkapan Rp 9.000.000 → sisa fisik Rp 8.547.200 → terpakai 452.800
    ("2008-04-30", "Beban Perlengkapan (sisa fisik Rp 8.547.200)", [
        ("515", 452_800, 0),
        ("113", 0, 452_800),
    ]),
    # AJP 2: Penyusutan peralatan
    # Rp 9.000.000 / 2 tahun / 12 bulan = Rp 375.000 per bulan
    ("2008-04-30", "Penyusutan Peralatan (garis lurus, umur 2 tahun)", [
        ("516", 375_000, 0),
        ("122", 0, 375_000),
    ]),
    # AJP 3: Reklasifikasi sewa (pendekatan beban)
    # Sewa 6 bulan dibayar 5/4, sudah expired 1 bulan; sisa 5 bulan = Rp 6.250.000
    ("2008-04-30", "Reklas Beban Sewa ke Sewa Dibayar Dimuka (5 bulan belum expired)", [
        ("114", 6_250_000, 0),
        ("511", 0, 6_250_000),
    ]),
    # AJP 4: Accrued Revenue (pendapatan yang masih harus diterima)
    ("2008-04-30", "Accrued Revenue — piutang jasa Rp 1.000.000", [
        ("112", 1_000_000, 0),
        ("411", 0, 1_000_000),
    ]),
    # AJP 5: Reklasifikasi sewa mesin (pendekatan pendapatan)
    # Sewa mesin 3 bulan diterima 27/4, baru earned 1/3 = 666.667; sisa 2/3 = 1.333.333
    ("2008-04-30", "Reklas Pendapatan Sewa Mesin ke Pendapatan Diterima Dimuka (2/3 belum earned)", [
        ("412", 1_333_333, 0),
        ("213", 0, 1_333_333),
    ]),
    # AJP 6: Accrued Expense (beban yang masih harus dibayar)
    ("2008-04-30", "Accrued Expense — gaji belum dibayar Rp 1.215.400", [
        ("512", 1_215_400, 0),
        ("212", 0, 1_215_400),
    ]),
]


def main():
    print("=" * 60)
    print("SEEDER TRANSAKSI LENGKAP — Jurnal Umum + Penyesuaian (April 2008)")
    print("=" * 60)

    db = SessionLocal()

    # Cek prasyarat
    if db.query(Akun).count() == 0:
        print("\n✗ ERROR: Tabel akun masih kosong.")
        print("  Jalankan dulu: python seed_utama.py")
        db.close()
        sys.exit(1)

    periode = db.query(Periode).filter_by(tahun=2008, bulan=4).first()
    if not periode:
        print("\n✗ ERROR: Periode April 2008 tidak ditemukan.")
        print("  Jalankan dulu: python seed_utama.py")
        db.close()
        sys.exit(1)

    # Cek idempotency (umum + penyesuaian)
    existing = (
        db.query(Transaksi)
        .filter(
            Transaksi.periode_id == periode.id,
            Transaksi.jenis.in_(["umum", "penyesuaian"]),
        )
        .count()
    )
    if existing:
        print(f"\n✗ Sudah ada {existing} transaksi umum/penyesuaian di periode April 2008.")
        print("  Jalankan dulu: python reset_transaksi.py  — kalau mau re-seed.")
        db.close()
        sys.exit(1)

    # Seed jurnal umum
    print(f"\n[1/2] Seeding {len(JURNAL_UMUM)} jurnal umum...")
    for tgl, ket, entries in JURNAL_UMUM:
        make_trx(db, periode.id, tgl, ket, "umum", entries)
    print(f"  ✓ {len(JURNAL_UMUM)} transaksi umum")

    # Seed jurnal penyesuaian
    print(f"\n[2/2] Seeding {len(JURNAL_PENYESUAIAN)} jurnal penyesuaian (AJP)...")
    for tgl, ket, entries in JURNAL_PENYESUAIAN:
        make_trx(db, periode.id, tgl, ket, "penyesuaian", entries)
    print(f"  ✓ {len(JURNAL_PENYESUAIAN)} transaksi penyesuaian")

    db.commit()
    db.close()

    print()
    print("=" * 60)
    print(f"SELESAI. Total {len(JURNAL_UMUM) + len(JURNAL_PENYESUAIAN)} transaksi di-seed.")
    print("Cek di /laporan/worksheet untuk lihat kolom NS + AJP + NSD.")
    print("=" * 60)


if __name__ == "__main__":
    main()
