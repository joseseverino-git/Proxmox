#!/usr/bin/env bash
# ==============================================================================
# 🚀 SPOTLIGHT ON PROXMOX VE — INSTALADOR Y COPIADOR A DESTINO DE PRODUCCIÓN
# ==============================================================================
# Propósito:
#   Toma los archivos de la aplicación una vez descomprimida y los copia de
#   forma limpia, segura y no destructiva al directorio de producción en la
#   Raspberry Pi o servidor Linux (por defecto: /home/sysadmin/Dashboard).
#
# Características:
#   • Respaldo automático de seguridad previo (.backups/).
#   • Preservación estricta de credenciales e IPs existentes en .env.
#   • Migración automática de nuevas variables (AUTH_TYPE, FALLBACK_TO_DEMO).
#   • Corrección automática de permisos de usuario (sysadmin) y ejecución (+x).
#   • Opción de desplegar inmediatamente el contenedor Docker con 1 solo paso.
#
# Sintaxis:
#   bash deploy_to_destination.sh [OPCIONES] [DIRECTORIO_DESTINO]
#
# Ejemplos:
#   bash deploy_to_destination.sh
#   bash deploy_to_destination.sh /home/sysadmin/Dashboard
#   bash deploy_to_destination.sh --deploy
#   bash deploy_to_destination.sh -y -d /opt/spotlight-proxmox --deploy
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
    echo "║     📂 SPOTLIGHT ON PROXMOX VE — INSTALADOR AL DIRECTORIO DESTINO    ║"
    echo "║       Copia Segura • Preservación de .env • Permisos y Despliegue    ║"
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

# --- Detección del Usuario Real y Destino por Defecto ---
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    TARGET_USER="$SUDO_USER"
    DEFAULT_DEST="/home/${SUDO_USER}/Dashboard"
elif [ -d "/home/sysadmin" ]; then
    TARGET_USER="sysadmin"
    DEFAULT_DEST="/home/sysadmin/Dashboard"
else
    TARGET_USER="$(id -un)"
    DEFAULT_DEST="${HOME}/Dashboard"
fi

CUSTOM_DEST=""
AUTO_CONFIRM=false
AUTO_DEPLOY=false

# --- Procesamiento de Argumentos ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            echo "Uso: bash deploy_to_destination.sh [OPCIONES] [DIRECTORIO_DESTINO]"
            echo ""
            echo "Opciones:"
            echo "  -d, --dest, --destination PATH  Directorio destino de producción."
            echo "  -y, --yes                       Confirmar automáticamente sin preguntar."
            echo "  --deploy, -b, --build           Compilar y levantar el contenedor tras copiar."
            echo "  -h, --help                      Mostrar esta ayuda."
            echo ""
            echo "Destino por defecto detectado: ${DEFAULT_DEST}"
            exit 0
            ;;
        -y|--yes)
            AUTO_CONFIRM=true
            shift
            ;;
        --deploy|-b|--build)
            AUTO_DEPLOY=true
            shift
            ;;
        -d|--dest|--destination)
            CUSTOM_DEST="$2"
            shift 2
            ;;
        *)
            if [ -z "$CUSTOM_DEST" ]; then
                CUSTOM_DEST="$1"
            fi
            shift
            ;;
    esac
done

DEST_DIR="${CUSTOM_DEST:-$DEFAULT_DEST}"

# ==============================================================================
# PASO 1: Localizar los archivos fuente de la aplicación descomprimida
# ==============================================================================
log_step "1. Localizando Archivos Fuente del Paquete Descomprimido"

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_DIR="$(pwd)"

SRC_DIR=""

# Búsqueda en rutas relativas probables
candidates=(
    "${SCRIPT_PATH}/Dashboard"
    "${SCRIPT_PATH}/../Dashboard"
    "${SCRIPT_PATH}"
    "${CURRENT_DIR}/Dashboard"
    "${CURRENT_DIR}"
)

for cand in "${candidates[@]}"; do
    if [ -f "${cand}/docker-compose.yml" ] && [ -d "${cand}/app" ]; then
        SRC_DIR="$(cd "$cand" && pwd)"
        break
    fi
done

if [ -z "$SRC_DIR" ]; then
    log_err "No se pudo localizar el paquete de la aplicación (se requiere docker-compose.yml y carpeta app/)."
    echo -e "Asegúrate de estar en el directorio donde descomprimiste el archivo .tar.gz o .zip.\n"
    exit 1
fi

log_ok "Archivos fuente localizados en: ${CYAN}${SRC_DIR}${NC}"

# ==============================================================================
# PASO 2: Confirmación del Directorio Destino
# ==============================================================================
log_step "2. Verificación del Directorio de Destino"

echo -e "  Directorio destino propuesto: ${BOLD}${CYAN}${DEST_DIR}${NC}"
echo -e "  Propietario de los archivos:   ${BOLD}${TARGET_USER}${NC}"

# Si las rutas de origen y destino son idénticas
if [ "$SRC_DIR" = "$DEST_DIR" ]; then
    log_warn "El directorio de origen y el de destino son exactamente el mismo (${SRC_DIR})."
    echo -e "  No es necesario copiar archivos. Se procederá a ajustar permisos y preparar el despliegue.\n"
    IS_SAME_DIR=true
else
    IS_SAME_DIR=false
    if [ "$AUTO_CONFIRM" = false ]; then
        read -rp "¿Deseas instalar/actualizar los archivos en '${DEST_DIR}'? (S/n): " CONFIRM
        CONFIRM=${CONFIRM:-s}
        if [[ ! "$CONFIRM" =~ ^[sS]$ ]]; then
            log_warn "Operación cancelada por el usuario."
            exit 0
        fi
    fi
fi

# Crear directorio destino si no existe
if [ ! -d "$DEST_DIR" ]; then
    echo -e "  ${DIM}Creando directorio destino ${DEST_DIR}...${NC}"
    mkdir -p "$DEST_DIR"
    log_ok "Directorio creado exitosamente."
fi

# ==============================================================================
# PASO 3: Respaldo No Destructivo (.backups/)
# ==============================================================================
log_step "3. Respaldo Preventivo de Configuración Existente"

BACKUP_TS=$(date +"%Y%m%d_%H%M%S")
BACKUP_PATH="${DEST_DIR}/.backups/pre_copy_${BACKUP_TS}"

if [ -f "${DEST_DIR}/.env" ] || [ -d "${DEST_DIR}/data" ]; then
    mkdir -p "$BACKUP_PATH"
    
    if [ -f "${DEST_DIR}/.env" ]; then
        cp "${DEST_DIR}/.env" "${BACKUP_PATH}/.env"
        log_ok "Archivo .env previo respaldado en: ${DIM}${BACKUP_PATH}/.env${NC}"
    fi

    if [ -d "${DEST_DIR}/data" ]; then
        cp -r "${DEST_DIR}/data" "${BACKUP_PATH}/data" 2>/dev/null || true
        log_ok "Directorio data/ previo respaldado en: ${DIM}${BACKUP_PATH}/data${NC}"
    fi
else
    log_ok "No existía configuración previa que respaldar (instalación limpia)."
fi

# ==============================================================================
# PASO 4: Copia Limpia y Sincronización de Archivos
# ==============================================================================
log_step "4. Copiando y Sincronizando Archivos hacia Destino"

if [ "$IS_SAME_DIR" = false ]; then
    # 1. Copiar código de aplicación (FastAPI + SPA Static HUD)
    mkdir -p "${DEST_DIR}/app"
    cp -r "${SRC_DIR}/app"/* "${DEST_DIR}/app/"
    log_ok "Componentes de aplicación copiados (app/)."

    # 2. Copiar scripts de operación
    mkdir -p "${DEST_DIR}/scripts"
    if [ -d "${SRC_DIR}/scripts" ]; then
        cp -r "${SRC_DIR}/scripts"/* "${DEST_DIR}/scripts/"
    fi
    # Si scripts está en el nivel superior de la fuente
    if [ -d "${SRC_DIR}/../scripts" ]; then
        cp -r "${SRC_DIR}/../scripts"/* "${DEST_DIR}/scripts/" 2>/dev/null || true
    fi
    log_ok "Scripts de automatización y auditoría copiados (scripts/)."

    # 3. Copiar manifiestos Docker y dependencias
    [ -f "${SRC_DIR}/Dockerfile" ] && cp "${SRC_DIR}/Dockerfile" "${DEST_DIR}/"
    [ -f "${SRC_DIR}/docker-compose.yml" ] && cp "${SRC_DIR}/docker-compose.yml" "${DEST_DIR}/"
    [ -f "${SRC_DIR}/requirements.txt" ] && cp "${SRC_DIR}/requirements.txt" "${DEST_DIR}/"
    [ -f "${SRC_DIR}/.env.example" ] && cp "${SRC_DIR}/.env.example" "${DEST_DIR}/"
    [ -f "${SRC_DIR}/setup_proxmox_guide.md" ] && cp "${SRC_DIR}/setup_proxmox_guide.md" "${DEST_DIR}/"
    [ -f "${SRC_DIR}/README.md" ] && cp "${SRC_DIR}/README.md" "${DEST_DIR}/"
    log_ok "Manifiestos Dockerfile, docker-compose.yml y guías copiados."
fi

# ==============================================================================
# PASO 5: Migración de Configuración (.env) y Directorio de Datos Persistentes
# ==============================================================================
log_step "5. Asegurando Persistencia y Migración de Variables (.env)"

ENV_TARGET="${DEST_DIR}/.env"
EXAMPLE_SRC="${DEST_DIR}/.env.example"

# Si no existe .env en destino, crearlo desde .env.example
if [ ! -f "$ENV_TARGET" ]; then
    if [ -f "$EXAMPLE_SRC" ]; then
        cp "$EXAMPLE_SRC" "$ENV_TARGET"
        log_ok "Archivo .env inicial creado a partir de .env.example."
    else
        cat << 'EOF' > "$ENV_TARGET"
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
        log_ok "Archivo .env creado con plantilla base."
    fi
else
    # Preservar configuración existente pero inyectar las nuevas variables si faltan
    append_var() {
        local var_name="$1"
        local default_val="$2"
        if ! grep -q "^[[:space:]]*${var_name}=" "$ENV_TARGET"; then
            echo "${var_name}=${default_val}" >> "$ENV_TARGET"
            log_ok "Variable inyectada en .env: ${CYAN}${var_name}=${default_val}${NC}"
        fi
    }
    
    append_var "AUTH_TYPE" "token"
    append_var "PVE_PASSWORD" ""
    append_var "FALLBACK_TO_DEMO" "false"

    # Forzar que FALLBACK_TO_DEMO no esté en true para no engañar al operador con datos demo
    if grep -q "^[[:space:]]*FALLBACK_TO_DEMO=true" "$ENV_TARGET"; then
        sed -i 's/^[[:space:]]*FALLBACK_TO_DEMO=true/FALLBACK_TO_DEMO=false/' "$ENV_TARGET"
        log_ok "Ajustado FALLBACK_TO_DEMO=false para reportar fallos reales en lugar de datos demo."
    fi
fi

# Directorio de persistencia para la configuración Web
mkdir -p "${DEST_DIR}/data"
chmod 775 "${DEST_DIR}/data" 2>/dev/null || true
log_ok "Directorio de persistencia ./data configurado."

# ==============================================================================
# PASO 6: Ajuste de Permisos de Archivos y Scripts
# ==============================================================================
log_step "6. Ajustando Permisos de Ejecución y Propietario"

# Dar permisos de ejecución a todos los scripts
find "${DEST_DIR}/scripts" -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true
[ -f "${DEST_DIR}/deploy_to_destination.sh" ] && chmod +x "${DEST_DIR}/deploy_to_destination.sh" 2>/dev/null || true
log_ok "Permisos de ejecución (+x) asignados a todos los scripts bash."

# Ajustar propietario si se ejecuta con permisos de sudo
if [ "$(id -u)" -eq 0 ] && [ "$TARGET_USER" != "root" ]; then
    chown -R "${TARGET_USER}:${TARGET_USER}" "$DEST_DIR" 2>/dev/null || true
    log_ok "Propietario de los archivos asignado a '${TARGET_USER}:${TARGET_USER}'."
fi

# ==============================================================================
# RESUMEN Y DESPLIEGUE OPCIONAL
# ==============================================================================
echo -e "\n${GREEN}${BOLD}========================================================================${NC}"
echo -e "${GREEN}${BOLD}  ✅ ¡APLICACIÓN COPIADA Y CONFIGURADA EXITOSAMENTE EN DESTINO!        ${NC}"
echo -e "${GREEN}${BOLD}========================================================================${NC}"
echo -e "  Ubicación de producción: ${CYAN}${BOLD}${DEST_DIR}${NC}"
echo -e "  Archivo de variables:    ${DIM}${DEST_DIR}/.env${NC}"
echo -e "  Almacenamiento Web:      ${DIM}${DEST_DIR}/data/${NC}"
echo -e "========================================================================\n"

# Opción de Despliegue Automático
RUN_DEPLOY=false
if [ "$AUTO_DEPLOY" = true ]; then
    RUN_DEPLOY=true
elif [ "$AUTO_CONFIRM" = false ]; then
    echo -e "${BOLD}¿Deseas iniciar o actualizar el contenedor Docker ahora mismo?${NC}"
    read -rp "Ejecutar despliegue en producción inmediatamente (S/n): " IN_DEPLOY
    IN_DEPLOY=${IN_DEPLOY:-s}
    if [[ "$IN_DEPLOY" =~ ^[sS]$ ]]; then
        RUN_DEPLOY=true
    fi
fi

if [ "$RUN_DEPLOY" = true ]; then
    log_step "Iniciando Despliegue en Producción..."
    cd "$DEST_DIR"
    if [ -f "${DEST_DIR}/scripts/update_production.sh" ]; then
        bash "${DEST_DIR}/scripts/update_production.sh"
    else
        docker compose down 2>/dev/null || true
        docker rm -f proxmox-spotlight-dashboard 2>/dev/null || true
        docker compose up -d --build
        echo -e "\n${GREEN}[✓] Contenedor Docker iniciado en segundo plano.${NC}"
        echo -e "Acceso: ${CYAN}http://localhost:8080${NC}\n"
    fi
else
    echo -e "Para iniciar o actualizar el contenedor más tarde, ejecuta:"
    echo -e "  ${CYAN}cd ${DEST_DIR} && bash scripts/update_production.sh${NC}\n"
fi
