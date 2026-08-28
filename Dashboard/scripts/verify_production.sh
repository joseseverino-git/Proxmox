#!/usr/bin/env bash
# ==============================================================================
# 🩺 SRE/DevOps Diagnostic & Verification Suite
# Spotlight on Proxmox VE — Producción & Health Check
# ==============================================================================
# Propósito:
#   Auditar y validar de punta a punta que la aplicación Spotlight Dashboard
#   en Docker (Raspberry Pi OS / Debian) esté 100% operativa y comunicándose
#   en VIVO con el clúster o servidor Proxmox VE en MODO PRODUCTIVO.
#
# Autor: DevOps / SRE Engineering Team
# ==============================================================================

set -uo pipefail

# --- Colores y Formato ANSI ---
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly NC='\033[0m' # No Color

# --- Variables de Diagnóstico ---
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0
declare -a REMEDIATION_STEPS=()

# --- Funciones de Salida ---
print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║       🚀 SPOTLIGHT ON PROXMOX VE — AUDITORÍA SRE EN PRODUCCIÓN       ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_section() {
    echo -e "\n${BOLD}${MAGENTA}▶ $1${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────────────────────────${NC}"
}

test_pass() {
    ((TOTAL_TESTS++))
    ((PASSED_TESTS++))
    echo -e "  ${GREEN}[✓] PASS:${NC} $1"
}

test_warn() {
    ((TOTAL_TESTS++))
    ((WARNINGS++))
    echo -e "  ${YELLOW}[!] WARN:${NC} $1"
    if [ -n "${2:-}" ]; then
        REMEDIATION_STEPS+=("🟡 [Advertencia] $2")
    fi
}

test_fail() {
    ((TOTAL_TESTS++))
    ((FAILED_TESTS++))
    echo -e "  ${RED}[✗] FAIL:${NC} $1"
    if [ -n "${2:-}" ]; then
        REMEDIATION_STEPS+=("🔴 [Corrección Crítica] $2")
    fi
}

# --- 1. Localizar Entorno y Archivo .env ---
locate_env_file() {
    local candidates=(
        "./.env"
        "./Dashboard/.env"
        "../.env"
        "../Dashboard/.env"
        "/opt/spotlight-proxmox/.env"
    )
    
    for path in "${candidates[@]}"; do
        if [[ -f "$path" ]]; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

# --- 2. Carga segura de variables .env ---
load_env_vars() {
    local env_path="$1"
    while IFS='=' read -r key value || [[ -n "$key" ]]; do
        # Omitir comentarios y líneas vacías
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        
        # Limpiar espacios y comillas
        key="$(echo "$key" | xargs)"
        value="$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')"
        
        case "$key" in
            PVE_HOST) PVE_HOST="$value" ;;
            AUTH_TYPE) AUTH_TYPE="$value" ;;
            PVE_USER) PVE_USER="$value" ;;
            PVE_TOKEN_NAME) PVE_TOKEN_NAME="$value" ;;
            PVE_TOKEN_VALUE) PVE_TOKEN_VALUE="$value" ;;
            PVE_PASSWORD) PVE_PASSWORD="$value" ;;
            PVE_VERIFY_SSL) PVE_VERIFY_SSL="$value" ;;
            PVE_TIMEOUT) PVE_TIMEOUT="$value" ;;
            PORT) PORT="$value" ;;
            DEMO_MODE) DEMO_MODE="$value" ;;
            FALLBACK_TO_DEMO) FALLBACK_TO_DEMO="$value" ;;
        esac
    done < "$env_path"
}

# ==============================================================================
# MAIN DIAGNOSTIC WORKFLOW
# ==============================================================================

print_banner

# ------------------------------------------------------------------------------
# FASE 1: Verificación de Archivos y Configuración (.env)
# ------------------------------------------------------------------------------
log_section "FASE 1: Análisis de Configuración y Variables de Entorno (.env)"

ENV_FILE=$(locate_env_file || true)

if [[ -z "$ENV_FILE" ]]; then
    test_fail "No se encontró el archivo '.env' en las rutas estándar." \
        "Crea el archivo .env ejecutando: cp Dashboard/.env.example Dashboard/.env y añade tu PVE_TOKEN_VALUE."
    PVE_HOST="https://192.168.1.100:8006"
    PVE_USER="monitoring@pve"
    PVE_TOKEN_NAME="spotlight"
    PVE_TOKEN_VALUE=""
    PVE_VERIFY_SSL="false"
    PORT="8080"
    DEMO_MODE="false"
else
    test_pass "Archivo de configuración encontrado en: ${BOLD}${ENV_FILE}${NC}"
    
    # Valores predeterminados
    PVE_HOST="https://192.168.1.100:8006"
    AUTH_TYPE="token"
    PVE_PASSWORD=""
    FALLBACK_TO_DEMO="false"
    
    load_env_vars "$ENV_FILE"
    
    # Validar PVE_HOST
    if [[ -z "$PVE_HOST" || "$PVE_HOST" == *"192.168.1.100"* ]]; then
        test_warn "PVE_HOST parece tener la IP por defecto de ejemplo (${PVE_HOST})." \
            "Si la IP de tu Proxmox no es 192.168.1.100, configúrala en la ventana '⚙ Configuración' o edita ${ENV_FILE}."
    else
        test_pass "PVE_HOST configurado: ${CYAN}${PVE_HOST}${NC}"
    fi

    # Validar DEMO_MODE
    if [[ "${DEMO_MODE,,}" == "true" ]]; then
        test_fail "DEMO_MODE está activado explícitamente (DEMO_MODE=true)." \
            "Para trabajar en producción real, cambia 'DEMO_MODE=false' en la ventana de Configuración o en ${ENV_FILE}."
    else
        test_pass "Modo Demo desactivado (DEMO_MODE=false) -> Modo Productivo habilitado."
    fi

    # Validar Autenticación
    AUTH_TYPE="${AUTH_TYPE:-token}"
    if [[ "${AUTH_TYPE,,}" == "password" ]]; then
        if [[ -z "$PVE_PASSWORD" ]]; then
            test_fail "AUTH_TYPE=password pero PVE_PASSWORD está vacío." \
                "Configura la contraseña de Proxmox en la ventana '⚙ Configuración' o en ${ENV_FILE}."
        else
            test_pass "Autenticación por contraseña configurada para el usuario ${CYAN}${PVE_USER}${NC}"
        fi
    else
        if [[ -z "$PVE_TOKEN_VALUE" || "$PVE_TOKEN_VALUE" == "your-token-secret-uuid-here" || "$PVE_TOKEN_VALUE" == *"xxxx"* ]]; then
            test_fail "PVE_TOKEN_VALUE está vacío o tiene el valor de plantilla." \
                "Genera el token en Proxmox o configúralo directamente en la ventana '⚙ Configuración' del Dashboard."
        else
            TOKEN_MASKED="${PVE_TOKEN_VALUE:0:6}******${PVE_TOKEN_VALUE: -4}"
            test_pass "Token Proxmox configurado: ${CYAN}${PVE_USER}!${PVE_TOKEN_NAME}=${TOKEN_MASKED}${NC}"
        fi
    fi

    # Validar formato de URL
    if [[ ! "$PVE_HOST" =~ ^https?:// ]]; then
        PVE_FORMATTED_HOST="https://${PVE_HOST}"
    else
        PVE_FORMATTED_HOST="$PVE_HOST"
    fi
    if [[ ! "$PVE_FORMATTED_HOST" =~ :[0-9]+$ ]]; then
        PVE_FORMATTED_HOST="${PVE_FORMATTED_HOST}:8006"
    fi
fi

# ------------------------------------------------------------------------------
# FASE 2: Conectividad de Red y Socket TCP hacia Proxmox VE
# ------------------------------------------------------------------------------
log_section "FASE 2: Conectividad de Red (Raspberry Pi ➔ Proxmox VE)"

# Extraer Host y Puerto
PVE_RAW_HOST=$(echo "$PVE_FORMATTED_HOST" | sed -e 's|^[^/]*//||' -e 's|/.*$||' -e 's|:.*$||')
PVE_RAW_PORT=$(echo "$PVE_FORMATTED_HOST" | sed -e 's|^[^/]*//||' -e 's|/.*$||' | grep -o ':[0-9]*$' | tr -d ':' || echo "8006")
[ -z "$PVE_RAW_PORT" ] && PVE_RAW_PORT="8006"

echo -e "  ${DIM}Destino Proxmox: ${PVE_RAW_HOST} en puerto TCP ${PVE_RAW_PORT}${NC}"

# Prueba de Socket TCP directo
if timeout 3 bash -c "</dev/tcp/${PVE_RAW_HOST}/${PVE_RAW_PORT}" 2>/dev/null; then
    test_pass "Conexión TCP establecida exitosamente con ${PVE_RAW_HOST}:${PVE_RAW_PORT}"
elif command -v nc &>/dev/null && nc -z -w 3 "$PVE_RAW_HOST" "$PVE_RAW_PORT" &>/dev/null; then
    test_pass "Conexión TCP (nc) exitosa hacia ${PVE_RAW_HOST}:${PVE_RAW_PORT}"
elif curl -k -s --connect-timeout 3 "${PVE_FORMATTED_HOST}/api2/json" &>/dev/null; then
    test_pass "Socket Web HTTPS accesible en ${PVE_FORMATTED_HOST}"
else
    test_fail "No se puede alcanzar ${PVE_RAW_HOST} en el puerto ${PVE_RAW_PORT}." \
        "Verifica: 1) Que la IP '${PVE_RAW_HOST}' sea correcta y esté encendida. 2) Que no haya un firewall bloqueando el puerto 8006. 3) Prueba hacer 'ping -c 3 ${PVE_RAW_HOST}'."
fi

# ------------------------------------------------------------------------------
# FASE 3: Autenticación y Autorización API Proxmox VE
# ------------------------------------------------------------------------------
log_section "FASE 3: Autenticación y Permisos del API Token en Proxmox VE"

CURL_SSL_FLAG="-k"
if [[ "${PVE_VERIFY_SSL,,}" == "true" ]]; then
    CURL_SSL_FLAG=""
fi

if [[ -n "$PVE_TOKEN_VALUE" && "$PVE_TOKEN_VALUE" != "your-token-secret-uuid-here" ]]; then
    AUTH_HEADER="Authorization: PVEAPIToken=${PVE_USER}!${PVE_TOKEN_NAME}=${PVE_TOKEN_VALUE}"
    
    # 1. Test Endpoint /api2/json/version (Autenticación)
    HTTP_RESP=$(curl -s -w "\n%{http_code}\n%{time_total}" $CURL_SSL_FLAG -m 5 \
        -H "$AUTH_HEADER" \
        "${PVE_FORMATTED_HOST}/api2/json/version" 2>&1 || true)
    
    HTTP_BODY=$(echo "$HTTP_RESP" | sed '$d' | sed '$d')
    HTTP_CODE=$(echo "$HTTP_RESP" | tail -n2 | head -n1)
    HTTP_TIME=$(echo "$HTTP_RESP" | tail -n1)

    if [[ "$HTTP_CODE" == "200" ]]; then
        PVE_VER_STR=$(echo "$HTTP_BODY" | grep -o '"release":"[^"]*"' | cut -d'"' -f4 || echo "OK")
        LATENCY_MS=$(awk "BEGIN {print int(${HTTP_TIME} * 1000)}")
        test_pass "API Token autenticado correctamente contra Proxmox VE (Versión: ${PVE_VER_STR} | Latencia: ${LATENCY_MS}ms)."
    elif [[ "$HTTP_CODE" == "401" ]]; then
        test_fail "Error 401 Unauthorized: El Token ID o Token Secret UUID es inválido en Proxmox." \
            "En Proxmox Shell, regenera el token: pveum user token add ${PVE_USER} ${PVE_TOKEN_NAME} --privsep 0 y actualiza PVE_TOKEN_VALUE en .env."
    elif [[ "$HTTP_CODE" == "403" ]]; then
        test_fail "Error 403 Forbidden: El usuario ${PVE_USER} no tiene permisos asignados." \
            "En Proxmox Shell, asigna el rol: pveum acl modify / -user ${PVE_USER} -role PVEAuditor"
    else
        test_fail "Respuesta inesperada de la API Proxmox (HTTP ${HTTP_CODE}). Detalle: ${HTTP_BODY:0:120}" \
            "Verifica que el servicio pveproxy esté corriendo en Proxmox (systemctl status pveproxy)."
    fi

    # 2. Test Endpoint /api2/json/cluster/resources (Autorización y lectura de recursos)
    RES_RESP=$(curl -s $CURL_SSL_FLAG -m 5 -H "$AUTH_HEADER" "${PVE_FORMATTED_HOST}/api2/json/cluster/resources" 2>&1 || true)
    if [[ "$RES_RESP" == *"\"data\":"* ]]; then
        NODE_COUNT=$(echo "$RES_RESP" | grep -o '"type":"node"' | wc -l | tr -d ' ' || echo "0")
        VM_COUNT=$(echo "$RES_RESP" | grep -o '"type":"qemu"' | wc -l | tr -d ' ' || echo "0")
        LXC_COUNT=$(echo "$RES_RESP" | grep -o '"type":"lxc"' | wc -l | tr -d ' ' || echo "0")
        test_pass "Permisos de lectura verificados: ${GREEN}${NODE_COUNT} Nodos${NC}, ${GREEN}${VM_COUNT} VMs (QEMU)${NC}, ${GREEN}${LXC_COUNT} Contenedores (LXC)${NC} detectados en vivo."
    else
        test_warn "No se pudieron listar los recursos del clúster. Verifica que el rol PVEAuditor esté asignado en el path '/'." \
            "Ejecuta en Proxmox: pveum acl modify / -user ${PVE_USER} -role PVEAuditor"
    fi
else
    test_fail "Omitiendo prueba de API Proxmox: PVE_TOKEN_VALUE no está configurado." \
        "Configura tu PVE_TOKEN_VALUE en el archivo .env."
fi

# ------------------------------------------------------------------------------
# FASE 4: Estado del Motor Docker y Contenedor en Raspberry Pi
# ------------------------------------------------------------------------------
log_section "FASE 4: Inspección de Docker y Contenedor en Raspberry Pi"

if command -v docker &>/dev/null; then
    test_pass "Motor Docker instalado y disponible ($(docker --version | awk '{print $3}' | tr -d ','))."
    
    # Buscar contenedor de Spotlight
    CONTAINER_ID=$(docker ps -q --filter "name=spotlight" --filter "name=proxmox" | head -n1 || true)
    
    if [[ -n "$CONTAINER_ID" ]]; then
        CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
        CONTAINER_HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER_ID" 2>/dev/null || echo "none")
        CONTAINER_PORTS=$(docker port "$CONTAINER_ID" 2>/dev/null || echo "8080/tcp")
        
        if [[ "$CONTAINER_STATUS" == "running" ]]; then
            test_pass "Contenedor en ejecución (ID: ${CONTAINER_ID:0:12} | Estado: ${CONTAINER_STATUS} | Puertos: ${CONTAINER_PORTS})."
            
            if [[ "$CONTAINER_HEALTH" == "healthy" ]]; then
                test_pass "Healthcheck de Docker: ${GREEN}HEALTHY${NC}"
            elif [[ "$CONTAINER_HEALTH" == "unhealthy" ]]; then
                test_fail "Healthcheck de Docker: UNHEALTHY" \
                    "Revisa los logs del contenedor con: docker logs --tail 50 ${CONTAINER_ID}"
            fi
        else
            test_fail "El contenedor no está en estado 'running' (Estado actual: ${CONTAINER_STATUS})." \
                "Inicia el servicio ejecutando: docker compose up -d"
        fi
    else
        test_fail "No se encontró ningún contenedor activo con el nombre 'spotlight' o 'proxmox'." \
            "Levanta el contenedor desde la carpeta Dashboard con: docker compose up -d --build"
    fi
else
    test_fail "El comando 'docker' no está disponible en este sistema." \
        "Instala Docker en Raspberry Pi OS con: curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker \$USER"
fi

# ------------------------------------------------------------------------------
# FASE 5: Salud Operativa del Dashboard y Modo Productivo End-to-End
# ------------------------------------------------------------------------------
log_section "FASE 5: Verificación End-to-End del Dashboard Web (/api/status)"

LOCAL_PORT="${PORT:-8080}"
DASH_HEALTH_URL="http://localhost:${LOCAL_PORT}/api/health"
DASH_STATUS_URL="http://localhost:${LOCAL_PORT}/api/status"

echo -e "  ${DIM}Consultando API local en: ${DASH_HEALTH_URL}${NC}"

HEALTH_JSON=$(curl -s -m 4 "$DASH_HEALTH_URL" 2>/dev/null || echo "")

if [[ -n "$HEALTH_JSON" && "$HEALTH_JSON" == *"\"status\":\"healthy\""* ]]; then
    test_pass "Endpoint /api/health responde con estado HTTP 200 OK y estado saludable."
    
    # Verificar si está en demo o productivo
    if [[ "$HEALTH_JSON" == *"\"demo_mode\":false"* && "$HEALTH_JSON" == *"\"configured\":true"* ]]; then
        test_pass "${BOLD}${GREEN}🎯 LA APLICACIÓN ESTÁ OPERANDO EN MODO PRODUCTIVO (TELEMETRÍA REAL EN VIVO).${NC}"
    else
        test_warn "La aplicación está respondiendo en MODO DEMO o MODO FALLBACK." \
            "El dashboard está mostrando datos simulados. Revisa que el archivo .env tenga las credenciales correctas y reinicia con: docker compose restart."
    fi
else
    test_fail "No se pudo comunicar con el Dashboard local en el puerto ${LOCAL_PORT}." \
        "Verifica que el puerto ${LOCAL_PORT} esté libre y que el contenedor esté corriendo con 'docker compose ps'."
fi

# Consultar endpoint completo de estado /api/status
STATUS_JSON=$(curl -s -m 5 "$DASH_STATUS_URL" 2>/dev/null || echo "")
if [[ -n "$STATUS_JSON" ]]; then
    CONN_MODE=$(echo "$STATUS_JSON" | grep -o '"mode":"[^"]*"' | cut -d'"' -f4 || echo "UNKNOWN")
    CONN_STATUS=$(echo "$STATUS_JSON" | grep -o '"connected":[^,}]*' | head -n1 || echo "")
    
    if [[ "$CONN_MODE" == "LIVE_PVE" ]]; then
        test_pass "Modo de conexión del Dashboard: ${GREEN}${BOLD}LIVE_PVE (Conexión activa y confirmada con Proxmox VE)${NC}"
        
        CLUSTER_NAME=$(echo "$STATUS_JSON" | grep -o '"cluster_name":"[^"]*"' | cut -d'"' -f4 || echo "Proxmox")
        HEALTH_SCORE=$(echo "$STATUS_JSON" | grep -o '"health_score":[0-9]*' | cut -d':' -f2 || echo "100")
        echo -e "     • Clúster detectado:   ${BOLD}${CYAN}${CLUSTER_NAME}${NC}"
        echo -e "     • Spotlight Health Score: ${BOLD}${GREEN}${HEALTH_SCORE} / 100${NC}"
    elif [[ "$CONN_MODE" == "FALLBACK_DEMO" ]]; then
        ERROR_MSG=$(echo "$STATUS_JSON" | grep -o '"message":"[^"]*"' | cut -d'"' -f4 || echo "Error de conexión")
        if [[ "$ERROR_MSG" == *"CERTIFICATE_VERIFY_FAILED"* || "$ERROR_MSG" == *"certificate verify failed"* ]]; then
            test_fail "El dashboard cayó en MODO FALLBACK por error de certificado SSL: ${ERROR_MSG}" \
                "Proxmox VE usa por defecto certificados SSL autofirmados. Configura 'PVE_VERIFY_SSL=false' en tu archivo .env y reinicia el contenedor con: docker compose down && docker compose up -d"
        else
            test_fail "El dashboard cayó en MODO FALLBACK por error de conexión con Proxmox: ${ERROR_MSG}" \
                "Revisa las credenciales en .env y la conectividad IP con Proxmox."
        fi
    elif [[ "$CONN_MODE" == "DEMO_MODE" ]]; then
        test_warn "El dashboard está operando en MODO DEMO (datos simulados)." \
            "Configura PVE_TOKEN_VALUE en .env y pon DEMO_MODE=false para activar la telemetría productiva."
    fi
fi

# ------------------------------------------------------------------------------
# RESUMEN FINAL & INSTRUCCIONES DE REMEDIACIÓN
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${CYAN}========================================================================${NC}"
echo -e "${BOLD}${CYAN}                        RESUMEN DE AUDITORÍA SRE                        ${NC}"
echo -e "${BOLD}${CYAN}========================================================================${NC}"

echo -e "  Total de Pruebas Ejecutadas: ${BOLD}${TOTAL_TESTS}${NC}"
echo -e "  Pruebas Exitosas:           ${GREEN}${BOLD}${PASSED_TESTS}${NC}"
echo -e "  Advertencias:               ${YELLOW}${BOLD}${WARNINGS}${NC}"
echo -e "  Fallos Críticos:            ${RED}${BOLD}${FAILED_TESTS}${NC}"

IP_LOCAL=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

if [[ "$FAILED_TESTS" -eq 0 && "$WARNINGS" -eq 0 ]]; then
    echo -e "\n${GREEN}${BOLD}🏆 ¡ESTADO EXCELENTE!${NC}"
    echo -e "${GREEN}La aplicación Spotlight on Proxmox VE está 100% operativa, integrada y en producción.${NC}"
    echo -e "Puedes acceder a tu Dashboard en: ${CYAN}${BOLD}http://${IP_LOCAL}:${LOCAL_PORT}${NC}\n"
    exit 0
elif [[ "$FAILED_TESTS" -eq 0 && "$WARNINGS" -gt 0 ]]; then
    echo -e "\n${YELLOW}${BOLD}⚠️ OPERATIVO CON ADVERTENCIAS${NC}"
    echo -e "La aplicación funciona pero hay recomendaciones de configuración a revisar:"
    for step in "${REMEDIATION_STEPS[@]}"; do
        echo -e "  $step"
    done
    echo ""
    exit 0
else
    echo -e "\n${RED}${BOLD}❌ ATENCIÓN: SE DETECTARON FALLOS CRÍTICOS EN LA INTEGRACIÓN${NC}"
    echo -e "Sigue las siguientes instrucciones paso a paso para corregir el entorno:\n"
    
    STEP_NUM=1
    for step in "${REMEDIATION_STEPS[@]}"; do
        echo -e "${BOLD}${CYAN}[PASO ${STEP_NUM}]${NC} $step"
        ((STEP_NUM++))
    done
    
    echo -e "\n${BOLD}Comandos rápidos de solución en caso de fallo común:${NC}"
    echo -e "${DIM}-----------------------------------------------------------------------${NC}"
    echo -e "${BOLD}1. Si el fallo es en Proxmox (Token o Permisos):${NC}"
    echo -e "   Ejecuta en la consola Shell de Proxmox:"
    echo -e "   ${CYAN}pveum user add monitoring@pve --comment 'Spotlight Dashboard'${NC}"
    echo -e "   ${CYAN}pveum acl modify / -user monitoring@pve -role PVEAuditor${NC}"
    echo -e "   ${CYAN}pveum user token add monitoring@pve spotlight --privsep 0${NC}"
    echo -e ""
    echo -e "${BOLD}2. Si el fallo es en Raspberry Pi (Variables .env o Docker):${NC}"
    echo -e "   Edita el archivo .env con tus datos reales:"
    echo -e "   ${CYAN}nano ${ENV_FILE:-Dashboard/.env}${NC}"
    echo -e "   Y reinicia el contenedor con:"
    echo -e "   ${CYAN}docker compose down && docker compose up -d --build${NC}"
    echo -e "${DIM}-----------------------------------------------------------------------${NC}\n"
    exit 1
fi
