"""Migrasi schema idempotent untuk perubahan struktur DB.

Dipanggil oleh `app.main` saat startup. Aman dijalankan berulang kali —
hanya menambahkan kolom/tabel yang belum ada.
"""
from sqlalchemy import inspect, text


def apply_migrations(engine):
    """Apply ALTER statements untuk schema changes yang belum di-apply."""
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    if not existing_tables:
        return  # DB kosong, create_all akan handle dari awal

    with engine.connect() as conn:
        # Migration: user.is_admin (Boolean)
        if "user" in existing_tables:
            cols = {c["name"] for c in insp.get_columns("user")}
            if "is_admin" not in cols:
                print("[MIGRATE] Adding column user.is_admin")
                conn.execute(text(
                    "ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
                ))

        # Migration: akun.is_universal (Boolean)
        if "akun" in existing_tables:
            cols = {c["name"] for c in insp.get_columns("akun")}
            if "is_universal" not in cols:
                print("[MIGRATE] Adding column akun.is_universal")
                conn.execute(text(
                    "ALTER TABLE akun ADD COLUMN is_universal BOOLEAN NOT NULL DEFAULT 0"
                ))

        conn.commit()
