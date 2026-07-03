"""Seeder Skenario Presentasi — Jurnal Umum #4 s/d #13 (April 2008).

Skenario: di awal presentasi DB kosong dari transaksi. User menginput 3
transaksi jurnal umum pertama secara MANUAL di depan audiens, lalu menjalankan
script ini untuk menambah 10 transaksi sisanya supaya presentasi tetap on-track.

Run: python seed_presentasi_umum.py

Prasyarat:
  • seed_utama.py sudah dijalankan (CoA + periode + user login)
  • 3 transaksi jurnal umum pertama sudah diinput di periode April 2008:
      #1 Modal Awal Tn Supriana
      #2 Sewa Ruangan untuk 6 Bulan
      #3 Dibeli Perlengkapan Kantor Secara Tunai

Yang DI-SEED (10 transaksi):
  #4  Dibeli Peralatan Kantor Secara Kredit
  #5  Prive
  #6  Bayar Gaji Karyawan
  #7  Pendapatan Jasa Secara Kredit
  #8  Beban lain-lain
  #9  Pendapatan Jasa Secara Tunai
  #10 Bayar Utang Usaha
  #11 Diterima Pendapatan Sewa Mesin Untuk 3 Bulan
  #12 Diterima Piutang Usaha
  #13 Bayar Utilitas
"""
import sys

from app.database import SessionLocal
from app.models import Akun, Periode, Transaksi
from seed_transaksi_umum import JURNAL_UMUM, make_trx


# Transaksi #4 s/d #13 (skip 3 pertama, yang diinput manual)
JURNAL_UMUM_LANJUTAN = JURNAL_UMUM[3:]


def main():
    print("=" * 60)
    print("SEEDER PRESENTASI — Jurnal Umum #4 s/d #13 (April 2008)")
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

    # Cek jumlah transaksi umum existing
    n_umum = (
        db.query(Transaksi)
        .filter(
            Transaksi.periode_id == periode.id,
            Transaksi.jenis == "umum",
        )
        .count()
    )

    if n_umum >= 4:
        print(f"\n[INFO] Sudah ada {n_umum} transaksi umum di April 2008.")
        print("  Sepertinya seeder ini sudah pernah dijalankan.")
        print("  Jalankan 'python reset_transaksi.py' kalau mau ulang dari awal.")
        db.close()
        sys.exit(0)

    if n_umum < 3:
        print(f"\n[PERHATIAN] Hanya ada {n_umum} transaksi umum (expected 3 manual).")
        print("  Pastikan Anda sudah input 3 transaksi pertama via UI:")
        for i, (tgl, ket, _) in enumerate(JURNAL_UMUM[:3], start=1):
            print(f"    #{i} {tgl}: {ket}")
        print()
        ans = input("  Lanjutkan tetap? (y/N): ").strip().lower()
        if ans not in ("y", "yes"):
            print("Dibatalkan.")
            db.close()
            sys.exit(0)

    # Seed
    print(f"\nSeeding {len(JURNAL_UMUM_LANJUTAN)} transaksi umum ke periode April 2008...")
    for i, (tgl, ket, entries) in enumerate(JURNAL_UMUM_LANJUTAN, start=4):
        make_trx(db, periode.id, tgl, ket, "umum", entries)
        print(f"  [#{i:2d}] {tgl}  {ket}")
    db.commit()
    db.close()

    print()
    print("=" * 60)
    print(f"SELESAI. {len(JURNAL_UMUM_LANJUTAN)} transaksi umum ditambahkan.")
    print("Buka /laporan/jurnal-umum untuk verifikasi.")
    print()
    print("Langkah berikutnya:")
    print("  • python seed_presentasi_ajp.py  — seed AJP #1 s/d #4")
    print("=" * 60)


if __name__ == "__main__":
    main()
