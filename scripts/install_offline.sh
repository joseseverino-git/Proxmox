#!/usr/bin/env bash
# ==============================================================================
# 🚀 SPOTLIGHT ON PROXMOX VE — INSTALADOR Y ACTUALIZADOR OFFLINE / LOCAL
# ==============================================================================
# Automatiza al 100% la instalación o actualización local sin requerir Git ni
# conexión a internet durante el despliegue.
#
# Acciones que realiza automáticamente:
#   1. Detecta si se ejecuta desde carpeta temporal o en destino de producción.
#   2. Si es necesario, copia los archivos a ~/Dashboard preservando .env.
#   3. Migra las nuevas variables de alertas por correo (Gmail) a .env.
#   4. Elimina contenedores previos y huérfanos:
#        docker rm -f proxmox-spotlight-dashboard
#   5. Recompila la imagen y arranca el contenedor con Docker Compose.
#   6. Verifica la salud de la aplicación (Healthcheck HTTP).
# ==============================================================================

set -uo pipefail

# --- Colores ANSI ---
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly NC='\033[0m'

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║       🚀 SPOTLIGHT ON PROXMOX VE — INSTALADOR AUTOMÁTICO LOCAL       ║"
    echo "║              Actualización Offline • Docker • Alertas Gmail          ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_step() {
    echo -e "\n${BOLD}${MAGENTA}▶ $1${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────────────────────────${NC}"
}

log_ok() {
    echo -e "  ${GREEN}[✓] ÉXITO:${NC} $1"
}

log_warn() {
    echo -e "  ${YELLOW}[!] AVISO:${NC} $1"
}

log_err() {
    echo -e "  ${RED}[✗] ERROR:${NC} $1"
}

print_banner

# Detectar directorio desde donde se ejecuta el instalador
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detectar usuario objetivo y destino predeterminado
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    RUN_USER="$SUDO_USER"
    DEST_DIR="/home/${SUDO_USER}/Dashboard"
elif [ -d "/home/sysadmin" ]; then
    RUN_USER="sysadmin"
    DEST_DIR="/home/sysadmin/Dashboard"
else
    RUN_USER="$(id -un)"
    DEST_DIR="${HOME}/Dashboard"
fi

# Detectar si ya estamos dentro del directorio de producción
IN_PLACE=false
if [ "$SCRIPT_DIR" == "$DEST_DIR" ] || [ "$(pwd)" == "$DEST_DIR" ] || [ -f "${SCRIPT_DIR}/docker-compose.yml" -a "${SCRIPT_DIR}" == "${HOME}/Dashboard" ]; then
    IN_PLACE=true
    DEST_DIR="$SCRIPT_DIR"
fi

# 1. Localización de fuentes
log_step "1. Detectando Origen y Destino de Archivos"
SOURCE_DIR="$SCRIPT_DIR"
if [ -d "${SCRIPT_DIR}/Dashboard" ] && [ ! -f "${SCRIPT_DIR}/Dockerfile" ]; then
    SOURCE_DIR="${SCRIPT_DIR}/Dashboard"
fi

echo -e "  • Directorio Origen:   ${CYAN}${SOURCE_DIR}${NC}"
echo -e "  • Directorio Destino:  ${CYAN}${DEST_DIR}${NC}"
echo -e "  • Modo de Instalación: ${BOLD}$([ "$IN_PLACE" = true ] && echo "Actualización Directa In-Place" || echo "Copia Segura a Destino")${NC}"

# 2. Copia de archivos (si no es in-place)
if [ "$IN_PLACE" = false ]; then
    log_step "2. Copiando Archivos Nuevos hacia ${DEST_DIR}"
    mkdir -p "$DEST_DIR"

    # Respaldo de seguridad previo de .env si existe
    if [ -f "${DEST_DIR}/.env" ]; then
        BACKUP_DIR="${DEST_DIR}/.backups"
        mkdir -p "$BACKUP_DIR"
        cp -f "${DEST_DIR}/.env" "${BACKUP_DIR}/.env.backup_$(date +%Y%m%d_%H%M%S)"
        log_ok "Respaldo previo de .env guardado en .backups/"
    fi

    # Copiar archivos excluyendo temporales y .env existente
    rsync -av \
        --exclude='.env' \
        --exclude='data/settings.json' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='*.tar.gz' \
        --exclude='*.zip' \
        "${SOURCE_DIR}/" "${DEST_DIR}/" 2>/dev/null || cp -rf "${SOURCE_DIR}/"* "${DEST_DIR}/" 2>/dev/null || true

    log_ok "Archivos de la versión actualizada copiados correctamente."
fi

cd "$DEST_DIR"

# 3. Configuración y Migración de Variables .env
log_step "3. Verificación y Migración de Variables de Entorno (.env)"
ENV_FILE="${DEST_DIR}/.env"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "${DEST_DIR}/.env.example" ]; then
        cp "${DEST_DIR}/.env.example" "$ENV_FILE"
        log_ok "Archivo .env creado a partir de .env.example."
    else
        cat << 'EOF' > "$ENV_FILE"
PVE_HOST=https://192.168.1.100:8006
AUTH_TYPE=token
PVE_USER=monitoring@pve
PVE_TOKEN_NAME=spotlight
PVE_TOKEN_VALUE=
PVE_PASSWORD=
PVE_VERIFY_SSL=false
PVE_TIMEOUT=6.0
CACHE_TTL_SECONDS=5
PORT=8080
DEMO_MODE=false
FALLBACK_TO_DEMO=false
ALERT_EMAIL_ENABLED=false
ALERT_EMAIL_TO=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=apps.monitor.lnx@gmail.com
SMTP_PASSWORD=uoilwckixdoemkfo
SMTP_USE_TLS=true
ALERT_COOLDOWN_MINUTES=30
EOF
        log_ok "Archivo .env inicializado con valores predeterminados."
    fi
fi

# Inyectar nuevas variables en .env existente si faltan
append_if_missing() {
    local key="$1"
    local default_val="$2"
    if ! grep -q "^[[:space:]]*${key}=" "$ENV_FILE"; then
        echo "${key}=${default_val}" >> "$ENV_FILE"
        log_ok "Variable inyectada en .env: ${CYAN}${key}=${default_val}${NC}"
    fi
}

append_if_missing "AUTH_TYPE" "token"
append_if_missing "PVE_PASSWORD" ""
append_if_missing "FALLBACK_TO_DEMO" "false"
append_if_missing "ALERT_EMAIL_ENABLED" "false"
append_if_missing "ALERT_EMAIL_TO" ""
append_if_missing "SMTP_HOST" "smtp.gmail.com"
append_if_missing "SMTP_PORT" "587"
append_if_missing "SMTP_USER" "apps.monitor.lnx@gmail.com"
append_if_missing "SMTP_PASSWORD" "uoilwckixdoemkfo"
append_if_missing "SMTP_USE_TLS" "true"
append_if_missing "ALERT_COOLDOWN_MINUTES" "30"

# Corregir FALLBACK_TO_DEMO si estuviese en true
if grep -q "^[[:space:]]*FALLBACK_TO_DEMO=true" "$ENV_FILE"; then
    sed -i -e 's/^[[:space:]]*FALLBACK_TO_DEMO=true/FALLBACK_TO_DEMO=false/' "$ENV_FILE"
    log_ok "FALLBACK_TO_DEMO ajustado a false para alertar errores reales."
fi

# Directorio de persistencia
mkdir -p "${DEST_DIR}/data"
chmod 775 "${DEST_DIR}/data" 2>/dev/null || true

# Permisos de ejecución
find "${DEST_DIR}/scripts" -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true
[ -f "${DEST_DIR}/install_offline.sh" ] && chmod +x "${DEST_DIR}/install_offline.sh" 2>/dev/null || true

# Sincronizar desde subcarpeta Dashboard si existe (creada por git clone o tar anidado)
if [ -d "${DEST_DIR}/Dashboard/app" ]; then
    echo -e "  [+] Sincronizando archivos actualizados desde Dashboard/ hacia app/..."
    cp -rf "${DEST_DIR}/Dashboard/app/"* "${DEST_DIR}/app/"
    [ -f "${DEST_DIR}/Dashboard/docker-compose.yml" ] && cp -f "${DEST_DIR}/Dashboard/docker-compose.yml" "${DEST_DIR}/docker-compose.yml"
    [ -f "${DEST_DIR}/Dashboard/Dockerfile" ] && cp -f "${DEST_DIR}/Dashboard/Dockerfile" "${DEST_DIR}/Dockerfile"
    [ -f "${DEST_DIR}/Dashboard/requirements.txt" ] && cp -f "${DEST_DIR}/Dashboard/requirements.txt" "${DEST_DIR}/requirements.txt"
    [ -d "${DEST_DIR}/Dashboard/scripts" ] && cp -rf "${DEST_DIR}/Dashboard/scripts/"* "${DEST_DIR}/scripts/"
    log_ok "Archivos del aplicativo consolidados en la raíz de producción."
fi

# 4. Despliegue en Docker
log_step "4. Desplegando Contenedor Docker en Producción"

# Detectar comando docker compose
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    log_err "Docker Compose no fue encontrado en el sistema. Asegúrate de tener Docker instalado."
    exit 1
fi

echo -e "  [+] Deteniendo contenedores antiguos..."
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true

echo -e "  [+] ${BOLD}Limpiando contenedor huérfano (docker rm -f proxmox-spotlight-dashboard)...${NC}"
docker rm -f proxmox-spotlight-dashboard 2>/dev/null || true
log_ok "Nombre de contenedor liberado sin conflictos."

echo -e "  [+] ${BOLD}Eliminando imágenes Docker anteriores para forzar reconstrucción limpia...${NC}"
docker rmi -f $(docker images -q "*spotlight*") 2>/dev/null || true
docker rmi -f $(docker images -q "*dashboard*") 2>/dev/null || true

echo -e "  [+] Recompilando imagen Docker sin caché..."
$COMPOSE_CMD build --no-cache

echo -e "  [+] Levantando servicio en segundo plano..."
$COMPOSE_CMD up -d

# 5. Validación del Healthcheck
log_step "5. Verificación de Salud de la Aplicación"
echo -e "  [+] Esperando 6 segundos para inicialización..."
sleep 6

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")"
DASH_PORT="8080"
if grep -q "^[[:space:]]*PORT=" "$ENV_FILE"; then
    DASH_PORT="$(grep "^[[:space:]]*PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' "\r')"
fi

HEALTH_STATUS="DESCONOCIDO"
if command -v curl &>/dev/null; then
    HTTP_CODE="$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${DASH_PORT}/api/health" 2>/dev/null || echo "000")"
    if [ "$HTTP_CODE" == "200" ]; then
        HEALTH_STATUS="HEALTHY (HTTP 200 OK)"
        log_ok "El Dashboard responde saludablemente en el puerto ${DASH_PORT}."
    else
        log_warn "El endpoint /api/health respondió con código HTTP: ${HTTP_CODE}."
    fi
fi

# 6. Resumen final
echo -e "\n${CYAN}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}       🎉 ¡DESPLIEGUE OFFLINE COMPLETADO EXITOSAMENTE!${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "  • URL de Acceso:        ${BOLD}${CYAN}http://${HOST_IP}:${DASH_PORT}${NC}"
echo -e "  • Directorio Instalado: ${BOLD}${DEST_DIR}${NC}"
echo -e "  • Estado Contenedor:    ${GREEN}RUNNING${NC}"
echo -e "  • Healthcheck:          ${BOLD}${HEALTH_STATUS}${NC}"
echo -e ""
echo -e "${YELLOW}${BOLD}🔔 PASOS SIGUIENTES:${NC}"
echo -e "  1. Abre el navegador en: ${CYAN}http://${HOST_IP}:${DASH_PORT}${NC}"
echo -e "  2. Haz ${BOLD}Ctrl + F5${NC} para recargar la interfaz web completa."
echo -e "  3. Abre ${BOLD}'⚙ Configuración'${NC} para:"
echo -e "     - Verificar tu token o clave de Proxmox."
echo -e "     - Habilitar las alertas por correo y enviar el correo de prueba."
echo -e "  4. Abre ${BOLD}'🩺 Troubleshooting SRE'${NC} para auditar la conexión en tiempo real."
echo -e "${CYAN}════════════════════════════════════════════════════════════════════════${NC}\n"
