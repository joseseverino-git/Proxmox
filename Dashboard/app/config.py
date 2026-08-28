import os
import json
import logging
from typing import Optional, Any, Dict
from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger("proxmox_dashboard")

def find_env_path() -> str:
    candidates = [
        os.path.abspath(".env"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
        "/app/.env",
        "/opt/spotlight-proxmox/.env"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Default to adjacent to app directory or current dir
    default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    return default_path

def get_data_dir() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(base, exist_ok=True)
    return base

def get_persisted_settings_path() -> str:
    return os.path.join(get_data_dir(), "settings.json")

class Settings(BaseSettings):
    PVE_HOST: str = "https://192.168.1.100:8006"
    AUTH_TYPE: str = "token"  # 'token' or 'password'
    PVE_USER: str = "monitoring@pve"
    PVE_TOKEN_NAME: str = "spotlight"
    PVE_TOKEN_VALUE: str = ""
    PVE_PASSWORD: str = ""
    PVE_VERIFY_SSL: bool = False
    PVE_TIMEOUT: float = 6.0
    CACHE_TTL_SECONDS: int = 5
    PORT: int = 8080
    HOST: str = "0.0.0.0"
    DEMO_MODE: bool = False
    FALLBACK_TO_DEMO: bool = False  # If false, show offline/error state when PVE is down instead of fake demo data

    class Config:
        env_file = find_env_path()
        env_file_encoding = "utf-8"
        extra = "ignore"

    @field_validator("PVE_VERIFY_SSL", "DEMO_MODE", "FALLBACK_TO_DEMO", mode="before")
    @classmethod
    def parse_bool_fields(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            cleaned = v.strip().strip("'\"").lower()
            return cleaned in ("true", "1", "t", "yes", "y", "on", "si", "sí")
        return bool(v)

    @property
    def formatted_pve_url(self) -> str:
        url = self.PVE_HOST.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        if ":" not in url.split("//")[1]:
            url = f"{url}:8006"
        return url.rstrip("/")

    @property
    def auth_header(self) -> dict:
        if self.AUTH_TYPE == "token" and self.PVE_TOKEN_VALUE:
            # PVEAPIToken=USER@REALM!TOKENID=UUID
            token_str = f"PVEAPIToken={self.PVE_USER}!{self.PVE_TOKEN_NAME}={self.PVE_TOKEN_VALUE}"
            return {"Authorization": token_str}
        return {}

    @property
    def is_configured(self) -> bool:
        if self.AUTH_TYPE == "password":
            return bool(self.PVE_USER and self.PVE_PASSWORD and self.PVE_PASSWORD.strip())
        return bool(
            self.PVE_TOKEN_VALUE 
            and self.PVE_TOKEN_VALUE.strip() 
            and self.PVE_TOKEN_VALUE != "your-token-secret-uuid-here"
            and self.PVE_TOKEN_VALUE != "tu-token-aqui"
        )

    def to_safe_dict(self) -> Dict[str, Any]:
        """Returns public/masked configuration for frontend display."""
        masked_token = ""
        if self.PVE_TOKEN_VALUE:
            val = self.PVE_TOKEN_VALUE.strip()
            if len(val) > 8:
                masked_token = f"{val[:4]}••••••••{val[-4:]}"
            else:
                masked_token = "••••••••"

        has_password = bool(self.PVE_PASSWORD and self.PVE_PASSWORD.strip())

        return {
            "pve_host": self.PVE_HOST,
            "auth_type": self.AUTH_TYPE,
            "pve_user": self.PVE_USER,
            "token_name": self.PVE_TOKEN_NAME,
            "token_value_masked": masked_token,
            "has_token_value": bool(self.PVE_TOKEN_VALUE and self.PVE_TOKEN_VALUE != "your-token-secret-uuid-here"),
            "has_password": has_password,
            "verify_ssl": self.PVE_VERIFY_SSL,
            "timeout": self.PVE_TIMEOUT,
            "cache_ttl": self.CACHE_TTL_SECONDS,
            "demo_mode": self.DEMO_MODE,
            "fallback_to_demo": self.FALLBACK_TO_DEMO,
            "is_configured": self.is_configured
        }

    def update_and_persist(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates in-memory settings and persists to data/settings.json and .env file.
        """
        # 1. Update in-memory attributes
        if "PVE_HOST" in new_data and new_data["PVE_HOST"]:
            self.PVE_HOST = str(new_data["PVE_HOST"]).strip()
        if "AUTH_TYPE" in new_data and new_data["AUTH_TYPE"]:
            self.AUTH_TYPE = str(new_data["AUTH_TYPE"]).strip().lower()
        if "PVE_USER" in new_data and new_data["PVE_USER"]:
            self.PVE_USER = str(new_data["PVE_USER"]).strip()
        if "PVE_TOKEN_NAME" in new_data and new_data["PVE_TOKEN_NAME"]:
            self.PVE_TOKEN_NAME = str(new_data["PVE_TOKEN_NAME"]).strip()
        
        # Only update token/password if explicitly provided (ignore empty when keeping existing)
        if "PVE_TOKEN_VALUE" in new_data and new_data["PVE_TOKEN_VALUE"] and new_data["PVE_TOKEN_VALUE"].strip():
            if not new_data["PVE_TOKEN_VALUE"].startswith("••"):
                self.PVE_TOKEN_VALUE = str(new_data["PVE_TOKEN_VALUE"]).strip()

        if "PVE_PASSWORD" in new_data and new_data["PVE_PASSWORD"] and new_data["PVE_PASSWORD"].strip():
            if not new_data["PVE_PASSWORD"].startswith("••"):
                self.PVE_PASSWORD = str(new_data["PVE_PASSWORD"]).strip()

        if "PVE_VERIFY_SSL" in new_data:
            self.PVE_VERIFY_SSL = self.parse_bool_fields(new_data["PVE_VERIFY_SSL"])
        if "PVE_TIMEOUT" in new_data and new_data["PVE_TIMEOUT"]:
            try:
                self.PVE_TIMEOUT = float(new_data["PVE_TIMEOUT"])
            except (ValueError, TypeError):
                pass
        if "DEMO_MODE" in new_data:
            self.DEMO_MODE = self.parse_bool_fields(new_data["DEMO_MODE"])
        if "FALLBACK_TO_DEMO" in new_data:
            self.FALLBACK_TO_DEMO = self.parse_bool_fields(new_data["FALLBACK_TO_DEMO"])

        # 2. Persist to data/settings.json
        try:
            persisted_file = get_persisted_settings_path()
            payload = {
                "PVE_HOST": self.PVE_HOST,
                "AUTH_TYPE": self.AUTH_TYPE,
                "PVE_USER": self.PVE_USER,
                "PVE_TOKEN_NAME": self.PVE_TOKEN_NAME,
                "PVE_TOKEN_VALUE": self.PVE_TOKEN_VALUE,
                "PVE_PASSWORD": self.PVE_PASSWORD,
                "PVE_VERIFY_SSL": self.PVE_VERIFY_SSL,
                "PVE_TIMEOUT": self.PVE_TIMEOUT,
                "CACHE_TTL_SECONDS": self.CACHE_TTL_SECONDS,
                "DEMO_MODE": self.DEMO_MODE,
                "FALLBACK_TO_DEMO": self.FALLBACK_TO_DEMO
            }
            with open(persisted_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Saved configuration to {persisted_file}")
        except Exception as e:
            logger.warning(f"Could not persist settings to JSON: {e}")

        # 3. Update or create .env file
        try:
            env_file = find_env_path()
            lines = []
            existing_keys = set()
            if os.path.exists(env_file):
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#") and "=" in stripped:
                            k = stripped.split("=")[0].strip()
                            existing_keys.add(k)
                            if k == "PVE_HOST":
                                lines.append(f"PVE_HOST={self.PVE_HOST}\n")
                            elif k == "AUTH_TYPE":
                                lines.append(f"AUTH_TYPE={self.AUTH_TYPE}\n")
                            elif k == "PVE_USER":
                                lines.append(f"PVE_USER={self.PVE_USER}\n")
                            elif k == "PVE_TOKEN_NAME":
                                lines.append(f"PVE_TOKEN_NAME={self.PVE_TOKEN_NAME}\n")
                            elif k == "PVE_TOKEN_VALUE":
                                lines.append(f"PVE_TOKEN_VALUE={self.PVE_TOKEN_VALUE}\n")
                            elif k == "PVE_PASSWORD":
                                lines.append(f"PVE_PASSWORD={self.PVE_PASSWORD}\n")
                            elif k == "PVE_VERIFY_SSL":
                                lines.append(f"PVE_VERIFY_SSL={str(self.PVE_VERIFY_SSL).lower()}\n")
                            elif k == "PVE_TIMEOUT":
                                lines.append(f"PVE_TIMEOUT={self.PVE_TIMEOUT}\n")
                            elif k == "DEMO_MODE":
                                lines.append(f"DEMO_MODE={str(self.DEMO_MODE).lower()}\n")
                            elif k == "FALLBACK_TO_DEMO":
                                lines.append(f"FALLBACK_TO_DEMO={str(self.FALLBACK_TO_DEMO).lower()}\n")
                            else:
                                lines.append(line)
                        else:
                            lines.append(line)

            # Append missing keys if .env was newly created or incomplete
            to_append = {
                "PVE_HOST": self.PVE_HOST,
                "AUTH_TYPE": self.AUTH_TYPE,
                "PVE_USER": self.PVE_USER,
                "PVE_TOKEN_NAME": self.PVE_TOKEN_NAME,
                "PVE_TOKEN_VALUE": self.PVE_TOKEN_VALUE,
                "PVE_PASSWORD": self.PVE_PASSWORD,
                "PVE_VERIFY_SSL": str(self.PVE_VERIFY_SSL).lower(),
                "PVE_TIMEOUT": str(self.PVE_TIMEOUT),
                "DEMO_MODE": str(self.DEMO_MODE).lower(),
                "FALLBACK_TO_DEMO": str(self.FALLBACK_TO_DEMO).lower()
            }
            for k, v in to_append.items():
                if k not in existing_keys:
                    lines.append(f"{k}={v}\n")

            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            logger.info(f"Updated .env at {env_file}")
        except Exception as e:
            logger.warning(f"Could not update .env file: {e}")

        return self.to_safe_dict()

# Instantiate settings
settings = Settings()

# Overlay persisted JSON settings if present
persisted_path = get_persisted_settings_path()
if os.path.exists(persisted_path):
    try:
        with open(persisted_path, "r", encoding="utf-8") as pf:
            saved_cfg = json.load(pf)
            for key, val in saved_cfg.items():
                if hasattr(settings, key) and val is not None:
                    if key in ("PVE_VERIFY_SSL", "DEMO_MODE", "FALLBACK_TO_DEMO"):
                        setattr(settings, key, settings.parse_bool_fields(val))
                    elif key == "PVE_TIMEOUT":
                        setattr(settings, key, float(val))
                    else:
                        setattr(settings, key, val)
        logger.info(f"Loaded persistent configuration from {persisted_path}")
    except Exception as e:
        logger.warning(f"Failed loading persisted settings: {e}")
