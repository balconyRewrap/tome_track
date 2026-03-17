#!/bin/sh
set -eu

HTTP_TEMPLATE="/etc/nginx/templates/http.conf.template"
HTTPS_TEMPLATE="/etc/nginx/templates/https.conf.template"
TARGET_CONFIG="/etc/nginx/conf.d/default.conf"

DOMAIN_NAME="${DOMAIN_NAME:-}"
DJANGO_ADMIN_PATH="${DJANGO_ADMIN_PATH:-admin/}"
SERVER_NAME="${DOMAIN_NAME:-_}"

CERT_PATH=""
KEY_PATH=""
if [ -n "$DOMAIN_NAME" ]; then
    CERT_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem"
    KEY_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem"
fi

export DOMAIN_NAME DJANGO_ADMIN_PATH SERVER_NAME

render_http_config() {
    envsubst '${DJANGO_ADMIN_PATH} ${SERVER_NAME}' < "$HTTP_TEMPLATE" > "$TARGET_CONFIG"
}

render_https_config() {
    envsubst '${DJANGO_ADMIN_PATH} ${DOMAIN_NAME} ${SERVER_NAME}' < "$HTTPS_TEMPLATE" > "$TARGET_CONFIG"
}

cert_fingerprint() {
    if [ -z "$DOMAIN_NAME" ]; then
        echo ""
        return
    fi

    if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
        cat "$CERT_PATH" "$KEY_PATH" | sha256sum | cut -d ' ' -f1
        return
    fi

    echo ""
}

LAST_CERT_FINGERPRINT=""
CURRENT_CERT_FINGERPRINT="$(cert_fingerprint)"
HTTPS_ENABLED=0

if [ -n "$CURRENT_CERT_FINGERPRINT" ]; then
    render_https_config
    HTTPS_ENABLED=1
    LAST_CERT_FINGERPRINT="$CURRENT_CERT_FINGERPRINT"
else
    render_http_config
fi

nginx -g 'daemon off;' &
NGINX_PID=$!

shutdown() {
    kill -TERM "$NGINX_PID" 2>/dev/null || true
    wait "$NGINX_PID" 2>/dev/null || true
}

trap shutdown INT TERM

while kill -0 "$NGINX_PID" 2>/dev/null; do
    CURRENT_CERT_FINGERPRINT="$(cert_fingerprint)"

    if [ -n "$CURRENT_CERT_FINGERPRINT" ] && [ "$HTTPS_ENABLED" -eq 0 ]; then
        render_https_config
        nginx -s reload
        HTTPS_ENABLED=1
        LAST_CERT_FINGERPRINT="$CURRENT_CERT_FINGERPRINT"
    fi

    if [ -n "$CURRENT_CERT_FINGERPRINT" ] && [ "$CURRENT_CERT_FINGERPRINT" != "$LAST_CERT_FINGERPRINT" ]; then
        render_https_config
        nginx -s reload
        LAST_CERT_FINGERPRINT="$CURRENT_CERT_FINGERPRINT"
    fi

    sleep 30
done

wait "$NGINX_PID"
