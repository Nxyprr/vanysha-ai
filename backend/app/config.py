"""Configuración central. Todo se puede cambiar con variables de entorno (ver .env.example)."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    """Lee backend/.env (CLAVE=valor) sin pisar las variables que ya estén definidas."""
    f = BASE_DIR / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()
DATA_DIR = Path(os.getenv("VANYSHA_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "evidence").mkdir(exist_ok=True)

DB_PATH = Path(os.getenv("VANYSHA_DB", DATA_DIR / "vanysha.db"))
FRONTEND_DIR = Path(os.getenv("VANYSHA_FRONTEND", BASE_DIR.parent / "frontend"))


def _secret() -> str:
    """Clave para firmar tokens. Si no se define, se genera una y se guarda en data/.secret"""
    s = os.getenv("VANYSHA_SECRET")
    if s:
        return s
    f = DATA_DIR / ".secret"
    if f.exists():
        return f.read_text().strip()
    s = secrets.token_hex(32)
    f.write_text(s)
    return s


SECRET_KEY = _secret()
TOKEN_HOURS = int(os.getenv("VANYSHA_TOKEN_HOURS", "12"))

# Cuenta de administradora inicial (solo se crea si la base de datos está vacía).
DEFAULT_ADMIN_PASSWORD = "Vanysha2026"
ADMIN_EMAIL = os.getenv("VANYSHA_ADMIN_EMAIL", "admin@vanysha.ai").lower()
ADMIN_PASSWORD = os.getenv("VANYSHA_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
ADMIN_NAME = os.getenv("VANYSHA_ADMIN_NAME", "Administradora")

# Motor de detección: auto | yolo | hog | demo
DETECTOR = os.getenv("VANYSHA_DETECTOR", "auto").lower()
MODEL_PATH = os.getenv("VANYSHA_MODEL", "yolov8n.pt")
CONFIDENCE = float(os.getenv("VANYSHA_CONF", "0.4"))

# Datos de ejemplo al crear la base de datos por primera vez (0 para empezar vacío)
DEMO_DATA = os.getenv("VANYSHA_DEMO_DATA", "1") != "0"

# Reglas en vivo
ZONE_SECONDS = float(os.getenv("VANYSHA_ZONE_SECONDS", "0.6"))   # tiempo dentro de la zona para alertar
COOLDOWN_SECONDS = float(os.getenv("VANYSHA_COOLDOWN", "8"))     # pausa entre alertas de la misma regla
CROWD_LIMIT = int(os.getenv("VANYSHA_CROWD_LIMIT", "5"))         # personas para "ocupación alta"

# Orígenes permitidos si el frontend se sirve desde otro dominio (separados por coma)
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("VANYSHA_ORIGINS", "").split(",") if o.strip()]
