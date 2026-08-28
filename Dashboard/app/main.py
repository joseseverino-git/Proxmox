import os
import time
import logging
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.proxmox_client import proxmox_client
from app.troubleshoot import troubleshooter, log_buffer
from app.notifier import email_notifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("proxmox_dashboard")

async def background_alert_checker():
    """Background SRE worker that checks cluster status every 45s and dispatches email alerts."""
    logger.info("Background Email Alert Monitor service started.")
    # Initial grace period on startup
    await asyncio.sleep(15)
    while True:
        try:
            if settings.ALERT_EMAIL_ENABLED and settings.ALERT_EMAIL_TO:
                data = await proxmox_client.get_dashboard_data(force_refresh=True)
                await email_notifier.evaluate_and_alert(data)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in background alert checker loop: {e}")
        
        await asyncio.sleep(45)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("==================================================")
    logger.info(" PROXMOX SPOTLIGHT DASHBOARD STARTING ")
    logger.info("==================================================")
    logger.info(f"Target PVE Host: {settings.PVE_HOST}")
    logger.info(f"Target PVE User: {settings.PVE_USER} (Auth: {settings.AUTH_TYPE})")
    logger.info(f"Demo Mode: {settings.DEMO_MODE} (Configured: {settings.is_configured})")
    logger.info(f"Fallback to Demo on error: {settings.FALLBACK_TO_DEMO}")
    logger.info(f"Email Alerts: {settings.ALERT_EMAIL_ENABLED} (To: {settings.ALERT_EMAIL_TO or 'None'}, Via: {settings.SMTP_USER})")
    logger.info(f"Listening on http://{settings.HOST}:{settings.PORT}")

    # Start background alert monitor
    bg_task = asyncio.create_task(background_alert_checker())
    yield
    bg_task.cancel()
    logger.info("Shutting down Proxmox Spotlight Dashboard.")

app = FastAPI(
    title="Proxmox Spotlight Dashboard",
    description="Quest Spotlight-inspired Monitoring Dashboard for Proxmox VE",
    version="1.1.0",
    lifespan=lifespan
)

# CORS support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=FileResponse)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    return FileResponse(index_file)

@app.get("/api/status")
async def get_cluster_status(force: bool = False):
    """Retrieve full cluster telemetry, nodes, VMs, storages, alarms and tasks."""
    data = await proxmox_client.get_dashboard_data(force_refresh=force)
    # Trigger alert evaluation in background
    if settings.ALERT_EMAIL_ENABLED and settings.ALERT_EMAIL_TO:
        asyncio.create_task(email_notifier.evaluate_and_alert(data))
    return JSONResponse(content=data)

@app.get("/api/health")
async def health_check():
    """Simple healthcheck endpoint for Docker container checks."""
    return {
        "status": "healthy",
        "demo_mode": settings.DEMO_MODE,
        "configured": settings.is_configured,
        "auth_type": settings.AUTH_TYPE,
        "fallback_to_demo": settings.FALLBACK_TO_DEMO,
        "email_alerts_enabled": settings.ALERT_EMAIL_ENABLED
    }

# --- Configuration Endpoints ---

@app.get("/api/config")
async def get_public_config():
    """Return safe public configuration metadata with secrets masked."""
    return settings.to_safe_dict()

@app.post("/api/config")
async def update_configuration(request: Request):
    """Update settings in-place, persist to settings.json and .env, and reset client cache."""
    try:
        body = await request.json()
        logger.info(f"Updating application configuration: PVE_HOST={body.get('PVE_HOST')}, User={body.get('PVE_USER')}, EmailAlerts={body.get('ALERT_EMAIL_ENABLED')}")
        
        # Save and persist settings
        updated_dict = settings.update_and_persist(body)
        
        # Reset proxmox client cache and auth tokens
        proxmox_client.reset_cache()
        
        return {
            "success": True,
            "message": "Configuración guardada y aplicada exitosamente.",
            "config": updated_dict
        }
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": f"Error al guardar configuración: {str(e)}"}
        )

# --- Email Alert Test Endpoint ---

@app.post("/api/alerts/test")
async def test_email_alert(request: Request):
    """Send an immediate test alert email using supplied or persisted settings."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    to_email = body.get("email_to") or settings.ALERT_EMAIL_TO
    if not to_email or not to_email.strip():
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Debes especificar la dirección de correo de destino."}
        )

    smtp_user = body.get("smtp_user") or settings.SMTP_USER
    smtp_pass = body.get("smtp_password") or settings.SMTP_PASSWORD
    smtp_host = body.get("smtp_host") or settings.SMTP_HOST
    smtp_port = int(body.get("smtp_port") or settings.SMTP_PORT)

    success, msg = await email_notifier.send_test_email(
        to_email=to_email,
        smtp_user=smtp_user,
        smtp_password=smtp_pass,
        smtp_host=smtp_host,
        smtp_port=smtp_port
    )

    return JSONResponse(
        status_code=200 if success else 400,
        content={"success": success, "message": msg}
    )

# --- Troubleshooting Endpoints ---

@app.post("/api/troubleshoot/test")
async def quick_test_connection(request: Request):
    """Quick connectivity test against Proxmox VE without saving settings yet."""
    try:
        override = await request.json()
    except Exception:
        override = None
        
    result = await troubleshooter.run_quick_test(override=override)
    return JSONResponse(content=result)

@app.post("/api/troubleshoot/diagnose")
async def run_platform_diagnostics(request: Request):
    """Execute full 6-stage platform audit and return detailed results with remediation commands."""
    try:
        override = await request.json()
    except Exception:
        override = None
        
    result = await troubleshooter.run_full_diagnostics(override=override)
    return JSONResponse(content=result)

@app.get("/api/troubleshoot/logs")
async def get_application_logs(level: Optional[str] = None):
    """Retrieve recent application logs captured by in-memory ring buffer."""
    entries = log_buffer.get_entries(level=level)
    return {
        "count": len(entries),
        "logs": entries
    }

@app.post("/api/troubleshoot/logs/clear")
async def clear_application_logs():
    """Clear the log buffer."""
    log_buffer.clear()
    return {"success": True, "message": "Logs limpiados correctamente."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
