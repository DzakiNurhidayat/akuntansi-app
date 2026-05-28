from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def _rupiah(value):
    try:
        n = round(float(value))
        prefix = "Rp " if n >= 0 else "-Rp "
        return f"{prefix}{abs(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


def _abs(value):
    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return 0


def _angka(value):
    """Format angka tanpa prefix Rp — untuk baris data worksheet."""
    try:
        n = round(float(value))
        return f"{abs(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


templates.env.filters["rupiah"] = _rupiah
templates.env.filters["abs"] = _abs
templates.env.filters["angka"] = _angka
