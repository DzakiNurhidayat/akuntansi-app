#!/bin/bash

# ============================================================
# run.sh — Jalankan aplikasi Cleaning Service Accounting
# Usage:
#   ./run.sh          → run server, buka browser
#   ./run.sh --seed   → seed ulang DB, run server, buka browser
#   ./run.sh --reset  → hapus DB, seed ulang, run server, buka browser
# ============================================================

PORT=8000
URL="http://127.0.0.1:$PORT"
DB_FILE="cleaning_service.db"

# Tentukan path venv (Windows Git Bash vs Linux/Mac)
if [[ -f "venv/Scripts/activate" ]]; then
    ACTIVATE="venv/Scripts/activate"
elif [[ -f "venv/bin/activate" ]]; then
    ACTIVATE="venv/bin/activate"
else
    echo "ERROR: virtual environment tidak ditemukan. Jalankan: python -m venv venv && pip install -r requirements.txt"
    exit 1
fi

source "$ACTIVATE"

# Handle flags
if [[ "$1" == "--reset" ]]; then
    echo ">>> Menghapus database lama..."
    rm -f "$DB_FILE"
    echo ">>> Seeding database..."
    python seed_data.py || { echo "ERROR: seed_data.py gagal"; exit 1; }
elif [[ "$1" == "--seed" ]]; then
    echo ">>> Seeding database..."
    python seed_data.py || { echo "ERROR: seed_data.py gagal"; exit 1; }
fi

# Buka browser setelah server siap (background)
(
    echo ">>> Menunggu server siap..."
    for i in $(seq 1 20); do
        sleep 1
        if curl -s "$URL" > /dev/null 2>&1; then
            echo ">>> Server siap! Membuka browser: $URL"
            # Windows Git Bash
            if command -v start > /dev/null 2>&1; then
                start "$URL"
            # Linux
            elif command -v xdg-open > /dev/null 2>&1; then
                xdg-open "$URL"
            # macOS
            elif command -v open > /dev/null 2>&1; then
                open "$URL"
            fi
            break
        fi
    done
) &

echo ">>> Menjalankan server di $URL (Ctrl+C untuk stop)"
uvicorn app.main:app --reload --port "$PORT"
