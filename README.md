# Cleaning Service Accounting App

Aplikasi akuntansi siklus lengkap untuk perusahaan jasa (*Cleaning Service April 2008*), dibuat sebagai tugas kuliah **Pengantar Akuntansi — JTK D3C Kelompok 1**.

Aplikasi mengotomasi proses yang tadinya manual:

> Jurnal Umum → Buku Besar → Neraca Saldo → AJP → Kertas Kerja → Laporan Keuangan → Jurnal Penutup

---

## Teknologi

| Layer | Stack |
|-------|-------|
| Backend | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.0 |
| Template | Jinja2 (server-side rendering) |
| Database | SQLite (dev) / PostgreSQL via Supabase (prod) |
| Frontend | HTML + CSS vanilla, tanpa framework JS |

---

## Cara Menjalankan (Development)

### 1. Clone repository

```bash
git clone <url-repo>
cd akuntansi
```

### 2. Buat dan aktifkan virtual environment

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate.bat

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Seed database (hanya pertama kali)

```bash
python seed_data.py
```

Script ini akan membuat:
- 20 akun (Chart of Accounts)
- 1 periode (Cleaning Service, April 2008)
- 13 transaksi jurnal umum
- 2 transaksi jurnal penyesuaian (AJP)

### 5. Jalankan server

```bash
uvicorn app.main:app --reload
```

### 6. Buka di browser

```
http://127.0.0.1:8000
```

---

## Reset Database

Matikan server terlebih dahulu, lalu:

```bash
# Linux / macOS
rm cleaning_service.db
python seed_data.py

# Windows PowerShell
Remove-Item cleaning_service.db
python seed_data.py
```

---

## Struktur Folder

```
akuntansi/
│
├── app/                        # Package utama aplikasi
│   ├── main.py                 # Entry point FastAPI, mount router
│   ├── database.py             # Koneksi SQLAlchemy, get_db dependency
│   ├── templates_env.py        # Shared Jinja2 instance + filter rupiah
│   │
│   ├── models/                 # ORM models (SQLAlchemy)
│   │   ├── akun.py             # Tabel akun (Chart of Accounts)
│   │   ├── periode.py          # Tabel periode (bulan/tahun aktif)
│   │   ├── transaksi.py        # Tabel transaksi
│   │   └── jurnal_entry.py     # Tabel jurnal_entry (baris debet/kredit)
│   │
│   ├── routers/                # Route handler FastAPI
│   │   ├── akun.py             # CRUD akun (/akun)
│   │   ├── transaksi.py        # Input transaksi (/transaksi)
│   │   └── laporan.py          # Laporan: JU, BB, NS (/laporan)
│   │
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html           # Layout utama (navbar, footer)
│   │   ├── akun/
│   │   │   ├── list.html       # Daftar akun
│   │   │   └── form.html       # Form tambah/edit akun
│   │   ├── transaksi/
│   │   │   ├── list.html       # Daftar transaksi
│   │   │   └── form.html       # Form input/edit transaksi
│   │   └── laporan/
│   │       ├── _filter_bar.html    # Komponen filter periode (include)
│   │       ├── jurnal_umum.html    # Halaman Jurnal Umum
│   │       ├── buku_besar.html     # Halaman Buku Besar
│   │       └── neraca_saldo.html   # Halaman Neraca Saldo
│   │
│   ├── static/
│   │   └── css/
│   │       └── style.css       # Stylesheet utama
│   │
│   ├── schemas/                # Pydantic schemas (reserved, belum dipakai)
│   └── services/               # Business logic layer (reserved)
│
├── seed_data.py                # Script seed CoA, periode, dan transaksi
├── requirements.txt            # Daftar dependencies Python
├── .env.example                # Contoh konfigurasi environment
└── .gitignore
```

---

## Struktur Database

```
akun           → kode_akun (PK), nama_akun, jenis_akun, saldo_normal, is_kontra, is_active
periode        → id, nama_perusahaan, tahun, bulan, is_closed
transaksi      → id, periode_id (FK), tanggal, keterangan, jenis*
jurnal_entry   → id, transaksi_id (FK), kode_akun (FK), debet, kredit, urutan
```

> \* `jenis`: `umum` | `penyesuaian` | `penutup` | `pembalik`

---

## Fitur yang Sudah Tersedia

- [x] Chart of Accounts (CRUD)
- [x] Input transaksi jurnal umum & penyesuaian
- [x] Jurnal Umum (dengan pagination per transaksi)
- [x] Buku Besar (dengan REF ke halaman Jurnal Umum)
- [x] Neraca Saldo
- [ ] Kertas Kerja (Worksheet)
- [ ] Laporan Keuangan (L/R, Perubahan Modal, Neraca)
- [ ] Jurnal Penutup (auto-generate)
- [ ] Deploy ke Render + Supabase
