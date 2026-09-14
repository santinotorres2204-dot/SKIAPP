import enum


def sql_in_values(enum_cls: type[enum.Enum]) -> str:
    """Arma la lista de valores para un CHECK ... IN (...) a partir de un enum.

    Se usa en vez de un tipo ENUM nativo de Postgres para mantener las
    migraciones simples y portables (evita el manejo de alta/baja de tipos
    ENUM en Alembic); la validez del valor se refuerza igual a nivel DB
    con un CHECK constraint.
    """
    return ", ".join(f"'{v.value}'" for v in enum_cls)


class SkiLevel(str, enum.Enum):
    PRINCIPIANTE = "principiante"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"
    EXPERTO = "experto"


class TripStatus(str, enum.Enum):
    PREPARING = "preparing"
    COMPLETED = "completed"


class Discipline(str, enum.Enum):
    CARVING = "carving"
    FREERIDE = "freeride"
    PARK = "park"
    POWDER = "powder"
    MOGULS = "moguls"
    ALL_MOUNTAIN = "all_mountain"


class TerrainTag(str, enum.Enum):
    PISTA_PISADA = "pista_pisada"
    POWDER = "powder"
    HIELO = "hielo"
    MIXTO = "mixto"


class SportType(str, enum.Enum):
    SKI = "ski"
    SNOWBOARD = "snowboard"


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class PatternSeverity(str, enum.Enum):
    """Mismas 3 clases que ya usa la deteccion heuristica (ver
    ai-analysis/analyze_ski_video.py, _severity_from_thresholds) -- se
    reusan aca para que la evaluacion manual del instructor (InstructorEvaluation)
    sea directamente comparable contra el severity que devuelve la IA."""

    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
