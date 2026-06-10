"""Seeder Transaksi — Jurnal Umum (April 2008).

Run: python seed_transaksi_umum.py

Prasyarat: jalankan `python seed_utama.py` terlebih dahulu (akun & periode
harus sudah ada).

Akan SKIP kalau sudah ada transaksi umum di periode April 2008. Jalankan
`python reset_transaksi.py` dulu jika ingin re-seed.
"""
import sys
from datetime import date

from app.database import SessionLocal
from app.models import Akun, JurnalEntry, Periode, Transaksi


def make_trx(db, periode_id, tanggal, keterangan, jenis, entries):
    """Buat 1 Transaksi + JurnalEntry-nya. entries = list (kode, debet, kredit)."""
    t = Transaksi(
        periode_id=periode_id,
        tanggal=date.fromisoformat(tanggal),
        keterangan=keterangan,
        jenis=jenis,
    )
    db.add(t)
    db.flush()
    for urutan, (kode, debet, kredit) in enumerate(entries):
        db.add(JurnalEntry(
            transaksi_id=t.id,
            kode_akun=kode,
            debet=debet,
            kredit=kredit,
            urutan=urutan,
        ))
    return t


# ── Definisi transaksi Jurnal Umum April 2008 ────────────────────────────────
JURNAL_UMUM = [
    ("2008-04-01", "Modal Awal Tn Supriana", [
        ("111", 75_000_000, 0),
        ("311", 0, 75_000_000),
    ]),
    ("2008-04-05", "Sewa Ruangan untuk 6 Bulan", [
        ("511", 7_500_000, 0),
        ("111", 0, 7_500_000),
    ]),
    ("2008-04-08", "Dibeli Perlengkapan Kantor Secara Tunai", [
        ("113", 9_000_000, 0),
        ("111", 0, 9_000_000),
    ]),
    ("2008-04-10", "Dibeli Peralatan Kantor Secara Kredit", [
        ("121", 9_000_000, 0),
        ("211", 0, 9_000_000),
    ]),
    ("2008-04-14", "Prive", [
        ("312", 3_500_000, 0),
        ("111", 0, 3_500_000),
    ]),
    ("2008-04-17", "Bayar Gaji Karyawan", [
        ("512", 2_750_000, 0),
        ("111", 0, 2_750_000),
    ]),
    ("2008-04-19", "Pendapatan Jasa Secara Kredit", [
        ("112", 7_500_000, 0),
        ("411", 0, 7_500_000),
    ]),
    ("2008-04-21", "Beban lain-lain", [
        ("514", 1_500_000, 0),
        ("111", 0, 1_500_000),
    ]),
    ("2008-04-23", "Pendapatan Jasa Secara Tunai", [
        ("111", 3_000_000, 0),
        ("411", 0, 3_000_000),
    ]),
    ("2008-04-25", "Bayar Utang Usaha", [
        ("211", 3_000_000, 0),
        ("111", 0, 3_000_000),
    ]),
    ("2008-04-27", "Diterima Pendapatan Sewa Mesin Untuk 3 Bulan", [
        ("111", 2_000_000, 0),
        ("412", 0, 2_000_000),
    ]),
    ("2008-04-28", "Diterima Piutang Usaha", [
        ("111", 4_000_000, 0),
        ("112", 0, 4_000_000),
    ]),
    ("2008-04-30", "Bayar Utilitas", [
        ("513", 1_250_000, 0),
        ("111", 0, 1_250_000),
    ]),
]


def main():
    print("=" * 60)
    print("SEEDER TRANSAKSI — Jurnal Umum (April 2008)")
    print("=" * 60)

    db = SessionLocal()

    # Cek prasyarat: harus ada akun + periode
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

    # Cek idempotency
    existing_umum = (
        db.query(Transaksi)
        .filter(
            Transaksi.periode_id == periode.id,
            Transaksi.jenis == "umum",
        )
        .count()
    )
    if existing_umum:
        print(f"\n✗ Sudah ada {existing_umum} transaksi jurnal umum di periode April 2008.")
        print("  Jalankan dulu: python reset_transaksi.py  — kalau mau re-seed.")
        db.close()
        sys.exit(1)

    # Seed
    print(f"\nSeeding {len(JURNAL_UMUM)} transaksi jurnal umum ke periode {periode.bulan}/{periode.tahun}...")
    for tgl, ket, entries in JURNAL_UMUM:
        make_trx(db, periode.id, tgl, ket, "umum", entries)
    db.commit()
    print(f"  ✓ {len(JURNAL_UMUM)} transaksi umum di-seed")

    db.close()

    print()
    print("=" * 60)
    print("SELESAI. Cek di /laporan/jurnal-umum atau /transaksi")
    print("=" * 60)


if __name__ == "__main__":
    main()
