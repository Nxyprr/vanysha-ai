"""Motor de reglas. Lógica pura: recibe detecciones normalizadas (0 a 1) y devuelve alertas.

Cada detección es un dict: {"c": clase, "p": confianza, "x": .., "y": .., "w": .., "h": ..}
Cada regla pertenece a un escenario del documento: seg, alm, cal, ret.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# código de escenario -> (nombre de la regla, severidad, mensaje)
RULE_INFO = {
    "seg": ("EPP incompleto", "Alta", "Persona sin casco o sin chaleco"),
    "alm": ("Zona restringida", "Alta", "Presencia dentro de la zona restringida"),
    "cal": ("Producto no conforme", "Media", "Defecto detectado en el producto"),
    "ret": ("Ocupación alta", "Baja", "Aforo por encima del límite"),
}

# mensajes de las alertas simuladas de la interfaz
SAMPLE_MESSAGES = {"seg": "Persona sin chaleco en planta", "alm": "Montacargas dentro de zona restringida",
                   "cal": "Defecto superficial en lote 88", "ret": "Aforo alto en pasillo 2"}

ZONE_CLASSES = {"person", "forklift", "truck", "car", "persona", "montacargas"}
PPE_MISSING = {"no_helmet", "no-helmet", "no_hardhat", "no-hardhat", "no_vest", "no-vest",
               "no_safety_vest", "no-safety-vest", "sin_casco", "sin_chaleco"}
DEFECT = {"defect", "defecto", "crack", "scratch"}


def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def center(d: dict):
    return d["x"] + d["w"] / 2, d["y"] + d["h"] / 2


def in_zone(d: dict, zone: List[float]) -> bool:
    cx, cy = center(d)
    return zone[0] <= cx <= zone[0] + zone[2] and zone[1] <= cy <= zone[1] + zone[3]


@dataclass
class LiveState:
    """Memoria de una conexión en vivo (tiempo dentro de la zona y pausas entre alertas)."""
    zone_since: Optional[float] = None
    last: Dict[str, float] = field(default_factory=dict)

    def ready(self, code: str, now: float, cooldown: float) -> bool:
        if now - self.last.get(code, -1e12) >= cooldown:
            self.last[code] = now
            return True
        return False


def _alert(code: str, message: Optional[str] = None) -> dict:
    name, sev, msg = RULE_INFO[code]
    return {"scenario": code, "rule": name, "severity": sev, "message": message or msg}


def evaluate(dets: List[dict], zone: Optional[List[float]], state: LiveState, enabled: Dict[str, bool],
             now: float, zone_seconds: float = 0.6, cooldown: float = 8.0, crowd_limit: int = 5) -> List[dict]:
    alerts: List[dict] = []
    persons = [d for d in dets if _norm(d["c"]) in ("person", "persona")]

    # 1) Zona restringida: algo de ZONE_CLASSES dentro de la zona el tiempo suficiente
    if zone:
        inside = [d for d in dets if _norm(d["c"]) in ZONE_CLASSES and in_zone(d, zone)]
        if inside:
            state.zone_since = state.zone_since if state.zone_since is not None else now
            if (enabled.get("alm", True) and now - state.zone_since >= zone_seconds
                    and state.ready("alm", now, cooldown)):
                alerts.append(_alert("alm", "Se detectó %d objeto(s) dentro de la zona restringida" % len(inside)))
        else:
            state.zone_since = None

    # 2) EPP: clases "sin casco / sin chaleco" (requiere un modelo propio entrenado)
    if enabled.get("seg", True) and any(_norm(d["c"]) in PPE_MISSING for d in dets):
        if state.ready("seg", now, cooldown):
            alerts.append(_alert("seg"))

    # 3) Producto no conforme
    if enabled.get("cal", True) and any(_norm(d["c"]) in DEFECT for d in dets):
        if state.ready("cal", now, cooldown):
            alerts.append(_alert("cal"))

    # 4) Ocupación alta
    if enabled.get("ret", True) and len(persons) >= crowd_limit:
        if state.ready("ret", now, cooldown):
            alerts.append(_alert("ret", "%d personas detectadas (límite %d)" % (len(persons), crowd_limit)))

    return alerts
