import time
import smtplib
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List, Tuple

from app.config import settings

logger = logging.getLogger("proxmox_dashboard.notifier")

class EmailNotifier:
    """
    SRE Alert & Notification Engine for Proxmox Spotlight Dashboard.
    Manages urgent incident detection, deduplication, cooldown, and Gmail SMTP delivery.
    """

    def __init__(self):
        # Maps alert_key -> timestamp of last notification
        self._sent_alerts: Dict[str, float] = {}
        # Tracks previously active incidents to send recovery notifications
        self._active_incidents: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def _format_html_alert(
        self,
        severity: str,
        title: str,
        description: str,
        details: List[Tuple[str, str]],
        is_recovery: bool = False
    ) -> str:
        color_header = "#10b981" if is_recovery else ("#ef4444" if severity == "CRITICAL" else "#f59e0b")
        badge_text = "RECUPERADO" if is_recovery else severity
        icon = "🟢" if is_recovery else ("🔴" if severity == "CRITICAL" else "🟠")

        details_rows = "".join([
            f"""<tr>
                <td style="padding: 8px 12px; color: #94a3b8; font-weight: 600; border-bottom: 1px solid #2d3748; width: 35%;">{label}</td>
                <td style="padding: 8px 12px; color: #f8fafc; border-bottom: 1px solid #2d3748; font-family: monospace;">{val}</td>
            </tr>"""
            for label, val in details
        ])

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #0e1117; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #161b24; border-radius: 8px; border: 1px solid {color_header}; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
        <div style="background-color: {color_header}; padding: 16px 20px; color: #ffffff;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <h2 style="margin: 0; font-size: 18px; font-weight: bold; letter-spacing: 0.5px;">
                    {icon} SPOTLIGHT ON PROXMOX VE — ALERTA SRE
                </h2>
            </div>
        </div>
        <div style="padding: 24px;">
            <div style="display: inline-block; background-color: rgba(255,255,255,0.1); border: 1px solid {color_header}; border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: bold; color: {color_header}; margin-bottom: 15px;">
                {badge_text}
            </div>
            <h3 style="margin: 0 0 12px 0; font-size: 20px; color: #ffffff;">{title}</h3>
            <p style="margin: 0 0 20px 0; color: #cbd5e1; font-size: 14px; line-height: 1.5;">{description}</p>
            
            <table style="width: 100%; border-collapse: collapse; background-color: #0d1117; border-radius: 6px; overflow: hidden; margin-bottom: 24px; font-size: 13px;">
                <tbody>
                    {details_rows}
                </tbody>
            </table>

            <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #2d3748;">
                <p style="font-size: 12px; color: #64748b; margin: 0 0 8px 0;">Esta notificación fue enviada automáticamente por el monitor Spotlight on Proxmox VE.</p>
                <p style="font-size: 11px; color: #475569; margin: 0;">Emisor: {settings.SMTP_USER}</p>
            </div>
        </div>
    </div>
</body>
</html>"""

    def send_smtp_email_sync(
        self,
        subject: str,
        html_body: str,
        to_email: Optional[str] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Synchronous SMTP sender method intended to run inside threadpool."""
        recipient = to_email or settings.ALERT_EMAIL_TO
        user = smtp_user or settings.SMTP_USER
        password = smtp_password or settings.SMTP_PASSWORD
        host = smtp_host or settings.SMTP_HOST
        port = smtp_port or settings.SMTP_PORT

        if not recipient or not recipient.strip():
            return False, "No se ha configurado una dirección de correo de destino (ALERT_EMAIL_TO)."
        if not user or not user.strip():
            return False, "No se ha configurado la cuenta emisora de Gmail (SMTP_USER)."
        if not password or not password.strip():
            return False, "No se ha configurado la contraseña de aplicación de Gmail (SMTP_PASSWORD)."

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Spotlight Proxmox <{user}>"
        msg["To"] = recipient
        msg["Date"] = time.strftime("%a, %d %b %Y %H:%M:%S %z")

        part = MIMEText(html_body, "html", "utf-8")
        msg.attach(part)

        try:
            logger.info(f"Connecting to SMTP server {host}:{port} via user {user}...")
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=12)
                server.login(user, password)
            else:
                server = smtplib.SMTP(host, port, timeout=12)
                server.ehlo()
                if server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
                server.login(user, password)

            server.sendmail(user, [recipient], msg.as_string())
            server.quit()
            logger.info(f"Alert email successfully delivered to {recipient}: {subject}")
            return True, f"Correo enviado exitosamente a {recipient}"
        except smtplib.SMTPAuthenticationError as e:
            err_msg = f"Fallo de autenticación SMTP con Gmail: {e.smtp_error.decode('utf-8', errors='ignore') if hasattr(e, 'smtp_error') else str(e)}"
            logger.error(err_msg)
            return False, f"{err_msg}. Asegúrate de usar una 'Contraseña de Aplicación' de 16 letras de Google, no tu clave habitual."
        except Exception as e:
            err_msg = f"Error al enviar correo vía SMTP ({host}:{port}): {str(e)}"
            logger.error(err_msg)
            return False, err_msg

    async def send_email(
        self,
        subject: str,
        html_body: str,
        to_email: Optional[str] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Asynchronous wrapper for SMTP sending."""
        return await asyncio.to_thread(
            self.send_smtp_email_sync,
            subject,
            html_body,
            to_email,
            smtp_user,
            smtp_password,
            smtp_host,
            smtp_port
        )

    async def send_test_email(
        self,
        to_email: str,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Sends an immediate verification test email."""
        subject = "🧪 [Spotlight on Proxmox] Prueba de Configuración de Alertas Exitosa"
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        details = [
            ("Estado", "Prueba de Conectividad Exitosa"),
            ("Cuenta Emisora", smtp_user or settings.SMTP_USER),
            ("Servidor SMTP", f"{smtp_host or settings.SMTP_HOST}:{smtp_port or settings.SMTP_PORT}"),
            ("Servidor Proxmox", settings.PVE_HOST),
            ("Fecha y Hora", now_str),
            ("Intervalo Cooldown", f"{settings.ALERT_COOLDOWN_MINUTES} minutos")
        ]
        body = self._format_html_alert(
            severity="NORMAL",
            title="Prueba de Notificación de Alertas por Correo",
            description="¡Excelente! El sistema de alertas por correo electrónico de Spotlight on Proxmox VE está correctamente configurado y listo para notificar incidencias críticas del clúster.",
            details=details,
            is_recovery=True
        )
        return await self.send_email(
            subject=subject,
            html_body=body,
            to_email=to_email,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            smtp_host=smtp_host,
            smtp_port=smtp_port
        )

    async def evaluate_and_alert(self, dashboard_data: Dict[str, Any]):
        """
        Analyzes live cluster telemetry for urgent errors and dispatches notifications
        with strict rate-limiting / deduplication.
        """
        if not settings.ALERT_EMAIL_ENABLED:
            return

        if not settings.ALERT_EMAIL_TO or not settings.ALERT_EMAIL_TO.strip():
            return

        now = time.time()
        cooldown_sec = max(300, settings.ALERT_COOLDOWN_MINUTES * 60)
        current_incidents: Dict[str, Dict[str, Any]] = {}

        conn = dashboard_data.get("connection_status", {})
        cluster = dashboard_data.get("cluster", {})
        nodes = dashboard_data.get("nodes", [])
        storages = dashboard_data.get("storages", [])
        vms = dashboard_data.get("vms", [])
        alarms = dashboard_data.get("alarms", [])
        health_score = cluster.get("health_score", 100)

        # 1. Check: Proxmox Connection Offline
        if not conn.get("connected") and not conn.get("unconfigured") and not conn.get("is_demo"):
            key = "proxmox_unreachable"
            current_incidents[key] = {
                "severity": "CRITICAL",
                "title": f"🚨 Servidor Proxmox VE Desconectado ({settings.PVE_HOST})",
                "description": f"El servicio de monitoreo Spotlight no pudo comunicarse con el host Proxmox VE. Detalle: {conn.get('message', 'Sin respuesta de red o API')}",
                "details": [
                    ("Host Afectado", settings.PVE_HOST),
                    ("Error Detectado", str(conn.get("error") or conn.get("message"))),
                    ("Usuario", settings.PVE_USER),
                    ("Fecha y Hora", time.strftime("%Y-%m-%d %H:%M:%S"))
                ]
            }

        # 2. Check: Physical Nodes Offline
        for n in nodes:
            node_name = n.get("node", "desconocido")
            if n.get("status") != "online":
                key = f"node_offline:{node_name}"
                current_incidents[key] = {
                    "severity": "CRITICAL",
                    "title": f"🚨 Nodo Proxmox Caído: {node_name}",
                    "description": f"El nodo físico '{node_name}' ha pasado a estado OFFLINE. Las cargas de trabajo asociadas podrían estar no disponibles o requieren migración HA.",
                    "details": [
                        ("Nodo Caído", node_name),
                        ("Clúster", cluster.get("name", "Proxmox Cluster")),
                        ("Estado Reportado", str(n.get("status"))),
                        ("Fecha y Hora", time.strftime("%Y-%m-%d %H:%M:%S"))
                    ]
                }

        # 3. Check: Critical Storage Saturation (> 95%)
        for s in storages:
            s_name = s.get("storage", "pool")
            s_pct = s.get("used_pct", 0)
            if s_pct >= 95.0:
                key = f"storage_critical:{s_name}"
                current_incidents[key] = {
                    "severity": "CRITICAL",
                    "title": f"🚨 Almacenamiento Saturado Crítico ({s_pct}%): {s_name}",
                    "description": f"El pool de almacenamiento '{s_name}' ha alcanzado el {s_pct}% de ocupación. Esto puede provocar pausas (freeze) en máquinas virtuales por falta de espacio para snapshots o discos temporales.",
                    "details": [
                        ("Pool Afectado", s_name),
                        ("Ocupación Actual", f"{s_pct}%"),
                        ("Espacio Usado", f"{round(s.get('used', 0) / (1024**3), 2)} GB"),
                        ("Espacio Total", f"{round(s.get('total', 0) / (1024**3), 2)} GB"),
                        ("Fecha y Hora", time.strftime("%Y-%m-%d %H:%M:%S"))
                    ]
                }

        # 4. Check: Critical Physical CPU Saturation (> 95%)
        for n in nodes:
            node_name = n.get("node", "nodo")
            cpu_pct = n.get("cpu", 0)
            if cpu_pct >= 95.0:
                key = f"node_cpu_critical:{node_name}"
                current_incidents[key] = {
                    "severity": "HIGH",
                    "title": f"⚠️ Saturación Extrema de CPU ({cpu_pct}%): {node_name}",
                    "description": f"El procesador del nodo físico '{node_name}' está al {cpu_pct}%, lo que puede provocar latencias críticas en las máquinas virtuales invitadas.",
                    "details": [
                        ("Nodo", node_name),
                        ("Carga de CPU", f"{cpu_pct}%"),
                        ("Cores vCPU", str(n.get("maxcpu", 0))),
                        ("Fecha y Hora", time.strftime("%Y-%m-%d %H:%M:%S"))
                    ]
                }

        # 5. Check: Global Health Score Drop below 50
        if health_score < 50 and not conn.get("is_demo"):
            key = "health_score_critical"
            if key not in current_incidents and not current_incidents:
                current_incidents[key] = {
                    "severity": "CRITICAL",
                    "title": f"🚨 Índice de Salud Global Crítico ({health_score}/100)",
                    "description": f"El Health Score de Spotlight ha caído a {health_score}/100 debido a múltiples anomalías acumuladas en el clúster.",
                    "details": [
                        ("Health Score", f"{health_score} / 100"),
                        ("Alarmas Críticas", str(cluster.get("alarm_counts", {}).get("critical", 0))),
                        ("Alarmas Altas", str(cluster.get("alarm_counts", {}).get("high", 0))),
                        ("Fecha y Hora", time.strftime("%Y-%m-%d %H:%M:%S"))
                    ]
                }

        async with self._lock:
            # Send alert for current incidents respecting cooldown
            for inc_key, inc_data in current_incidents.items():
                last_time = self._sent_alerts.get(inc_key, 0.0)
                if (now - last_time) >= cooldown_sec:
                    subject = f"[{inc_data['severity']}] {inc_data['title']}"
                    html = self._format_html_alert(
                        severity=inc_data["severity"],
                        title=inc_data["title"],
                        description=inc_data["description"],
                        details=inc_data["details"],
                        is_recovery=False
                    )
                    success, msg = await self.send_email(subject, html)
                    if success:
                        self._sent_alerts[inc_key] = now
                        self._active_incidents[inc_key] = inc_data

            # Check for resolved incidents (were active before, now not in current_incidents)
            resolved_keys = [k for k in self._active_incidents if k not in current_incidents]
            for r_key in resolved_keys:
                past = self._active_incidents.pop(r_key, None)
                if past:
                    rec_title = f"🟢 RECUPERADO: {past.get('title', r_key)}"
                    rec_details = [
                        ("Incidencia Resuelta", past.get("title", r_key)),
                        ("Estado Actual", "Operativo / Normal"),
                        ("Servidor Proxmox", settings.PVE_HOST),
                        ("Fecha de Resolución", time.strftime("%Y-%m-%d %H:%M:%S"))
                    ]
                    rec_html = self._format_html_alert(
                        severity="NORMAL",
                        title=rec_title,
                        description="La incidencia urgente ha sido resuelta y los parámetros han retornado a niveles saludables.",
                        details=rec_details,
                        is_recovery=True
                    )
                    await self.send_email(rec_title, rec_html)
                    # Clear sent time so future incidents trigger immediately
                    self._sent_alerts.pop(r_key, None)

email_notifier = EmailNotifier()
