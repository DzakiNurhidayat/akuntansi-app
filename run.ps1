param(
    [switch]$seed,
    [switch]$reset
)

$PORT = 8000
$URL = "http://127.0.0.1:$PORT"
$DB_FILE = "cleaning_service.db"

# Aktifkan venv
if (Test-Path "venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
} else {
    Write-Error "venv tidak ditemukan. Jalankan: python -m venv venv && pip install -r requirements.txt"
    exit 1
}

# Handle flags
if ($reset) {
    Write-Host ">>> Menghapus database lama..."
    Remove-Item -Force $DB_FILE -ErrorAction SilentlyContinue
    Write-Host ">>> Seeding database..."
    python seed_data.py
}
elseif ($seed) {
    Write-Host ">>> Seeding database..."
    python seed_data.py
}

# Buka browser setelah server siap (background job)
Start-Job -ScriptBlock {
    param($url)
    Start-Sleep -Seconds 3
    for ($i = 0; $i -lt 15; $i++) {
        try {
            $res = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
            Write-Host ">>> Server siap! Membuka browser: $url"
            Start-Process $url
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
} -ArgumentList $URL | Out-Null

Write-Host ">>> Menjalankan server di $URL (Ctrl+C untuk stop)"
uvicorn app.main:app --reload --port $PORT
