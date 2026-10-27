# Diseño y reglas actuales

## Componentes

| Archivo | Responsabilidad |
| --- | --- |
| app.py | Chat Streamlit, estado por sesión, historial visible, recuperación ante APIError |
| agente.py | Prompt, contratos de herramientas, cliente Anthropic y bucle de hasta ocho iteraciones |
| Consulta.py | Conexión, normalización, consultas parametrizadas y agregados |

`responder` modifica la lista de mensajes recibida. Agrega respuestas del modelo y resultados de herramientas; devuelve el texto final o el aviso de límite de pasos. No garantiza completar una pregunta dentro de ocho iteraciones.

## Contrato de base de datos

- dim_equipo: equipo_key, equipo_codigo.
- fact_tickets: numero_ticket, equipo_key, asunto, ts_creacion, ts_cierre, duracion_min, solucion.
- El esquema y nombres están fijados en las consultas.

## Reglas de agregación

- Se permite agrupar por equipo, tipo (primer término de equipo_codigo) o mes de creación.
- Orden por cantidad de tickets, horas o mediana; límite ajustado entre 1 y 50.
- Fecha final inclusiva: se convierte al día siguiente para aplicar comparación exclusiva.
- Duración almacenada hasta 43.200 minutos; si falta, se calcula desde timestamps válidos hasta 30 días.
- No existe comprobación explícita de que duracion_min sea no negativa: pendiente.
- El historial no aplica el mismo máximo de 30 días que los agregados: pendiente de unificar.
- Las filas sin equipo se conservan en agregados generales mediante LEFT JOIN.

## Trabajo pendiente

1. Obtener contexto temporal y cantidades desde la base, en lugar de fijarlos en el prompt.
2. Unificar normalización de códigos y validación de duraciones.
3. Probar errores, límites de pasos y recuperación del historial.
4. Incorporar autenticación y límites de uso antes de cualquier exposición pública.
5. Añadir DDL y datos de demostración revisados para reproducibilidad.
