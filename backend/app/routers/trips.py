import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DayLog, Trip, TripParticipant, User
from app.models.enums import TripStatus
from app.routers.users import get_user_or_404
from app.schemas.trip import TripCreate, TripJoinRequest, TripRankingEntry, TripRead, TripUpdate

router = APIRouter(tags=["trips"])

# Sin 0/O/1/I para evitar confusiones al dictar o tipear el codigo a mano.
_JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_join_code() -> str:
    return "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(6))


def get_trip_or_404(db: Session, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado")
    return trip


@router.post("/users/{user_id}/trips", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(user_id: int, payload: TripCreate, db: Session = Depends(get_db)) -> Trip:
    get_user_or_404(db, user_id)
    trip = Trip(user_id=user_id, destination=payload.destination, start_date=payload.start_date)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/users/{user_id}/trips", response_model=list[TripRead])
def list_user_trips(user_id: int, db: Session = Depends(get_db)) -> list[Trip]:
    get_user_or_404(db, user_id)
    return db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.created_at.desc()).all()


@router.get("/trips/{trip_id}", response_model=TripRead)
def get_trip(trip_id: int, db: Session = Depends(get_db)) -> Trip:
    return get_trip_or_404(db, trip_id)


@router.patch("/trips/{trip_id}", response_model=TripRead)
def update_trip(trip_id: int, payload: TripUpdate, db: Session = Depends(get_db)) -> Trip:
    trip = get_trip_or_404(db, trip_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trip, field, getattr(value, "value", value))
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/trips/{trip_id}/complete", response_model=TripRead)
def complete_trip(trip_id: int, db: Session = Depends(get_db)) -> Trip:
    """Marca un viaje como completado (spec seccion 5, paso 8). Equivalente a
    PATCH /trips/{trip_id} con {"status": "completed"}, expuesto aparte
    porque es la accion puntual que dispara el flujo de Season Review.
    """
    trip = get_trip_or_404(db, trip_id)
    trip.status = TripStatus.COMPLETED.value
    db.commit()
    db.refresh(trip)
    return trip


# ---------------------------------------------------------------------------
# Social Ride (spec seccion 7 etapa 2): codigo de invitacion, sumarse a un
# viaje ajeno, y ranking comparando los DayLogs de los participantes.
# ---------------------------------------------------------------------------

@router.post("/trips/{trip_id}/join-code", response_model=TripRead)
def get_or_create_join_code(trip_id: int, db: Session = Depends(get_db)) -> Trip:
    """Genera el codigo corto para invitar participantes, o devuelve el que
    ya existia -- no lo regenera para no invalidar links ya compartidos."""
    trip = get_trip_or_404(db, trip_id)
    if trip.join_code:
        return trip

    for _ in range(5):
        trip.join_code = _generate_join_code()
        db.add(trip)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
    else:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo generar un codigo unico")

    db.refresh(trip)
    return trip


@router.post("/users/{user_id}/trips/join", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def join_trip(user_id: int, payload: TripJoinRequest, db: Session = Depends(get_db)) -> Trip:
    get_user_or_404(db, user_id)
    trip = db.query(Trip).filter(Trip.join_code == payload.code.strip().upper()).first()
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Codigo de invitacion invalido")
    if user_id in trip.participant_user_ids:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Ya formas parte de este viaje")

    db.add(TripParticipant(trip_id=trip.id, user_id=user_id))
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/trips/{trip_id}/ranking", response_model=list[TripRankingEntry])
def get_trip_ranking(trip_id: int, db: Session = Depends(get_db)) -> list[TripRankingEntry]:
    """Compara los DayLogs de todos los participantes del viaje: km totales,
    desnivel total, velocidad maxima alcanzada y dias cargados. Solo incluye
    a quienes ya cargaron al menos un DayLog."""
    get_trip_or_404(db, trip_id)
    rows = (
        db.query(
            DayLog.user_id,
            User.name.label("user_name"),
            func.sum(DayLog.distance_km).label("total_km"),
            func.sum(DayLog.elevation_gain_m).label("total_elevation_m"),
            func.max(DayLog.max_speed_kmh).label("max_speed_kmh"),
            func.count(DayLog.id).label("days_logged"),
        )
        .join(User, User.id == DayLog.user_id)
        .filter(DayLog.trip_id == trip_id)
        .group_by(DayLog.user_id, User.name)
        .order_by(func.sum(DayLog.distance_km).desc())
        .all()
    )
    return [TripRankingEntry(**row._mapping) for row in rows]
