#!/bin/sh
# Genera un certificado autofirmado (con SAN) solo si todavía no existe.
set -eu

CERT_DIR=/certs
CRT="$CERT_DIR/server.crt"
KEY="$CERT_DIR/server.key"

if [ -s "$CRT" ] && [ -s "$KEY" ]; then
    echo "Certificado existente en $CERT_DIR, no se regenera."
    exit 0
fi

apk add --no-cache openssl >/dev/null

SAN=""
for host in $(echo "${CERT_HOSTS:-localhost}" | tr ',' ' '); do
    case "$host" in
        *[!0-9.]*) entry="DNS:$host" ;;
        *) entry="IP:$host" ;;
    esac
    SAN="${SAN:+$SAN,}$entry"
done

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY" -out "$CRT" \
    -subj "/C=CO/ST=Valle/L=Cali/O=ZemZysteM/CN=OpsCenter" \
    -addext "subjectAltName=$SAN"

chmod 644 "$CRT"
chmod 600 "$KEY"
echo "Certificado generado para: $SAN"
