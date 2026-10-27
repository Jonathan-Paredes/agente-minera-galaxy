import os
import re
import unicodedata
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, timedelta

# Lee el archivo .env y carga las variables
load_dotenv()


def obtener_conexion():
    """Crea y devuelve una conexión de solo lectura a la base de datos."""
    conexion = psycopg2.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "Galaxy_mina"),
        user=os.environ.get("DB_USER"),
        password=os.environ["DB_PASSWORD"],
        options="-c statement_timeout=5000",
    )
    conexion.set_session(readonly=True)
    return conexion


def normalizar_codigo(texto: str) -> str:
    """Convierte lo que escribe el usuario al formato de la base: 'CAMION 374'."""
    # 1. Quitar tildes
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    # 2. Mayúsculas
    texto = texto.upper()

    # 3. Separar letra pegada a número: 'CAMION374' -> 'CAMION 374'
    texto = re.sub(r"([A-Z])(\d)", r"\1 \2", texto)

    # 4. Colapsar espacios múltiples y recortar bordes
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def buscar_equipos(texto: str) -> list[str]:
    """Lista códigos de equipo que contienen el texto buscado (máx. 20)."""
    texto = normalizar_codigo(texto)

    if not texto:
        raise ValueError("Debes indicar un texto de búsqueda.")

    # Escapar comodines para que '%' o '_' del usuario se traten como texto normal
    texto = texto.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")

    sql = """
        SELECT DISTINCT equipo_codigo
        FROM galaxy_dw.dim_equipo
        WHERE equipo_codigo ILIKE %s
        ORDER BY equipo_codigo
        LIMIT 20;
    """

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, (f"%{texto}%",))
            return [fila[0] for fila in cursor.fetchall()]
    finally:
        conexion.close()


def consultar_historial_equipo(codigo_equipo: str) -> list[dict]:
    """Devuelve el historial de tickets de un equipo en formato de diccionarios."""
    codigo_equipo = codigo_equipo.strip()

    if not codigo_equipo:
        raise ValueError("Debes indicar el código del equipo.")

    sql = """
        SELECT
            f.numero_ticket,
            e.equipo_codigo,
            f.asunto,
            f.ts_creacion,
            f.ts_cierre,
            f.duracion_min AS duracion_almacenada_min,
            CASE
                WHEN f.duracion_min IS NOT NULL
                    THEN f.duracion_min
                WHEN f.ts_creacion IS NOT NULL
                   AND f.ts_cierre IS NOT NULL
                   AND f.ts_cierre >= f.ts_creacion
                    THEN EXTRACT(EPOCH FROM (f.ts_cierre - f.ts_creacion)) / 60
                ELSE NULL
            END AS duracion_utilizable_min,
            f.solucion
        FROM galaxy_dw.fact_tickets AS f
        JOIN galaxy_dw.dim_equipo AS e
            ON f.equipo_key = e.equipo_key
        WHERE TRIM(e.equipo_codigo) = %s
        ORDER BY f.ts_creacion DESC
        LIMIT 100;
    """

    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (codigo_equipo,))
            resultados = cursor.fetchall()

        return [dict(fila) for fila in resultados]
    finally:
        conexion.close()

AGRUPACIONES = {
    "equipo": "COALESCE(e.equipo_codigo, 'SIN EQUIPO')",
    "tipo": "COALESCE(split_part(e.equipo_codigo, ' ', 1), 'SIN EQUIPO')",
    "mes": "to_char(date_trunc('month', f.ts_creacion), 'YYYY-MM')",
}

ORDENES = {
    "tickets": "total_tickets",
    "horas_totales": "horas_totales",
    "mediana": "mediana_min",
}

DURACION_SQL = """
    CASE
        WHEN f.duracion_min IS NOT NULL
         AND f.duracion_min <= 43200
            THEN f.duracion_min
        WHEN f.duracion_min IS NULL
         AND f.ts_creacion IS NOT NULL
         AND f.ts_cierre IS NOT NULL
         AND f.ts_cierre >= f.ts_creacion
         AND f.ts_cierre - f.ts_creacion <= INTERVAL '30 days'
            THEN EXTRACT(EPOCH FROM (f.ts_cierre - f.ts_creacion)) / 60
        ELSE NULL
    END
"""


def _parsear_fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        raise ValueError(f"Fecha inválida '{valor}'. Usa el formato AAAA-MM-DD.")


def estadisticas_tickets(
    agrupar_por: str = "equipo",
    ordenar_por: str = "tickets",
    tipo_equipo: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    limite: int = 10,
) -> list[dict]:
    """Estadísticas de tickets agrupadas por equipo, tipo de equipo o mes."""
    if agrupar_por not in AGRUPACIONES:
        raise ValueError(f"agrupar_por debe ser uno de: {list(AGRUPACIONES)}")
    if ordenar_por not in ORDENES:
        raise ValueError(f"ordenar_por debe ser uno de: {list(ORDENES)}")

    desde = _parsear_fecha(fecha_desde)
    hasta = _parsear_fecha(fecha_hasta)
    if hasta:
        hasta = hasta + timedelta(days=1)  # 'hasta' inclusivo
    if desde and hasta and desde >= hasta:
        raise ValueError("fecha_desde debe ser anterior a fecha_hasta.")

    tipo = normalizar_codigo(tipo_equipo) if tipo_equipo else None
    limite = max(1, min(int(limite), 50))

    sql = f"""
        WITH base AS (
            SELECT
                {AGRUPACIONES[agrupar_por]} AS grupo,
                {DURACION_SQL} AS dur
            FROM galaxy_dw.fact_tickets AS f
            LEFT JOIN galaxy_dw.dim_equipo AS e
                ON f.equipo_key = e.equipo_key
            WHERE (%(desde)s::date IS NULL OR f.ts_creacion >= %(desde)s::date)
              AND (%(hasta)s::date IS NULL OR f.ts_creacion <  %(hasta)s::date)
              AND (%(tipo)s::text IS NULL
                   OR split_part(e.equipo_codigo, ' ', 1) = %(tipo)s::text)
        )
        SELECT
            grupo,
            COUNT(*)                                   AS total_tickets,
            COUNT(dur)                                 AS tickets_con_duracion,
            ROUND(AVG(dur)::numeric, 1)                AS promedio_min,
            ROUND((percentile_cont(0.5)
                   WITHIN GROUP (ORDER BY dur))::numeric, 1) AS mediana_min,
            ROUND(MAX(dur)::numeric, 1)                AS maximo_min,
            ROUND((SUM(dur) / 60)::numeric, 1)         AS horas_totales
        FROM base
        GROUP BY grupo
        ORDER BY {ORDENES[ordenar_por]} DESC NULLS LAST
        LIMIT %(limite)s;
    """

    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, {
                "desde": desde, "hasta": hasta, "tipo": tipo, "limite": limite,
            })
            return [dict(fila) for fila in cursor.fetchall()]
    finally:
        conexion.close()

if __name__ == "__main__":
    print("Top 5 equipos por cantidad de tickets:")
    for fila in estadisticas_tickets(limite=5):
        print(fila)

    print("\nPor tipo de equipo:")
    for fila in estadisticas_tickets(agrupar_por="tipo", ordenar_por="horas_totales"):
        print(fila)

    print("\nTickets por mes:")
    for fila in estadisticas_tickets(agrupar_por="mes", limite=50):
        print(fila)

    print("\nSolo camiones, enero 2025:")
    for fila in estadisticas_tickets(
        tipo_equipo="camión", fecha_desde="2025-01-01", fecha_hasta="2025-01-31", limite=3
    ):
        print(fila)