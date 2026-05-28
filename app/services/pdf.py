"""Layanan generate PDF menggunakan xhtml2pdf (pure-Python, tanpa GTK)."""
import io
import os

from xhtml2pdf import pisa
from jinja2 import Environment, FileSystemLoader

from app.templates_env import _rupiah, _abs, _angka

_TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "pdf")
)

_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))
_env.filters["rupiah"] = _rupiah
_env.filters["abs"]    = _abs
_env.filters["angka"]  = _angka


def render_pdf(template_name: str, context: dict) -> bytes:
    """Render Jinja2 template ke PDF bytes menggunakan xhtml2pdf."""
    html_str = _env.get_template(template_name).render(**context)
    buf = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_str), dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError(f"xhtml2pdf error ({result.err}): cek template {template_name}")
    return buf.getvalue()
