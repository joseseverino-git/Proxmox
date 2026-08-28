#!/usr/bin/env bash
# ==============================================================================
# 🛡️ Spotlight on Proxmox VE — Script de Configuración en el Servidor Proxmox
# ==============================================================================
# Este script crea automáticamente en Proxmox VE:
#  1. El usuario 'monitoring@pve'.
#  2. Asigna permisos de solo lectura (rol PVEAuditor) en la raíz '/'.
#  3. Genera un API Token llamado 'spotlight' (sin separación de privilegios).
#  4. Muestra en pantalla el UUID secreto formateado listo para copiar al .env.
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "\n${BOLD}${CYAN}======================================================${NC}"
echo -e "${BOLD}${CYAN}  🛡️ Configuración de Usuario y Token en Proxmox VE${NC}"
echo -e "${BOLD}${CYAN}======================================================${NC}\n"

# 1. Verificar si se está ejecutando en un nodo Proxmox VE
if ! command -v pveum &>/dev/null; then
    echo -e "${RED}[ERROR] El comando 'pveum' no fue encontrado.${NC}"
    echo -e "Este script debe ejecutarse directamente en la consola Shell del servidor Proxmox VE.\n"
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Este script debe ejecutarse como root en Proxmox VE.${NC}\n"
    exit 1
fi

USER_NAME="monitoring"
REALM="pve"
FULL_USER="${USER_NAME}@${REALM}"
TOKEN_NAME="spotlight"

# 2. Crear usuario si no existe
if pveum user list | grep -q "$FULL_USER"; then
    echo -e "${YELLOW}[INFO] El usuario '${FULL_USER}' ya existe en Proxmox VE.${NC}"
else
    echo -e "${CYAN}[INFO] Creando usuario '${FULL_USER}'...${NC}"
    pveum user add "$FULL_USER" --comment "Usuario solo lectura para Spotlight Dashboard"
    echo -e "${GREEN}[OK] Usuario creado exitosamente.${NC}"
fi

# 3. Asignar rol PVEAuditor
echo -e "${CYAN}[INFO] Asignando permisos de solo lectura (rol PVEAuditor) en '/'...${NC}"
pveum acl modify / -user "$FULL_USER" -role PVEAuditor
echo -e "${GREEN}[OK] Permisos asignados correctamente.${NC}"

# 4. Crear API Token
echo -e "${CYAN}[INFO] Generando API Token '${TOKEN_NAME}' para '${FULL_USER}'...${NC}"

# Si el token ya existe, preguntar si se desea regenerar
if pveum user token list "$FULL_USER" 2>/dev/null | grep -q "$TOKEN_NAME"; then
    echo -e "${YELLOW}[WARN] El token '${TOKEN_NAME}' ya existe.${NC}"
    read -rp "¿Deseas eliminar el token existente y generar uno nuevo? (s/N): " REGEN_TOKEN
    if [[ "$REGEN_TOKEN" =~ ^[sS]$ ]]; then
        pveum user token delete "$FULL_USER" "$TOKEN_NAME"
        echo -e "${CYAN}[INFO] Token anterior eliminado.${NC}"
    else
        echo -e "${YELLOW}[INFO] Operación finalizada. Usa el token previamente generado.${NC}"
        exit 0
    fi
fi

TOKEN_OUTPUT=$(pveum user token add "$FULL_USER" "$TOKEN_NAME" --privsep 0 --output-format json 2>/dev/null || pveum user token add "$FULL_USER" "$TOKEN_NAME" --privsep 0)

# Extraer el valor del token
SECRET_VAL=""
if echo "$TOKEN_OUTPUT" | grep -q "^{"; then
    SECRET_VAL=$(echo "$TOKEN_OUTPUT" | grep -o '"value":"[^"]*"' | cut -d'"' -f4)
else
    SECRET_VAL=$(echo "$TOKEN_OUTPUT" | grep -E "value\s*│" | awk -F'│' '{print $3}' | tr -d ' ')
fi

echo -e "\n${BOLD}${GREEN}======================================================${NC}"
echo -e "${BOLD}${GREEN}  ✅ ¡API Token Generado con Éxito!${NC}"
echo -e "${BOLD}${GREEN}======================================================${NC}\n"

echo -e "Datos para tu archivo ${BOLD}.env${NC} en la Raspberry Pi:\n"
echo -e "  • ${BOLD}PVE_USER${NC}=${FULL_USER}"
echo -e "  • ${BOLD}PVE_TOKEN_NAME${NC}=${TOKEN_NAME}"
echo -e "  • ${BOLD}PVE_TOKEN_VALUE${NC}=${BOLD}${YELLOW}${SECRET_VAL}${NC}"
echo -e ""
echo -e "${YELLOW}⚠️ NOTA: Guarda el valor secreto (PVE_TOKEN_VALUE), Proxmox no lo volverá a mostrar.${NC}\n"
