# Microproyecto 2 - Servicios Telematicos

Aplicacion web segura empaquetada con Docker + Docker Compose, con monitoreo
mediante Prometheus, Node Exporter y Grafana.

## Componentes (docker-compose.yml)
- db: MySQL 8.0 (base de datos de la aplicacion).
- app: aplicacion Flask (MiniWebApp) empaquetada en Docker.
- nginx: reverse proxy con SSL (HTTPS) y redireccion automatica HTTP a HTTPS.
- node_exporter: recoleccion de metricas del sistema.
- prometheus: almacenamiento y consulta de metricas.
- grafana: visualizacion de metricas (dashboard Node Exporter Full, ID 1860).

## Requisitos previos
- Docker y Docker Compose instalados.

## Generar el certificado SSL (no incluido en el repo por seguridad)
Ejecutar:

    mkdir -p nginx/certs
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/certs/server.key -out nginx/certs/server.crt -subj "/C=CO/ST=Valle/L=Cali/O=ZemZysteM/CN=192.168.50.3"

## Despliegue
Ejecutar:

    docker compose up -d

## Acceso a los servicios
- Aplicacion web HTTPS: https://192.168.50.3
- Prometheus: http://192.168.50.3:9090
- Grafana: http://192.168.50.3:3000 (usuario admin, password admin)

## Verificacion
- La app redirige HTTP a HTTPS automaticamente.
- El endpoint /api/users devuelve los usuarios desde MySQL.
- Prometheus recolecta metricas de Node Exporter (ver /targets).
- Grafana muestra el dashboard con metricas en tiempo real.

Ver METRICAS.md para la documentacion de las metricas del sistema.
