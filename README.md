# 🌟 Spotlight on Proxmox VE — Dashboard de Monitoreo Autocontenido

Aplicación de monitoreo autocontenida y ligera inspirada en la clásica interfaz y paleta diagnóstica de **Spotlight de Quest Software**, diseñada específicamente para desplegarse mediante **Docker** en un **Raspberry Pi 4 B (ARM64)** o Debian y monitorear servidores o clústeres de **Proxmox VE**.

---

## 🚀 Nuevas Funcionalidades: Configuración Web y Centro de Troubleshooting SRE

### 1. ⚙️ Ventana de Configuración en el Aplicativo (Web UI)
Ya no necesitas editar manualmente archivos por terminal para configurar o cambiar la conexión con tu servidor Proxmox VE:
- **Acceso directo**: Haz clic en el botón `⚙ Configuración` en la esquina superior derecha del dashboard.
- **Parámetros configurables**:
  - **Host / IP de Proxmox**: URL con puerto 8006 (ej. `https://192.168.1.100:8006`).
  - **Tipo de Autenticación**: Selector entre **API Token** (recomendado para monitoreo) y **Usuario y Contraseña** (autenticación por ticket PVE).
  - **Usuario y Realm**: Soporte para reinos `@pve` y `@pam` (ej. `monitoring@pve` o `root@pam`).
  - **Secret UUID o Password**: Campo protegido con botón de mostrar/ocultar y detección de credenciales ya guardadas.
  - **Seguridad SSL**: Conmutador para ignorar verificación de certificados autofirmados (estándar en Proxmox VE).
  - **Modo de Operación**: Selector de **Producción (Datos Reales)** vs. **Demostración (Simulado)**.
  - **Política de Fallback a Demo**: Permite activar o desactivar si deseas que la plataforma muestre datos falsos en caso de caída de red (por defecto desactivado para garantizar transparencia de diagnóstico).
- **Prueba en Vivo**: Botón **"Probar Conexión Ahora"** que evalúa la conectividad y credenciales en tiempo real mostrando latencia RTT antes de guardar.
- **Persistencia en Caliente**: Guarda cambios en `.env` y `data/settings.json`, recargando la configuración en memoria instantáneamente sin requerir reiniciar el contenedor Docker.

---

### 2. 🩺 Centro de Troubleshooting & Diagnóstico SRE
Diagnostica con precisión quirúrgica cualquier problema de comunicación entre la Raspberry Pi / host y tu servidor Proxmox VE:
- **Acceso directo**: Botón `🩺 Troubleshooting` en la barra superior o mediante el banner de advertencia automático si se detecta desconexión.
- **Pestaña 1: Auditoría Automatizada de 6 Capas**:
  1. **Configuración Local**: Valida variables `.env`, formato de IP, usuario y token.
  2. **Conectividad de Red L4 / TCP**: Abre un socket TCP hacia el puerto 8006, mide la latencia de red y detecta bloqueos de firewall o caída de `pveproxy`.
  3. **Seguridad SSL / TLS**: Analiza la negociación criptográfica y certificados autofirmados.
  4. **API de Proxmox VE**: Consulta el endpoint `/api2/json/version` y detecta la versión exacta instalada.
  5. **Autenticación**: Valida el API Token o genera un ticket de sesión para comprobar validez de credenciales.
  6. **Permisos RBAC y Telemetría**: Comprueba lectura en `/api2/json/cluster/resources` y audita el rol `PVEAuditor`.
- **Pestaña 2: Comandos Rápidos de Remediación**: Comandos exactos de Proxmox CLI (`pveum`) con botones de copiado en un clic para crear usuarios, asignar roles y generar tokens.
- **Pestaña 3: Visor de Logs del Servidor**: Consola interactiva en vivo con los últimos eventos del backend, filtros por nivel (`ERROR`, `WARN`, `INFO`), recarga y copiado al portapapeles.

---

## ⚡ Despliegue Rápido Automatizado con Scripts

### 1. En el Servidor Proxmox VE (Crear Usuario y API Token)
Ejecuta en la consola Shell (como `root`) de tu servidor Proxmox VE:

```bash
sudo bash scripts/setup_proxmox.sh
```
*Este script crea automáticamente el usuario `monitoring@pve`, le asigna el rol de solo lectura `PVEAuditor` y genera el API Token `spotlight` mostrando el valor secreto listo para copiar.*

---

### 2. En la Raspberry Pi 4 B (Desplegar directamente con el usuario sysadmin)
Ejecuta en la terminal de tu Raspberry Pi como usuario `sysadmin` (sin necesidad de `sudo`):

```bash
bash scripts/setup_raspberry.sh
```
*Este script realiza todo automáticamente:*
- ✅ Verifica el acceso al motor Docker y Docker Compose bajo `sysadmin`.
- ✅ Configura interactivamente las credenciales de conexión con Proxmox VE (`.env`).
- ✅ Compila e inicia el contenedor con `docker compose up -d --build`.
- ✅ Muestra los enlaces de acceso y comandos de mantenimiento.
- ✅ Proporciona opcionalmente la plantilla para el autoarranque con `systemd`.

---

### 3. 🩺 Auditoría SRE y Verificación de Producción por Terminal
Para validar que todo está 100% operativo en producción desde la consola:

```bash
bash scripts/verify_production.sh
```
*Si se detecta alguna anomalía, el script genera el diagnóstico de causa raíz y los comandos de solución paso a paso.*

---

## 🎨 Características Visuales y Funcionales (Estilo Quest Spotlight)

- **Paleta y Tema Diagnostic Dark**: Fondo grafito oscuro (`#0e1117` / `#161b24`), bordes de estado con brillo y alertas de alta visibilidad.
- **Semáforo de Alarmas Spotlight**: Contador visual categorizado en 5 niveles de severidad:
  - 🔴 **CRITICAL** (Nodos caídos, saturación extrema)
  - 🟠 **HIGH** (CPU/RAM > 85%, Pools de almacenamiento críticos)
  - 🟡 **MEDIUM** (Cargas elevadas en VMs individuales)
  - 🔵 **LOW** (Advertencias de I/O wait o alertas informativas)
  - 🟢 **NORMAL** (Componentes saludables)
- **Índice Global de Salud (Spotlight Health Score)**: Puntuación de 0 a 100 con diagnóstico instantáneo del estado de la infraestructura.
- **Flujo Topológico Diagnóstico**: Matriz visual que conecta Quórum del Clúster ➔ Nodos Físicos ➔ Cómputo CPU ➔ Memoria RAM ➔ Almacenamiento ➔ Cargas de Trabajo (VMs/LXC).

---

## 📊 Vistas Disponibles

### 1. 📈 Vista Ejecutiva (Executive View)
- **Tarjetas de KPIs Globales**:
  - Uso consolidado de CPU y vCPUs totales con medidores circulares tipo reloj (*Ring Gauges*).
  - Memoria RAM total física vs. asignada en GB/TB y porcentaje.
  - Almacenamiento consolidado en TB y porcentaje de ocupación.
  - Resumen de cargas de trabajo activas vs. detenidas (VMs QEMU y Contenedores LXC).
- **Tablas de Principales Consumidores (Leaderboards)**: Top 5 de máquinas virtuales y contenedores con mayor consumo de CPU, RAM y E/S.
- **Monitoreo de Nodos Físicos**: Estado de quórum, tiempo de actividad (*uptime*), retardo de E/S (*IO Delay*) y carga promedio.
- **Desglose de Pools de Almacenamiento**: Estado y ocupación de ZFS, Ceph, LVM, NFS y almacenamiento local.

### 2. ⚙️ Vista Técnica (Technical Deep-Dive View)
- **Inventario Completo de Cargas de Trabajo**:
  - Filtro instantáneo por texto (ID, nombre, tags, SO).
  - Filtros por tipo (Solo VMs QEMU / Solo Contenedores LXC), nodo y estado (En ejecución / Detenido).
  - Columnas detalladas: VMID, Nombre, Tipo, Nodo, Estado, vCPUs, CPU %, RAM Usada / Máx, Ocupación RAM %, Disco, E/S de Red (RX/TX), Uptime y Etiquetas.
- **Modal de Diagnóstico Detallado**: Al hacer clic en cualquier máquina o contenedor, se despliega una ficha técnica con métricas en tiempo real.
- **Telemetría de Nodos**: Desglose de carga 1m/5m/15m, modelo de procesador, memoria swap, versión de kernel y versión de Proxmox VE.

### 3. 🔔 Vista de Alarmas y Registro de Tareas (Alarms & Logs)
- Registro activo de anomalías detectadas con nivel de severidad.
- Historial de tareas recientes ejecutadas en Proxmox VE (Backups vzdump, migraciones en caliente, snapshots, encendido/apagado) con usuario, nodo, estado y duración.

---

## 📁 Estructura del Proyecto

```text
.
├── .gitignore
├── README.md
├── scripts/
│   ├── setup_raspberry.sh     # Script automatizado para Raspberry Pi
│   ├── setup_proxmox.sh       # Script automatizado para Proxmox VE
│   └── verify_production.sh   # Suite de auditoría SRE y verificación productiva
└── Dashboard/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── .env.example
    ├── .env                   # Variables de entorno activas
    ├── setup_proxmox_guide.md
    ├── data/                  # Almacenamiento persistente de configuraciones
    ├── scripts/
    │   ├── setup_raspberry.sh
    │   ├── setup_proxmox.sh
    │   └── verify_production.sh
    └── app/
        ├── config.py          # Gestor de configuración y persistencia en caliente
        ├── troubleshoot.py    # Motor de diagnóstico L4/SSL/API/RBAC y buffer de logs
        ├── main.py            # API REST FastAPI y endpoints de configuración
        ├── mock_data.py       # Generador de datos de demostración
        ├── proxmox_client.py  # Cliente Proxmox VE (Token & Ticket Auth, Caché TTL)
        └── static/
            ├── index.html     # SPA con modales de configuración y diagnóstico
            ├── css/spotlight.css # Estilos Quest Spotlight HUD Dark
            └── js/app.js      # Controlador frontend reactivo
```

---

## 🚀 Despliegue y Actualización con Docker

```bash
cd Dashboard
# Detener contenedores previos y asegurar que el nombre esté libre
docker compose down --remove-orphans
docker rm -f proxmox-spotlight-dashboard 2>/dev/null || true

# Iniciar contenedor Docker con volumen persistente y reconstrucción
docker compose up -d --build
```

Abre en tu navegador: `http://<IP_RASPBERRY_PI>:8080` (o `http://localhost:8080`).

Si la aplicación arranca sin configuración previa, haz clic en **"Configuración"** en la barra superior o en la pantalla de bienvenida para ingresar la IP y credenciales de tu Proxmox VE.
