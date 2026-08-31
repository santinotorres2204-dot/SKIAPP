from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Trip
from app.routers.users import get_user_or_404
from app.schemas.trip import TripCreate, TripRead, TripUpdate

router = APIRouter(tags=["trips"])


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
