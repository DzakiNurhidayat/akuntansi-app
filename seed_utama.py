"""Seeder Utama — Chart of Accounts, Periode awal, dan User login.

Run: python seed_utama.py

Idempotent: aman dijalankan berkali-kali; akan SKIP data yang sudah ada,
SERTA upgrade flag yang baru (mis. is_admin pada admin user, is_universal
pada akun Kas) bila kolom-nya baru ditambahkan oleh migrasi.

Jalankan SEKALI dulu sebelum seeder transaksi.
"""
from app.database import Base, SessionLocal, engine
from app.migrations import apply_migrations
from app.models import Akun, Periode, User
from app.services.auth import hash_password


# ──────────────────────────────────────────────────────────────────────────────
# 0. Buat semua tabel
# ──────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("SEEDER UTAMA — Chart of Accounts, Periode, User")
print("=" * 60)
print("Applying migrations (kolom baru ke tabel existing)...")
apply_migrations(engine)
print("Creating tables (jika belum ada)...")
Base.metadata.create_all(bind=engine)
print("  ✓ Schema OK")

db = SessionLocal()

# ──────────────────────────────────────────────────────────────────────────────
# 1. Chart of Accounts (sesuai soal Cleaning Service April 2008)
# ──────────────────────────────────────────────────────────────────────────────
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

n_akun = db.query(Akun).count()
if n_akun:
    print(f"\n[1/3] Akun sudah ada ({n_akun} record). Skip.")
else:
    print(f"\n[1/3] Seeding Chart of Accounts...")
    for data in akun_data:
        db.add(Akun(**data))
    db.commit()
    print(f"  ✓ {len(akun_data)} akun di-seed")


# ──────────────────────────────────────────────────────────────────────────────
# 2. Periode default
# ──────────────────────────────────────────────────────────────────────────────
existing_periode = db.query(Periode).count()
if existing_periode:
    print(f"\n[2/3] Periode sudah ada ({existing_periode} record). Skip.")
else:
    print(f"\n[2/3] Seeding periode awal...")
    periode = Periode(nama_perusahaan="Perusahaan Jasa", tahun=2008, bulan=4)
    db.add(periode)
    db.commit()
    print(f"  ✓ Periode April 2008 — Perusahaan Jasa")


# ──────────────────────────────────────────────────────────────────────────────
# 3. User login default
# ──────────────────────────────────────────────────────────────────────────────
# Edit list ini untuk menambah/mengubah akun login. Tidak ada form pendaftaran di UI.
user_data = [
    {"username": "admin",    "password": "admin123",    "nama": "Administrator", "is_admin": True},
    {"username": "supriana", "password": "supriana123", "nama": "Tuan Supriana", "is_admin": False},
]

existing_users = db.query(User).count()
if existing_users:
    print(f"\n[3/3] User sudah ada ({existing_users} record). Skip seeding.")
else:
    print(f"\n[3/3] Seeding user login...")
    for u in user_data:
        db.add(User(
            username=u["username"].lower(),
            password_hash=hash_password(u["password"]),
            nama=u["nama"],
            is_active=True,
            is_admin=u["is_admin"],
        ))
    db.commit()
    print(f"  ✓ {len(user_data)} user di-seed:")
    for u in user_data:
        role = "👑 admin" if u["is_admin"] else "regular"
        print(f"      • {u['username']:12s} / {u['password']:14s} ({u['nama']:18s}) — {role}")


# ──────────────────────────────────────────────────────────────────────────────
# 4. Upgrade idempotent — pasang flag is_admin & is_universal kalau belum di-set
# ──────────────────────────────────────────────────────────────────────────────
# Setelah migrasi menambahkan kolom is_admin & is_universal dengan default 0,
# data lama perlu di-upgrade. Idempotent: skip kalau sudah di-set.
print("\n[upgrade] Memeriksa flag is_admin & is_universal...")

admin_user = db.query(User).filter(User.username == "admin").first()
if admin_user and not admin_user.is_admin:
    admin_user.is_admin = True
    print(f"  ✓ User 'admin' di-mark is_admin=True")

kas = db.query(Akun).filter(Akun.kode_akun == "111").first()
if kas and not kas.is_universal:
    kas.is_universal = True
    print(f"  ✓ Akun 111 (Kas) di-mark is_universal=True (bisa dipakai semua user)")

db.commit()
db.close()

print()
print("=" * 60)
print("SELESAI. Langkah berikutnya (opsional):")
print("  • python seed_transaksi_umum.py     — seed jurnal umum saja")
print("  • python seed_transaksi_lengkap.py  — seed sampai jurnal penyesuaian")
print("=" * 60)
