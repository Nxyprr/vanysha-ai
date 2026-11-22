"""Base de datos SQLite (módulo estándar de Python, sin dependencias).

Para producción se puede migrar a PostgreSQL manteniendo estas mismas funciones (ver README).
Los serializadores devuelven el formato que usa la interfaz: id, an, sc, r, sev, m, t, e, n ...
"""
import sqlite3
import time
from contextlib import contextmanager

from . import config, rules, security

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, cargo TEXT,
  role TEXT NOT NULL, pw_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS analyses (
  id TEXT PRIMARY KEY, created_at INTEGER NOT NULL, scenario TEXT NOT NULL, profile TEXT,
  duration REAL, confidence REAL, objects INTEGER, mode TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY, analysis_id TEXT, scenario TEXT NOT NULL, rule TEXT NOT NULL,
  severity TEXT NOT NULL, message TEXT, status TEXT NOT NULL DEFAULT 'nueva', note TEXT DEFAULT '',
  created_at INTEGER NOT NULL, evidence INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS rules (
  scenario TEXT PRIMARY KEY, name TEXT NOT NULL, severity TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_at INTEGER NOT NULL, user TEXT, action TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC);
"""


def now_ms() -> int:
    return int(time.time() * 1000)


@contextmanager
def conn():
    c = sqlite3.connect(str(config.DB_PATH), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def next_id(c, key: str, prefix: str, width: int = 4) -> str:
    row = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    n = (row["value"] if row else 0) + 1
    c.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, n))
    return f"{prefix}-{n:0{width}d}"


# ---------- serializadores (formato de la interfaz) ----------
def ser_user(r) -> dict:
    return {"id": r["id"], "name": r["name"], "email": r["email"], "cargo": r["cargo"], "role": r["role"], "t": r["created_at"]}


def ser_alert(r) -> dict:
    return {"id": r["id"], "an": r["analysis_id"], "sc": r["scenario"], "r": r["rule"], "sev": r["severity"],
            "m": r["message"], "t": r["created_at"], "e": r["status"], "n": r["note"] or ""}


def ser_analysis(r) -> dict:
    return {"id": r["id"], "t": r["created_at"], "sc": r["scenario"], "prof": r["profile"], "dur": r["duration"],
            "conf": r["confidence"], "obj": r["objects"], "modo": r["mode"]}


# ---------- operaciones ----------
def audit(c, user: str, action: str) -> None:
    c.execute("INSERT INTO audit(created_at,user,action) VALUES(?,?,?)", (now_ms(), user, action))


def create_user(c, name: str, email: str, cargo: str, role: str, password: str) -> dict:
    uid = "U-" + next_id(c, "user", "X", 6)[2:]
    c.execute("INSERT INTO users(id,name,email,cargo,role,pw_hash,created_at) VALUES(?,?,?,?,?,?,?)",
              (uid, name, email.lower(), cargo, role, security.hash_password(password), now_ms()))
    return ser_user(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())


def create_analysis(c, scenario, profile, duration, confidence, objects, mode, source) -> dict:
    aid = next_id(c, "analysis", "AN")
    c.execute("INSERT INTO analyses(id,created_at,scenario,profile,duration,confidence,objects,mode,source) VALUES(?,?,?,?,?,?,?,?,?)",
              (aid, now_ms(), scenario, profile, duration, round(float(confidence), 3), int(objects), mode, source))
    return ser_analysis(c.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone())


def create_alert(c, analysis_id, scenario, rule, severity, message, evidence=False) -> dict:
    lid = next_id(c, "alert", "AL")
    c.execute("INSERT INTO alerts(id,analysis_id,scenario,rule,severity,message,status,note,created_at,evidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (lid, analysis_id, scenario, rule, severity, message, "nueva", "", now_ms(), 1 if evidence else 0))
    return ser_alert(c.execute("SELECT * FROM alerts WHERE id=?", (lid,)).fetchone())


def enabled_rules(c=None) -> dict:
    def _q(cc):
        return {r["scenario"]: bool(r["enabled"]) for r in cc.execute("SELECT scenario,enabled FROM rules")}
    if c is not None:
        return _q(c)
    with conn() as cc:
        return _q(cc)


_DEMO_OBJ = {"seg": 5, "alm": 3, "cal": 3, "ret": 6}
_DEMO_CONF = {"seg": .926, "alm": .92, "cal": .927, "ret": .867}
_DEMO_DUR = {"seg": 1.2, "alm": 1.4, "cal": 1.1, "ret": 1.6}


def seed_demo(c) -> None:
    """Carga 12 análisis y 5 alertas de ejemplo, igual que la versión de demostración (solo si no hay análisis)."""
    if c.execute("SELECT COUNT(*) AS n FROM analyses").fetchone()["n"]:
        return
    keys, now = list(rules.RULE_INFO), now_ms()
    states = ["nueva", "nueva", "revisada", "cerrada", "nueva"]
    for i in range(11, -1, -1):  # del más antiguo al más reciente, para que los números crezcan
        sc, t = keys[i % 4], now - int(i * 5.5 * 3600 * 1000)
        aid = next_id(c, "analysis", "AN")
        c.execute("INSERT INTO analyses(id,created_at,scenario,profile,duration,confidence,objects,mode,source) VALUES(?,?,?,?,?,?,?,?,?)",
                  (aid, t, sc, "Combinado", _DEMO_DUR[sc], _DEMO_CONF[sc], _DEMO_OBJ[sc], "DEMO", "demo"))
        if i < 5:
            name, sev, _ = rules.RULE_INFO[sc]
            c.execute("INSERT INTO alerts(id,analysis_id,scenario,rule,severity,message,status,note,created_at,evidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (next_id(c, "alert", "AL"), aid, sc, name, sev, rules.SAMPLE_MESSAGES[sc], states[i], "", t, 0))
    audit(c, "Sistema", "Datos de demostración cargados")


def init_db() -> None:
    """Crea las tablas y los datos iniciales (reglas y cuenta de administradora)."""
    with conn() as c:
        c.executescript(SCHEMA)
        for code, (name, sev, _msg) in rules.RULE_INFO.items():
            c.execute("INSERT OR IGNORE INTO rules(scenario,name,severity,enabled) VALUES(?,?,?,1)", (code, name, sev))
        if c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0:
            create_user(c, config.ADMIN_NAME, config.ADMIN_EMAIL, "Administración del sistema", "admin", config.ADMIN_PASSWORD)
            audit(c, "Sistema", "Sistema iniciado: cuenta de administradora creada")
        if config.DEMO_DATA:
            seed_demo(c)
