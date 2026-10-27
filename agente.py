import json
import anthropic
from dotenv import load_dotenv

from Consulta import buscar_equipos, consultar_historial_equipo, estadisticas_tickets

load_dotenv()

client = anthropic.Anthropic()
MODELO = "claude-sonnet-4-6"

SYSTEM = """Eres un asistente de mantenimiento minero. Respondes en español.
Consultas una base de tickets de equipos (camiones, bulldozers, palas, perforadoras,
motoniveladoras, watertrucks, wheeldozers y wheelloaders).

Reglas:
- Usa solo datos que devuelvan tus herramientas. Si no hay datos, dilo; no inventes.
- Si el usuario nombra un equipo de forma ambigua o no existe, usa buscar_equipos
  y pregunta cuál quiso decir.
- Las duraciones están en minutos. Si hay valores extremos, menciónalo.
- Para estadísticas, prefiere la mediana sobre el promedio cuando haya valores
  extremos, y explica la diferencia si es grande.
- Si tickets_con_duracion es menor que total_tickets, menciónalo.
- Si no se indica un rango de fechas, aclara que el cálculo cubre todos los datos disponibles.
- Los tickets cubren desde 2024-04-23 hasta 2025-02-28. Usa este rango para
  interpretar "el último mes", "este año" o "el último trimestre", y avisa si
  lo que piden queda fuera.
- La base tiene 961 tickets entre 2024-04-23 y 2025-02-28. Unos 458 no están
  asociados a un equipo de flota: son tickets de infraestructura y comunicaciones
  (sitios, antenas, CCTV, radios, carros). Aparecen como 'SIN EQUIPO' al agrupar
  por equipo o tipo. No los llames "fallas de equipos".
- Las duraciones mayores a 30 días se descartan por considerarse errores de
  registro. Si tickets_con_duracion es menor que total_tickets, avísalo.
- Entre abril y agosto de 2024 hay muy pocos registros (1 a 3 por mes). Advierte
  que esos meses no son comparables con los siguientes.
- No expliques causas que no estén en los datos. Si propones una hipótesis,
  di claramente que es una hipótesis."""

TOOLS = [
    {
        "name": "buscar_equipos",
        "description": (
            "Busca códigos de equipo que contengan un texto (máx. 20). Úsala cuando "
            "el usuario no dé un código exacto o pregunte por un tipo de equipo, "
            "por ejemplo 'pala' o '374'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Texto a buscar, ej. 'pala'"}
            },
            "required": ["texto"],
        },
    },
    {
        "name": "consultar_historial_equipo",
        "description": (
            "Devuelve hasta 100 tickets recientes de un equipo (más nuevos primero), "
            "con asunto, fechas, duración en minutos y solución. Requiere el código "
            "del equipo, ej. 'CAMION 374'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "codigo_equipo": {"type": "string", "description": "Ej. 'CAMION 374'"}
            },
            "required": ["codigo_equipo"],
        },
    },
        {
        "name": "estadisticas_tickets",
        "description": (
            "Estadísticas agregadas de tickets (cantidad, promedio, mediana, máximo y "
            "horas totales en minutos/horas), agrupadas por equipo, tipo de equipo o mes. "
            "Úsala para preguntas como 'qué equipos fallan más', 'cuál tipo de equipo "
            "acumula más horas' o 'cómo evolucionan los tickets por mes'. "
            "Para el detalle de UN equipo usa consultar_historial_equipo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agrupar_por": {
                    "type": "string",
                    "enum": ["equipo", "tipo", "mes"],
                    "description": "Cómo agrupar los resultados",
                },
                "ordenar_por": {
                    "type": "string",
                    "enum": ["tickets", "horas_totales", "mediana"],
                    "description": "Criterio de orden, de mayor a menor",
                },
                "tipo_equipo": {
                    "type": "string",
                    "description": "Filtro opcional por tipo: CAMION, PALA, BULLDOZER, "
                                   "PERFORADORA, MOTONIVELADORA, WATERTRUCK, WHEELDOZER, WHEELLOADER",
                },
                "fecha_desde": {"type": "string", "description": "AAAA-MM-DD, opcional"},
                "fecha_hasta": {"type": "string", "description": "AAAA-MM-DD, opcional, inclusiva"},
                "limite": {"type": "integer", "description": "Máximo de filas (1 a 50, por defecto 10)"},
            },
            "required": [],
        },
    },
]

FUNCIONES = {
    "buscar_equipos": buscar_equipos,
    "consultar_historial_equipo": consultar_historial_equipo,
    "estadisticas_tickets": estadisticas_tickets,
}


def ejecutar_herramienta(nombre: str, argumentos: dict) -> tuple[str, bool]:
    """Ejecuta la función pedida. Devuelve (texto, es_error)."""
    try:
        resultado = FUNCIONES[nombre](**argumentos)
        return json.dumps(resultado, default=str, ensure_ascii=False), False
    except Exception as e:
        return f"Error: {e}", True


def responder(mensajes: list, on_tool=None) -> str:
    """Corre el bucle hasta obtener la respuesta final. Modifica 'mensajes'."""
    for _ in range(8):
        respuesta = client.messages.create(
            model=MODELO,
            max_tokens=2000,
            system=SYSTEM,
            tools=TOOLS,
            messages=mensajes,
        )
        mensajes.append({"role": "assistant", "content": respuesta.content})

        if respuesta.stop_reason != "tool_use":
            return "".join(b.text for b in respuesta.content if b.type == "text")

        resultados = []
        for bloque in respuesta.content:
            if bloque.type == "tool_use":
                if on_tool:
                    on_tool(bloque.name, bloque.input)
                texto, es_error = ejecutar_herramienta(bloque.name, bloque.input)
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": bloque.id,
                    "content": texto,
                    "is_error": es_error,
                })
        mensajes.append({"role": "user", "content": resultados})

    return "No pude completar la consulta en el número de pasos permitido."


if __name__ == "__main__":
    mensajes = []
    print("Agente Minera Galaxy (escribe 'salir' para terminar)")
    while True:
        pregunta = input("\nTú: ").strip()
        if pregunta.lower() in ("salir", "exit"):
            break
        if not pregunta:
            continue
        mensajes.append({"role": "user", "content": pregunta})
        print("\nAgente:", responder(mensajes))