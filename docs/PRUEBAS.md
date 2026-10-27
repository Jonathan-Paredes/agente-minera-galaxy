# Plan de pruebas del agente

Estado: no hay suite automatizada en los archivos originales revisados. No se ha llamado a la API ni consultado PostgreSQL durante esta preparación.

| Nivel | Casos por implementar | Criterio |
| --- | --- | --- |
| Unitario | normalizar_codigo con tildes, espacios y números pegados | Código esperado sin perder dígitos |
| Unitario | Fechas inválidas, rangos invertidos, agrupación y orden no permitidos | ValueError descriptivo |
| Unitario | Límite inferior y superior | Ajuste a 1..50 |
| Consulta con mocks | búsqueda con %, _ y barra inversa | Parámetros escapados, sin concatenar valores |
| Integración aislada | Equipo conocido, inexistente y tickets sin equipo | Conteos coincidentes con SQL directo |
| Integración aislada | Duraciones nulas, negativas y mayores a 30 días | Evidenciar y corregir diferencias historial/agregados |
| Agente con mocks | Selección de herramienta, error y ocho iteraciones | Mensajes tool_use/tool_result consistentes |
| Interfaz | APIError y nueva conversación | Recuperación sin turno incompleto |
| Evaluación manual | Preguntas ambiguas y fechas fuera de cobertura | Aclaración, sin inventar datos |

Separar pruebas unitarias sin red de pruebas de integración y de las que consumen API. Registrar fecha, versión, datos usados y resultado real de cada ejecución. No declarar estos casos aprobados hasta ejecutarlos.
