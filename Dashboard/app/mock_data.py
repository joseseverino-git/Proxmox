import time
import random
import math

def get_mock_data():
    now = time.time()
    t = now / 10.0
    
    # Slight oscillation for realistic real-time telemetry
    cpu_osc_1 = 38.5 + 14.0 * math.sin(t) + random.uniform(-2, 2)
    cpu_osc_2 = 62.0 + 10.0 * math.cos(t * 1.3) + random.uniform(-3, 3)
    cpu_osc_3 = 24.0 + 8.0 * math.sin(t * 0.7) + random.uniform(-1.5, 1.5)
    
    ram_osc_1 = 48.2 + 2.5 * math.sin(t * 0.5)
    ram_osc_2 = 78.4 + 3.0 * math.cos(t * 0.4)
    ram_osc_3 = 31.0 + 1.5 * math.sin(t * 0.3)

    nodes = [
        {
            "id": "node/pve-node-01",
            "node": "pve-node-01",
            "status": "online",
            "ip": "192.168.1.101",
            "cpu": round(max(5.0, min(95.0, cpu_osc_1)), 1),
            "maxcpu": 16,
            "cpu_model": "AMD Ryzen 7 5700X 8-Core (16 vCPU)",
            "mem": int(32.4 * 1024 * 1024 * 1024 * (ram_osc_1 / 100)),
            "maxmem": 64 * 1024 * 1024 * 1024,
            "mem_used_pct": round(ram_osc_1, 1),
            "swap": int(1.8 * 1024 * 1024 * 1024),
            "maxswap": 8 * 1024 * 1024 * 1024,
            "disk": 240 * 1024 * 1024 * 1024,
            "maxdisk": 960 * 1024 * 1024 * 1024,
            "disk_used_pct": 25.0,
            "uptime": 2489200,  # ~28 days
            "loadavg": [round(1.45 + 0.3 * math.sin(t), 2), 1.62, 1.55],
            "pveversion": "pve-manager/8.2-4/e8587d191246",
            "kernel": "6.8.8-2-pve",
            "iowait": round(max(0.1, 1.2 + 0.8 * math.sin(t * 1.5)), 2),
            "netin": int(18500000 + random.randint(-2000000, 2000000)),
            "netout": int(42000000 + random.randint(-3000000, 3000000)),
            "role": "Master / Quorum"
        },
        {
            "id": "node/pve-node-02",
            "node": "pve-node-02",
            "status": "online",
            "ip": "192.168.1.102",
            "cpu": round(max(5.0, min(95.0, cpu_osc_2)), 1),
            "maxcpu": 16,
            "cpu_model": "AMD Ryzen 7 5700X 8-Core (16 vCPU)",
            "mem": int(64 * 1024 * 1024 * 1024 * (ram_osc_2 / 100)),
            "maxmem": 64 * 1024 * 1024 * 1024,
            "mem_used_pct": round(ram_osc_2, 1),
            "swap": int(3.2 * 1024 * 1024 * 1024),
            "maxswap": 8 * 1024 * 1024 * 1024,
            "disk": 680 * 1024 * 1024 * 1024,
            "maxdisk": 960 * 1024 * 1024 * 1024,
            "disk_used_pct": 70.8,
            "uptime": 1823400,
            "loadavg": [round(3.85 + 0.5 * math.cos(t), 2), 3.40, 3.12],
            "pveversion": "pve-manager/8.2-4/e8587d191246",
            "kernel": "6.8.8-2-pve",
            "iowait": round(max(0.2, 3.8 + 1.2 * math.cos(t * 1.8)), 2),
            "netin": int(58000000 + random.randint(-4000000, 4000000)),
            "netout": int(112000000 + random.randint(-6000000, 6000000)),
            "role": "Compute Node"
        },
        {
            "id": "node/pve-node-03",
            "node": "pve-node-03",
            "status": "online",
            "ip": "192.168.1.103",
            "cpu": round(max(5.0, min(95.0, cpu_osc_3)), 1),
            "maxcpu": 8,
            "cpu_model": "Intel Core i5-10400 6-Core (12 vCPU)",
            "mem": int(32 * 1024 * 1024 * 1024 * (ram_osc_3 / 100)),
            "maxmem": 32 * 1024 * 1024 * 1024,
            "mem_used_pct": round(ram_osc_3, 1),
            "swap": int(0.4 * 1024 * 1024 * 1024),
            "maxswap": 4 * 1024 * 1024 * 1024,
            "disk": 190 * 1024 * 1024 * 1024,
            "maxdisk": 480 * 1024 * 1024 * 1024,
            "disk_used_pct": 39.5,
            "uptime": 3412000,
            "loadavg": [round(0.85 + 0.2 * math.sin(t * 0.8), 2), 0.90, 0.82],
            "pveversion": "pve-manager/8.2-4/e8587d191246",
            "kernel": "6.8.8-2-pve",
            "iowait": 0.4,
            "netin": int(9500000 + random.randint(-1000000, 1000000)),
            "netout": int(14200000 + random.randint(-1500000, 1500000)),
            "role": "Backup & Storage Node"
        }
    ]

    vms = [
        {
            "vmid": 100,
            "name": "srv-prod-db-postgres",
            "node": "pve-node-02",
            "type": "qemu",
            "status": "running",
            "cpus": 4,
            "cpu": round(random.uniform(45.0, 72.0), 1),
            "mem": int(14.8 * 1024 * 1024 * 1024),
            "maxmem": 16 * 1024 * 1024 * 1024,
            "mem_pct": 92.5,
            "disk": 180 * 1024 * 1024 * 1024,
            "maxdisk": 250 * 1024 * 1024 * 1024,
            "uptime": 1823100,
            "netin": 45000000,
            "netout": 98000000,
            "diskread": 14500000,
            "diskwrite": 38000000,
            "os": "Debian 12 (Bookworm)",
            "ip": "192.168.10.15",
            "tags": "production;database;critical"
        },
        {
            "vmid": 101,
            "name": "srv-k8s-master-01",
            "node": "pve-node-01",
            "type": "qemu",
            "status": "running",
            "cpus": 4,
            "cpu": round(random.uniform(22.0, 38.0), 1),
            "mem": int(6.8 * 1024 * 1024 * 1024),
            "maxmem": 8 * 1024 * 1024 * 1024,
            "mem_pct": 85.0,
            "disk": 42 * 1024 * 1024 * 1024,
            "maxdisk": 80 * 1024 * 1024 * 1024,
            "uptime": 2489000,
            "netin": 28000000,
            "netout": 32000000,
            "diskread": 2100000,
            "diskwrite": 5400000,
            "os": "Ubuntu 22.04 LTS",
            "ip": "192.168.10.20",
            "tags": "k8s;control-plane"
        },
        {
            "vmid": 102,
            "name": "srv-k8s-worker-01",
            "node": "pve-node-02",
            "type": "qemu",
            "status": "running",
            "cpus": 6,
            "cpu": round(random.uniform(55.0, 84.0), 1),
            "mem": int(19.5 * 1024 * 1024 * 1024),
            "maxmem": 24 * 1024 * 1024 * 1024,
            "mem_pct": 81.2,
            "disk": 95 * 1024 * 1024 * 1024,
            "maxdisk": 150 * 1024 * 1024 * 1024,
            "uptime": 1823000,
            "netin": 62000000,
            "netout": 74000000,
            "diskread": 8400000,
            "diskwrite": 24000000,
            "os": "Ubuntu 22.04 LTS",
            "ip": "192.168.10.21",
            "tags": "k8s;worker"
        },
        {
            "vmid": 103,
            "name": "win-server-ad-01",
            "node": "pve-node-01",
            "type": "qemu",
            "status": "running",
            "cpus": 4,
            "cpu": round(random.uniform(8.0, 18.0), 1),
            "mem": int(5.4 * 1024 * 1024 * 1024),
            "maxmem": 8 * 1024 * 1024 * 1024,
            "mem_pct": 67.5,
            "disk": 52 * 1024 * 1024 * 1024,
            "maxdisk": 100 * 1024 * 1024 * 1024,
            "uptime": 2488500,
            "netin": 4500000,
            "netout": 7800000,
            "diskread": 1200000,
            "diskwrite": 3100000,
            "os": "Windows Server 2022",
            "ip": "192.168.10.5",
            "tags": "windows;activedirectory"
        },
        {
            "vmid": 104,
            "name": "truenas-core-vm",
            "node": "pve-node-03",
            "type": "qemu",
            "status": "running",
            "cpus": 4,
            "cpu": round(random.uniform(12.0, 28.0), 1),
            "mem": int(14.2 * 1024 * 1024 * 1024),
            "maxmem": 16 * 1024 * 1024 * 1024,
            "mem_pct": 88.7,
            "disk": 1200 * 1024 * 1024 * 1024,
            "maxdisk": 4000 * 1024 * 1024 * 1024,
            "uptime": 3411000,
            "netin": 35000000,
            "netout": 52000000,
            "diskread": 18500000,
            "diskwrite": 28000000,
            "os": "FreeBSD / TrueNAS Core",
            "ip": "192.168.10.30",
            "tags": "storage;nas"
        },
        {
            "vmid": 105,
            "name": "dev-sandbox-test",
            "node": "pve-node-03",
            "type": "qemu",
            "status": "stopped",
            "cpus": 2,
            "cpu": 0.0,
            "mem": 0,
            "maxmem": 4 * 1024 * 1024 * 1024,
            "mem_pct": 0.0,
            "disk": 22 * 1024 * 1024 * 1024,
            "maxdisk": 40 * 1024 * 1024 * 1024,
            "uptime": 0,
            "netin": 0,
            "netout": 0,
            "diskread": 0,
            "diskwrite": 0,
            "os": "Debian 12",
            "ip": "-",
            "tags": "testing;dev"
        },
        # Containers (LXC)
        {
            "vmid": 200,
            "name": "ct-nginx-reverse-proxy",
            "node": "pve-node-01",
            "type": "lxc",
            "status": "running",
            "cpus": 2,
            "cpu": round(random.uniform(4.0, 12.0), 1),
            "mem": 420 * 1024 * 1024,
            "maxmem": 1024 * 1024 * 1024,
            "mem_pct": 41.0,
            "disk": int(3.8 * 1024 * 1024 * 1024),
            "maxdisk": 10 * 1024 * 1024 * 1024,
            "uptime": 2489100,
            "netin": 48000000,
            "netout": 52000000,
            "diskread": 300000,
            "diskwrite": 1200000,
            "os": "Alpine Linux 3.19",
            "ip": "192.168.10.2",
            "tags": "gateway;proxy"
        },
        {
            "vmid": 201,
            "name": "ct-pihole-dns-primary",
            "node": "pve-node-01",
            "type": "lxc",
            "status": "running",
            "cpus": 1,
            "cpu": round(random.uniform(1.5, 4.0), 1),
            "mem": 260 * 1024 * 1024,
            "maxmem": 512 * 1024 * 1024,
            "mem_pct": 50.7,
            "disk": int(2.4 * 1024 * 1024 * 1024),
            "maxdisk": 8 * 1024 * 1024 * 1024,
            "uptime": 2489200,
            "netin": 3200000,
            "netout": 4100000,
            "diskread": 150000,
            "diskwrite": 450000,
            "os": "Debian 12",
            "ip": "192.168.10.3",
            "tags": "dns;network"
        },
        {
            "vmid": 202,
            "name": "ct-home-assistant-core",
            "node": "pve-node-01",
            "type": "lxc",
            "status": "running",
            "cpus": 2,
            "cpu": round(random.uniform(5.0, 15.0), 1),
            "mem": int(1.4 * 1024 * 1024 * 1024),
            "maxmem": 2 * 1024 * 1024 * 1024,
            "mem_pct": 70.0,
            "disk": int(12.8 * 1024 * 1024 * 1024),
            "maxdisk": 30 * 1024 * 1024 * 1024,
            "uptime": 2489000,
            "netin": 6800000,
            "netout": 7400000,
            "diskread": 900000,
            "diskwrite": 2800000,
            "os": "Debian 12",
            "ip": "192.168.10.80",
            "tags": "iot;homeautomation"
        },
        {
            "vmid": 203,
            "name": "ct-vaultwarden-pw",
            "node": "pve-node-02",
            "type": "lxc",
            "status": "running",
            "cpus": 1,
            "cpu": round(random.uniform(0.5, 3.0), 1),
            "mem": 180 * 1024 * 1024,
            "maxmem": 512 * 1024 * 1024,
            "mem_pct": 35.1,
            "disk": int(1.8 * 1024 * 1024 * 1024),
            "maxdisk": 8 * 1024 * 1024 * 1024,
            "uptime": 1822800,
            "netin": 800000,
            "netout": 950000,
            "diskread": 80000,
            "diskwrite": 320000,
            "os": "Alpine Linux 3.19",
            "ip": "192.168.10.90",
            "tags": "security;passwords"
        },
        {
            "vmid": 204,
            "name": "ct-docker-runner",
            "node": "pve-node-02",
            "type": "lxc",
            "status": "running",
            "cpus": 4,
            "cpu": round(random.uniform(18.0, 42.0), 1),
            "mem": int(3.8 * 1024 * 1024 * 1024),
            "maxmem": 6 * 1024 * 1024 * 1024,
            "mem_pct": 63.3,
            "disk": int(28.5 * 1024 * 1024 * 1024),
            "maxdisk": 60 * 1024 * 1024 * 1024,
            "uptime": 1822500,
            "netin": 24000000,
            "netout": 29000000,
            "diskread": 4200000,
            "diskwrite": 9800000,
            "os": "Ubuntu 22.04 LTS",
            "ip": "192.168.10.40",
            "tags": "docker;containers"
        },
        {
            "vmid": 205,
            "name": "ct-grafana-influxdb",
            "node": "pve-node-03",
            "type": "lxc",
            "status": "running",
            "cpus": 2,
            "cpu": round(random.uniform(8.0, 19.0), 1),
            "mem": int(1.9 * 1024 * 1024 * 1024),
            "maxmem": 4 * 1024 * 1024 * 1024,
            "mem_pct": 47.5,
            "disk": int(18.2 * 1024 * 1024 * 1024),
            "maxdisk": 40 * 1024 * 1024 * 1024,
            "uptime": 3410500,
            "netin": 8500000,
            "netout": 9800000,
            "diskread": 2100000,
            "diskwrite": 5600000,
            "os": "Debian 12",
            "ip": "192.168.10.50",
            "tags": "monitoring;metrics"
        }
    ]

    storages = [
        {
            "storage": "local",
            "node": "pve-node-01",
            "type": "dir",
            "content": "iso,vztmpl,backup",
            "used": 48 * 1024 * 1024 * 1024,
            "total": 120 * 1024 * 1024 * 1024,
            "avail": 72 * 1024 * 1024 * 1024,
            "used_pct": 40.0,
            "status": "active",
            "shared": 0
        },
        {
            "storage": "local-zfs-nvme",
            "node": "pve-node-01",
            "type": "zfspool",
            "content": "rootdir,images",
            "used": 420 * 1024 * 1024 * 1024,
            "total": 960 * 1024 * 1024 * 1024,
            "avail": 540 * 1024 * 1024 * 1024,
            "used_pct": 43.7,
            "status": "active",
            "shared": 0
        },
        {
            "storage": "ceph-fast-pool",
            "node": "cluster",
            "type": "rbd",
            "content": "rootdir,images",
            "used": 1840 * 1024 * 1024 * 1024,
            "total": 3840 * 1024 * 1024 * 1024,
            "avail": 2000 * 1024 * 1024 * 1024,
            "used_pct": 47.9,
            "status": "active",
            "shared": 1
        },
        {
            "storage": "nfs-truenas-backups",
            "node": "cluster",
            "type": "nfs",
            "content": "backup,snippets",
            "used": 5400 * 1024 * 1024 * 1024,
            "total": 12000 * 1024 * 1024 * 1024,
            "avail": 6600 * 1024 * 1024 * 1024,
            "used_pct": 45.0,
            "status": "active",
            "shared": 1
        },
        {
            "storage": "pbs-offsite-backup",
            "node": "cluster",
            "type": "pbs",
            "content": "backup",
            "used": 3200 * 1024 * 1024 * 1024,
            "total": 8000 * 1024 * 1024 * 1024,
            "avail": 4800 * 1024 * 1024 * 1024,
            "used_pct": 40.0,
            "status": "active",
            "shared": 1
        }
    ]

    cluster_tasks = [
        {
            "upid": "UPID:pve-node-01:0001FA21:0B891A42:66C63391:vzdump:100:root@pam:",
            "node": "pve-node-01",
            "user": "root@pam",
            "type": "vzdump",
            "id": "100",
            "starttime": int(now - 1420),
            "endtime": int(now - 1200),
            "status": "OK",
            "description": "Backup VM 100 (srv-prod-db-postgres) to nfs-truenas-backups"
        },
        {
            "upid": "UPID:pve-node-02:00018C44:0A112440:66C63510:qmigrate:102:root@pam:",
            "node": "pve-node-02",
            "user": "root@pam",
            "type": "qmigrate",
            "id": "102",
            "starttime": int(now - 3600),
            "endtime": int(now - 3550),
            "status": "OK",
            "description": "Live Migration VM 102 from pve-node-01 to pve-node-02"
        },
        {
            "upid": "UPID:pve-node-01:00021A04:0C554101:66C63622:vzsnapshot:200:admin@pve:",
            "node": "pve-node-01",
            "user": "admin@pve",
            "type": "vzsnapshot",
            "id": "200",
            "starttime": int(now - 5400),
            "endtime": int(now - 5390),
            "status": "OK",
            "description": "Snapshot CT 200 (pre-upgrade-nginx)"
        },
        {
            "upid": "UPID:pve-node-03:00009121:04B50119:66C63890:qmstart:104:monitoring@pve:",
            "node": "pve-node-03",
            "user": "monitoring@pve",
            "type": "qmstart",
            "id": "104",
            "starttime": int(now - 18000),
            "endtime": int(now - 17985),
            "status": "OK",
            "description": "Start VM 104 (truenas-core-vm)"
        }
    ]

    # Calculate cluster totals
    total_cpu_cores = sum(n["maxcpu"] for n in nodes)
    avg_cpu_pct = round(sum(n["cpu"] * n["maxcpu"] for n in nodes) / total_cpu_cores, 1)
    
    total_ram = sum(n["maxmem"] for n in nodes)
    used_ram = sum(n["mem"] for n in nodes)
    ram_pct = round((used_ram / total_ram) * 100, 1)

    total_storage = sum(s["total"] for s in storages)
    used_storage = sum(s["used"] for s in storages)
    storage_pct = round((used_storage / total_storage) * 100, 1)

    # Spotlight Alarms logic
    alarms = []
    if ram_pct > 80:
        alarms.append({"severity": "High", "component": "Memory", "msg": f"Cluster Memory utilization is elevated ({ram_pct}%)", "target": "Cluster"})
    if avg_cpu_pct > 75:
        alarms.append({"severity": "Critical", "component": "CPU", "msg": f"High Cluster CPU load ({avg_cpu_pct}%)", "target": "Cluster"})
    for vm in vms:
        if vm["status"] == "running" and vm["cpu"] > 70:
            alarms.append({"severity": "Medium", "component": "vCPU", "msg": f"VM {vm['name']} ({vm['vmid']}) sustained CPU > {vm['cpu']}%", "target": f"VM {vm['vmid']}"})
        if vm["status"] == "running" and vm["mem_pct"] > 90:
            alarms.append({"severity": "Medium", "component": "vRAM", "msg": f"VM {vm['name']} ({vm['vmid']}) Memory > {vm['mem_pct']}%", "target": f"VM {vm['vmid']}"})
    for n in nodes:
        if n["iowait"] > 3.0:
            alarms.append({"severity": "Low", "component": "Disk I/O", "msg": f"Node {n['node']} IO Delay is {n['iowait']}%", "target": n["node"]})

    # Summary counts
    running_vms = sum(1 for v in vms if v["status"] == "running" and v["type"] == "qemu")
    stopped_vms = sum(1 for v in vms if v["status"] == "stopped" and v["type"] == "qemu")
    running_lxc = sum(1 for v in vms if v["status"] == "running" and v["type"] == "lxc")
    stopped_lxc = sum(1 for v in vms if v["status"] == "stopped" and v["type"] == "lxc")

    alarm_counts = {
        "critical": sum(1 for a in alarms if a["severity"] == "Critical"),
        "high": sum(1 for a in alarms if a["severity"] == "High"),
        "medium": sum(1 for a in alarms if a["severity"] == "Medium"),
        "low": sum(1 for a in alarms if a["severity"] == "Low"),
        "normal": max(0, len(nodes) + len(vms) - len(alarms))
    }

    # Cluster health rating (Spotlight health index 0-100)
    health_score = 100 - (alarm_counts["critical"] * 25 + alarm_counts["high"] * 12 + alarm_counts["medium"] * 5 + alarm_counts["low"] * 2)
    health_score = max(10, min(100, health_score))

    cluster_info = {
        "cluster_name": "PVE-HYPERVISOR-PROD",
        "health_score": health_score,
        "health_status": "CRITICAL" if alarm_counts["critical"] > 0 else "WARNING" if alarm_counts["high"] > 0 else "HEALTHY",
        "quorum": "3/3 (100% OK)",
        "pve_version": "Proxmox VE 8.2-4",
        "nodes_online": f"{len(nodes)}/{len(nodes)}",
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
        "timestamp": now,
        "is_mock": True
    }

    return {
        "cluster": cluster_info,
        "nodes": nodes,
        "vms": vms,
        "storages": storages,
        "alarms": alarms,
        "tasks": cluster_tasks
    }
