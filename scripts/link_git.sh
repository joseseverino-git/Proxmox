#!/usr/bin/env bash
# ==============================================================================
# 🔗 VINCULADOR DE REPOSITORIO GIT PARA SPOTLIGHT ON PROXMOX VE
# ==============================================================================
# Convierte el directorio local en un repositorio Git conectado a:
# https://github.com/joseseverino-git/Proxmox.git
# Permitiendo que "git pull origin main" funcione en futuras actualizaciones.
# ==============================================================================

set -uo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_URL="https://github.com/joseseverino-git/Proxmox.git"
TARGET_DIR="$(pwd)"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║       🔗 VINCULACIÓN CON REPOSITORIO GITHUB EN PRODUCCIÓN            ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "Directorio actual: ${BOLD}${TARGET_DIR}${NC}"
echo -e "Repositorio remoto: ${CYAN}${REPO_URL}${NC}\n"

# 1. Asegurar git instalado
if ! command -v git &>/dev/null; then
    echo -e "${YELLOW}[!] Git no está instalado. Instalando con apt...${NC}"
    sudo apt update -y && sudo apt install -y git
fi

# 2. Inicializar repositorio si no existe
if [ ! -d ".git" ]; then
    echo -e "  [+] Inicializando repositorio git local..."
    git init -b main
else
    echo -e "  [✓] Repositorio git ya inicializado localmente."
fi

# 3. Configurar remote origin
if git remote | grep -q "^origin$"; then
    echo -e "  [+] Actualizando URL de origen remoto a: ${REPO_URL}"
    git remote set-url origin "$REPO_URL"
else
    echo -e "  [+] Añadiendo origen remoto: ${REPO_URL}"
    git remote add origin "$REPO_URL"
fi

# 4. Descargar historial y sincronizar sin borrar .env
echo -e "  [+] Obteniendo última versión de GitHub (git fetch)..."
git fetch origin main

# Preservar .env
if [ -f ".env" ]; then
    cp .env .env.bak.gitlink
    echo -e "  [✓] Respaldo de .env asegurado."
fi

echo -e "  [+] Alineando rama local con origin/main..."
git branch -M main
git reset --mixed origin/main 2>/dev/null || true
git checkout -f main 2>/dev/null || git checkout -b main origin/main

if [ -f ".env.bak.gitlink" ]; then
    mv -f .env.bak.gitlink .env
fi

# Dar permisos de ejecución
find scripts/ -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true

echo -e "\n${GREEN}${BOLD}✓ ¡VINCULACIÓN EXITOSA!${NC}"
echo -e "A partir de ahora puedes actualizar en cualquier momento ejecutando:"
echo -e "  ${BOLD}git pull origin main${NC}"
echo -e "  ${BOLD}bash scripts/update_production.sh${NC}\n"
