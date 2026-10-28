# Documentación de métricas

OpsCenter combina métricas del **sistema** (Node Exporter) y de la **aplicación** (instrumentación propia con `prometheus_client`). Todas se pueden consultar en Prometheus (http://localhost:9090/graph), aparecen en el dashboard de Grafana y alimentan al copiloto IA.

## Métricas del sistema (Node Exporter)

### 1. Uso de CPU
```promql
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```
Porcentaje de tiempo en que la CPU está ocupada (100 % menos el tiempo en reposo).
**Para qué sirve:** detectar saturación del procesador. Un uso sostenido alto indica que el sistema necesita más recursos o que un proceso consume demasiado.
**Umbrales del copiloto:** advertencia ≥ 70 %, crítico ≥ 85 % (alerta `CPUAlta`).

### 2. Memoria usada
```promql
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100
```
Porcentaje de RAM en uso, calculado a partir de la memoria disponible para nuevos procesos (`MemAvailable`).
**Para qué sirve:** anticipar el agotamiento de memoria. Si baja demasiado, el sistema empieza a usar swap y el rendimiento se degrada.
**Umbrales:** advertencia ≥ 80 %, crítico ≥ 90 % (alerta `MemoriaBaja`).

### 3. Espacio en disco
```promql
max((1 - node_filesystem_avail_bytes{fstype=~"ext4|xfs|btrfs|zfs"}
       / node_filesystem_size_bytes{fstype=~"ext4|xfs|btrfs|zfs"}) * 100
    and on (device, mountpoint) node_filesystem_readonly == 0)
```
Ocupación del sistema de archivos escribible más lleno. Se excluyen tmpfs, overlay y los montajes de solo lectura, así funciona igual en Linux, en la VM de Vagrant y en Docker Desktop/WSL.
**Para qué sirve:** evitar que el disco se llene, porque eso puede detener servicios, impedir que se escriban logs o corromper la base de datos.
**Umbrales:** advertencia ≥ 75 %, crítico ≥ 85 % (alerta `DiscoCasiLleno`).

### 4. Carga promedio (load average)
```promql
node_load1
```
Número promedio de procesos listos para ejecutarse en el último minuto. El copiloto la divide por el número de núcleos: más de 1 proceso por núcleo indica que hay cola.

## Métricas de la aplicación

### 5. Tráfico
```promql
sum by (status) (rate(opscenter_http_requests_total[5m]))
```
Peticiones por segundo, separadas por código HTTP.

### 6. Tasa de errores 5xx
```promql
sum(rate(opscenter_http_requests_total{status=~"5.."}[5m]))
  / clamp_min(sum(rate(opscenter_http_requests_total[5m])), 0.001) * 100
```
Porcentaje de peticiones que fallan del lado del servidor. Alerta `ErroresHTTP5xx` por encima del 5 %.

### 7. Latencia p95
```promql
histogram_quantile(0.95, sum by (le) (rate(opscenter_http_request_duration_seconds_bucket[5m])))
```
Tiempo por debajo del cual se responde el 95 % de las peticiones. Es más representativo de la experiencia del usuario que el promedio. Alerta `LatenciaAlta` por encima de 1 s.
