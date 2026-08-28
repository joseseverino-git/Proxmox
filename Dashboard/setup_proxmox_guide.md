# 🛡️ Guía de Configuración en Proxmox VE para Spotlight Dashboard

Esta guía detalla paso a paso cómo crear un usuario de sólo lectura (auditoría) y un **API Token** en Proxmox VE para permitir que el dashboard obtenga las métricas de monitoreo de manera segura y sin privilegios administrativos.

---

## 📋 Método 1: Configuración Rápida por Terminal / CLI (Recomendado)

Conéctate por SSH a tu nodo Proxmox VE o abre la consola Shell desde la interfaz web y ejecuta los siguientes comandos:

### 1. Crear el usuario `monitoring` en el reino `pve`
```bash
pveum user add monitoring@pve --comment "Usuario para Spotlight Dashboard"
```

### 2. Asignar el rol de auditoría de sólo lectura (`PVEAuditor`) en la raíz `/`
El rol predeterminado `PVEAuditor` permite leer el estado de nodos, VMs, contenedores LXC, almacenamientos y tareas sin permitir ninguna modificación:
```bash
pveum acl modify / -user monitoring@pve -role PVEAuditor
```

### 3. Crear el API Token
Crea un token llamado `spotlight` para el usuario `monitoring@pve`. El parámetro `--privsep 0` hereda los permisos del usuario:
```bash
pveum user token add monitoring@pve spotlight --privsep 0
```

### 4. Salida obtenida
La terminal mostrará una salida similar a esta:
```text
┌──────────────┬──────────────────────────────────────┐
│ key          │ value                                │
├──────────────┼──────────────────────────────────────┤
│ full-tokenid │ monitoring@pve!spotlight             │
│ info         │ {"privsep":"0"}                      │
│ value        │ 98765432-abcd-ef01-2345-6789abcdef01 │
└──────────────┴──────────────────────────────────────┘
```

> ⚠️ **IMPORTANTE**: Copia el valor de `value` (el token UUID secreto). **Proxmox sólo lo muestra una vez**.

---

## 🖥️ Método 2: Configuración mediante la Interfaz Web (GUI)

Si prefieres realizar la configuración desde el navegador:

### Paso 1: Crear el Usuario
1. En el menú de la izquierda, selecciona **Datacenter**.
2. Ve a **Permissions** -> **Users**.
3. Haz clic en **Add**.
4. Configura:
   - **User name**: `monitoring`
   - **Realm**: `Proxmox VE authentication server` (`pve`)
   - **Expire**: `never`
5. Haz clic en **Add**.

### Paso 2: Crear el API Token
1. En **Datacenter** -> **Permissions** -> **API Tokens**.
2. Haz clic en **Add**.
3. Selecciona:
   - **User**: `monitoring@pve`
   - **Token ID**: `spotlight`
   - **Privilege Separation**: Desmarca la casilla (para que use los permisos del usuario).
4. Haz clic en **Add**.
5. Aparecerá una ventana con el **Token ID** y el **Secret Value**. Cópialo inmediatamente.

### Paso 3: Asignar Permisos (ACL)
1. En **Datacenter** -> **Permissions**.
2. Haz clic en **Add** -> **User Permission**.
3. Configura:
   - **Path**: `/`
   - **User**: `monitoring@pve`
   - **Role**: `PVEAuditor`
4. Haz clic en **Add**.

---

## 🔒 Configuración de Red y Firewall

- **Puerto Requerido**: El dashboard realiza peticiones HTTPS al puerto **`8006`** de Proxmox VE (`https://<IP_PROXMOX>:8006`).
- Si tienes activo el firewall de Proxmox VE o de la red local, asegúrate de permitir tráfico TCP entrante al puerto `8006` desde la IP de tu Raspberry Pi 4 B.

---

## 🧪 Comprobación de Conectividad desde la Raspberry Pi

Puedes verificar la conexión desde la Raspberry Pi ejecutando:

```bash
curl -k -H "Authorization: PVEAPIToken=monitoring@pve!spotlight=TU_SECRET_UUID" \
  https://IP_DE_PROXMOX:8006/api2/json/version
```

Si la respuesta devuelve un JSON con la versión de Proxmox VE (ej. `{"data":{"version":"8.2",...}}`), la configuración ha sido exitosa.
