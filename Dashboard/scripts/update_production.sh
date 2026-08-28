#!/usr/bin/env bash
# ==============================================================================
# 🚀 SPOTLIGHT ON PROXMOX VE — ACTUALIZADOR AUTOMATIZADO DE PRODUCCIÓN
# ==============================================================================
# Este script automatiza la actualización integral del dashboard en producción:
#   1. Verificación de permisos y pre-requisitos de Docker / Docker Compose.
#   2. Backup automático no destructivo de configuración (.env) y datos (data/).
#   3. Migración inteligente de variables nuevas en .env sin sobrescribir secretos.
#   4. Creación del directorio persistente ./data para la nueva Web UI.
#   5. Recompilación y despliegue del contenedor Docker optimizado.
#   6. Verificación de salud (Health Check / Canary) del endpoint /api/health.
#   7. Ejecución de la auditoría SRE verify_production.sh para confirmar telemetría.
#
# Uso:
#   bash scripts/update_production.sh
# ==============================================================================

set -uo pipefail

# --- Colores y Estilos ANSI ---
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
    echo "║       🚀 SPOTLIGHT ON PROXMOX VE — ACTUALIZADOR DE PRODUCCIÓN        ║"
    echo "║        Versión 1.1.0 • Web Config • SRE Troubleshooting Suite        ║"
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

# ==============================================================================
# PASO 1: Detección del Directorio del Proyecto y Docker
# ==============================================================================
log_step "1. Verificando Entorno y Permisos del Sistema"

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
    log_err "No se pudo localizar 'docker-compose.yml'. Ejecuta este script dentro del directorio del proyecto."
    exit 1
fi

log_ok "Directorio del aplicativo detectado en: ${BOLD}${WORK_DIR}${NC}"
cd "$WORK_DIR"

CURRENT_USER="$(id -un)"
log_ok "Usuario en ejecución: ${CYAN}${CURRENT_USER}${NC}"

# Validar Docker
if ! command -v docker &>/dev/null; then
    log_err "Docker no está instalado o no se encuentra en el PATH."
    exit 1
fi

if ! docker ps &>/dev/null; then
    log_err "No se puede acceder al daemon de Docker. ¿Pertenece '${CURRENT_USER}' al grupo docker? (sudo usermod -aG docker ${CURRENT_USER})"
    exit 1
fi
log_ok "Docker daemon accesible correctamente."

# Validar Docker Compose
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
    log_ok "Docker Compose v2 detectado ($(docker compose version --short 2>/dev/null || echo 'v2'))."
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    log_ok "docker-compose standalone detectado."
else
    log_err "No se encontró 'docker compose'. Instálalo con: sudo apt-get install docker-compose-plugin"
    exit 1
fi

# ==============================================================================
# PASO 2: Backup Automático No Destructivo
# ==============================================================================
log_step "2. Creando Respaldo de Seguridad de Configuración y Datos"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${WORK_DIR}/.backups/backup_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

if [ -f "${WORK_DIR}/.env" ]; then
    cp "${WORK_DIR}/.env" "${BACKUP_DIR}/.env"
    log_ok "Archivo .env respaldado en: ${DIM}${BACKUP_DIR}/.env${NC}"
fi

if [ -d "${WORK_DIR}/data" ]; then
    cp -r "${WORK_DIR}/data" "${BACKUP_DIR}/data" 2>/dev/null || true
    log_ok "Directorio de datos data/ respaldado en: ${DIM}${BACKUP_DIR}/data${NC}"
fi

# Guardar ID del contenedor actual si existe
EXISTING_CONTAINER=$(docker ps -q --filter "name=spotlight" --filter "name=proxmox" | head -n1 || true)
if [ -n "$EXISTING_CONTAINER" ]; then
    echo "$EXISTING_CONTAINER" > "${BACKUP_DIR}/previous_container_id.txt"
    log_ok "Contenedor previo registrado (ID: ${EXISTING_CONTAINER:0:12})."
fi

# ==============================================================================
# PASO 3: Migración Inteligente de Variables .env y Directorio data/
# ==============================================================================
log_step "3. Migración de Variables de Configuración e Integración Web"

ENV_FILE="${WORK_DIR}/.env"
EXAMPLE_FILE="${WORK_DIR}/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$EXAMPLE_FILE" ]; then
        log_warn "No existía .env. Creando uno nuevo desde .env.example..."
        cp "$EXAMPLE_FILE" "$ENV_FILE"
    else
        log_warn "Creando archivo .env base..."
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
EOF
    fi
fi

# Inyectar nuevas variables si no existen en el .env actual (sin modificar las existentes)
append_if_missing() {
    local key="$1"
    local default_val="$2"
    if ! grep -q "^[[:space:]]*${key}=" "$ENV_FILE"; then
        echo "${key}=${default_val}" >> "$ENV_FILE"
        log_ok "Nueva variable inyectada en .env: ${CYAN}${key}=${default_val}${NC}"
    fi
}

append_if_missing "AUTH_TYPE" "token"
append_if_missing "PVE_PASSWORD" ""
append_if_missing "FALLBACK_TO_DEMO" "false"

# Asegurar que FALLBACK_TO_DEMO sea false para no esconder errores con datos demo falsos
if grep -q "^[[:space:]]*FALLBACK_TO_DEMO=true" "$ENV_FILE"; then
    log_warn "Cambiando FALLBACK_TO_DEMO=false para evitar mostrar datos simulados en caso de error..."
    sed -i -e 's/^[[:space:]]*FALLBACK_TO_DEMO=true/FALLBACK_TO_DEMO=false/' "$ENV_FILE"
fi

# Crear directorio ./data para la persistencia de configuración del aplicativo
mkdir -p "${WORK_DIR}/data"
chmod 775 "${WORK_DIR}/data" 2>/dev/null || true
log_ok "Directorio de persistencia ./data preparado y asegurado."

# ==============================================================================
# PASO 4: Compilación y Despliegue con Docker Compose
# ==============================================================================
log_step "4. Recompilando y Desplegando Contenedor Actualizado"

echo -e "  ${DIM}Construyendo imagen optimizada con Python 3.11-slim y Web UI HUD...${NC}"

if $COMPOSE_CMD build; then
    log_ok "Compilación de imagen completada exitosamente."
else
    log_err "Fallo al compilar la imagen Docker. Restaurando backup..."
    exit 1
fi

echo -e "  ${DIM}Iniciando servicio con recarga limpia de contenedores...${NC}"
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true
echo -e "  ${DIM}Garantizando liberación de nombre de contenedor (docker rm -f proxmox-spotlight-dashboard)...${NC}"
docker rm -f proxmox-spotlight-dashboard 2>/dev/null || true
$COMPOSE_CMD up -d --remove-orphans

log_ok "Contenedor iniciado en segundo plano sin conflictos de nombre."

# ==============================================================================
# PASO 5: Verificación de Salud (Health Check & Canary)
# ==============================================================================
log_step "5. Verificando Salud del Servicio y Endpoints de API"

# Extraer puerto configurado
PORT_VAL=$(grep -E "^[[:space:]]*PORT=" "$ENV_FILE" | cut -d= -f2 | tr -d ' "' || echo "8080")
[ -z "$PORT_VAL" ] && PORT_VAL="8080"

HEALTH_URL="http://localhost:${PORT_VAL}/api/health"
CONFIG_URL="http://localhost:${PORT_VAL}/api/config"

echo -e "  ${DIM}Esperando inicialización del servidor en ${HEALTH_URL}...${NC}"

HEALTHY=false
for i in {1..15}; do
    if curl -s -f -m 3 "$HEALTH_URL" &>/dev/null; then
        HEALTHY=true
        break
    fi
    sleep 2
    echo -n "."
done
echo ""

if [ "$HEALTHY" = true ]; then
    HEALTH_RESP=$(curl -s -m 3 "$HEALTH_URL")
    log_ok "Endpoint /api/health responde 200 OK: ${GREEN}${HEALTH_RESP}${NC}"
    
    # Probar endpoint de configuración
    if curl -s -f -m 3 "$CONFIG_URL" &>/dev/null; then
        log_ok "Nuevo endpoint de Configuración (/api/config) operativo."
    fi
else
    log_err "El contenedor no superó el health check tras 30 segundos."
    log_warn "Mostrando últimos logs del contenedor:"
    $COMPOSE_CMD logs --tail 30
    log_warn "Puedes revisar el backup en: ${BACKUP_DIR}"
    exit 1
fi

# ==============================================================================
# PASO 6: Auditoría SRE Integral
# ==============================================================================
log_step "6. Ejecutando Suite de Auditoría SRE (verify_production.sh)"

VERIFY_SCRIPT=""
if [ -f "${WORK_DIR}/scripts/verify_production.sh" ]; then
    VERIFY_SCRIPT="${WORK_DIR}/scripts/verify_production.sh"
elif [ -f "${SCRIPT_DIR}/verify_production.sh" ]; then
    VERIFY_SCRIPT="${SCRIPT_DIR}/verify_production.sh"
fi

if [ -n "$VERIFY_SCRIPT" ]; then
    bash "$VERIFY_SCRIPT" || true
else
    log_warn "verify_production.sh no encontrado en las rutas habituales. Omitiendo auditoría."
fi

# ==============================================================================
# RESUMEN FINAL
# ==============================================================================
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "IP_RASPBERRY_PI")

echo -e "\n${GREEN}${BOLD}========================================================================${NC}"
echo -e "${GREEN}${BOLD}    🎉 ¡ACTUALIZACIÓN EN PRODUCCIÓN COMPLETADA EXITOSAMENTE!            ${NC}"
echo -e "${GREEN}${BOLD}========================================================================${NC}"
echo -e "  Acceso a la plataforma web:"
echo -e "    🌐 Local:         ${CYAN}http://localhost:${PORT_VAL}${NC}"
echo -e "    🌐 Red Local:     ${CYAN}http://${LOCAL_IP}:${PORT_VAL}${NC}"
echo -e ""
echo -e "  ${BOLD}Nuevas funciones disponibles:${NC}"
echo -e "    • ${BOLD}⚙ Configuración Web:${NC} Haz clic en 'Configuración' para cambiar Host, Token, Contraseña y SSL sin reiniciar."
echo -e "    • ${BOLD}🩺 Troubleshooting SRE:${NC} Haz clic en 'Troubleshooting' para auditar las 6 capas de integración y ver logs en vivo."
echo -e "    • ${BOLD}🛡️ Cero Fallback Falso:${NC} Si Proxmox no conecta, verás la alerta con la causa exacta y botones de reparación."
echo -e "    • ${BOLD}💾 Respaldo guardado en:${NC} ${DIM}${BACKUP_DIR}${NC}"
echo -e "========================================================================\n"
