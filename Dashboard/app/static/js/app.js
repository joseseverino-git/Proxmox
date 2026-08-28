/**
 * Spotlight on Proxmox VE - Frontend Application
 * Diagnostics, Real-Time Telemetry & Enterprise Management UI
 */

const AppState = {
  currentView: 'executive',
  refreshInterval: 5000,
  timerId: null,
  isFetching: false,
  data: null,
  history: {
    timestamps: [],
    cpu: [],
    ram: []
  },
  filters: {
    search: '',
    node: 'all',
    type: 'all',
    status: 'all',
    alarmSeverity: 'all'
  },
  selectedGuest: null
};

// --- Helper Utilities ---

function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return 'Stopped';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function getProgressClass(pct) {
  if (pct >= 90) return 'fill-red';
  if (pct >= 80) return 'fill-orange';
  if (pct >= 65) return 'fill-yellow';
  return 'fill-green';
}

function getGaugeColor(pct) {
  if (pct >= 90) return '#ff2a4b';
  if (pct >= 80) return '#ff7b00';
  if (pct >= 65) return '#ffcc00';
  return '#00e676';
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// --- Data Fetching ---

async function fetchDashboardData(force = false) {
  if (AppState.isFetching) return;
  AppState.isFetching = true;
  
  const refreshIcon = document.getElementById('refresh-icon');
  if (refreshIcon) refreshIcon.classList.add('spin');

  try {
    const response = await fetch(`/api/status?force=${force}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    AppState.data = data;
    
    // Update telemetry history buffer (max 20 points)
    if (data.cluster) {
      const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      AppState.history.timestamps.push(nowStr);
      AppState.history.cpu.push(data.cluster.avg_cpu_pct || 0);
      AppState.history.ram.push(data.cluster.ram_pct || 0);
      if (AppState.history.timestamps.length > 20) {
        AppState.history.timestamps.shift();
        AppState.history.cpu.shift();
        AppState.history.ram.shift();
      }
    }

    renderHeader();
    renderAlarmStrip();
    renderCurrentView();
  } catch (err) {
    console.error('Fetch error:', err);
    showErrorToast(err.message);
  } finally {
    AppState.isFetching = false;
    if (refreshIcon) refreshIcon.classList.remove('spin');
  }
}

function showErrorToast(msg) {
  const connPill = document.getElementById('connection-status-pill');
  if (connPill) {
    connPill.className = 'conn-status-pill demo';
    connPill.innerHTML = `<span class="pulse-dot" style="background:#ff2a4b"></span> Error: ${escapeHtml(msg)}`;
  }
}

// --- Rendering Core Sections ---

function renderHeader() {
  if (!AppState.data) return;
  const conn = AppState.data.connection_status || {};
  const connPill = document.getElementById('connection-status-pill');
  const alertBanner = document.getElementById('connection-alert-banner');
  const alertTitle = document.getElementById('alert-banner-title');
  const alertMsg = document.getElementById('alert-banner-msg');
  
  if (connPill) {
    if (conn.connected && !conn.is_demo) {
      connPill.className = 'conn-status-pill live';
      connPill.innerHTML = `<span class="pulse-dot"></span> LIVE: ${escapeHtml(conn.host)} (${conn.latency_ms || 0}ms)`;
      if (alertBanner) alertBanner.style.display = 'none';
    } else if (conn.mode === 'DEMO_MODE') {
      connPill.className = 'conn-status-pill demo';
      connPill.innerHTML = `<span class="pulse-dot" style="background:#ffcc00"></span> MODO DEMO`;
      if (alertBanner) alertBanner.style.display = 'none';
    } else {
      // Disconnected, unconfigured or fallback demo
      connPill.className = 'conn-status-pill demo';
      const label = conn.unconfigured ? 'NO CONFIGURADO' : 'DESCONECTADO';
      connPill.innerHTML = `<span class="pulse-dot" style="background:#ff2a4b"></span> ${label}`;
      if (alertBanner) {
        alertBanner.style.display = 'flex';
        if (alertTitle) alertTitle.textContent = conn.unconfigured ? 'Servidor Proxmox no configurado:' : 'Sin conexión con Proxmox VE:';
        if (alertMsg) alertMsg.textContent = conn.message || conn.error || 'No se puede contactar la API de Proxmox.';
      }
    }
  }

  const clusterTitle = document.getElementById('cluster-title');
  if (clusterTitle && AppState.data.cluster) {
    clusterTitle.textContent = AppState.data.cluster.cluster_name || 'Proxmox Cluster';
  }
}

function renderAlarmStrip() {
  if (!AppState.data || !AppState.data.cluster) return;
  const cl = AppState.data.cluster;
  const alarms = cl.alarm_counts || { critical: 0, high: 0, medium: 0, low: 0, normal: 0 };

  document.getElementById('count-critical').textContent = alarms.critical;
  document.getElementById('count-high').textContent = alarms.high;
  document.getElementById('count-medium').textContent = alarms.medium;
  document.getElementById('count-low').textContent = alarms.low;
  document.getElementById('count-normal').textContent = alarms.normal;

  // Health Score badge
  const healthPill = document.getElementById('health-score-container');
  if (healthPill) {
    const score = cl.health_score || 0;
    const statusClass = score >= 85 ? 'healthy' : score >= 60 ? 'warning' : 'critical';
    healthPill.className = `health-score-pill ${statusClass}`;
    healthPill.innerHTML = `<span>HEALTH:</span> <strong>${score}/100</strong> (${cl.health_status})`;
  }

  // Cluster meta strip
  document.getElementById('meta-pve-version').textContent = cl.pve_version || '-';
  document.getElementById('meta-nodes-count').textContent = cl.nodes_online || '0/0';
  document.getElementById('meta-vms-count').textContent = cl.vms_running || '0/0';
  document.getElementById('meta-lxc-count').textContent = cl.lxc_running || '0/0';
}

function renderCurrentView() {
  const container = document.getElementById('view-content-area');
  if (!container || !AppState.data) return;
  const conn = AppState.data.connection_status || {};

  // If disconnected or unconfigured and NOT in demo mode, show the clear offline diagnostic hero
  if (!conn.connected && !conn.is_demo && (!AppState.data.nodes || AppState.data.nodes.length === 0)) {
    container.innerHTML = getOfflineStateHtml(conn);
    attachOfflineEventListeners();
    return;
  }

  if (AppState.currentView === 'executive') {
    container.innerHTML = getExecutiveViewHtml();
    drawGauges();
  } else if (AppState.currentView === 'technical') {
    container.innerHTML = getTechnicalViewHtml();
    attachTechnicalEventListeners();
  } else if (AppState.currentView === 'alarms') {
    container.innerHTML = getAlarmsAndLogsViewHtml();
  }
}

function getOfflineStateHtml(conn) {
  return `
    <div class="offline-hero-card">
      <i class="lucide-server-off offline-hero-icon"></i>
      <div class="offline-hero-title">${conn.unconfigured ? 'Servidor Proxmox VE No Configurado' : 'Sin Conexión con Proxmox VE'}</div>
      <div class="offline-hero-desc">
        ${conn.unconfigured 
          ? 'Para visualizar la telemetría real de tus nodos, máquinas virtuales (QEMU), contenedores (LXC) y almacenamiento, ingresa los datos de conexión de tu servidor.'
          : `El dashboard no pudo comunicarse con el servidor Proxmox VE en <strong>${escapeHtml(conn.host || '')}</strong>.`
        }
      </div>
      ${conn.error ? `<div class="offline-error-quote">${escapeHtml(conn.error)}</div>` : ''}
      <div class="offline-actions-row">
        <button class="action-btn action-btn-troubleshoot" id="btn-hero-troubleshoot" style="padding:10px 18px;font-size:13px;">
          <i class="lucide-activity"></i> Ejecutar Troubleshooting
        </button>
        <button class="action-btn action-btn-config" id="btn-hero-config" style="padding:10px 18px;font-size:13px;">
          <i class="lucide-settings"></i> Configurar Conexión
        </button>
      </div>
    </div>
  `;
}

function attachOfflineEventListeners() {
  const tbBtn = document.getElementById('btn-hero-troubleshoot');
  if (tbBtn) tbBtn.addEventListener('click', openTroubleshootModal);
  const cfgBtn = document.getElementById('btn-hero-config');
  if (cfgBtn) cfgBtn.addEventListener('click', openConfigModal);
}


// --- View 1: Executive View ---

function getExecutiveViewHtml() {
  const cl = AppState.data.cluster || {};
  const nodes = AppState.data.nodes || [];
  const vms = AppState.data.vms || [];
  const storages = AppState.data.storages || [];

  // Sort VMs for leaderboards
  const runningVms = vms.filter(v => v.status === 'running');
  const topCpuVms = [...runningVms].sort((a, b) => b.cpu - a.cpu).slice(0, 5);

  const ramUsedGb = (cl.ram_used_bytes / (1024 ** 3)).toFixed(1);
  const ramTotalGb = (cl.ram_total_bytes / (1024 ** 3)).toFixed(1);
  const storageUsedTb = (cl.storage_used_bytes / (1024 ** 4)).toFixed(2);
  const storageTotalTb = (cl.storage_total_bytes / (1024 ** 4)).toFixed(2);

  return `
    <!-- Spotlight Diagnostic Topology Bar -->
    <div class="topology-container">
      <div class="panel-header">
        <h3><i class="lucide-activity"></i> Spotlight Diagnostic Topology Flow</h3>
        <span style="font-size:11px;color:var(--text-muted);">Real-Time Infrastructure Health Matrix</span>
      </div>
      <div class="topology-grid">
        <div class="topo-node status-${cl.health_score > 70 ? 'healthy' : 'warning'}">
          <div class="topo-title">
            <span>Cluster Quorum</span>
            <span class="status-pill ok">OK</span>
          </div>
          <div class="topo-value">${escapeHtml(cl.quorum || '3/3')}</div>
          <div class="topo-subtext">${escapeHtml(cl.cluster_name)}</div>
          <div class="spotlight-bar-wrap">
            <div class="spotlight-bar-fill fill-green" style="width: 100%;"></div>
          </div>
        </div>

        <div class="topo-node status-healthy">
          <div class="topo-title">
            <span>Physical Nodes</span>
            <span class="status-pill active">${nodes.filter(n=>n.status==='online').length}/${nodes.length}</span>
          </div>
          <div class="topo-value">${nodes.length} Nodes</div>
          <div class="topo-subtext">${cl.total_cpu_cores} Total Cores Allocated</div>
          <div class="spotlight-bar-wrap">
            <div class="spotlight-bar-fill fill-green" style="width: 100%;"></div>
          </div>
        </div>

        <div class="topo-node status-${cl.avg_cpu_pct > 80 ? 'critical' : cl.avg_cpu_pct > 60 ? 'warning' : 'healthy'}">
          <div class="topo-title">
            <span>Compute (CPU)</span>
            <span>${cl.avg_cpu_pct}%</span>
          </div>
          <div class="topo-value">${cl.avg_cpu_pct}%</div>
          <div class="topo-subtext">Avg Cluster Load</div>
          <div class="spotlight-bar-wrap">
            <div class="spotlight-bar-fill ${getProgressClass(cl.avg_cpu_pct)}" style="width: ${cl.avg_cpu_pct}%;"></div>
          </div>
        </div>

        <div class="topo-node status-${cl.ram_pct > 85 ? 'critical' : cl.ram_pct > 70 ? 'warning' : 'healthy'}">
          <div class="topo-title">
            <span>Memory (RAM)</span>
            <span>${cl.ram_pct}%</span>
          </div>
          <div class="topo-value">${cl.ram_pct}%</div>
          <div class="topo-subtext">${ramUsedGb} GB / ${ramTotalGb} GB</div>
          <div class="spotlight-bar-wrap">
            <div class="spotlight-bar-fill ${getProgressClass(cl.ram_pct)}" style="width: ${cl.ram_pct}%;"></div>
          </div>
        </div>

        <div class="topo-node status-${cl.storage_pct > 85 ? 'warning' : 'healthy'}">
          <div class="topo-title">
            <span>Storage Pools</span>
            <span>${cl.storage_pct}%</span>
          </div>
          <div class="topo-value">${cl.storage_pct}%</div>
          <div class="topo-subtext">${storageUsedTb} TB / ${storageTotalTb} TB</div>
          <div class="spotlight-bar-wrap">
            <div class="spotlight-bar-fill ${getProgressClass(cl.storage_pct)}" style="width: ${cl.storage_pct}%;"></div>
          </div>
        </div>

        <div class="topo-node status-healthy">
          <div class="topo-title">
            <span>Workloads</span>
            <span class="status-pill active">${vms.length} Total</span>
          </div>
          <div class="topo-value">${vms.filter(v=>v.status==='running').length} Active</div>
          <div class="topo-subtext">${cl.vms_running} VMs | ${cl.lxc_running} LXC</div>
          <div class="spotlight-bar-wrap">
            <div class="spotlight-bar-fill fill-green" style="width: ${Math.round((vms.filter(v=>v.status==='running').length / (vms.length || 1))*100)}%;"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- KPI Gauges Grid -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="panel-header">
          <h3>Cluster CPU Utilization</h3>
          <span>${cl.total_cpu_cores} vCPUs</span>
        </div>
        <div class="kpi-body">
          <div class="kpi-metric-group">
            <div class="kpi-title">Average Core Load</div>
            <div class="kpi-main-val">${cl.avg_cpu_pct}%</div>
            <div class="kpi-sub-val">Combined capacity across ${nodes.length} nodes</div>
          </div>
          <div class="gauge-wrapper" id="gauge-cpu"></div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="panel-header">
          <h3>Cluster Memory (RAM)</h3>
          <span>${cl.ram_pct}% Used</span>
        </div>
        <div class="kpi-body">
          <div class="kpi-metric-group">
            <div class="kpi-title">Allocated RAM</div>
            <div class="kpi-main-val">${ramUsedGb} <span style="font-size:14px;color:var(--text-secondary)">GB</span></div>
            <div class="kpi-sub-val">Total Physical: ${ramTotalGb} GB</div>
          </div>
          <div class="gauge-wrapper" id="gauge-ram"></div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="panel-header">
          <h3>Cluster Storage Pools</h3>
          <span>${cl.storage_pct}% Used</span>
        </div>
        <div class="kpi-body">
          <div class="kpi-metric-group">
            <div class="kpi-title">Storage Space</div>
            <div class="kpi-main-val">${storageUsedTb} <span style="font-size:14px;color:var(--text-secondary)">TB</span></div>
            <div class="kpi-sub-val">Total Capacity: ${storageTotalTb} TB</div>
          </div>
          <div class="gauge-wrapper" id="gauge-storage"></div>
        </div>
      </div>
    </div>

    <!-- Middle Row: Top Consumers & Node Overview -->
    <div class="dashboard-row">
      <!-- Top Resource Consumers -->
      <div class="spot-table-container">
        <div class="panel-header">
          <h3><i class="lucide-trending-up"></i> Top CPU & RAM Consumers (Workloads)</h3>
          <span>Top Active VMs / LXC</span>
        </div>
        <div class="spot-table-scroll">
          <table class="spot-table">
            <thead>
              <tr>
                <th>Guest</th>
                <th>Type</th>
                <th>Node</th>
                <th>CPU %</th>
                <th>RAM %</th>
                <th>RAM Used</th>
              </tr>
            </thead>
            <tbody>
              ${topCpuVms.map(v => `
                <tr onclick="openGuestDetailModal(${v.vmid})">
                  <td><strong>${escapeHtml(v.name)}</strong> <span style="color:var(--text-muted);font-size:10px;">(#${v.vmid})</span></td>
                  <td><span class="type-pill ${v.type}">${v.type}</span></td>
                  <td>${escapeHtml(v.node)}</td>
                  <td>
                    <div style="display:flex;align-items:center;gap:6px;">
                      <span style="font-weight:700;color:${getGaugeColor(v.cpu)}">${v.cpu}%</span>
                      <div class="spotlight-bar-wrap" style="width:50px;margin-top:0;">
                        <div class="spotlight-bar-fill ${getProgressClass(v.cpu)}" style="width:${v.cpu}%;"></div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div style="display:flex;align-items:center;gap:6px;">
                      <span>${v.mem_pct}%</span>
                      <div class="spotlight-bar-wrap" style="width:50px;margin-top:0;">
                        <div class="spotlight-bar-fill ${getProgressClass(v.mem_pct)}" style="width:${v.mem_pct}%;"></div>
                      </div>
                    </div>
                  </td>
                  <td>${formatBytes(v.mem)}</td>
                </tr>
              `).join('')}
              ${topCpuVms.length === 0 ? '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">No running workloads found</td></tr>' : ''}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Node Health Summary Cards -->
      <div class="spot-table-container">
        <div class="panel-header">
          <h3><i class="lucide-server"></i> Proxmox Nodes Status</h3>
          <span>${nodes.length} Nodes</span>
        </div>
        <div class="spot-table-scroll">
          <table class="spot-table">
            <thead>
              <tr>
                <th>Node Name</th>
                <th>Status</th>
                <th>CPU</th>
                <th>Memory</th>
                <th>IO Delay</th>
                <th>Uptime</th>
              </tr>
            </thead>
            <tbody>
              ${nodes.map(n => `
                <tr>
                  <td><strong>${escapeHtml(n.node)}</strong></td>
                  <td><span class="status-pill ${n.status}">${n.status}</span></td>
                  <td>
                    <div style="display:flex;align-items:center;gap:6px;">
                      <strong>${n.cpu}%</strong>
                      <div class="spotlight-bar-wrap" style="width:45px;margin-top:0;">
                        <div class="spotlight-bar-fill ${getProgressClass(n.cpu)}" style="width:${n.cpu}%;"></div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div style="display:flex;align-items:center;gap:6px;">
                      <strong>${n.mem_used_pct}%</strong>
                      <div class="spotlight-bar-wrap" style="width:45px;margin-top:0;">
                        <div class="spotlight-bar-fill ${getProgressClass(n.mem_used_pct)}" style="width:${n.mem_used_pct}%;"></div>
                      </div>
                    </div>
                  </td>
                  <td><span style="color:${n.iowait > 3 ? 'var(--alarm-high)' : 'var(--text-secondary)'}">${n.iowait}%</span></td>
                  <td>${formatUptime(n.uptime)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Storage Overview Row -->
    <div class="spot-table-container">
      <div class="panel-header">
        <h3><i class="lucide-hard-drive"></i> Storage Pools Capacity Breakdown</h3>
        <span>${storages.length} Pools</span>
      </div>
      <div class="spot-table-scroll">
        <table class="spot-table">
          <thead>
            <tr>
              <th>Storage Pool</th>
              <th>Node / Scope</th>
              <th>Type</th>
              <th>Content</th>
              <th>Usage Bar</th>
              <th>Used</th>
              <th>Total</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${storages.map(s => `
              <tr>
                <td><strong>${escapeHtml(s.storage)}</strong></td>
                <td>${escapeHtml(s.node)}</td>
                <td><span class="type-pill" style="background:#1d2e38;color:#7ee787;">${s.type}</span></td>
                <td style="color:var(--text-muted);font-size:11px;">${escapeHtml(s.content)}</td>
                <td style="min-width:140px;">
                  <div style="display:flex;align-items:center;gap:8px;">
                    <div class="spotlight-bar-wrap" style="flex:1;margin-top:0;">
                      <div class="spotlight-bar-fill ${getProgressClass(s.used_pct)}" style="width:${s.used_pct}%;"></div>
                    </div>
                    <span style="font-weight:700;font-size:11px;">${s.used_pct}%</span>
                  </div>
                </td>
                <td>${formatBytes(s.used)}</td>
                <td>${formatBytes(s.total)}</td>
                <td><span class="status-pill active">${s.status}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function drawGauges() {
  const cl = AppState.data.cluster || {};
  renderRingGauge('gauge-cpu', cl.avg_cpu_pct || 0);
  renderRingGauge('gauge-ram', cl.ram_pct || 0);
  renderRingGauge('gauge-storage', cl.storage_pct || 0);
}

function renderRingGauge(elementId, pct) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const strokeColor = getGaugeColor(pct);

  el.innerHTML = `
    <svg class="gauge-svg" width="70" height="70" viewBox="0 0 70 70">
      <circle class="gauge-bg" cx="35" cy="35" r="${radius}"></circle>
      <circle class="gauge-circle" cx="35" cy="35" r="${radius}" 
        stroke="${strokeColor}" 
        stroke-dasharray="${circumference}" 
        stroke-dashoffset="${offset}"></circle>
    </svg>
    <div class="gauge-label">${pct}%</div>
  `;
}

// --- View 2: Technical Deep-Dive View ---

function getTechnicalViewHtml() {
  const nodes = AppState.data.nodes || [];
  const vms = AppState.data.vms || [];
  const storages = AppState.data.storages || [];

  // Filter VMs
  let filteredVms = vms.filter(v => {
    if (AppState.filters.node !== 'all' && v.node !== AppState.filters.node) return false;
    if (AppState.filters.type !== 'all' && v.type !== AppState.filters.type) return false;
    if (AppState.filters.status !== 'all' && v.status !== AppState.filters.status) return false;
    if (AppState.filters.search) {
      const q = AppState.filters.search.toLowerCase();
      const matchName = (v.name || '').toLowerCase().includes(q);
      const matchId = String(v.vmid).includes(q);
      const matchTags = (v.tags || '').toLowerCase().includes(q);
      const matchOs = (v.os || '').toLowerCase().includes(q);
      if (!matchName && !matchId && !matchTags && !matchOs) return false;
    }
    return true;
  });

  return `
    <!-- Node Telemetry Cards -->
    <div class="node-card-grid">
      ${nodes.map(n => `
        <div class="node-card">
          <div class="node-card-header">
            <div>
              <strong style="font-size:13px;color:var(--text-bright);">${escapeHtml(n.node)}</strong>
              <div style="font-size:11px;color:var(--text-muted);">${escapeHtml(n.cpu_model)}</div>
            </div>
            <span class="status-pill ${n.status}">${n.status}</span>
          </div>
          <div class="node-card-body">
            <div class="metric-row">
              <div class="metric-labels">
                <span>CPU (${n.maxcpu} Cores)</span>
                <strong>${n.cpu}%</strong>
              </div>
              <div class="spotlight-bar-wrap">
                <div class="spotlight-bar-fill ${getProgressClass(n.cpu)}" style="width:${n.cpu}%;"></div>
              </div>
            </div>

            <div class="metric-row">
              <div class="metric-labels">
                <span>Memory (${formatBytes(n.mem)} / ${formatBytes(n.maxmem)})</span>
                <strong>${n.mem_used_pct}%</strong>
              </div>
              <div class="spotlight-bar-wrap">
                <div class="spotlight-bar-fill ${getProgressClass(n.mem_used_pct)}" style="width:${n.mem_used_pct}%;"></div>
              </div>
            </div>

            <div class="metric-row">
              <div class="metric-labels">
                <span>Root Disk (${formatBytes(n.disk)} / ${formatBytes(n.maxdisk)})</span>
                <strong>${n.disk_used_pct}%</strong>
              </div>
              <div class="spotlight-bar-wrap">
                <div class="spotlight-bar-fill ${getProgressClass(n.disk_used_pct)}" style="width:${n.disk_used_pct}%;"></div>
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;padding-top:6px;border-top:1px solid var(--border-color);font-size:11px;">
              <div><span style="color:var(--text-muted)">Load:</span> <strong>${(n.loadavg || []).join(', ')}</strong></div>
              <div><span style="color:var(--text-muted)">IO Delay:</span> <strong>${n.iowait}%</strong></div>
              <div><span style="color:var(--text-muted)">Uptime:</span> <strong>${formatUptime(n.uptime)}</strong></div>
            </div>
          </div>
        </div>
      `).join('')}
    </div>

    <!-- Workloads Filter & Search Toolbar -->
    <div class="filter-bar">
      <div class="filter-group">
        <input type="text" id="workload-search" class="search-input" placeholder="Search VM, Container, Tag, ID..." value="${escapeHtml(AppState.filters.search)}">
      </div>
      <div class="filter-group">
        <select id="filter-node" class="filter-select">
          <option value="all" ${AppState.filters.node === 'all' ? 'selected' : ''}>All Nodes (${nodes.length})</option>
          ${nodes.map(n => `<option value="${n.node}" ${AppState.filters.node === n.node ? 'selected' : ''}>${n.node}</option>`).join('')}
        </select>
        <select id="filter-type" class="filter-select">
          <option value="all" ${AppState.filters.type === 'all' ? 'selected' : ''}>All Types</option>
          <option value="qemu" ${AppState.filters.type === 'qemu' ? 'selected' : ''}>QEMU VMs Only</option>
          <option value="lxc" ${AppState.filters.type === 'lxc' ? 'selected' : ''}>LXC Containers Only</option>
        </select>
        <select id="filter-status" class="filter-select">
          <option value="all" ${AppState.filters.status === 'all' ? 'selected' : ''}>All Status</option>
          <option value="running" ${AppState.filters.status === 'running' ? 'selected' : ''}>Running Only</option>
          <option value="stopped" ${AppState.filters.status === 'stopped' ? 'selected' : ''}>Stopped Only</option>
        </select>
      </div>
    </div>

    <!-- Complete Workloads Grid -->
    <div class="spot-table-container" style="margin-bottom:20px;">
      <div class="panel-header">
        <h3><i class="lucide-layers"></i> Virtual Machines & LXC Containers Inventory</h3>
        <span>Showing ${filteredVms.length} of ${vms.length} Workloads</span>
      </div>
      <div class="spot-table-scroll">
        <table class="spot-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Type</th>
              <th>Node</th>
              <th>Status</th>
              <th>vCPUs</th>
              <th>CPU %</th>
              <th>Memory Used / Max</th>
              <th>Memory %</th>
              <th>Disk Size</th>
              <th>Net In / Out</th>
              <th>Uptime</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            ${filteredVms.map(v => `
              <tr onclick="openGuestDetailModal(${v.vmid})">
                <td><strong>${v.vmid}</strong></td>
                <td><strong>${escapeHtml(v.name)}</strong></td>
                <td><span class="type-pill ${v.type}">${v.type}</span></td>
                <td>${escapeHtml(v.node)}</td>
                <td><span class="status-pill ${v.status}">${v.status}</span></td>
                <td>${v.cpus || 1}</td>
                <td>
                  <div style="display:flex;align-items:center;gap:6px;">
                    <span style="color:${getGaugeColor(v.cpu)};font-weight:700;">${v.cpu}%</span>
                    <div class="spotlight-bar-wrap" style="width:40px;margin-top:0;">
                      <div class="spotlight-bar-fill ${getProgressClass(v.cpu)}" style="width:${v.cpu}%;"></div>
                    </div>
                  </div>
                </td>
                <td>${formatBytes(v.mem)} / ${formatBytes(v.maxmem)}</td>
                <td>
                  <div style="display:flex;align-items:center;gap:6px;">
                    <span>${v.mem_pct}%</span>
                    <div class="spotlight-bar-wrap" style="width:40px;margin-top:0;">
                      <div class="spotlight-bar-fill ${getProgressClass(v.mem_pct)}" style="width:${v.mem_pct}%;"></div>
                    </div>
                  </div>
                </td>
                <td>${formatBytes(v.maxdisk)}</td>
                <td style="font-size:11px;color:var(--text-secondary)">${formatBytes(v.netin)} / ${formatBytes(v.netout)}</td>
                <td>${formatUptime(v.uptime)}</td>
                <td>
                  ${(v.tags || '').split(';').filter(Boolean).map(t => `<span style="background:#1f2838;color:#79c0ff;padding:1px 4px;border-radius:2px;font-size:9px;margin-right:2px;">${escapeHtml(t)}</span>`).join('')}
                </td>
              </tr>
            `).join('')}
            ${filteredVms.length === 0 ? '<tr><td colspan="13" style="text-align:center;padding:18px;color:var(--text-muted)">No matching workloads found for current filters</td></tr>' : ''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function attachTechnicalEventListeners() {
  const searchInput = document.getElementById('workload-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      AppState.filters.search = e.target.value;
      renderCurrentView();
    });
  }

  const nodeSelect = document.getElementById('filter-node');
  if (nodeSelect) {
    nodeSelect.addEventListener('change', (e) => {
      AppState.filters.node = e.target.value;
      renderCurrentView();
    });
  }

  const typeSelect = document.getElementById('filter-type');
  if (typeSelect) {
    typeSelect.addEventListener('change', (e) => {
      AppState.filters.type = e.target.value;
      renderCurrentView();
    });
  }

  const statusSelect = document.getElementById('filter-status');
  if (statusSelect) {
    statusSelect.addEventListener('change', (e) => {
      AppState.filters.status = e.target.value;
      renderCurrentView();
    });
  }
}

// --- View 3: Alarms & Cluster Tasks View ---

function getAlarmsAndLogsViewHtml() {
  const alarms = AppState.data.alarms || [];
  const tasks = AppState.data.tasks || [];

  return `
    <div class="dashboard-row">
      <!-- Active Alarms Panel -->
      <div class="spot-table-container">
        <div class="panel-header">
          <h3><i class="lucide-alert-triangle"></i> Spotlight Active Alarms (${alarms.length})</h3>
          <span>Diagnostic Issues</span>
        </div>
        <div class="spot-table-scroll">
          <table class="spot-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Component</th>
                <th>Target</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              ${alarms.map(a => `
                <tr>
                  <td><span class="alarm-badge ${a.severity.toLowerCase()}" style="padding:2px 6px;">${a.severity}</span></td>
                  <td><strong>${escapeHtml(a.component)}</strong></td>
                  <td>${escapeHtml(a.target)}</td>
                  <td style="color:var(--text-bright);">${escapeHtml(a.msg)}</td>
                </tr>
              `).join('')}
              ${alarms.length === 0 ? '<tr><td colspan="4" style="text-align:center;color:var(--alarm-normal);padding:18px;">✅ All systems normal. No active alarms.</td></tr>' : ''}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Cluster Tasks & Audit Log -->
      <div class="spot-table-container">
        <div class="panel-header">
          <h3><i class="lucide-list"></i> Recent Cluster Tasks & Audit Log</h3>
          <span>Last Proxmox Operations</span>
        </div>
        <div class="spot-table-scroll">
          <table class="spot-table">
            <thead>
              <tr>
                <th>Action Type</th>
                <th>Node</th>
                <th>User</th>
                <th>Target</th>
                <th>Status</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              ${tasks.map(t => `
                <tr>
                  <td><span class="type-pill" style="background:#1e293b;color:#38bdf8;">${escapeHtml(t.type)}</span></td>
                  <td>${escapeHtml(t.node)}</td>
                  <td style="font-size:11px;color:var(--text-muted)">${escapeHtml(t.user)}</td>
                  <td><strong>#${escapeHtml(t.id)}</strong></td>
                  <td><span class="status-pill ${t.status === 'OK' ? 'ok' : 'running'}">${escapeHtml(t.status)}</span></td>
                  <td style="font-size:11px;">${escapeHtml(t.description || t.upid)}</td>
                </tr>
              `).join('')}
              ${tasks.length === 0 ? '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:18px;">No recent task logs available</td></tr>' : ''}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

// --- Guest Drilldown Modal ---

function openGuestDetailModal(vmid) {
  if (!AppState.data || !AppState.data.vms) return;
  const guest = AppState.data.vms.find(v => v.vmid === vmid);
  if (!guest) return;

  const modal = document.getElementById('guest-modal');
  const title = document.getElementById('modal-guest-title');
  const body = document.getElementById('modal-guest-body');

  title.innerHTML = `<span class="type-pill ${guest.type}">${guest.type}</span> ${escapeHtml(guest.name)} (#${guest.vmid})`;
  
  body.innerHTML = `
    <div class="detail-grid">
      <div class="detail-box">
        <div class="detail-label">Status</div>
        <div class="detail-val"><span class="status-pill ${guest.status}">${guest.status}</span></div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Assigned Node</div>
        <div class="detail-val">${escapeHtml(guest.node)}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">vCPUs Allocated</div>
        <div class="detail-val">${guest.cpus || 1} Cores (${guest.cpu}% usage)</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Memory (RAM)</div>
        <div class="detail-val">${formatBytes(guest.mem)} / ${formatBytes(guest.maxmem)} (${guest.mem_pct}%)</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Disk Storage Allocated</div>
        <div class="detail-val">${formatBytes(guest.maxdisk)}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Uptime</div>
        <div class="detail-val">${formatUptime(guest.uptime)}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Network Throughput (In / Out)</div>
        <div class="detail-val">${formatBytes(guest.netin)} / ${formatBytes(guest.netout)}</div>
      </div>
      <div class="detail-box">
        <div class="detail-label">Disk I/O (Read / Write)</div>
        <div class="detail-val">${formatBytes(guest.diskread || 0)} / ${formatBytes(guest.diskwrite || 0)}</div>
      </div>
    </div>

    <div style="background:var(--bg-subtle);border:1px solid var(--border-color);padding:12px;border-radius:4px;">
      <div style="font-size:11px;font-weight:700;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;">Tags & Metadata</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        ${(guest.tags || 'none').split(';').map(t => `<span style="background:#202a3a;color:#00f0ff;padding:3px 8px;border-radius:4px;font-size:11px;border:1px solid #2d3e56;">${escapeHtml(t)}</span>`).join('')}
      </div>
    </div>
  `;

  modal.classList.add('active');
}

function closeGuestDetailModal() {
  const modal = document.getElementById('guest-modal');
  if (modal) modal.classList.remove('active');
}

// =========================================================================
// ⚙️ CONFIGURATION MODAL CONTROLLER
// =========================================================================

async function openConfigModal() {
  const modal = document.getElementById('config-modal');
  const alertBox = document.getElementById('config-feedback-alert');
  if (alertBox) alertBox.style.display = 'none';

  try {
    const res = await fetch('/api/config');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const cfg = await res.json();

    // Populate values
    const hostInput = document.getElementById('cfg-host');
    if (hostInput) hostInput.value = cfg.pve_host || '';

    const userInput = document.getElementById('cfg-user');
    if (userInput) userInput.value = cfg.pve_user || '';

    const tokenNameInput = document.getElementById('cfg-token-name');
    if (tokenNameInput) tokenNameInput.value = cfg.token_name || 'spotlight';

    const tokenValInput = document.getElementById('cfg-token-value');
    const tokenHint = document.getElementById('token-status-hint');
    if (tokenValInput) {
      tokenValInput.value = '';
      if (cfg.has_token_value) {
        tokenValInput.placeholder = `Guardado: ${cfg.token_value_masked || '••••••••'}`;
        if (tokenHint) {
          tokenHint.innerHTML = `<span style="color:#00e676;">✓ Token UUID guardado (${cfg.token_value_masked}). Déjalo en blanco para mantenerlo o escribe uno nuevo para cambiarlo.</span>`;
        }
      } else {
        tokenValInput.placeholder = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx';
        if (tokenHint) {
          tokenHint.innerHTML = `UUID generado en Datacenter -> Permissions -> API Tokens.`;
        }
      }
    }

    const pwdInput = document.getElementById('cfg-password');
    const pwdHint = document.getElementById('password-status-hint');
    if (pwdInput) {
      pwdInput.value = '';
      if (cfg.has_password) {
        pwdInput.placeholder = '•••••••••••• (Guardada)';
        if (pwdHint) {
          pwdHint.innerHTML = `<span style="color:#00e676;">✓ Contraseña guardada. Déjala en blanco para mantenerla o escribe una nueva para cambiarla.</span>`;
        }
      } else {
        pwdInput.placeholder = '••••••••••••';
        if (pwdHint) {
          pwdHint.innerHTML = `Contraseña del usuario en Proxmox VE.`;
        }
      }
    }

    const sslCb = document.getElementById('cfg-verify-ssl');
    if (sslCb) sslCb.checked = !!cfg.verify_ssl;

    const demoCb = document.getElementById('cfg-demo-mode');
    if (demoCb) demoCb.checked = !!cfg.demo_mode;

    const fallbackCb = document.getElementById('cfg-fallback-demo');
    if (fallbackCb) fallbackCb.checked = !!cfg.fallback_to_demo;

    const timeoutInput = document.getElementById('cfg-timeout');
    if (timeoutInput) timeoutInput.value = cfg.timeout || 6.0;

    // Email alert settings
    const emailAlertCb = document.getElementById('cfg-alert-email-enabled');
    if (emailAlertCb) emailAlertCb.checked = !!cfg.alert_email_enabled;

    const emailToInput = document.getElementById('cfg-alert-email-to');
    if (emailToInput) emailToInput.value = cfg.alert_email_to || '';

    const smtpUserInput = document.getElementById('cfg-smtp-user');
    if (smtpUserInput) smtpUserInput.value = cfg.smtp_user || 'apps.monitor.lnx@gmail.com';

    const smtpPwdInput = document.getElementById('cfg-smtp-password');
    if (smtpPwdInput) {
      smtpPwdInput.value = '';
      if (cfg.has_smtp_password) {
        smtpPwdInput.placeholder = '•••••••••••• (Guardada)';
      } else {
        smtpPwdInput.placeholder = '••••••••••••';
      }
    }

    const smtpHostInput = document.getElementById('cfg-smtp-host');
    if (smtpHostInput) smtpHostInput.value = cfg.smtp_host || 'smtp.gmail.com';

    const smtpPortInput = document.getElementById('cfg-smtp-port');
    if (smtpPortInput) smtpPortInput.value = cfg.smtp_port || 587;

    const cooldownInput = document.getElementById('cfg-alert-cooldown');
    if (cooldownInput) cooldownInput.value = cfg.alert_cooldown_minutes || 30;

    updateEmailAlertFields();

    // Auth type radio
    if (cfg.auth_type === 'password') {
      const radioPwd = document.getElementById('auth-type-password');
      if (radioPwd) radioPwd.checked = true;
    } else {
      const radioToken = document.getElementById('auth-type-token');
      if (radioToken) radioToken.checked = true;
    }
    updateAuthTypeFields();

  } catch (err) {
    console.error('Error loading config:', err);
  }

  if (modal) modal.classList.add('active');
}

function closeConfigModal() {
  const modal = document.getElementById('config-modal');
  if (modal) modal.classList.remove('active');
}

function updateEmailAlertFields() {
  const isEnabled = document.getElementById('cfg-alert-email-enabled')?.checked;
  const container = document.getElementById('email-alert-fields');
  if (container) {
    container.style.display = isEnabled ? 'block' : 'none';
  }
}

function updateAuthTypeFields() {
  const isToken = document.getElementById('auth-type-token')?.checked;
  const tokenGroup = document.getElementById('token-fields-group');
  const pwdGroup = document.getElementById('password-fields-group');

  if (tokenGroup) tokenGroup.style.display = isToken ? 'block' : 'none';
  if (pwdGroup) pwdGroup.style.display = isToken ? 'none' : 'block';
}

function getFormData() {
  const authType = document.querySelector('input[name="AUTH_TYPE"]:checked')?.value || 'token';
  return {
    PVE_HOST: document.getElementById('cfg-host')?.value.trim() || '',
    AUTH_TYPE: authType,
    PVE_USER: document.getElementById('cfg-user')?.value.trim() || '',
    PVE_TOKEN_NAME: document.getElementById('cfg-token-name')?.value.trim() || 'spotlight',
    PVE_TOKEN_VALUE: document.getElementById('cfg-token-value')?.value.trim() || '',
    PVE_PASSWORD: document.getElementById('cfg-password')?.value.trim() || '',
    PVE_VERIFY_SSL: document.getElementById('cfg-verify-ssl')?.checked || false,
    DEMO_MODE: document.getElementById('cfg-demo-mode')?.checked || false,
    FALLBACK_TO_DEMO: document.getElementById('cfg-fallback-demo')?.checked || false,
    PVE_TIMEOUT: parseFloat(document.getElementById('cfg-timeout')?.value) || 6.0,

    // Email alert settings
    ALERT_EMAIL_ENABLED: document.getElementById('cfg-alert-email-enabled')?.checked || false,
    ALERT_EMAIL_TO: document.getElementById('cfg-alert-email-to')?.value.trim() || '',
    SMTP_USER: document.getElementById('cfg-smtp-user')?.value.trim() || 'apps.monitor.lnx@gmail.com',
    SMTP_PASSWORD: document.getElementById('cfg-smtp-password')?.value.trim() || '',
    SMTP_HOST: document.getElementById('cfg-smtp-host')?.value.trim() || 'smtp.gmail.com',
    SMTP_PORT: parseInt(document.getElementById('cfg-smtp-port')?.value, 10) || 587,
    ALERT_COOLDOWN_MINUTES: parseInt(document.getElementById('cfg-alert-cooldown')?.value, 10) || 30
  };
}

async function testEmailAlert() {
  const btn = document.getElementById('btn-test-email');
  const icon = document.getElementById('test-email-icon');
  const statusSpan = document.getElementById('test-email-status');
  const emailTo = document.getElementById('cfg-alert-email-to')?.value.trim();

  if (!emailTo) {
    if (statusSpan) {
      statusSpan.style.color = '#ef4444';
      statusSpan.textContent = '❌ Ingresa un correo de destino para la prueba.';
    }
    return;
  }

  if (btn) btn.disabled = true;
  if (icon) icon.className = 'lucide-loader-2 spin';
  if (statusSpan) {
    statusSpan.style.color = 'var(--text-secondary)';
    statusSpan.textContent = 'Enviando correo de prueba vía Gmail...';
  }

  const payload = {
    email_to: emailTo,
    smtp_user: document.getElementById('cfg-smtp-user')?.value.trim() || 'apps.monitor.lnx@gmail.com',
    smtp_password: document.getElementById('cfg-smtp-password')?.value.trim() || '',
    smtp_host: document.getElementById('cfg-smtp-host')?.value.trim() || 'smtp.gmail.com',
    smtp_port: parseInt(document.getElementById('cfg-smtp-port')?.value, 10) || 587
  };

  try {
    const res = await fetch('/api/alerts/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    if (result.success) {
      if (statusSpan) {
        statusSpan.style.color = '#10b981';
        statusSpan.textContent = `✓ ${result.message}`;
      }
    } else {
      if (statusSpan) {
        statusSpan.style.color = '#ef4444';
        statusSpan.textContent = `❌ ${result.message}`;
      }
    }
  } catch (err) {
    if (statusSpan) {
      statusSpan.style.color = '#ef4444';
      statusSpan.textContent = `❌ Error: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
    if (icon) icon.className = 'lucide-send';
  }
}

async function testConfigConnection() {
  const alertBox = document.getElementById('config-feedback-alert');
  const btn = document.getElementById('btn-test-connection');
  const icon = document.getElementById('test-conn-icon');
  
  if (alertBox) alertBox.style.display = 'none';
  if (btn) btn.disabled = true;
  if (icon) icon.classList.add('spin');

  const payload = getFormData();

  try {
    const resp = await fetch('/api/troubleshoot/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await resp.json();

    if (alertBox) {
      alertBox.style.display = 'flex';
      if (result.success) {
        alertBox.className = 'config-feedback success';
        alertBox.innerHTML = `
          <i class="lucide-check-circle" style="font-size:18px;"></i>
          <div>
            <strong>¡Conexión Exitosa con Proxmox VE!</strong>
            <div>${escapeHtml(result.message)} (Latencia: ${result.latency_ms} ms)</div>
          </div>
        `;
      } else {
        alertBox.className = 'config-feedback error';
        alertBox.innerHTML = `
          <i class="lucide-alert-circle" style="font-size:18px;"></i>
          <div>
            <strong>Error de Conexión:</strong>
            <div>${escapeHtml(result.message)}</div>
          </div>
        `;
      }
    }
  } catch (err) {
    if (alertBox) {
      alertBox.style.display = 'flex';
      alertBox.className = 'config-feedback error';
      alertBox.innerHTML = `<strong>Error inesperado:</strong> ${escapeHtml(err.message)}`;
    }
  } finally {
    if (btn) btn.disabled = false;
    if (icon) icon.classList.remove('spin');
  }
}

async function saveConfig() {
  const alertBox = document.getElementById('config-feedback-alert');
  const btn = document.getElementById('btn-save-config');
  const payload = getFormData();

  if (!payload.PVE_HOST) {
    if (alertBox) {
      alertBox.style.display = 'flex';
      alertBox.className = 'config-feedback error';
      alertBox.textContent = 'Por favor ingresa la URL o IP de tu servidor Proxmox VE.';
    }
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="lucide-loader-2 spin"></i> Guardando...`;
  }

  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await resp.json();

    if (alertBox) {
      alertBox.style.display = 'flex';
      if (result.success) {
        alertBox.className = 'config-feedback success';
        alertBox.innerHTML = `<strong>¡Configuración Guardada!</strong> Aplicando cambios y recargando telemetría...`;
        setTimeout(() => {
          closeConfigModal();
          fetchDashboardData(true);
        }, 1200);
      } else {
        alertBox.className = 'config-feedback error';
        alertBox.innerHTML = `<strong>Fallo al guardar:</strong> ${escapeHtml(result.message)}`;
      }
    }
  } catch (err) {
    if (alertBox) {
      alertBox.style.display = 'flex';
      alertBox.className = 'config-feedback error';
      alertBox.innerHTML = `<strong>Error:</strong> ${escapeHtml(err.message)}`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="lucide-save"></i> Guardar y Aplicar`;
    }
  }
}

// =========================================================================
// 🩺 TROUBLESHOOTING MODAL & SRE DIAGNOSTICS CONTROLLER
// =========================================================================

function openTroubleshootModal() {
  const modal = document.getElementById('troubleshoot-modal');
  const hostLabel = document.getElementById('tb-target-host');
  const userLabel = document.getElementById('tb-target-user');

  if (AppState.data?.connection_status) {
    const cs = AppState.data.connection_status;
    if (hostLabel) hostLabel.textContent = cs.host || '-';
    if (userLabel) userLabel.textContent = cs.user || '-';
  }

  // Set active tab to audit
  switchTroubleshootTab('tb-audit');

  if (modal) modal.classList.add('active');

  // Auto-run full diagnostics on open
  runFullDiagnostics();
}

function closeTroubleshootModal() {
  const modal = document.getElementById('troubleshoot-modal');
  if (modal) modal.classList.remove('active');
}

function switchTroubleshootTab(tabId) {
  document.querySelectorAll('.tb-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });
  document.querySelectorAll('.tb-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `${tabId}-tab`);
  });

  if (tabId === 'tb-logs') {
    fetchLogs();
  }
}

async function runFullDiagnostics() {
  const btn = document.getElementById('btn-run-full-diagnostics');
  const icon = document.getElementById('diag-run-icon');
  const stagesContainer = document.getElementById('tb-stages-container');
  const summaryBox = document.getElementById('tb-summary-cards');
  const remediationAlert = document.getElementById('tb-remediation-alert');

  if (btn) btn.disabled = true;
  if (icon) icon.classList.add('spin');
  if (remediationAlert) remediationAlert.style.display = 'none';

  if (stagesContainer) {
    stagesContainer.innerHTML = `
      <div style="text-align:center;padding:40px;color:var(--text-secondary);">
        <i class="lucide-loader-2 spin" style="font-size:32px;color:var(--spotlight-cyan);"></i>
        <div style="margin-top:12px;font-size:13px;">Ejecutando auditoría de las 6 capas de integración con Proxmox VE...</div>
      </div>
    `;
  }

  try {
    const resp = await fetch('/api/troubleshoot/diagnose', { method: 'POST' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    // Render Summary Badges
    if (summaryBox) {
      summaryBox.style.display = 'flex';
      document.getElementById('tb-stat-passed').innerHTML = `Pasadas: <strong>${data.summary.passed}</strong>`;
      document.getElementById('tb-stat-warn').innerHTML = `Advertencias: <strong>${data.summary.warnings}</strong>`;
      document.getElementById('tb-stat-failed').innerHTML = `Fallos: <strong>${data.summary.failed}</strong>`;
    }

    // Render Remediation Box if errors or warnings exist
    if (data.remediations && data.remediations.length > 0 && remediationAlert) {
      remediationAlert.style.display = 'block';
      remediationAlert.innerHTML = `
        <h4><i class="lucide-alert-triangle"></i> Acciones Correctivas Detectadas (${data.remediations.length}):</h4>
        ${data.remediations.map(r => `
          <div class="tb-rem-item">
            <div><strong>${escapeHtml(r.title)}:</strong> ${escapeHtml(r.description)}</div>
            ${r.command ? `<pre class="cli-block" style="margin-top:4px;"><code>${escapeHtml(r.command)}</code></pre>` : ''}
          </div>
        `).join('')}
      `;
    }

    // Render Stages
    if (stagesContainer) {
      stagesContainer.innerHTML = data.stages.map(s => {
        const badgeClass = s.status;
        const badgeLabel = s.status === 'pass' ? 'PASÓ' : s.status === 'warn' ? 'AVISO' : s.status === 'fail' ? 'FALLÓ' : 'OMITIDO';
        return `
          <div class="tb-stage-card ${s.status}">
            <div class="tb-stage-header">
              <div class="tb-stage-title">
                <i class="lucide-${s.icon || 'activity'}"></i>
                ${escapeHtml(s.title)}
              </div>
              <span class="tb-stage-badge ${badgeClass}">${badgeLabel}</span>
            </div>
            <div class="tb-stage-body">
              ${s.items.map(item => `
                <div class="tb-stage-item ${item.status}">
                  <i class="lucide-${item.status === 'pass' ? 'check-circle' : item.status === 'warn' ? 'alert-triangle' : item.status === 'fail' ? 'x-circle' : 'minus-circle'}"></i>
                  <div>
                    <strong>${escapeHtml(item.label)}:</strong> ${escapeHtml(item.text)}
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }).join('');
    }

  } catch (err) {
    if (stagesContainer) {
      stagesContainer.innerHTML = `
        <div class="tb-stage-card fail">
          <div class="tb-stage-header">
            <div class="tb-stage-title">Fallo en la prueba de diagnóstico</div>
            <span class="tb-stage-badge fail">ERROR</span>
          </div>
          <div class="tb-stage-body">
            <div class="tb-stage-item fail">
              <i class="lucide-alert-circle"></i>
              <div>${escapeHtml(err.message)}</div>
            </div>
          </div>
        </div>
      `;
    }
  } finally {
    if (btn) btn.disabled = false;
    if (icon) icon.classList.remove('spin');
  }
}

// --- Logs Viewer ---

async function fetchLogs() {
  const consoleBox = document.getElementById('logs-console-box');
  const levelFilter = document.getElementById('log-level-filter')?.value || '';
  const refreshBtn = document.getElementById('btn-refresh-logs');

  if (refreshBtn) refreshBtn.classList.add('spin');

  try {
    const url = levelFilter ? `/api/troubleshoot/logs?level=${encodeURIComponent(levelFilter)}` : '/api/troubleshoot/logs';
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (consoleBox) {
      if (!data.logs || data.logs.length === 0) {
        consoleBox.innerHTML = `<div class="log-entry log-info">[INFO] No hay registros en el búfer para el nivel seleccionado.</div>`;
      } else {
        consoleBox.innerHTML = data.logs.map(l => {
          const cls = l.level === 'ERROR' ? 'log-error' : l.level === 'WARNING' ? 'log-warn' : 'log-info';
          return `<div class="log-entry ${cls}">${escapeHtml(l.timestamp)} [${escapeHtml(l.level)}] ${escapeHtml(l.name)}: ${escapeHtml(l.message)}${l.traceback ? '\n' + escapeHtml(l.traceback) : ''}</div>`;
        }).join('');
        consoleBox.scrollTop = consoleBox.scrollHeight;
      }
    }
  } catch (err) {
    if (consoleBox) {
      consoleBox.innerHTML = `<div class="log-entry log-error">[ERROR] No se pudieron obtener los logs: ${escapeHtml(err.message)}</div>`;
    }
  } finally {
    if (refreshBtn) refreshBtn.classList.remove('spin');
  }
}

async function clearLogs() {
  try {
    await fetch('/api/troubleshoot/logs/clear', { method: 'POST' });
    const consoleBox = document.getElementById('logs-console-box');
    if (consoleBox) consoleBox.innerHTML = `<div class="log-entry log-info">[INFO] Búfer de logs limpiado.</div>`;
  } catch (err) {
    console.error('Error clearing logs:', err);
  }
}

function copyLogs() {
  const consoleBox = document.getElementById('logs-console-box');
  const btn = document.getElementById('btn-copy-logs');
  if (!consoleBox) return;

  const text = consoleBox.innerText;
  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = `<i class="lucide-check"></i> ¡Copiado!`;
      setTimeout(() => { btn.innerHTML = orig; }, 1500);
    }
  });
}

// --- App Initialization & Event Listeners ---

document.addEventListener('DOMContentLoaded', () => {
  // Navigation Tabs
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      const targetView = btn.dataset.view;
      btn.classList.add('active');
      AppState.currentView = targetView;
      renderCurrentView();
    });
  });

  // Manual Refresh Button
  const refreshBtn = document.getElementById('manual-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => fetchDashboardData(true));
  }

  // Refresh Interval Select
  const refreshIntervalSelect = document.getElementById('refresh-interval-select');
  if (refreshIntervalSelect) {
    refreshIntervalSelect.addEventListener('change', (e) => {
      const val = parseInt(e.target.value, 10);
      AppState.refreshInterval = val;
      if (AppState.timerId) clearInterval(AppState.timerId);
      if (val > 0) {
        AppState.timerId = setInterval(() => fetchDashboardData(false), val);
      }
    });
  }

  // Guest Detail Modal Close
  const modalCloseBtn = document.getElementById('modal-close-btn');
  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeGuestDetailModal);
  
  const modalOverlay = document.getElementById('guest-modal');
  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeGuestDetailModal();
    });
  }

  // --- Configuration Modal Listeners ---
  const btnOpenConfig = document.getElementById('btn-open-config');
  if (btnOpenConfig) btnOpenConfig.addEventListener('click', openConfigModal);

  const btnBannerConfig = document.getElementById('banner-btn-config');
  if (btnBannerConfig) btnBannerConfig.addEventListener('click', openConfigModal);

  const btnCloseConfig = document.getElementById('config-modal-close-btn');
  if (btnCloseConfig) btnCloseConfig.addEventListener('click', closeConfigModal);

  const btnCancelConfig = document.getElementById('btn-cancel-config');
  if (btnCancelConfig) btnCancelConfig.addEventListener('click', closeConfigModal);

  const cfgModalOverlay = document.getElementById('config-modal');
  if (cfgModalOverlay) {
    cfgModalOverlay.addEventListener('click', (e) => {
      if (e.target === cfgModalOverlay) closeConfigModal();
    });
  }

  const btnTestConn = document.getElementById('btn-test-connection');
  if (btnTestConn) btnTestConn.addEventListener('click', testConfigConnection);

  const btnSaveConfig = document.getElementById('btn-save-config');
  if (btnSaveConfig) btnSaveConfig.addEventListener('click', saveConfig);

  // Email alert listeners
  const alertEmailCb = document.getElementById('cfg-alert-email-enabled');
  if (alertEmailCb) alertEmailCb.addEventListener('change', updateEmailAlertFields);

  const toggleSmtpPwd = document.getElementById('toggle-smtp-pwd');
  if (toggleSmtpPwd) {
    toggleSmtpPwd.addEventListener('click', () => {
      const inp = document.getElementById('cfg-smtp-password');
      if (inp) {
        const isPwd = inp.type === 'password';
        inp.type = isPwd ? 'text' : 'password';
        toggleSmtpPwd.textContent = isPwd ? '🙈' : '👁';
      }
    });
  }

  const btnTestEmail = document.getElementById('btn-test-email');
  if (btnTestEmail) btnTestEmail.addEventListener('click', testEmailAlert);

  // Auth type radio buttons
  document.querySelectorAll('input[name="AUTH_TYPE"]').forEach(r => {
    r.addEventListener('change', updateAuthTypeFields);
  });

  // Password toggle show/hide buttons
  document.querySelectorAll('.toggle-password-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.target;
      const inp = document.getElementById(targetId);
      if (inp) {
        const isPwd = inp.type === 'password';
        inp.type = isPwd ? 'text' : 'password';
        btn.innerHTML = `<i class="lucide-${isPwd ? 'eye-off' : 'eye'}"></i>`;
      }
    });
  });

  // --- Troubleshooting Modal Listeners ---
  const btnOpenTb = document.getElementById('btn-open-troubleshoot');
  if (btnOpenTb) btnOpenTb.addEventListener('click', openTroubleshootModal);

  const btnBannerTb = document.getElementById('banner-btn-troubleshoot');
  if (btnBannerTb) btnBannerTb.addEventListener('click', openTroubleshootModal);

  const btnCloseTb = document.getElementById('troubleshoot-modal-close-btn');
  if (btnCloseTb) btnCloseTb.addEventListener('click', closeTroubleshootModal);

  const tbModalOverlay = document.getElementById('troubleshoot-modal');
  if (tbModalOverlay) {
    tbModalOverlay.addEventListener('click', (e) => {
      if (e.target === tbModalOverlay) closeTroubleshootModal();
    });
  }

  // Troubleshooting Sub-Navigation Tabs
  document.querySelectorAll('.tb-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      switchTroubleshootTab(tab);
    });
  });

  // Run full diagnostics button
  const btnRunDiag = document.getElementById('btn-run-full-diagnostics');
  if (btnRunDiag) btnRunDiag.addEventListener('click', runFullDiagnostics);

  // Copy command buttons
  document.querySelectorAll('.copy-cmd-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const code = btn.dataset.code;
      if (code) {
        navigator.clipboard.writeText(code).then(() => {
          const orig = btn.innerHTML;
          btn.innerHTML = `<i class="lucide-check"></i> ¡Copiado!`;
          setTimeout(() => { btn.innerHTML = orig; }, 1500);
        });
      }
    });
  });

  // Log viewer buttons
  const btnRefreshLogs = document.getElementById('btn-refresh-logs');
  if (btnRefreshLogs) btnRefreshLogs.addEventListener('click', fetchLogs);

  const btnClearLogs = document.getElementById('btn-clear-logs');
  if (btnClearLogs) btnClearLogs.addEventListener('click', clearLogs);

  const btnCopyLogs = document.getElementById('btn-copy-logs');
  if (btnCopyLogs) btnCopyLogs.addEventListener('click', copyLogs);

  const logLevelFilter = document.getElementById('log-level-filter');
  if (logLevelFilter) logLevelFilter.addEventListener('change', fetchLogs);

  // Initial Fetch & Start Polling
  fetchDashboardData(true);
  AppState.timerId = setInterval(() => fetchDashboardData(false), AppState.refreshInterval);
});

