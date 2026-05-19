"""
Script untuk populate Chart of Accounts, Periode, dan Transaksi awal.
Run: python seed_data.py
"""
from datetime import date
from app.database import engine, SessionLocal, Base
from app.models import Akun, Periode, Transaksi, JurnalEntry

# Buat semua tabel
print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Tables created.")

db = SessionLocal()

# ====== Chart of Accounts dari soal Cleaning Service ======
akun_data = [
    # Aset
    {"kode_akun": "111", "nama_akun": "Kas", "nama_akun_en": "Cash",
     "jenis_akun": "aset", "saldo_normal": "debet"},
    {"kode_akun": "112", "nama_akun": "Piutang Usaha", "nama_akun_en": "Account Receivable",
     "jenis_akun": "aset", "saldo_normal": "debet"},
    {"kode_akun": "113", "nama_akun": "Perlengkapan", "nama_akun_en": "Supplies",
     "jenis_akun": "aset", "saldo_normal": "debet"},
    {"kode_akun": "114", "nama_akun": "Sewa Dibayar Dimuka", "nama_akun_en": "Prepaid Rent",
     "jenis_akun": "aset", "saldo_normal": "debet"},
    {"kode_akun": "121", "nama_akun": "Peralatan", "nama_akun_en": "Equipment",
     "jenis_akun": "aset", "saldo_normal": "debet"},
    {"kode_akun": "122", "nama_akun": "Akumulasi Penyusutan Peralatan",
     "nama_akun_en": "Accumulated Depreciation - Equipment",
     "jenis_akun": "aset", "saldo_normal": "kredit", "is_kontra": True},

    # Kewajiban
    {"kode_akun": "211", "nama_akun": "Hutang Usaha", "nama_akun_en": "Account Payable",
     "jenis_akun": "kewajiban", "saldo_normal": "kredit"},
    {"kode_akun": "212", "nama_akun": "Hutang Gaji", "nama_akun_en": "Salaries Payable",
     "jenis_akun": "kewajiban", "saldo_normal": "kredit"},
    {"kode_akun": "213", "nama_akun": "Pendapatan Diterima Dimuka",
     "nama_akun_en": "Unearned Revenue",
     "jenis_akun": "kewajiban", "saldo_normal": "kredit"},

    # Modal
    {"kode_akun": "311", "nama_akun": "Modal Tuan Supriana", "nama_akun_en": "Supriana, Capital",
     "jenis_akun": "modal", "saldo_normal": "kredit"},
    {"kode_akun": "312", "nama_akun": "Prive Tuan Supriana", "nama_akun_en": "Supriana, Drawing",
     "jenis_akun": "modal", "saldo_normal": "debet", "is_kontra": True},
    {"kode_akun": "313", "nama_akun": "Ikhtisar Laba Rugi", "nama_akun_en": "Income Summary",
     "jenis_akun": "modal", "saldo_normal": "kredit"},

    # Pendapatan
    {"kode_akun": "411", "nama_akun": "Pendapatan Jasa", "nama_akun_en": "Service Revenue",
     "jenis_akun": "pendapatan", "saldo_normal": "kredit"},
    {"kode_akun": "412", "nama_akun": "Pendapatan Sewa Mesin", "nama_akun_en": "Rent Machine Revenue",
     "jenis_akun": "pendapatan", "saldo_normal": "kredit"},

    # Beban
    {"kode_akun": "511", "nama_akun": "Beban Sewa", "nama_akun_en": "Rent Expense",
     "jenis_akun": "beban", "saldo_normal": "debet"},
    {"kode_akun": "512", "nama_akun": "Beban Gaji", "nama_akun_en": "Salaries Expense",
     "jenis_akun": "beban", "saldo_normal": "debet"},
    {"kode_akun": "513", "nama_akun": "Beban Air, Listrik, Telepon",
     "nama_akun_en": "Water, Electric, Telephone Expense",
     "jenis_akun": "beban", "saldo_normal": "debet"},
    {"kode_akun": "514", "nama_akun": "Beban Serba-Serbi", "nama_akun_en": "Other Expense",
     "jenis_akun": "beban", "saldo_normal": "debet"},
    {"kode_akun": "515", "nama_akun": "Beban Perlengkapan", "nama_akun_en": "Supplies Expense",
     "jenis_akun": "beban", "saldo_normal": "debet"},
    {"kode_akun": "516", "nama_akun": "Beban Penyusutan Peralatan",
     "nama_akun_en": "Depreciation Expense - Equipment",
     "jenis_akun": "beban", "saldo_normal": "debet"},
]

existing = db.query(Akun).count()
if existing > 0:
    print(f"Akun sudah ada ({existing} record). Skip seeding akun.")
else:
    print("Seeding akun...")
    for data in akun_data:
        db.add(Akun(**data))
    db.commit()
    print(f"Seeded {len(akun_data)} akun.")

# ====== Periode default ======
existing_periode = db.query(Periode).count()
if existing_periode == 0:
    print("Creating default periode...")
    periode = Periode(nama_perusahaan="Cleaning Service", tahun=2008, bulan=4)
    db.add(periode)
    db.commit()
    print(f"Periode created: {periode}")
else:
    print(f"Periode sudah ada ({existing_periode} record).")

# ====== Transaksi & Jurnal Entry April 2008 ======
existing_trx = db.query(Transaksi).count()
if existing_trx > 0:
    print(f"Transaksi sudah ada ({existing_trx} record). Skip seeding transaksi.")
else:
    periode = db.query(Periode).filter_by(tahun=2008, bulan=4).first()

    def trx(tanggal, keterangan, jenis, entries):
        t = Transaksi(
            periode_id=periode.id,
            tanggal=date.fromisoformat(tanggal),
            keterangan=keterangan,
            jenis=jenis,
        )
        db.add(t)
        db.flush()  # dapat t.id
        for urutan, (kode, debet, kredit) in enumerate(entries):
            db.add(JurnalEntry(
                transaksi_id=t.id,
                kode_akun=kode,
                debet=debet,
                kredit=kredit,
                urutan=urutan,
            ))

    print("Seeding transaksi...")

    # ── Jurnal Umum ──────────────────────────────────────────────────────────
    trx("2008-04-01", "Modal Awal Tn Supriana", "umum", [
        ("111", 75_000_000, 0),
        ("311", 0, 75_000_000),
    ])
    trx("2008-04-05", "Sewa Ruangan untuk 6 Bulan", "umum", [
        ("511", 7_500_000, 0),
        ("111", 0, 7_500_000),
    ])
    trx("2008-04-08", "Dibeli Perlengkapan Kantor Secara Tunai", "umum", [
        ("113", 9_000_000, 0),
        ("111", 0, 9_000_000),
    ])
    trx("2008-04-10", "Dibeli Peralatan Kantor Secara Kredit", "umum", [
        ("121", 9_000_000, 0),
        ("211", 0, 9_000_000),
    ])
    trx("2008-04-14", "Prive", "umum", [
        ("312", 3_500_000, 0),
        ("111", 0, 3_500_000),
    ])
    trx("2008-04-17", "Bayar Gaji Karyawan", "umum", [
        ("512", 2_750_000, 0),
        ("111", 0, 2_750_000),
    ])
    trx("2008-04-19", "Pendapatan Jasa Secara Kredit", "umum", [
        ("112", 7_500_000, 0),
        ("411", 0, 7_500_000),
    ])
    trx("2008-04-21", "Beban lain-lain", "umum", [
        ("514", 1_500_000, 0),
        ("111", 0, 1_500_000),
    ])
    trx("2008-04-23", "Pendapatan Jasa Secara Tunai", "umum", [
        ("111", 3_000_000, 0),
        ("411", 0, 3_000_000),
    ])
    trx("2008-04-25", "Bayar Utang Usaha", "umum", [
        ("211", 3_000_000, 0),
        ("111", 0, 3_000_000),
    ])
    trx("2008-04-27", "Diterima Pendapatan Sewa Mesin Untuk 3 Bulan", "umum", [
        ("111", 2_000_000, 0),
        ("412", 0, 2_000_000),
    ])
    trx("2008-04-28", "Diterima Piutang Usaha", "umum", [
        ("111", 4_000_000, 0),
        ("112", 0, 4_000_000),
    ])
    trx("2008-04-30", "Bayar Utilitas", "umum", [
        ("513", 1_250_000, 0),
        ("111", 0, 1_250_000),
    ])

    # ── Jurnal Penyesuaian ───────────────────────────────────────────────────
    # AJP 1: Beban perlengkapan (sisa fisik Rp 8.547.200 dari saldo Rp 9.000.000)
    trx("2008-04-30", "Beban Perlengkapan (sisa Rp 8.547.200)", "penyesuaian", [
        ("515", 452_800, 0),
        ("113", 0, 452_800),
    ])
    # AJP 2: Penyusutan peralatan (9.000.000 / 24 bulan = Rp 375.000)
    trx("2008-04-30", "Penyusutan Peralatan (garis lurus 2 tahun)", "penyesuaian", [
        ("516", 375_000, 0),
        ("122", 0, 375_000),
    ])

    db.commit()
    print("Seeded 13 transaksi umum + 2 transaksi penyesuaian.")

db.close()
print("\nSeed selesai!")
