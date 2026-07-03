"""[DEPRECATED] File ini sudah dipecah jadi beberapa seeder terpisah.

═════════════════════════════════════════════════════════════════════════════
SETUP STANDAR
═════════════════════════════════════════════════════════════════════════════

  1. python seed_utama.py
     → Chart of Accounts + Periode awal + User login (WAJIB JALAN PERTAMA)

  2a. python seed_transaksi_umum.py
      → Setup + 13 transaksi jurnal umum saja

  2b. python seed_transaksi_lengkap.py
      → Setup + 13 jurnal umum + 6 jurnal penyesuaian (paket lengkap)

═════════════════════════════════════════════════════════════════════════════
SKENARIO PRESENTASI
═════════════════════════════════════════════════════════════════════════════

  Untuk demo live di mana user input sebagian transaksi manual:

  1. python seed_utama.py
  2. [Input 3 jurnal umum pertama MANUAL via UI]
  3. python seed_presentasi_umum.py
     → Lengkapi jurnal umum #4 s/d #13
  4. python seed_presentasi_ajp.py
     → Seed 4 AJP pertama
  5. [Input 2 AJP terakhir MANUAL via UI:
        AJP #5: 412 D / 213 K  Rp 1.333.333
        AJP #6: 512 D / 212 K  Rp 1.215.400]

═════════════════════════════════════════════════════════════════════════════
RESET
═════════════════════════════════════════════════════════════════════════════

  python reset_transaksi.py
  → Hapus semua transaksi & saldo awal, pertahankan CoA + user + periode awal
"""
print(__doc__)
