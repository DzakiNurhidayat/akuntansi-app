"""Seeder Skenario Presentasi — Jurnal Penyesuaian #1 s/d #4 (April 2008).

Skenario: setelah jurnal umum lengkap (#1-13), jalankan script ini untuk
seed 4 AJP pertama. User akan input AJP #5 dan #6 secara MANUAL di depan
audiens.

Run: python seed_presentasi_ajp.py

Prasyarat:
  • seed_utama.py sudah dijalankan
  • Periode April 2008 ada
  • (Disarankan) Jurnal umum sudah lengkap

Yang DI-SEED (4 AJP):
  AJP #1  Beban Perlengkapan (sisa fisik Rp 8.547.200)
            515 Beban Perlengkapan      (D) Rp   452.800
            113 Perlengkapan            (K) Rp   452.800

  AJP #2  Penyusutan Peralatan (garis lurus, umur 2 tahun)
            516 Beban Penyusutan        (D) Rp   375.000
            122 Akumulasi Penyusutan    (K) Rp   375.000

  AJP #3  Reklas Beban Sewa ke Sewa Dibayar Dimuka
            114 Sewa Dibayar Dimuka     (D) Rp 6.250.000
            511 Beban Sewa              (K) Rp 6.250.000

  AJP #4  Accrued Revenue — piutang jasa
            112 Piutang Usaha           (D) Rp 1.000.000
            411 Pendapatan Jasa         (K) Rp 1.000.000

Yang DI-INPUT MANUAL OLEH USER (saat presentasi):
  AJP #5  Reklas Pendapatan Sewa Mesin ke Pendapatan Diterima Dimuka
            412 Pendapatan Sewa Mesin   (D) Rp 1.333.333
            213 Pendapatan Diterima DD  (K) Rp 1.333.333

  AJP #6  Accrued Expense — gaji yang belum dibayar
            512 Beban Gaji              (D) Rp 1.215.400
            212 Hutang Gaji             (K) Rp 1.215.400
"""
import sys

from app.database import SessionLocal
from app.models import Akun, Periode, Transaksi
from seed_transaksi_lengkap import JURNAL_PENYESUAIAN
from seed_transaksi_umum import make_trx


# AJP #1 s/d #4 (skip 2 terakhir — diinput manual oleh user saat presentasi)
AJP_LANJUTAN = JURNAL_PENYESUAIAN[:4]


def main():
    print("=" * 60)
    print("SEEDER PRESENTASI — Jurnal Penyesuaian #1 s/d #4 (April 2008)")
    print("=" * 60)

    db = SessionLocal()

    # Cek prasyarat
    if db.query(Akun).count() == 0:
        print("\n[ERROR] Tabel akun masih kosong.")
        print("  Jalankan dulu: python seed_utama.py")
        db.close()
        sys.exit(1)

    periode = db.query(Periode).filter_by(tahun=2008, bulan=4).first()
    if not periode:
        print("\n[ERROR] Periode April 2008 tidak ditemukan.")
        print("  Jalankan dulu: python seed_utama.py")
        db.close()
        sys.exit(1)

    # Cek apakah AJP sudah ada
    n_ajp = (
        db.query(Transaksi)
        .filter(
            Transaksi.periode_id == periode.id,
            Transaksi.jenis == "penyesuaian",
        )
        .count()
    )

    if n_ajp >= 1:
        print(f"\n[INFO] Sudah ada {n_ajp} transaksi penyesuaian di April 2008.")
        print("  Sepertinya seeder ini sudah pernah dijalankan.")
        print("  Jalankan 'python reset_transaksi.py' kalau mau ulang dari awal.")
        db.close()
        sys.exit(0)

    # Seed
    print(f"\nSeeding {len(AJP_LANJUTAN)} AJP ke periode April 2008...")
    for i, (tgl, ket, entries) in enumerate(AJP_LANJUTAN, start=1):
        make_trx(db, periode.id, tgl, ket, "penyesuaian", entries)
        print(f"  [AJP #{i}] {tgl}  {ket}")
    db.commit()
    db.close()

    print()
    print("=" * 60)
    print(f"SELESAI. {len(AJP_LANJUTAN)} AJP ditambahkan.")
    print()
    print("Untuk presentasi selanjutnya, input MANUAL 2 AJP terakhir via UI:")
    print()
    print("  AJP #5  Reklas Pendapatan Sewa Mesin (2/3 belum earned)")
    print("    Tanggal     : 30 April 2008")
    print("    Keterangan  : Reklas Pendapatan Sewa Mesin ke Pendapatan Diterima Dimuka")
    print("    412 Pendapatan Sewa Mesin       Debet  Rp 1.333.333")
    print("    213 Pendapatan Diterima Dimuka  Kredit Rp 1.333.333")
    print()
    print("  AJP #6  Accrued Expense - gaji belum dibayar")
    print("    Tanggal     : 30 April 2008")
    print("    Keterangan  : Accrued Expense - gaji belum dibayar Rp 1.215.400")
    print("    512 Beban Gaji  Debet  Rp 1.215.400")
    print("    212 Hutang Gaji Kredit Rp 1.215.400")
    print("=" * 60)


if __name__ == "__main__":
    main()
