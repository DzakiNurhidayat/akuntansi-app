from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def _rupiah(value):
    try:
        n = int(value)
        return f"Rp {n:,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


templates.env.filters["rupiah"] = _rupiah
