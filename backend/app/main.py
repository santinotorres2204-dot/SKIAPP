from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine

app = FastAPI(title="Ski App API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
