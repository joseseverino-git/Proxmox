import logging
import time
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.mock_data import get_mock_data

logger = logging.getLogger("proxmox_dashboard")

class ProxmoxClient:
    def __init__(self):
        self._cache_data: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0
        self._lock = asyncio.Lock()
        self._ticket: Optional[str] = None
        self._ticket_timestamp: float = 0
        self._csrf_token: Optional[str] = None

    def reset_cache(self):
        """Invalidate cache and tickets when configuration changes."""
        self._cache_data = None
        self._cache_timestamp = 0
        self._ticket = None
        self._ticket_timestamp = 0
        self._csrf_token = None
        logger.info("Proxmox client cache and session reset.")

    async def get_dashboard_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch and aggregate Proxmox VE cluster data with intelligent fallback control."""
        now = time.time()
        
        # 1. Explicit Demo Mode
        if settings.DEMO_MODE:
            mock = get_mock_data()
            mock["connection_status"] = {
                "connected": True,
                "mode": "DEMO_MODE",
                "message": "Modo Demostración Activo. Se muestran datos simulados para pruebas.",
                "host": settings.PVE_HOST,
                "user": settings.PVE_USER,
                "is_demo": True
            }
            return mock

        # 2. Unconfigured State
        if not settings.is_configured:
            if settings.FALLBACK_TO_DEMO:
                mock = get_mock_data()
                mock["connection_status"] = {
                    "connected": False,
                    "mode": "UNCONFIGURED_DEMO",
                    "message": "Servidor Proxmox VE no configurado. Mostrando datos demo simulados por política de fallback.",
                    "host": settings.PVE_HOST,
                    "user": settings.PVE_USER,
                    "unconfigured": True,
                    "is_demo": True
                }
                return mock
            else:
                return self._get_unconfigured_payload()

        # 3. Cached data check
        if not force_refresh and self._cache_data and (now - self._cache_timestamp < settings.CACHE_TTL_SECONDS):
            return self._cache_data

        # 4. Fetch Live Data
        async with self._lock:
            if not force_refresh and self._cache_data and (now - self._cache_timestamp < settings.CACHE_TTL_SECONDS):
                return self._cache_data
            
            try:
                data = await self._fetch_live_proxmox_data()
                data["connection_status"] = {
                    "connected": True,
                    "mode": "LIVE_PVE",
                    "message": "Conectado a la API de Proxmox VE exitosamente",
                    "host": settings.formatted_pve_url,
                    "user": settings.PVE_USER,
                    "latency_ms": data.get("_fetch_latency_ms", 0),
                    "is_demo": False
                }
                self._cache_data = data
                self._cache_timestamp = time.time()
                return data
            except Exception as e:
                logger.error(f"Error fetching data from Proxmox VE ({settings.formatted_pve_url}): {e}")
                
                # If explicit fallback is enabled, show mock data with warning banner
                if settings.FALLBACK_TO_DEMO:
                    mock = get_mock_data()
                    mock["connection_status"] = {
                        "connected": False,
                        "mode": "FALLBACK_DEMO",
                        "message": f"Error de conexión con Proxmox VE: {str(e)}. Mostrando datos de respaldo.",
                        "host": settings.formatted_pve_url,
                        "user": settings.PVE_USER,
                        "error": str(e),
                        "is_demo": True
                    }
                    return mock
                
                # Otherwise, return clear OFFLINE state with zero fake data!
                return self._get_offline_error_payload(str(e))

    def _get_unconfigured_payload(self) -> Dict[str, Any]:
        """Returns clean unconfigured structure when no credentials exist."""
        return {
            "connection_status": {
                "connected": False,
                "mode": "NOT_CONFIGURED",
                "message": "Servidor Proxmox VE no configurado. Ingresa los datos en '⚙ Configuración'.",
                "host": settings.formatted_pve_url,
                "user": settings.PVE_USER,
                "unconfigured": True,
                "is_demo": False
            },
            "cluster": {
                "cluster_name": "Proxmox no configurado",
                "health_score": 0,
                "health_status": "OFFLINE",
                "quorum": "0/0",
                "pve_version": "Sin conexión",
                "nodes_online": "0/0",
                "vms_running": "0/0",
                "lxc_running": "0/0",
                "avg_cpu_pct": 0,
                "total_cpu_cores": 0,
                "ram_used_bytes": 0,
                "ram_total_bytes": 1,
                "ram_pct": 0,
                "storage_used_bytes": 0,
                "storage_total_bytes": 1,
                "storage_pct": 0,
                "alarm_counts": {"critical": 1, "high": 0, "medium": 0, "low": 0, "normal": 0},
                "timestamp": time.time(),
                "is_mock": False
            },
            "nodes": [],
            "vms": [],
            "storages": [],
            "alarms": [
                {
                    "severity": "Critical",
                    "component": "Configuración PVE",
                    "msg": "No se han configurado credenciales válidas para el servidor Proxmox VE.",
                    "target": "Dashboard"
                }
            ],
            "tasks": []
        }

    def _get_offline_error_payload(self, error_msg: str) -> Dict[str, Any]:
        """Returns accurate offline error state so the user isn't fooled by mock servers."""
        return {
            "connection_status": {
                "connected": False,
                "mode": "CONNECTION_FAILED",
                "message": f"Fallo al conectar con Proxmox VE: {error_msg}",
                "host": settings.formatted_pve_url,
                "user": settings.PVE_USER,
                "error": error_msg,
                "unconfigured": False,
                "is_demo": False
            },
            "cluster": {
                "cluster_name": "Servidor Proxmox Inaccesible",
                "health_score": 0,
                "health_status": "CRITICAL",
                "quorum": "OFFLINE",
                "pve_version": "Desconectado",
                "nodes_online": "0/0",
                "vms_running": "0/0",
                "lxc_running": "0/0",
                "avg_cpu_pct": 0,
                "total_cpu_cores": 0,
                "ram_used_bytes": 0,
                "ram_total_bytes": 1,
                "ram_pct": 0,
                "storage_used_bytes": 0,
                "storage_total_bytes": 1,
                "storage_pct": 0,
                "alarm_counts": {"critical": 1, "high": 0, "medium": 0, "low": 0, "normal": 0},
                "timestamp": time.time(),
                "is_mock": False
            },
            "nodes": [],
            "vms": [],
            "storages": [],
            "alarms": [
                {
                    "severity": "Critical",
                    "component": "Conectividad Proxmox",
                    "msg": f"Error comunicando con {settings.formatted_pve_url}: {error_msg}",
                    "target": settings.formatted_pve_url
                }
            ],
            "tasks": []
        }

    async def _get_auth_headers(self, client: httpx.AsyncClient) -> Dict[str, str]:
        """Generates appropriate authentication headers for Token or Ticket."""
        if settings.AUTH_TYPE == "token":
            return settings.auth_header
        
        # Password ticket authentication
        now = time.time()
        # Proxmox tickets are valid for 2 hours (7200s); refresh after 1.5 hours (5400s)
        if not self._ticket or (now - self._ticket_timestamp > 5400):
            base_url = settings.formatted_pve_url
            login_resp = await client.post(
                f"{base_url}/api2/json/access/ticket",
                data={
                    "username": settings.PVE_USER,
                    "password": settings.PVE_PASSWORD
                }
            )
            if login_resp.status_code != 200:
                raise Exception(f"Autenticación fallida con usuario {settings.PVE_USER} (HTTP {login_resp.status_code}): {login_resp.text}")
            
            tdata = login_resp.json().get("data", {})
            self._ticket = tdata.get("ticket")
            self._csrf_token = tdata.get("CSRFPreventionToken")
            self._ticket_timestamp = time.time()

        return {
            "Cookie": f"PVEAuthCookie={self._ticket}",
            "CSRFPreventionToken": self._csrf_token or ""
        }

    async def _fetch_live_proxmox_data(self) -> Dict[str, Any]:
        base_url = settings.formatted_pve_url
        start_t = time.time()

        async with httpx.AsyncClient(
            verify=settings.PVE_VERIFY_SSL,
            timeout=settings.PVE_TIMEOUT
        ) as client:
            headers = await self._get_auth_headers(client)

            # 1. Fetch cluster resources (vms, nodes, storages, pools)
            res_response = await client.get(f"{base_url}/api2/json/cluster/resources", headers=headers)
            if res_response.status_code != 200:
                raise Exception(f"HTTP {res_response.status_code}: {res_response.text}")
            
            resources = res_response.json().get("data", [])

            # 2. Fetch cluster status or version
            cluster_name = "Proxmox Cluster"
            pve_version = "Proxmox VE"
            try:
                ver_resp = await client.get(f"{base_url}/api2/json/version", headers=headers)
                if ver_resp.status_code == 200:
                    ver_data = ver_resp.json().get("data", {})
                    pve_version = f"Proxmox VE {ver_data.get('version', '')}-{ver_data.get('release', '')}"
            except Exception:
                pass

            try:
                cl_status_resp = await client.get(f"{base_url}/api2/json/cluster/status", headers=headers)
                if cl_status_resp.status_code == 200:
                    for item in cl_status_resp.json().get("data", []):
                        if item.get("type") == "cluster":
                            cluster_name = item.get("name", cluster_name)
            except Exception:
                pass

            # 3. Fetch cluster tasks
            cluster_tasks = []
            try:
                tasks_resp = await client.get(f"{base_url}/api2/json/cluster/tasks", headers=headers)
                if tasks_resp.status_code == 200:
                    raw_tasks = tasks_resp.json().get("data", [])[:15]
                    for t in raw_tasks:
                        cluster_tasks.append({
                            "upid": t.get("upid", ""),
                            "node": t.get("node", ""),
                            "user": t.get("user", ""),
                            "type": t.get("type", ""),
                            "id": t.get("id", ""),
                            "starttime": t.get("starttime", 0),
                            "endtime": t.get("endtime", 0),
                            "status": t.get("status", "running" if not t.get("endtime") else "OK"),
                            "description": f"{t.get('type')} on {t.get('id', t.get('node'))}"
                        })
            except Exception as e:
                logger.warning(f"Could not fetch cluster tasks: {e}")

            # 4. Process nodes and fetch node details
            raw_nodes = [r for r in resources if r.get("type") == "node"]
            nodes = []
            
            # Fetch node detailed status concurrently
            node_status_tasks = [client.get(f"{base_url}/api2/json/nodes/{n.get('node')}/status", headers=headers) for n in raw_nodes]
            node_responses = await asyncio.gather(*node_status_tasks, return_exceptions=True)

            for idx, n in enumerate(raw_nodes):
                node_name = n.get("node")
                status = n.get("status", "unknown")
                maxcpu = n.get("maxcpu", 1) or 1
                cpu_pct = round((n.get("cpu", 0.0) or 0.0) * 100, 1)
                mem_used = n.get("mem", 0) or 0
                maxmem = n.get("maxmem", 1) or 1
                mem_pct = round((mem_used / maxmem) * 100, 1) if maxmem > 0 else 0.0
                disk_used = n.get("disk", 0) or 0
                maxdisk = n.get("maxdisk", 1) or 1
                disk_pct = round((disk_used / maxdisk) * 100, 1) if maxdisk > 0 else 0.0
                uptime = n.get("uptime", 0) or 0

                # Additional details from node status endpoint
                loadavg = [0.0, 0.0, 0.0]
                kernel = "-"
                iowait = 0.0
                cpu_model = "x86_64 CPU"
                swap_used = 0
                maxswap = 0
                node_ip = "-"
                
                resp = node_responses[idx] if idx < len(node_responses) else None
                if isinstance(resp, httpx.Response) and resp.status_code == 200:
                    nd = resp.json().get("data", {})
                    loadavg = nd.get("loadavg", [0.0, 0.0, 0.0])
                    kernel = nd.get("kversion", "-")
                    iowait = round(nd.get("wait", 0.0) * 100, 2)
                    cpu_info = nd.get("cpuinfo", {})
                    cpu_model = cpu_info.get("model", cpu_model)
                    swap_data = nd.get("swap", {})
                    swap_used = swap_data.get("used", 0)
                    maxswap = swap_data.get("total", 0)

                nodes.append({
                    "id": n.get("id", f"node/{node_name}"),
                    "node": node_name,
                    "status": status,
                    "ip": node_ip,
                    "cpu": cpu_pct,
                    "maxcpu": maxcpu,
                    "cpu_model": cpu_model,
                    "mem": mem_used,
                    "maxmem": maxmem,
                    "mem_used_pct": mem_pct,
                    "swap": swap_used,
                    "maxswap": maxswap,
                    "disk": disk_used,
                    "maxdisk": maxdisk,
                    "disk_used_pct": disk_pct,
                    "uptime": uptime,
                    "loadavg": loadavg,
                    "pveversion": pve_version,
                    "kernel": kernel,
                    "iowait": iowait,
                    "netin": n.get("netin", 0) or 0,
                    "netout": n.get("netout", 0) or 0,
                    "role": "Cluster Node"
                })

            # 5. Process VMs and LXCs
            vms = []
            raw_vms = [r for r in resources if r.get("type") in ("qemu", "lxc")]
            for v in raw_vms:
                v_type = v.get("type")
                v_status = v.get("status", "stopped")
                v_cpu_pct = round((v.get("cpu", 0.0) or 0.0) * 100, 1) if v_status == "running" else 0.0
                v_mem = v.get("mem", 0) or 0
                v_maxmem = v.get("maxmem", 1) or 1
                v_mem_pct = round((v_mem / v_maxmem) * 100, 1) if (v_status == "running" and v_maxmem > 0) else 0.0
                
                vms.append({
                    "vmid": v.get("vmid"),
                    "name": v.get("name", f"{v_type}-{v.get('vmid')}"),
                    "node": v.get("node"),
                    "type": v_type,
                    "status": v_status,
                    "cpus": v.get("maxcpu", 1),
                    "cpu": v_cpu_pct,
                    "mem": v_mem,
                    "maxmem": v_maxmem,
                    "mem_pct": v_mem_pct,
                    "disk": v.get("disk", 0) or 0,
                    "maxdisk": v.get("maxdisk", 0) or 0,
                    "uptime": v.get("uptime", 0) or 0,
                    "netin": v.get("netin", 0) or 0,
                    "netout": v.get("netout", 0) or 0,
                    "diskread": v.get("diskread", 0) or 0,
                    "diskwrite": v.get("diskwrite", 0) or 0,
                    "tags": v.get("tags", ""),
                    "os": "Linux / Guest" if v_type == "lxc" else "VM Guest",
                    "ip": "-"
                })

            # 6. Process Storages
            storages = []
            raw_storages = [r for r in resources if r.get("type") == "storage"]
            for s in raw_storages:
                s_used = s.get("disk", 0) or 0
                s_max = s.get("maxdisk", 1) or 1
                s_pct = round((s_used / s_max) * 100, 1) if s_max > 0 else 0.0
                storages.append({
                    "storage": s.get("storage"),
                    "node": s.get("node", "cluster"),
                    "type": s.get("plugintype", "dir"),
                    "content": s.get("content", ""),
                    "used": s_used,
                    "total": s_max,
                    "avail": max(0, s_max - s_used),
                    "used_pct": s_pct,
                    "status": "active" if s.get("status") == "available" or s.get("shared") else s.get("status", "active"),
                    "shared": s.get("shared", 0)
                })

            # 7. Aggregate cluster totals & Spotlight health scoring
            total_cpu_cores = sum(n["maxcpu"] for n in nodes) or 1
            avg_cpu_pct = round(sum(n["cpu"] * n["maxcpu"] for n in nodes) / total_cpu_cores, 1) if total_cpu_cores > 0 else 0.0
            
            total_ram = sum(n["maxmem"] for n in nodes) or 1
            used_ram = sum(n["mem"] for n in nodes)
            ram_pct = round((used_ram / total_ram) * 100, 1) if total_ram > 0 else 0.0

            total_storage = sum(s["total"] for s in storages) or 1
            used_storage = sum(s["used"] for s in storages)
            storage_pct = round((used_storage / total_storage) * 100, 1) if total_storage > 0 else 0.0

            # Alarms calculation
            alarms = []
            for n in nodes:
                if n["status"] != "online":
                    alarms.append({"severity": "Critical", "component": "Node State", "msg": f"Node {n['node']} is OFFLINE", "target": n["node"]})
                if n["cpu"] > 85:
                    alarms.append({"severity": "High", "component": "Node CPU", "msg": f"Node {n['node']} CPU load is {n['cpu']}%", "target": n["node"]})
                if n["mem_used_pct"] > 90:
                    alarms.append({"severity": "High", "component": "Node Memory", "msg": f"Node {n['node']} RAM is {n['mem_used_pct']}% full", "target": n["node"]})
                if n["iowait"] > 5.0:
                    alarms.append({"severity": "Medium", "component": "I/O Delay", "msg": f"Node {n['node']} high IO wait ({n['iowait']}%)", "target": n["node"]})

            for s in storages:
                if s["used_pct"] > 90:
                    alarms.append({"severity": "High", "component": "Storage", "msg": f"Storage pool {s['storage']} is {s['used_pct']}% full", "target": s["storage"]})
                elif s["used_pct"] > 80:
                    alarms.append({"severity": "Low", "component": "Storage", "msg": f"Storage pool {s['storage']} > 80% used", "target": s["storage"]})

            for v in vms:
                if v["status"] == "running" and v["cpu"] > 85:
                    alarms.append({"severity": "Medium", "component": "Guest CPU", "msg": f"{v['type'].upper()} {v['name']} ({v['vmid']}) CPU {v['cpu']}%", "target": f"{v['vmid']}"})
                if v["status"] == "running" and v["mem_pct"] > 92:
                    alarms.append({"severity": "Low", "component": "Guest RAM", "msg": f"{v['type'].upper()} {v['name']} ({v['vmid']}) RAM {v['mem_pct']}%", "target": f"{v['vmid']}"})

            running_vms = sum(1 for v in vms if v["status"] == "running" and v["type"] == "qemu")
            stopped_vms = sum(1 for v in vms if v["status"] == "stopped" and v["type"] == "qemu")
            running_lxc = sum(1 for v in vms if v["status"] == "running" and v["type"] == "lxc")
            stopped_lxc = sum(1 for v in vms if v["status"] == "stopped" and v["type"] == "lxc")
            online_nodes = sum(1 for n in nodes if n["status"] == "online")

            alarm_counts = {
                "critical": sum(1 for a in alarms if a["severity"] == "Critical"),
                "high": sum(1 for a in alarms if a["severity"] == "High"),
                "medium": sum(1 for a in alarms if a["severity"] == "Medium"),
                "low": sum(1 for a in alarms if a["severity"] == "Low"),
                "normal": max(0, len(nodes) + len(vms) - len(alarms))
            }

            health_score = 100 - (alarm_counts["critical"] * 25 + alarm_counts["high"] * 12 + alarm_counts["medium"] * 5 + alarm_counts["low"] * 2)
            health_score = max(10, min(100, health_score))

            cluster_info = {
                "cluster_name": cluster_name,
                "health_score": health_score,
                "health_status": "CRITICAL" if alarm_counts["critical"] > 0 else "WARNING" if alarm_counts["high"] > 0 else "HEALTHY",
                "quorum": f"{online_nodes}/{len(nodes)} Online",
                "pve_version": pve_version,
                "nodes_online": f"{online_nodes}/{len(nodes)}",
                "vms_running": f"{running_vms}/{running_vms + stopped_vms}",
                "lxc_running": f"{running_lxc}/{running_lxc + stopped_lxc}",
                "avg_cpu_pct": avg_cpu_pct,
                "total_cpu_cores": total_cpu_cores,
                "ram_used_bytes": used_ram,
                "ram_total_bytes": total_ram,
                "ram_pct": ram_pct,
                "storage_used_bytes": used_storage,
                "storage_total_bytes": total_storage,
                "storage_pct": storage_pct,
                "alarm_counts": alarm_counts,
                "timestamp": time.time(),
                "is_mock": False
            }

            latency_ms = round((time.time() - start_t) * 1000, 1)

            return {
                "_fetch_latency_ms": latency_ms,
                "cluster": cluster_info,
                "nodes": nodes,
                "vms": vms,
                "storages": storages,
                "alarms": alarms,
                "tasks": cluster_tasks
            }

proxmox_client = ProxmoxClient()
