#!/bin/sh
# Genera, solo la primera vez, los secretos del stack en ./secrets.
# Si la variable correspondiente viene definida en .env, se usa ese valor.
set -eu

DIR=/secrets
mkdir -p "$DIR"

secret() {
    file="$DIR/$1"
    if [ -s "$file" ]; then
        return
    fi
    if [ -n "${2:-}" ]; then
        printf '%s' "$2" > "$file"
    else
        tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "${3:-32}" > "$file"
    fi
    # Legible por los usuarios sin privilegios de app (10001) y grafana (472)
    chmod 644 "$file"
    echo "Secreto creado: $1"
}

# Cada servicio recibe SOLO sus secretos, en su propia carpeta (mínimo privilegio). Se montan carpetas y no archivos sueltos porque
# Docker crea como directorio un archivo que aún no existe al montarlo. Se copian en cada arranque: así también se migran los
# secretos de instalaciones anteriores (que estaban todos juntos en ./secrets).
share() {
    service="$1"
    shift
    mkdir -p "$DIR/$service"
    for name in "$@"; do
        cp "$DIR/$name" "$DIR/$service/$name"
        chmod 644 "$DIR/$service/$name"
    done
}

secret db_root_password "${MYSQL_ROOT_PASSWORD:-}"
secret db_password "${MYSQL_PASSWORD:-}"
secret secret_key "${SECRET_KEY:-}" 64
secret admin_password "${ADMIN_PASSWORD:-}" 20
secret grafana_admin_password "${GRAFANA_ADMIN_PASSWORD:-}" 20

share db db_root_password db_password
share app db_password secret_key admin_password
share grafana grafana_admin_password
