from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models import DayLog
from app.schemas.achievement import AchievementStatus


@dataclass(frozen=True)
class _DayLogStats:
    days_logged: int
    max_speed_kmh: float
    max_distance_km: float


@dataclass(frozen=True)
class _Achievement:
    id: str
    title: str
    description: str
    check: Callable[[_DayLogStats], bool]


# Logros predefinidos (spec seccion 7 etapa 2): se calculan on-the-fly a
# partir de los DayLogs del usuario, no se persisten. Agregar uno nuevo es
# sumar una entrada aca -- no requiere migracion.
ACHIEVEMENTS: list[_Achievement] = [
    _Achievement(
        id="velocidad_80",
        title="80+ km/h alcanzados",
        description="Llegaste a los 80 km/h o mas en una bajada.",
        check=lambda s: s.max_speed_kmh >= 80,
    ),
    _Achievement(
        id="diez_dias_acumulados",
        title="10 dias de ski acumulados",
        description="Sumaste 10 o mas jornadas de ski registradas en total.",
        check=lambda s: s.days_logged >= 10,
    ),
    _Achievement(
        id="cuarenta_km_en_un_dia",
        title="40+ km en un solo dia",
        description="Hiciste 40 km o mas en una unica jornada.",
        check=lambda s: s.max_distance_km >= 40,
    ),
]


def _compute_stats(day_logs: list[DayLog]) -> _DayLogStats:
    if not day_logs:
        return _DayLogStats(days_logged=0, max_speed_kmh=0.0, max_distance_km=0.0)
    return _DayLogStats(
        days_logged=len(day_logs),
        max_speed_kmh=max(d.max_speed_kmh for d in day_logs),
        max_distance_km=max(d.distance_km for d in day_logs),
    )


def compute_achievements(day_logs: list[DayLog]) -> list[AchievementStatus]:
    stats = _compute_stats(day_logs)
    return [
        AchievementStatus(id=a.id, title=a.title, description=a.description, earned=a.check(stats))
        for a in ACHIEVEMENTS
    ]
