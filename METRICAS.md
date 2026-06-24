# Documentación de métricas del sistema (Node Exporter)

Tres métricas recolectadas por Node Exporter y consultadas en Prometheus/Grafana:

## 1. Uso de CPU
Query: `100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`
Significa el porcentaje de tiempo que la CPU está ocupada (100% menos el tiempo en reposo).
Utilidad: detectar saturación del procesador; un uso sostenido alto indica que el
sistema necesita más recursos o que un proceso está consumiendo demasiado.

## 2. Memoria disponible
Query: `node_memory_MemAvailable_bytes`
Indica la cantidad de memoria RAM disponible para nuevos procesos, en bytes.
Utilidad: anticipar agotamiento de memoria; si baja demasiado, el sistema empieza
a usar swap y se degrada el rendimiento.

## 3. Espacio en disco disponible
Query: `node_filesystem_avail_bytes`
Muestra el espacio libre en los sistemas de archivos, en bytes.
Utilidad: prevenir que el disco se llene, lo que puede detener servicios, impedir
escritura de logs o corromper bases de datos.
