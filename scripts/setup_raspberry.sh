#!/usr/bin/env bash
# ==============================================================================
# 🌟 Spotlight on Proxmox VE — Despliegue en Raspberry Pi 4 B (Usuario sysadmin)
# ==============================================================================
# Este script está optimizado para ejecutarse directamente con el usuario 'sysadmin'
# (que ya cuenta con permisos para correr Docker sin privilegios de root).
#
# Pasos que realiza:
#  1. Verifica conectividad con el daemon de Docker sin requerir 'sudo'.
#  2. Detecta la versión de Docker Compose.
#  3. Configura interactivamente las variables de entorno (.env) para Proxmox VE.
#  4. Compila y levanta el contenedor con 'docker compose up -d --build'.
#  5. (Opcional) Provee la configuración de servicio systemd para autoarranque.
# ==============================================================================

set -euo pipefail

# Colores para salida formateada
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Valores por defecto
DEFAULT_PORT="8080"
SERVICE_NAME="spotlight-proxmox"

# Funciones de ayuda visual
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo -e "\n${BOLD}${CYAN}======================================================${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}======================================================${NC}\n"
}

CURRENT_USER="$(id -un)"

log_header "🌟 Despliegue de Spotlight Dashboard en Raspberry Pi 4 B"
log_info "Usuario actual en ejecución: ${BOLD}${CURRENT_USER}${NC}"

# 1. Comprobar acceso a Docker sin root
log_info "Verificando acceso a Docker para el usuario '${CURRENT_USER}'..."

if ! command -v docker &>/dev/null; then
    log_error "El comando 'docker' no se encuentra en el PATH."
    exit 1
fi

if ! docker ps &>/dev/null; then
    log_error "No se puede comunicar con el servicio Docker sin privilegios de root."
    log_warn "Asegúrate de que '${CURRENT_USER}' pertenece al grupo 'docker' (ej. sudo usermod -aG docker ${CURRENT_USER}) y reinicia la sesión."
    exit 1
fi

DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
log_success "Docker está disponible y accesible por '${CURRENT_USER}' (Versión: ${DOCKER_VER})."

# 2. Comprobar Docker Compose
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VER=$(docker compose version | awk '{print $4}')
    log_success "Docker Compose v2 detectado (${COMPOSE_VER})."
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    log_success "docker-compose detectado."
else
    log_error "No se encontró el plugin 'docker compose' ni el binario 'docker-compose'."
    echo -e "Instálalo ejecutando: ${BOLD}sudo apt-get update && sudo apt-get install -y docker-compose-plugin${NC}\n"
    exit 1
fi

# 3. Detectar directorio del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR=""

if [ -f "${SCRIPT_DIR}/../docker-compose.yml" ]; then
    WORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [ -f "${SCRIPT_DIR}/../Dashboard/docker-compose.yml" ]; then
    WORK_DIR="$(cd "${SCRIPT_DIR}/../Dashboard" && pwd)"
elif [ -f "./docker-compose.yml" ]; then
    WORK_DIR="$(pwd)"
elif [ -f "./Dashboard/docker-compose.yml" ]; then
    WORK_DIR="$(pwd)/Dashboard"
else
    log_error "No se localizó el archivo 'docker-compose.yml'."
    exit 1
fi

log_info "Directorio de trabajo: ${BOLD}${WORK_DIR}${NC}"
cd "$WORK_DIR"

# 4. Configuración de Variables de Entorno (.env)
ENV_FILE="${WORK_DIR}/.env"
EXAMPLE_FILE="${WORK_DIR}/.env.example"

log_header "⚙️ Configuración de Conexión con Proxmox VE"

PVE_HOST_VAL="https://192.168.1.100:8006"
PVE_USER_VAL="monitoring@pve"
PVE_TOKEN_NAME_VAL="spotlight"
PVE_TOKEN_SECRET_VAL="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
PVE_VERIFY_SSL_VAL="false"
DASH_PORT="${DEFAULT_PORT}"
DEMO_MODE_VAL="false"

# Si ya existe un .env, leer valores actuales como defaults
if [ -f "$ENV_FILE" ]; then
    log_info "Ya existe un archivo .env configurado."
    read -rp "¿Deseas reconfigurar los parámetros de conexión con Proxmox? (s/N): " RECONFIG_ENV
    if [[ ! "$RECONFIG_ENV" =~ ^[sS]$ ]]; then
        SKIP_ENV=true
    else
        SKIP_ENV=false
    fi
else
    SKIP_ENV=false
fi

if [ "$SKIP_ENV" = false ]; then
    echo -e "Introduce los datos de tu servidor Proxmox VE (o presiona Enter para usar valores por defecto/demo):\n"
    
    read -rp "1. URL / IP de Proxmox VE (ej. https://192.168.1.100:8006) [${PVE_HOST_VAL}]: " IN_HOST
    [ -n "$IN_HOST" ] && PVE_HOST_VAL="$IN_HOST"
    
    read -rp "2. Usuario Proxmox [${PVE_USER_VAL}]: " IN_USER
    [ -n "$IN_USER" ] && PVE_USER_VAL="$IN_USER"
    
    read -rp "3. Nombre del API Token [${PVE_TOKEN_NAME_VAL}]: " IN_TOKEN_NAME
    [ -n "$IN_TOKEN_NAME" ] && PVE_TOKEN_NAME_VAL="$IN_TOKEN_NAME"
    
    read -rp "4. Valor Secreto del Token UUID (o Enter para Modo Demo): " IN_SECRET
    if [ -n "$IN_SECRET" ]; then
        PVE_TOKEN_SECRET_VAL="$IN_SECRET"
        DEMO_MODE_VAL="false"
    else
        log_warn "No se ingresó Token Secreto. El dashboard iniciará en MODO DEMO."
        DEMO_MODE_VAL="true"
    fi
    
    read -rp "5. Puerto web en la Raspberry Pi [${DEFAULT_PORT}]: " IN_PORT
    [ -n "$IN_PORT" ] && DASH_PORT="$IN_PORT"
    
    read -rp "6. ¿Verificar certificado SSL de Proxmox? (Recomendado 'false' para cert autofirmado) [${PVE_VERIFY_SSL_VAL}]: " IN_SSL
    if [ -n "$IN_SSL" ]; then
        if [[ "${IN_SSL,,}" =~ ^(t|true|1|y|yes|s|si|sí)$ ]]; then
            PVE_VERIFY_SSL_VAL="true"
        else
            PVE_VERIFY_SSL_VAL="false"
        fi
    fi
    
    cat <<EOF > "$ENV_FILE"
# Configuración generada para Spotlight Dashboard
PVE_HOST=${PVE_HOST_VAL}
PVE_USER=${PVE_USER_VAL}
PVE_TOKEN_NAME=${PVE_TOKEN_NAME_VAL}
PVE_TOKEN_VALUE=${PVE_TOKEN_SECRET_VAL}
PVE_VERIFY_SSL=${PVE_VERIFY_SSL_VAL}
PORT=${DASH_PORT}
DEMO_MODE=${DEMO_MODE_VAL}
EOF

    chmod 600 "$ENV_FILE" 2>/dev/null || true
    log_success "Archivo .env creado/actualizado correctamente."
else
    # Extraer puerto del .env existente si es posible
    if grep -q "PORT=" "$ENV_FILE"; then
        DASH_PORT=$(grep "PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' "\r')
    fi
fi

# 5. Iniciar o compilar el Contenedor
log_header "🚀 Compilando y Levantando Contenedor Docker"

log_info "Asegurando que no existan conflictos de nombres de contenedor previos..."
docker rm -f proxmox-spotlight-dashboard 2>/dev/null || true

log_info "Ejecutando '${COMPOSE_CMD} up -d --build' como usuario '${CURRENT_USER}'..."
$COMPOSE_CMD up -d --build

log_success "¡Contenedor de Spotlight Dashboard iniciado con éxito!"

# 6. Detección de IP de la Raspberry Pi
IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
[ -z "$IP_ADDR" ] && IP_ADDR="<IP_DE_TU_RASPBERRY_PI>"

# 7. Resumen de Estado y Acceso
log_header "🎉 ¡Despliegue Finalizado con Éxito!"

echo -e "El dashboard de Spotlight está operando y listo para su uso:\n"
echo -e "  • ${BOLD}Usuario de ejecución:${NC} ${GREEN}${CURRENT_USER}${NC} (sin requerir root)"
echo -e "  • ${BOLD}Directorio de trabajo:${NC} ${WORK_DIR}"
echo -e "  • ${BOLD}URL de acceso web:${NC}    ${BOLD}${GREEN}http://${IP_ADDR}:${DASH_PORT}${NC}"
echo -e ""
echo -e "${BOLD}Comandos de gestión rápida para ${CURRENT_USER}:${NC}"
echo -e "  • ${CYAN}${COMPOSE_CMD} ps${NC}               - Ver estado del contenedor"
echo -e "  • ${CYAN}${COMPOSE_CMD} logs -f${NC}          - Ver telemetría y logs en vivo"
echo -e "  • ${CYAN}${COMPOSE_CMD} restart${NC}          - Reiniciar el dashboard"
echo -e "  • ${CYAN}${COMPOSE_CMD} up -d --build${NC}    - Recompilar tras cambios"
echo -e "  • ${CYAN}${COMPOSE_CMD} down${NC}             - Detener el contenedor"
echo -e ""

# 8. Sugerencia opcional para Autoarranque en el Sistema (systemd)
echo -e "${BOLD}--- Opcional: Autoarranque al encender la Raspberry Pi ---${NC}"
echo -e "Para que el dashboard inicie automáticamente tras un reinicio, puedes registrar el servicio systemd:"
echo -e "${CYAN}sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Spotlight on Proxmox VE Dashboard
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${WORK_DIR}
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload && sudo systemctl enable ${SERVICE_NAME}.service${NC}\n"
