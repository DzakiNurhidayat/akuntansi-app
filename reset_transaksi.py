"""Reset SELURUH data transaksi tanpa menghapus akun/user/periode awal.

Run: python reset_transaksi.py

Yang DIHAPUS:
  • Semua Transaksi (umum, penyesuaian, penutup, pembalik)
  • Semua JurnalEntry (otomatis lewat CASCADE saat Transaksi dihapus)
  • Semua SaldoAwal (carry-forward periode)
  • Semua Periode TAMBAHAN (yang auto-dibuat saat Tutup Periode); hanya
    periode tertua (April 2008) yang dipertahankan & is_closed di-reset ke False

Yang DIPERTAHANKAN:
  • Tabel Akun (Chart of Accounts) — tidak disentuh
  • Tabel User (login) — tidak disentuh
  • Periode tertua — di-unlock dan dibersihkan

Pakai script ini sebelum re-seed transaksi.
"""
import sys

from app.database import SessionLocal
from app.models import JurnalEntry, Periode, SaldoAwal, Transaksi


def main():
    print("=" * 60)
    print("RESET TRANSAKSI — hapus seluruh data transaksi")
    print("=" * 60)

    db = SessionLocal()

    # Hitung dulu untuk laporan
    n_trx = db.query(Transaksi).count()
    n_entries = db.query(JurnalEntry).count()
    n_saldo_awal = db.query(SaldoAwal).count()
    n_periode = db.query(Periode).count()

    print(f"\nState saat ini:")
    print(f"  • {n_trx:>4} Transaksi")
    print(f"  • {n_entries:>4} JurnalEntry")
    print(f"  • {n_saldo_awal:>4} SaldoAwal")
    print(f"  • {n_periode:>4} Periode")

    if n_trx == 0 and n_saldo_awal == 0 and n_periode <= 1:
        print("\nTidak ada data transaksi untuk dihapus. Periode awal tetap.")
        db.close()
        return

    # Konfirmasi
    print("\n⚠  PERINGATAN:")
    print("   Operasi ini menghapus SEMUA Transaksi + JurnalEntry + SaldoAwal,")
    print("   serta Periode tambahan (selain yang tertua). Tidak bisa di-undo.")
    print()
    jawab = input("   Lanjutkan? Ketik 'RESET' untuk konfirmasi: ").strip()
    if jawab != "RESET":
        print("\nDibatalkan.")
        db.close()
        return

    # ── 1. Hapus semua transaksi (JurnalEntry ikut via CASCADE) ──────────────
    print("\n[1/3] Hapus seluruh Transaksi (JurnalEntry otomatis via CASCADE)...")
    # Pakai bulk delete agar efisien
    for t in db.query(Transaksi).all():
        db.delete(t)
    db.flush()
    print(f"  ✓ {n_trx} transaksi dihapus")

    # ── 2. Hapus semua SaldoAwal ─────────────────────────────────────────────
    print("\n[2/3] Hapus seluruh SaldoAwal...")
    db.query(SaldoAwal).delete()
    db.flush()
    print(f"  ✓ {n_saldo_awal} saldo awal dihapus")

    # ── 3. Hapus periode tambahan, sisakan & unlock periode tertua ───────────
    print("\n[3/3] Reset periode...")
    periodes = (
        db.query(Periode)
        .order_by(Periode.tahun, Periode.bulan)
        .all()
    )
    if not periodes:
        print("  (Tidak ada periode — lewati)")
    else:
        anchor = periodes[0]
        # Hapus periode tambahan
        n_extra = 0
        for p in periodes[1:]:
            db.delete(p)
            n_extra += 1
        # Unlock periode tertua
        was_closed = anchor.is_closed
        anchor.is_closed = False
        print(f"  ✓ {n_extra} periode tambahan dihapus")
        print(f"  ✓ Periode tertua dipertahankan: {anchor.bulan}/{anchor.tahun} — {anchor.nama_perusahaan}"
              f" (is_closed: {was_closed} → False)")

    db.commit()
    db.close()

    print()
    print("=" * 60)
    print("RESET SELESAI. Sekarang bisa jalankan:")
    print("  • python seed_transaksi_umum.py")
    print("  • python seed_transaksi_lengkap.py")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDibatalkan (Ctrl+C).")
        sys.exit(130)
