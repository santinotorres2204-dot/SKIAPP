from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.users import get_user_or_404

router = APIRouter(tags=["ride"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/ride")
def ride_page(request: Request, user_id: int | None = None, db: Session = Depends(get_db)):
    """Ride Mode (PWA): tracking de bajadas por GPS. Sin login todavia (ver
    app/routers/passport.py) -- el link de navegacion pasa ?user_id=, pero el
    manifest.json declara start_url=/ride sin query string (asi lo pide una
    PWA instalada), asi que si no viene user_id caemos al primer usuario
    registrado en vez de romper el arranque desde el ícono de la home."""
    if user_id is not None:
        user = get_user_or_404(db, user_id)
    else:
        user = db.query(User).order_by(User.id).first()
        if user is None:
            return RedirectResponse(url="/register", status_code=303)

    return templates.TemplateResponse(request, "ride.html", {"user": user})
