"""[DEPRECATED] File ini sudah dipecah menjadi 3 seeder terpisah.

Pakai salah satu kombinasi berikut:

  1. python seed_utama.py
     → Chart of Accounts + Periode awal + User login (WAJIB JALAN PERTAMA)

  2. python seed_utama.py
     python seed_transaksi_umum.py
     → Setup + 13 transaksi jurnal umum saja (untuk eksplorasi tahap pencatatan)

  3. python seed_utama.py
     python seed_transaksi_lengkap.py
     → Setup + 13 jurnal umum + 6 jurnal penyesuaian (paket lengkap, siap tutup buku)

Untuk reset data transaksi tanpa kehilangan CoA/User:
  python reset_transaksi.py
"""
print(__doc__)
