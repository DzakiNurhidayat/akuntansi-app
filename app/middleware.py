"""Middleware autentikasi & otorisasi.

1. AuthMiddleware: blok semua route kecuali public; redirect ke /login.
2. Admin gate: blok /akun/* dan /admin/* untuk non-admin → redirect ke
   dashboard dengan pesan error.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from urllib.parse import quote


# Route yang TIDAK butuh login
PUBLIC_PATHS = {"/login", "/logout", "/api/health"}
PUBLIC_PREFIXES = ("/static/", "/favicon")


def _is_admin_only(path: str) -> bool:
    """Path yang hanya boleh diakses user dengan is_admin=True."""
    if path == "/akun" or path.startswith("/akun/"):
        return True
    if path == "/admin" or path.startswith("/admin/"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        # Static / public — lewat
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        # Cek session
        if not request.session.get("user_id"):
            next_url = path
            if request.url.query:
                next_url = f"{path}?{request.url.query}"
            return RedirectResponse(
                f"/login?next={quote(next_url, safe='')}",
                status_code=303,
            )

        # Cek admin gate
        if _is_admin_only(path) and not request.session.get("is_admin"):
            return RedirectResponse(
                "/?msg=Akses+ditolak+%E2%80%94+hanya+administrator&type=error",
                status_code=303,
            )

        return await call_next(request)
