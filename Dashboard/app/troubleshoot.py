import os
import time
import socket
import ssl
import logging
import asyncio
from typing import Dict, Any, List, Optional
from collections import deque
import httpx

from app.config import settings

logger = logging.getLogger("proxmox_dashboard")

# In-memory log buffer to capture recent application logs for the Troubleshooting UI
class LogBufferHandler(logging.Handler):
    def __init__(self, max_entries: int = 200):
        super().__init__()
        self.buffer = deque(maxlen=max_entries)

    def emit(self, record):
        try:
            entry = {
                "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage()
            }
            if record.exc_info:
                entry["traceback"] = self.format(record)
            self.buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_entries(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        entries = list(self.buffer)
        if level:
            level = level.upper()
            entries = [e for e in entries if e["level"] == level]
        return entries

    def clear(self):
        self.buffer.clear()

# Global log buffer
log_buffer = LogBufferHandler(max_entries=200)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log_buffer.setFormatter(formatter)
logging.getLogger().addHandler(log_buffer)


class Troubleshooter:
    """
    Platform and Proxmox VE Troubleshooting Suite.
    Runs deep non-destructive diagnostics on Network, SSL, API, Auth, and RBAC.
    """

    async def run_quick_test(self, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Quick test for configuration form validation without running the entire suite.
        """
        cfg = self._resolve_config(override)
        start_t = time.time()
        
        try:
            # 1. Parse URL & TCP test
            host, port = self._parse_host_port(cfg["PVE_HOST"])
            await self._test_tcp_socket(host, port, timeout=3.0)
            
            # 2. HTTP test against /api2/json/version
            async with httpx.AsyncClient(
                verify=cfg["PVE_VERIFY_SSL"],
                timeout=cfg["PVE_TIMEOUT"],
                headers=self._build_auth_header(cfg)
            ) as client:
                url = self._format_url(cfg["PVE_HOST"])
                resp = await client.get(f"{url}/api2/json/version")
                latency_ms = round((time.time() - start_t) * 1000, 1)
                
                if resp.status_code == 200:
                    v_data = resp.json().get("data", {})
                    pve_ver = f"{v_data.get('version', '8.x')}-{v_data.get('release', '')}"
                    return {
                        "success": True,
                        "status": "connected",
                        "latency_ms": latency_ms,
                        "pve_version": pve_ver,
                        "message": f"Conexión exitosa con Proxmox VE ({pve_ver}) en {latency_ms} ms."
                    }
                elif resp.status_code == 401:
                    return {
                        "success": False,
                        "status": "unauthorized",
                        "latency_ms": latency_ms,
                        "message": f"Error 401: Credenciales rechazadas por Proxmox VE ({cfg['PVE_USER']})."
                    }
                else:
                    return {
                        "success": False,
                        "status": f"http_{resp.status_code}",
                        "latency_ms": latency_ms,
                        "message": f"Error HTTP {resp.status_code}: {resp.text[:120]}"
                    }
        except ssl.SSLCertVerificationError as e:
            return {
                "success": False,
                "status": "ssl_error",
                "message": f"Error de certificado SSL: {str(e)}. Activa 'Ignorar verificación SSL'."
            }
        except (socket.timeout, asyncio.TimeoutError):
            return {
                "success": False,
                "status": "timeout",
                "message": f"Timeout alcanzando {cfg['PVE_HOST']}. Revisa la IP, puerto y firewall."
            }
        except ConnectionRefusedError:
            return {
                "success": False,
                "status": "connection_refused",
                "message": f"Conexión rechazada en {cfg['PVE_HOST']}. Verifica que pveproxy esté activo."
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Fallo al conectar: {str(e)}"
            }

    async def run_full_diagnostics(self, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a 6-stage deep diagnostic audit and produces actionable remediation steps.
        """
        cfg = self._resolve_config(override)
        results = []
        overall_passed = True
        remediations = []
        
        # --- Stage 1: Environment & Configuration Syntax ---
        stage1 = {
            "id": "config",
            "title": "1. Configuración y Parámetros Locales",
            "icon": "settings",
            "status": "pass",
            "details": [],
            "items": []
        }
        
        host_val = cfg.get("PVE_HOST", "").strip()
        user_val = cfg.get("PVE_USER", "").strip()
        auth_type = cfg.get("AUTH_TYPE", "token").lower()
        token_name = cfg.get("PVE_TOKEN_NAME", "").strip()
        token_val = cfg.get("PVE_TOKEN_VALUE", "").strip()
        pwd_val = cfg.get("PVE_PASSWORD", "").strip()
        demo_mode = cfg.get("DEMO_MODE", False)
        
        if demo_mode:
            stage1["status"] = "warn"
            stage1["items"].append({
                "label": "Modo Demostración",
                "status": "warn",
                "text": "DEMO_MODE=true está activo. La plataforma mostrará datos simulados en lugar del servidor real."
            })
            remediations.append({
                "severity": "high",
                "title": "Desactivar DEMO_MODE",
                "description": "Cambia DEMO_MODE a 'false' en la ventana de Configuración para ver datos reales.",
                "command": "DEMO_MODE=false"
            })
        else:
            stage1["items"].append({
                "label": "Modo de Operación",
                "status": "pass",
                "text": "Modo Productivo activo (DEMO_MODE=false)."
            })

        if not host_val:
            stage1["status"] = "fail"
            stage1["items"].append({"label": "PVE_HOST", "status": "fail", "text": "URL de Proxmox no está configurada."})
            overall_passed = False
        else:
            stage1["items"].append({"label": "PVE_HOST", "status": "pass", "text": f"Configurado: {host_val}"})

        if "@" not in user_val:
            stage1["status"] = "fail"
            stage1["items"].append({
                "label": "PVE_USER",
                "status": "fail",
                "text": f"Usuario '{user_val}' no incluye realm (ej. @pve o @pam). Ej: monitoring@pve o root@pam."
            })
            overall_passed = False
        else:
            stage1["items"].append({"label": "PVE_USER", "status": "pass", "text": f"Usuario válido: {user_val}"})

        if auth_type == "token":
            if not token_val or token_val in ("your-token-secret-uuid-here", "tu-token-aqui", ""):
                stage1["status"] = "fail"
                stage1["items"].append({
                    "label": "API Token",
                    "status": "fail",
                    "text": "PVE_TOKEN_VALUE está vacío o tiene el valor de plantilla predeterminado."
                })
                overall_passed = False
                remediations.append({
                    "severity": "critical",
                    "title": "Generar y Configurar API Token en Proxmox",
                    "description": "Crea el token 'spotlight' en tu servidor Proxmox VE y pega el UUID en Configuración:",
                    "command": f"pveum user token add {user_val} {token_name or 'spotlight'} --privsep 0"
                })
            else:
                masked = token_val[:4] + "•" * 12 + token_val[-4:] if len(token_val) > 8 else "••••••••"
                stage1["items"].append({
                    "label": "API Token",
                    "status": "pass",
                    "text": f"Token '{token_name}' configurado ({masked})."
                })
        else:
            if not pwd_val:
                stage1["status"] = "fail"
                stage1["items"].append({"label": "Contraseña", "status": "fail", "text": "Contraseña no configurada."})
                overall_passed = False
            else:
                stage1["items"].append({"label": "Contraseña", "status": "pass", "text": "Contraseña configurada."})
                
        results.append(stage1)

        # --- Stage 2: DNS & TCP Socket Connectivity ---
        stage2 = {
            "id": "network",
            "title": "2. Conectividad de Red y Socket TCP (L4)",
            "icon": "wifi",
            "status": "pending",
            "items": []
        }
        
        host, port = self._parse_host_port(host_val)
        tcp_ok = False
        tcp_latency = 0.0
        
        try:
            t0 = time.time()
            await self._test_tcp_socket(host, port, timeout=cfg["PVE_TIMEOUT"])
            tcp_latency = round((time.time() - t0) * 1000, 1)
            tcp_ok = True
            stage2["status"] = "pass"
            stage2["items"].append({
                "label": "Socket TCP",
                "status": "pass",
                "text": f"Conexión TCP establecida exitosamente con {host}:{port} en {tcp_latency} ms."
            })
        except socket.gaierror as e:
            stage2["status"] = "fail"
            stage2["items"].append({
                "label": "Resolución DNS",
                "status": "fail",
                "text": f"No se pudo resolver el nombre de host '{host}': {str(e)}."
            })
            remediations.append({
                "severity": "critical",
                "title": "Verificar IP o Nombre DNS del Servidor",
                "description": f"Asegúrate de que la IP '{host}' sea accesible y esté en la misma subred.",
                "command": f"ping -c 3 {host}"
            })
            overall_passed = False
        except (socket.timeout, asyncio.TimeoutError):
            stage2["status"] = "fail"
            stage2["items"].append({
                "label": "Timeout TCP",
                "status": "fail",
                "text": f"Timeout superado ({cfg['PVE_TIMEOUT']}s) intentando conectar con {host}:{port}."
            })
            remediations.append({
                "severity": "critical",
                "title": "Verificar Reglas de Firewall y Enrutamiento",
                "description": "El puerto 8006 podría estar bloqueado en Proxmox VE o en el firewall de red.",
                "command": f"# En Proxmox VE:\npve-firewall status\nufw status"
            })
            overall_passed = False
        except ConnectionRefusedError:
            stage2["status"] = "fail"
            stage2["items"].append({
                "label": "Conexión Rechazada",
                "status": "fail",
                "text": f"Conexión rechazada en {host}:{port}. El puerto está cerrado o el servicio pveproxy está detenido."
            })
            remediations.append({
                "severity": "critical",
                "title": "Verificar Servicio pveproxy en Proxmox",
                "description": "Reinicia el servicio web de la API de Proxmox en la consola Shell del nodo:",
                "command": "systemctl restart pveproxy && systemctl status pveproxy"
            })
            overall_passed = False
        except Exception as e:
            stage2["status"] = "fail"
            stage2["items"].append({"label": "Error de Red", "status": "fail", "text": f"Error de socket: {str(e)}"})
            overall_passed = False
            
        results.append(stage2)

        # --- Stage 3: SSL / TLS Certificate Validation ---
        stage3 = {
            "id": "ssl",
            "title": "3. Seguridad SSL / TLS y Certificado",
            "icon": "shield-check",
            "status": "pending",
            "items": []
        }
        
        if not tcp_ok:
            stage3["status"] = "skip"
            stage3["items"].append({
                "label": "SSL Skip",
                "status": "skip",
                "text": "Omitido porque la conexión TCP no pudo completarse."
            })
        else:
            try:
                ssl_t0 = time.time()
                ssl_info = await self._check_ssl_handshake(host, port, verify=cfg["PVE_VERIFY_SSL"])
                ssl_lat = round((time.time() - ssl_t0) * 1000, 1)
                
                if ssl_info.get("self_signed") and cfg["PVE_VERIFY_SSL"]:
                    stage3["status"] = "fail"
                    stage3["items"].append({
                        "label": "Certificado Autofirmado",
                        "status": "fail",
                        "text": "El servidor utiliza un certificado SSL autofirmado de Proxmox y PVE_VERIFY_SSL=true está forzado."
                    })
                    remediations.append({
                        "severity": "high",
                        "title": "Desactivar Verificación SSL para Certificado Autofirmado",
                        "description": "Activa 'Ignorar verificación SSL' en la ventana de Configuración:",
                        "command": "PVE_VERIFY_SSL=false"
                    })
                    overall_passed = False
                elif ssl_info.get("self_signed") and not cfg["PVE_VERIFY_SSL"]:
                    stage3["status"] = "pass"
                    stage3["items"].append({
                        "label": "Certificado SSL",
                        "status": "pass",
                        "text": f"Certificado autofirmado aceptado correctamente (PVE_VERIFY_SSL=false) ({ssl_lat} ms)."
                    })
                else:
                    stage3["status"] = "pass"
                    stage3["items"].append({
                        "label": "Certificado SSL",
                        "status": "pass",
                        "text": f"Certificado TLS válido ({ssl_info.get('issuer', 'CA')}) ({ssl_lat} ms)."
                    })
            except ssl.SSLCertVerificationError as e:
                stage3["status"] = "fail"
                stage3["items"].append({
                    "label": "Fallo de Verificación SSL",
                    "status": "fail",
                    "text": f"Error de verificación: {str(e)}. Proxmox usa certificados autofirmados por defecto."
                })
                remediations.append({
                    "severity": "high",
                    "title": "Habilitar Modo Inseguro SSL en la App",
                    "description": "Desactiva la verificación SSL en Configuración para permitir certificados autofirmados.",
                    "command": "PVE_VERIFY_SSL=false"
                })
                overall_passed = False
            except Exception as e:
                stage3["status"] = "warn"
                stage3["items"].append({"label": "TLS Check", "status": "warn", "text": f"Aviso TLS: {str(e)}"})

        results.append(stage3)

        # --- Stage 4: Proxmox API Root & Version ---
        stage4 = {
            "id": "api_version",
            "title": "4. API de Proxmox VE (/api2/json/version)",
            "icon": "cpu",
            "status": "pending",
            "items": []
        }
        
        api_ok = False
        pve_version_str = "Desconocida"
        
        if not tcp_ok:
            stage4["status"] = "skip"
            stage4["items"].append({"label": "API Skip", "status": "skip", "text": "Omitido por fallo de red."})
        else:
            try:
                base_url = self._format_url(cfg["PVE_HOST"])
                async with httpx.AsyncClient(
                    verify=cfg["PVE_VERIFY_SSL"],
                    timeout=cfg["PVE_TIMEOUT"]
                ) as client:
                    resp = await client.get(f"{base_url}/api2/json/version")
                    if resp.status_code == 200:
                        api_ok = True
                        stage4["status"] = "pass"
                        vdata = resp.json().get("data", {})
                        pve_version_str = f"Proxmox VE {vdata.get('version', '')}-{vdata.get('release', '')}"
                        stage4["items"].append({
                            "label": "API Proxmox VE",
                            "status": "pass",
                            "text": f"API activa y respondiendo. Versión: {pve_version_str}"
                        })
                    else:
                        stage4["status"] = "fail"
                        stage4["items"].append({
                            "label": "Estado API",
                            "status": "fail",
                            "text": f"HTTP {resp.status_code}: {resp.text[:120]}"
                        })
                        overall_passed = False
            except Exception as e:
                stage4["status"] = "fail"
                stage4["items"].append({"label": "Error de API", "status": "fail", "text": str(e)})
                overall_passed = False

        results.append(stage4)

        # --- Stage 5: Autenticación (Token o Password) ---
        stage5 = {
            "id": "auth",
            "title": "5. Autenticación y Credenciales",
            "icon": "key",
            "status": "pending",
            "items": []
        }
        
        auth_ok = False
        ticket_header = {}
        
        if not api_ok:
            stage5["status"] = "skip"
            stage5["items"].append({"label": "Auth Skip", "status": "skip", "text": "Omitido por fallo de API."})
        else:
            base_url = self._format_url(cfg["PVE_HOST"])
            try:
                if auth_type == "token":
                    headers = self._build_auth_header(cfg)
                    async with httpx.AsyncClient(
                        verify=cfg["PVE_VERIFY_SSL"],
                        timeout=cfg["PVE_TIMEOUT"],
                        headers=headers
                    ) as client:
                        resp = await client.get(f"{base_url}/api2/json/cluster/resources")
                        if resp.status_code == 200:
                            auth_ok = True
                            stage5["status"] = "pass"
                            stage5["items"].append({
                                "label": "API Token",
                                "status": "pass",
                                "text": f"Token '{token_name}' para '{user_val}' autenticado correctamente."
                            })
                        elif resp.status_code == 401:
                            stage5["status"] = "fail"
                            stage5["items"].append({
                                "label": "401 Unauthorized",
                                "status": "fail",
                                "text": f"El API Token '{token_name}' o el secret UUID son inválidos en Proxmox."
                            })
                            remediations.append({
                                "severity": "critical",
                                "title": "Regenerar Token en Proxmox VE",
                                "description": "Ejecuta en la consola Shell de Proxmox para recrear el token:",
                                "command": f"pveum user token add {user_val} {token_name} --privsep 0"
                            })
                            overall_passed = False
                        elif resp.status_code == 403:
                            auth_ok = True
                            stage5["status"] = "warn"
                            stage5["items"].append({
                                "label": "Autenticación Parcial",
                                "status": "warn",
                                "text": "Token autenticado pero permisos insuficientes (403 Forbidden)."
                            })
                        else:
                            stage5["status"] = "fail"
                            stage5["items"].append({
                                "label": "Respuesta Auth",
                                "status": "fail",
                                "text": f"HTTP {resp.status_code}: {resp.text[:120]}"
                            })
                            overall_passed = False
                else:
                    async with httpx.AsyncClient(
                        verify=cfg["PVE_VERIFY_SSL"],
                        timeout=cfg["PVE_TIMEOUT"]
                    ) as client:
                        resp = await client.post(
                            f"{base_url}/api2/json/access/ticket",
                            data={"username": user_val, "password": pwd_val}
                        )
                        if resp.status_code == 200:
                            auth_ok = True
                            stage5["status"] = "pass"
                            t_data = resp.json().get("data", {})
                            ticket = t_data.get("ticket")
                            ticket_header = {"Cookie": f"PVEAuthCookie={ticket}"}
                            stage5["items"].append({
                                "label": "Password Ticket",
                                "status": "pass",
                                "text": f"Ticket de sesión generado exitosamente para {user_val}."
                            })
                        else:
                            stage5["status"] = "fail"
                            stage5["items"].append({
                                "label": "Fallo de Login",
                                "status": "fail",
                                "text": f"Credenciales incorrectas (HTTP {resp.status_code}): {resp.text[:100]}"
                            })
                            remediations.append({
                                "severity": "critical",
                                "title": "Verificar Usuario y Contraseña",
                                "description": "Comprueba que el usuario y contraseña sean válidos (ej. root@pam).",
                                "command": "pveum user list"
                            })
                            overall_passed = False
            except Exception as e:
                stage5["status"] = "fail"
                stage5["items"].append({"label": "Error de Autenticación", "status": "fail", "text": str(e)})
                overall_passed = False

        results.append(stage5)

        # --- Stage 6: Authorization & RBAC Permissions Check ---
        stage6 = {
            "id": "permissions",
            "title": "6. Permisos RBAC y Telemetría de Recursos",
            "icon": "database",
            "status": "pending",
            "items": []
        }
        
        if not auth_ok:
            stage6["status"] = "skip"
            stage6["items"].append({
                "label": "Permisos Skip",
                "status": "skip",
                "text": "Omitido por fallo en la autenticación."
            })
        else:
            base_url = self._format_url(cfg["PVE_HOST"])
            headers = self._build_auth_header(cfg) if auth_type == "token" else ticket_header
            
            try:
                async with httpx.AsyncClient(
                    verify=cfg["PVE_VERIFY_SSL"],
                    timeout=cfg["PVE_TIMEOUT"],
                    headers=headers
                ) as client:
                    resp = await client.get(f"{base_url}/api2/json/cluster/resources")
                    if resp.status_code == 200:
                        stage6["status"] = "pass"
                        items = resp.json().get("data", [])
                        nodes = [i for i in items if i.get("type") == "node"]
                        vms = [i for i in items if i.get("type") == "qemu"]
                        lxcs = [i for i in items if i.get("type") == "lxc"]
                        storages = [i for i in items if i.get("type") == "storage"]
                        
                        stage6["items"].append({
                            "label": "Recursos Proxmox Detectados",
                            "status": "pass",
                            "text": f"Lectura exitosa: {len(nodes)} Nodos, {len(vms)} VMs, {len(lxcs)} Contenedores LXC, {len(storages)} Almacenamientos."
                        })
                        
                        if nodes:
                            first_node = nodes[0].get("node")
                            node_resp = await client.get(f"{base_url}/api2/json/nodes/{first_node}/status")
                            if node_resp.status_code == 200:
                                stage6["items"].append({
                                    "label": "Telemetría de Nodos",
                                    "status": "pass",
                                    "text": f"Telemetría detallada accesible en nodo '{first_node}' (CPU/RAM/IO/Kernel)."
                                })
                    elif resp.status_code == 403:
                        stage6["status"] = "fail"
                        stage6["items"].append({
                            "label": "Permisos Insuficientes (403)",
                            "status": "fail",
                            "text": f"El usuario '{user_val}' no tiene el rol PVEAuditor en '/'."
                        })
                        remediations.append({
                            "severity": "critical",
                            "title": "Asignar Permisos de Auditoría en Proxmox",
                            "description": "Otorga el rol PVEAuditor de sólo lectura al usuario en la raíz:",
                            "command": f"pveum acl modify / -user {user_val} -role PVEAuditor"
                        })
                        overall_passed = False
                    else:
                        stage6["status"] = "warn"
                        stage6["items"].append({
                            "label": "Recursos",
                            "status": "warn",
                            "text": f"HTTP {resp.status_code}: {resp.text[:100]}"
                        })
            except Exception as e:
                stage6["status"] = "fail"
                stage6["items"].append({"label": "Error de Permisos", "status": "fail", "text": str(e)})
                overall_passed = False

        results.append(stage6)

        # Build final summary
        passed_count = sum(1 for s in results if s["status"] == "pass")
        warn_count = sum(1 for s in results if s["status"] == "warn")
        fail_count = sum(1 for s in results if s["status"] == "fail")
        
        return {
            "timestamp": time.time(),
            "target_host": host_val,
            "target_user": user_val,
            "auth_type": auth_type,
            "overall_passed": overall_passed and fail_count == 0,
            "summary": {
                "total_stages": len(results),
                "passed": passed_count,
                "warnings": warn_count,
                "failed": fail_count
            },
            "stages": results,
            "remediations": remediations,
            "pve_version": pve_version_str
        }

    def _resolve_config(self, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Combines system settings with optional runtime overrides for testing."""
        cfg = {
            "PVE_HOST": settings.PVE_HOST,
            "PVE_USER": settings.PVE_USER,
            "AUTH_TYPE": getattr(settings, "AUTH_TYPE", "token"),
            "PVE_TOKEN_NAME": settings.PVE_TOKEN_NAME,
            "PVE_TOKEN_VALUE": settings.PVE_TOKEN_VALUE,
            "PVE_PASSWORD": getattr(settings, "PVE_PASSWORD", ""),
            "PVE_VERIFY_SSL": settings.PVE_VERIFY_SSL,
            "PVE_TIMEOUT": settings.PVE_TIMEOUT,
            "DEMO_MODE": settings.DEMO_MODE,
            "FALLBACK_TO_DEMO": getattr(settings, "FALLBACK_TO_DEMO", False)
        }
        if override:
            for k, v in override.items():
                if v is not None:
                    cfg[k] = v
        return cfg

    def _parse_host_port(self, raw_host: str) -> (str, int):
        clean = raw_host.strip()
        if "://" in clean:
            clean = clean.split("://")[1]
        clean = clean.split("/")[0]
        if ":" in clean:
            parts = clean.split(":")
            return parts[0], int(parts[1])
        return clean, 8006

    def _format_url(self, raw_host: str) -> str:
        url = raw_host.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        if ":" not in url.split("//")[1]:
            url = f"{url}:8006"
        return url.rstrip("/")

    def _build_auth_header(self, cfg: Dict[str, Any]) -> Dict[str, str]:
        token_val = cfg.get("PVE_TOKEN_VALUE", "")
        if token_val:
            user = cfg.get("PVE_USER", "monitoring@pve")
            token_name = cfg.get("PVE_TOKEN_NAME", "spotlight")
            return {"Authorization": f"PVEAPIToken={user}!{token_name}={token_val}"}
        return {}

    async def _test_tcp_socket(self, host: str, port: int, timeout: float = 3.0):
        loop = asyncio.get_event_loop()
        def _connect():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect((host, port))
            finally:
                sock.close()
        await loop.run_in_executor(None, _connect)

    async def _check_ssl_handshake(self, host: str, port: int, verify: bool = False) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        def _ssl():
            context = ssl.create_default_context()
            if not verify:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, port), timeout=4.0) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    is_self_signed = not bool(cert)
                    return {
                        "cipher": ssock.cipher(),
                        "version": ssock.version(),
                        "self_signed": is_self_signed,
                        "issuer": "Self-Signed (PVE)" if is_self_signed else "Public CA"
                    }
        return await loop.run_in_executor(None, _ssl)

troubleshooter = Troubleshooter()
