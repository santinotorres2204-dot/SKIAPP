"""Motor de respuestas del AI Ski Coach Chat.

Por ahora es 100% mock (sin API externa): matchea keywords en el mensaje del
usuario y arma una respuesta con contexto de su perfil (nivel, anos
esquiando, proximo viaje, plan de entrenamiento). La arquitectura ya queda
lista para el reemplazo real -- el router llama a generate_mock_response()
con la misma firma que despues va a llamar a la version con Claude.

# TODO: reemplazar generate_mock_response() con llamada real a Claude API
# anthropic.messages.create(model="claude-opus-4-5", system=SYSTEM_PROMPT, messages=history)
"""

from app.models import User
from app.models.enums import TripStatus

SYSTEM_PROMPT = (
    "Sos el AI Ski Coach de Ski App: un entrenador de ski/snowboard cercano y concreto. "
    "Respondes en espanol rioplatense, con consejos accionables adaptados al nivel, anos "
    "de experiencia y proximo viaje del usuario. Nunca das diagnosticos medicos ni afirmas "
    "causas fisicas con certeza absoluta -- si detectas una lesion o dolor persistente, "
    "sugeris consultar a un profesional."
)


def _next_trip(user: User):
    """Viaje 'preparing' mas cercano en el tiempo, o None si no tiene ninguno."""
    preparing = [t for t in user.trips if t.status == TripStatus.PREPARING.value]
    if not preparing:
        return None
    return min(preparing, key=lambda t: t.start_date)


def generate_mock_response(message: str, user: User) -> str:
    text = message.lower()
    trip = _next_trip(user)
    name = user.name

    if any(k in text for k in ("calentamiento", "entrada en calor")):
        response = (
            f"Dale {name}, para tu nivel {user.ski_level} después de {user.years_skiing} años "
            "esquiando, el calentamiento que más me gusta antes de una jornada es: 5 minutos de "
            "trote suave o bici para subir la frecuencia cardíaca, después movilidad de tobillo y "
            "cadera (círculos, sentadillas con peso corporal), y terminar con 2-3 series de "
            "sentadillas dinámicas y saltos cortos para activar el tren inferior. 10-12 minutos "
            "totales, antes de ponerte las botas."
        )
        if trip:
            response += (
                f" Con {trip.destination} cerca, no te lo saltees el primer día — las piernas frías "
                "son la razón número uno de caídas tempranas."
            )
        return response

    if any(k in text for k in ("rodilla", "pierna", "cuádriceps", "cuadriceps", "sentadilla")):
        return (
            f"{name}, para fortalecer piernas de cara al ski te recomiendo enfocarte en sentadillas "
            "búlgaras (3-4 series de 8-10 por pierna), zancadas laterales con pausa, y elevación de "
            "cadera a una pierna para el glúteo — eso te da estabilidad lateral, que es lo que más se "
            "usa en los giros. Si sentís molestia puntual en la rodilla (no el cansancio normal de "
            "entrenar), mejor consultalo con un profesional antes de cargar más volumen."
        )

    if any(k in text for k in ("carving", "giro", "técnica", "tecnica")):
        response = (
            f"Para tu nivel {user.ski_level}, {name}, en carving lo que más cambia el juego es la "
            "presión progresiva sobre el borde exterior del ski a lo largo de todo el giro, no solo "
            "al principio."
        )
        if user.ski_level in ("principiante", "intermedio"):
            response += (
                " Como todavía estás en ese nivel, enfocate primero en giros amplios y velocidad "
                "controlada antes de buscar más angulación."
            )
        else:
            response += (
                " En tu nivel ya podés buscar más angulación de cadera y separar el movimiento del "
                "tren superior del tren inferior para ganar velocidad en el giro sin perder línea."
            )
        response += " Si subís un video a tu perfil te puedo dar feedback más puntual sobre tu técnica."
        return response

    if any(k in text for k in ("miedo", "pendiente", "vértigo", "vertigo")):
        return (
            f"Te entiendo {name}, el miedo en pendientes pronunciadas es re común, hasta esquiadores "
            "con muchos años lo sienten. Lo que mejor funciona es bajar el ritmo: mirá la pendiente en "
            "segmentos cortos en vez de la bajada completa, respirá profundo antes de largar, y si "
            "hace falta hacé giros más cerrados para controlar la velocidad en vez de ir directo. El "
            "miedo baja con exposición gradual, no forzando el límite de una sola vez."
        )

    if any(k in text for k in ("plan", "rutina", "entrenamiento")):
        if user.training_plans:
            return (
                f"{name}, ya tenés un plan de entrenamiento cargado en tu perfil — lo podés ver en la "
                "sección 'Planes de entrenamiento' de tu Ski Passport. Contame en qué bloque estás y "
                "te doy contexto específico sobre por qué está armado así."
            )
        return (
            f"Todavía no tenés un plan de entrenamiento cargado, {name}. Subí un video esquiando "
            "desde tu perfil para que lo analicemos y arme uno específico para vos."
        )

    if any(k in text for k in ("velocidad", "rápido", "rapido", "freeski")):
        return (
            f"Para ganar velocidad con control, {name}, la progresión que recomiendo es: primero "
            "asegurate de que tu posición (flexión de rodillas, peso centrado) se mantiene estable a "
            "velocidad media antes de buscar más. Después sumás velocidad en pistas que ya conocés "
            "bien, nunca en terreno nuevo. Tu confidence score en tu Ski Card te sirve de referencia "
            "de cuánto margen tenés para progresar sin arriesgar de más."
        )

    trip_note = f" y tu próximo viaje a {trip.destination}" if trip else ""
    return (
        f"Recibí tu consulta, {name}. Estoy revisando tu perfil{trip_note} y te respondo en breve "
        "con algo específico para tu nivel y tu próximo viaje."
    )
