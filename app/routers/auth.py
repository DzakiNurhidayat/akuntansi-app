from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth import login_user, logout_user, verify_password
from app.templates_env import templates

router = APIRouter(tags=["auth"])


@router.get("/login")
def form_login(request: Request):
    # Kalau sudah login, langsung ke dashboard
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": request.query_params.get("error"),
        "next": request.query_params.get("next", "/"),
    })


@router.post("/login")
def proses_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/", alias="next"),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    user = (
        db.query(User)
        .filter(User.username == username, User.is_active.is_(True))
        .first()
    )

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Username atau password salah.",
                "next": next_url,
                "username": username,
            },
            status_code=401,
        )

    login_user(request, user)

    # Sanitasi next agar hanya path internal (mencegah open-redirect)
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"
    return RedirectResponse(next_url, status_code=303)


@router.get("/logout")
@router.post("/logout")
def proses_logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login?msg=logged_out", status_code=303)
