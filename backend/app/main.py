"""API de Vanysha AI (FastAPI).

Ejecutar desde la carpeta backend:   uvicorn app.main:app --reload --port 8000
La misma aplicación sirve el frontend en http://localhost:8000/
"""
import csv
import io
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
from fastapi import (Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile,
                     WebSocket, WebSocketDisconnect)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, config, db, rules, security
from .detector import build_detector

log = logging.getLogger("vanysha")
ROLES = {"admin", "supervisor", "operador", "auditor"}
SCENARIOS = set(rules.RULE_INFO)
STATUSES = {"nueva", "revisada", "cerrada"}
SAMPLE_MESSAGES = rules.SAMPLE_MESSAGES
DEFAULT_ZONE = [0.55, 0.18, 0.4, 0.7]

detector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector
    db.init_db()
    detector = build_detector(config.DETECTOR, config.MODEL_PATH, config.CONFIDENCE)
    if config.ADMIN_PASSWORD == config.DEFAULT_ADMIN_PASSWORD:
        log.warning("La administradora usa la contraseña por defecto. Cámbiala (POST /api/auth/password).")
    yield


app = FastAPI(title="Vanysha AI", version=__version__, lifespan=lifespan)
if config.ALLOWED_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- modelos de entrada
class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    cargo: Optional[str] = Field(default=None, max_length=80)
    role: str
    password: str = Field(min_length=8, max_length=128)


class PasswordIn(BaseModel):
    old: str
    new: str = Field(min_length=8, max_length=128)


class AlertPatch(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)


class RulePatch(BaseModel):
    enabled: bool


class AnalysisIn(BaseModel):
    scenario: str
    profile: str = "Combinado"
    duration: float = 1.2
    confidence: float = 0.9
    objects: int = 1
    alert: bool = False


# ---------------------------------------------------------------- autenticación
_fails: dict = {}


def user_from_token(token: Optional[str]):
    payload = security.decode_token(token or "")
    if not payload:
        return None
    with db.conn() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (payload["sub"],)).fetchone()


def current_user(authorization: Optional[str] = Header(None), token: Optional[str] = Query(None)):
    tok = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else token
    u = user_from_token(tok)
    if not u:
        raise HTTPException(401, "Sesión no válida. Inicia sesión de nuevo.")
    return u


def require(*roles):
    def dep(u=Depends(current_user)):
        if u["role"] not in roles:
            raise HTTPException(403, "Tu rol no tiene permiso para esta acción.")
        return u
    return dep


WRITERS = ("admin", "supervisor", "operador")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "mode": "REAL" if detector and detector.real else "DEMO",
            "detector": detector.name if detector else "-",
            "hint": config.ADMIN_PASSWORD == config.DEFAULT_ADMIN_PASSWORD}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()
    key = (email, request.client.host if request.client else "-")
    n, first = _fails.get(key, (0, time.time()))
    if n >= 5 and time.time() - first < 300:
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")
    with db.conn() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not u or not security.verify_password(body.password, u["pw_hash"]):
            _fails[key] = (n + 1, first if n else time.time())
            db.audit(c, email, "Intento de inicio de sesión fallido")
            raise HTTPException(401, "Correo o contraseña incorrectos.")
        _fails.pop(key, None)
        db.audit(c, u["name"], "Inicio de sesión")
    return {"token": security.create_token(u["id"], u["role"]), "user": db.ser_user(u)}


@app.get("/api/auth/me")
def me(u=Depends(current_user)):
    return db.ser_user(u)


@app.post("/api/auth/password")
def change_password(body: PasswordIn, u=Depends(current_user)):
    if not security.verify_password(body.old, u["pw_hash"]):
        raise HTTPException(400, "La contraseña actual no es correcta.")
    with db.conn() as c:
        c.execute("UPDATE users SET pw_hash=? WHERE id=?", (security.hash_password(body.new), u["id"]))
        db.audit(c, u["name"], "Cambió su contraseña")
    return {"ok": True}


# ---------------------------------------------------------------- usuarios (solo administración)
@app.get("/api/users")
def list_users(u=Depends(require("admin"))):
    with db.conn() as c:
        return [db.ser_user(r) for r in c.execute("SELECT * FROM users ORDER BY created_at")]


@app.post("/api/users", status_code=201)
def add_user(body: UserIn, u=Depends(require("admin"))):
    email = body.email.strip().lower()
    at = email.find("@")
    if body.role not in ROLES:
        raise HTTPException(400, "Rol no válido.")
    if at < 1 or email.find(".", at) < at + 2 or " " in email:
        raise HTTPException(400, "El correo no es válido.")
    with db.conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(409, "Ya existe una cuenta con ese correo.")
        out = db.create_user(c, body.name.strip(), email, (body.cargo or "").strip() or body.role, body.role, body.password)
        db.audit(c, u["name"], "Cuenta creada: %s (%s)" % (email, body.role))
    return out


@app.delete("/api/users/{uid}", status_code=204)
def delete_user(uid: str, u=Depends(require("admin"))):
    if uid == u["id"]:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta.")
    with db.conn() as c:
        t = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not t:
            raise HTTPException(404, "Cuenta no encontrada.")
        if t["role"] == "admin" and c.execute("SELECT COUNT(*) AS n FROM users WHERE role='admin'").fetchone()["n"] < 2:
            raise HTTPException(400, "Debe quedar al menos una cuenta de administración.")
        c.execute("DELETE FROM users WHERE id=?", (uid,))
        db.audit(c, u["name"], "Cuenta eliminada: " + t["email"])
    return Response(status_code=204)


# ---------------------------------------------------------------- alertas, análisis, reglas, auditoría
@app.get("/api/alerts")
def list_alerts(u=Depends(current_user), limit: int = Query(200, le=1000)):
    with db.conn() as c:
        return [db.ser_alert(r) for r in c.execute("SELECT * FROM alerts ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))]


@app.patch("/api/alerts/{aid}")
def patch_alert(aid: str, body: AlertPatch, u=Depends(require(*WRITERS))):
    if body.status is not None and body.status not in STATUSES:
        raise HTTPException(400, "Estado no válido.")
    with db.conn() as c:
        if not c.execute("SELECT 1 FROM alerts WHERE id=?", (aid,)).fetchone():
            raise HTTPException(404, "Alerta no encontrada.")
        if body.status is not None:
            c.execute("UPDATE alerts SET status=? WHERE id=?", (body.status, aid))
            db.audit(c, u["name"], "Alerta %s → %s" % (aid, body.status))
        if body.note is not None:
            c.execute("UPDATE alerts SET note=? WHERE id=?", (body.note, aid))
            db.audit(c, u["name"], "Nota en alerta " + aid)
        return db.ser_alert(c.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone())


@app.get("/api/alerts/{aid}/evidence")
def alert_evidence(aid: str, u=Depends(current_user)):
    if not re.fullmatch(r"AL-\d+", aid):
        raise HTTPException(400, "Identificador no válido.")
    f = config.DATA_DIR / "evidence" / (aid + ".jpg")
    if not f.exists():
        raise HTTPException(404, "Sin evidencia para esta alerta.")
    return FileResponse(f, media_type="image/jpeg")


@app.get("/api/analyses")
def list_analyses(u=Depends(current_user), limit: int = Query(300, le=2000)):
    with db.conn() as c:
        return [db.ser_analysis(r) for r in c.execute("SELECT * FROM analyses ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))]


@app.post("/api/analyses", status_code=201)
def ingest_analysis(body: AnalysisIn, u=Depends(require(*WRITERS))):
    """Registra un análisis hecho en la interfaz (simulación DEMO) y aplica las reglas del servidor."""
    if body.scenario not in SCENARIOS:
        raise HTTPException(400, "Escenario no válido.")
    with db.conn() as c:
        an = db.create_analysis(c, body.scenario, body.profile, body.duration, body.confidence, body.objects, "DEMO", u["name"])
        al = None
        if body.alert and db.enabled_rules(c).get(body.scenario, True):
            name, sev, _ = rules.RULE_INFO[body.scenario]
            al = db.create_alert(c, an["id"], body.scenario, name, sev, SAMPLE_MESSAGES[body.scenario])
        db.audit(c, u["name"], "Análisis %s · %s" % (an["id"], body.scenario))
    return {"analysis": an, "alert": al}


@app.get("/api/analyses.csv")
def analyses_csv(u=Depends(current_user)):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "fecha", "escenario", "perfil", "objetos", "confianza_pct", "tiempo_s", "modo"])
    with db.conn() as c:
        for r in c.execute("SELECT * FROM analyses ORDER BY created_at"):
            w.writerow([r["id"], datetime.fromtimestamp(r["created_at"] / 1000, timezone.utc).isoformat(), r["scenario"],
                        r["profile"], r["objects"], round((r["confidence"] or 0) * 100), r["duration"], r["mode"]])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=analisis_vanysha.csv"})


@app.get("/api/rules")
def get_rules(u=Depends(current_user)):
    return db.enabled_rules()


@app.patch("/api/rules/{code}")
def patch_rule(code: str, body: RulePatch, u=Depends(require("admin", "supervisor"))):
    if code not in SCENARIOS:
        raise HTTPException(404, "Regla no encontrada.")
    with db.conn() as c:
        c.execute("UPDATE rules SET enabled=? WHERE scenario=?", (1 if body.enabled else 0, code))
        db.audit(c, u["name"], "Regla «%s» %s" % (rules.RULE_INFO[code][0], "activada" if body.enabled else "desactivada"))
        return db.enabled_rules(c)


@app.get("/api/audit")
def get_audit(u=Depends(require("admin", "supervisor", "auditor")), limit: int = Query(200, le=1000)):
    with db.conn() as c:
        return [{"t": r["created_at"], "a": r["action"], "u": r["user"]}
                for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]


@app.get("/api/stats")
def stats(u=Depends(current_user)):
    with db.conn() as c:
        q = lambda s: c.execute(s).fetchone()[0]  # noqa: E731
        return {"analyses": q("SELECT COUNT(*) FROM analyses"), "objects": q("SELECT COALESCE(SUM(objects),0) FROM analyses"),
                "confidence": q("SELECT COALESCE(AVG(confidence),0) FROM analyses"),
                "alerts_new": q("SELECT COUNT(*) FROM alerts WHERE status='nueva'"), "alerts": q("SELECT COUNT(*) FROM alerts")}


# ---------------------------------------------------------------- detección real
def _clean_zone(z):
    try:
        z = [float(v) for v in z]
        if len(z) == 4 and all(0 <= v <= 1 for v in z) and z[2] > 0 and z[3] > 0:
            return z
    except Exception:  # noqa: BLE001
        pass
    return None


def _annotate(frame, dets):
    h, w = frame.shape[:2]
    for d in dets:
        p1 = (int(d["x"] * w), int(d["y"] * h))
        p2 = (int((d["x"] + d["w"]) * w), int((d["y"] + d["h"]) * h))
        cv2.rectangle(frame, p1, p2, (90, 36, 224), 2)
        cv2.putText(frame, "%s %d%%" % (d["c"], d["p"] * 100), (p1[0], max(14, p1[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


class Hub:
    def __init__(self):
        self.clients = set()

    async def broadcast(self, msg: dict):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


hub = Hub()


async def emit_alert(a: dict, dets: list, frame, source: str):
    ok, buf = cv2.imencode(".jpg", _annotate(frame.copy(), dets), [cv2.IMWRITE_JPEG_QUALITY, 70])
    conf = sum(d["p"] for d in dets) / len(dets) if dets else 0.8
    with db.conn() as c:
        an = db.create_analysis(c, a["scenario"], "Cámara real", 0.1, conf, max(1, len(dets)), "REAL", "camara")
        al = db.create_alert(c, an["id"], a["scenario"], a["rule"], a["severity"], a["message"], evidence=bool(ok))
        db.audit(c, "Sistema", "Alerta de cámara real %s · %s" % (al["id"], a["rule"]))
    if ok:
        (config.DATA_DIR / "evidence" / (al["id"] + ".jpg")).write_bytes(buf.tobytes())
    await hub.broadcast({"type": "alert", "alert": al, "analysis": an, "evidence": bool(ok)})


@app.post("/api/analyze/image")
async def analyze_image(scenario: str = "seg", file: UploadFile = File(...), u=Depends(require(*WRITERS))):
    """Analiza una imagen subida con el detector activo y aplica las reglas."""
    if scenario not in SCENARIOS:
        raise HTTPException(400, "Escenario no válido.")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "La imagen supera los 10 MB.")
    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "El archivo no es una imagen válida.")
    t0 = time.time()
    dets = await run_in_threadpool(detector.detect_scenario, frame, scenario)
    dur = round(time.time() - t0, 2)
    state = rules.LiveState()
    found = rules.evaluate(dets, DEFAULT_ZONE, state, db.enabled_rules(), time.time(), zone_seconds=0, cooldown=0,
                           crowd_limit=config.CROWD_LIMIT)
    conf = sum(d["p"] for d in dets) / len(dets) if dets else 0
    with db.conn() as c:
        an = db.create_analysis(c, scenario, "Imagen", dur, conf, len(dets), "REAL" if detector.real else "DEMO", u["name"])
        alerts = [db.create_alert(c, an["id"], a["scenario"], a["rule"], a["severity"], a["message"]) for a in found]
        db.audit(c, u["name"], "Análisis de imagen %s (%d objetos)" % (an["id"], len(dets)))
    return {"analysis": an, "detections": dets, "alerts": alerts, "detector": detector.name}


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket, token: str = Query("")):
    if not user_from_token(token):
        await ws.close(code=4401)
        return
    await ws.accept()
    hub.clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # mantiene la conexión abierta
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.clients.discard(ws)


@app.websocket("/ws/detect")
async def ws_detect(ws: WebSocket, token: str = Query("")):
    """Recibe fotogramas JPEG (texto con la zona + bytes de la imagen) y devuelve detecciones."""
    u = user_from_token(token)
    if not u or u["role"] not in WRITERS:
        await ws.close(code=4401)
        return
    await ws.accept()
    await ws.send_json({"type": "hello", "detector": detector.name, "mode": "REAL" if detector.real else "DEMO"})
    state = rules.LiveState()
    try:
        while True:
            meta = json.loads(await ws.receive_text())
            data = await ws.receive_bytes()
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                await ws.send_json({"type": "dets", "dets": [], "ms": 0})
                continue
            t0 = time.time()
            dets = await run_in_threadpool(detector.detect, frame)
            await ws.send_json({"type": "dets", "dets": dets, "ms": int((time.time() - t0) * 1000)})
            for a in rules.evaluate(dets, _clean_zone(meta.get("zone")), state, db.enabled_rules(), time.time(),
                                    config.ZONE_SECONDS, config.COOLDOWN_SECONDS, config.CROWD_LIMIT):
                await emit_alert(a, dets, frame, u["name"])
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass


# El frontend se sirve desde la misma aplicación (debe montarse al final).
if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
