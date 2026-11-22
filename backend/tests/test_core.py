"""Pruebas de la lógica central (no necesitan FastAPI)."""
import numpy as np

from app import db, rules, security
from app.detector import DemoDetector, HogDetector, build_detector


def setup_module(_m=None):
    db.init_db()


def test_password_hash_and_verify():
    h = security.hash_password("Secreta123")
    assert security.verify_password("Secreta123", h)
    assert not security.verify_password("otra", h)
    assert h != security.hash_password("Secreta123")  # sal distinta cada vez


def test_token_roundtrip_and_tamper():
    t = security.create_token("U-1", "admin")
    assert security.decode_token(t)["sub"] == "U-1"
    assert security.decode_token(t + "x") is None


def test_db_seed_and_ids():
    db.init_db()
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] == 1
        assert set(db.enabled_rules(c)) == {"seg", "alm", "cal", "ret"}
        a = db.create_analysis(c, "seg", "Combinado", 1.2, .9, 3, "DEMO", "test")
        b = db.create_analysis(c, "alm", "Combinado", 1.2, .9, 3, "DEMO", "test")
        assert a["id"] != b["id"] and a["id"].startswith("AN-")
        al = db.create_alert(c, a["id"], "seg", "EPP incompleto", "Alta", "x")
        assert al["e"] == "nueva" and al["an"] == a["id"]


def person(x, y, w=.1, h=.4, c="person"):
    return {"c": c, "p": .9, "x": x, "y": y, "w": w, "h": h}


def test_zone_rule_needs_time_and_respects_cooldown():
    zone = [.5, .1, .4, .8]
    st = rules.LiveState()
    en = {"alm": True}
    d = [person(.6, .3)]
    assert rules.evaluate(d, zone, st, en, 100.0) == []                 # acaba de entrar
    out = rules.evaluate(d, zone, st, en, 100.7)                       # 0,7 s dentro
    assert len(out) == 1 and out[0]["rule"] == "Zona restringida"
    assert rules.evaluate(d, zone, st, en, 101.0) == []                 # pausa entre alertas
    assert len(rules.evaluate(d, zone, st, en, 109.0)) == 1             # pasó la pausa


def test_zone_rule_resets_when_leaving_and_when_disabled():
    zone = [.5, .1, .4, .8]
    st = rules.LiveState()
    rules.evaluate([person(.6, .3)], zone, st, {"alm": True}, 10.0)
    rules.evaluate([person(.05, .3)], zone, st, {"alm": True}, 10.3)   # sale
    assert st.zone_since is None
    st2 = rules.LiveState()
    rules.evaluate([person(.6, .3)], zone, st2, {"alm": False}, 10.0)
    assert rules.evaluate([person(.6, .3)], zone, st2, {"alm": False}, 12.0) == []


def test_ppe_defect_and_crowd_rules():
    st = rules.LiveState()
    en = {"seg": True, "cal": True, "ret": True}
    assert rules.evaluate([person(.1, .1, c="NO-Hardhat")], None, st, en, 1.0)[0]["scenario"] == "seg"
    assert rules.evaluate([person(.1, .1, c="defecto")], None, st, en, 1.0)[0]["scenario"] == "cal"
    crowd = [person(i / 10, .2) for i in range(5)]
    assert rules.evaluate(crowd, None, st, en, 1.0, crowd_limit=5)[0]["scenario"] == "ret"
    assert rules.evaluate(crowd[:4], None, rules.LiveState(), en, 1.0, crowd_limit=5) == []


def test_demo_detector_is_deterministic():
    d = DemoDetector()
    f = np.zeros((90, 160, 3), np.uint8)
    assert d.detect(f) == []
    assert d.detect_scenario(f, "alm") == d.detect_scenario(f, "alm")
    assert any(x["c"] == "forklift" for x in d.detect_scenario(f, "alm"))


def test_hog_detector_runs_on_blank_image():
    import cv2
    if not hasattr(cv2, "HOGDescriptor"):  # OpenCV 5 no incluye HOG: usa opencv 4.x (ver requirements.txt)
        return
    d = HogDetector()
    assert d.detect(np.zeros((360, 640, 3), np.uint8)) == []


def test_build_detector_falls_back():
    assert isinstance(build_detector("demo"), DemoDetector)
    assert build_detector("auto").name  # nunca falla: yolo -> hog -> demo


def test_demo_seed_loaded_once():
    import tempfile
    from pathlib import Path
    from app import config
    old = config.DB_PATH
    config.DB_PATH = Path(tempfile.mkdtemp()) / "seed.db"  # base aislada: no depende de otras pruebas
    try:
        db.init_db(); db.init_db()  # la segunda vez no duplica
        with db.conn() as c:
            assert c.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 12
            assert c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 5
            assert c.execute("SELECT COUNT(*) FROM alerts WHERE status='nueva'").fetchone()[0] == 3
            assert db.create_analysis(c, "seg", "x", 1, .9, 1, "DEMO", "t")["id"] == "AN-0013"
    finally:
        config.DB_PATH = old


def test_cli_creates_users_and_changes_password():
    from app import cli
    u = cli.create("Operaria Uno", "Op1@X.com", "operador", None, "Operacion123")
    assert u["email"] == "op1@x.com" and u["role"] == "operador"
    for bad in [("N", "mal", "operador", "Operacion123"), ("Nombre Ok", "a@b.co", "dios", "Operacion123"),
                ("Nombre Ok", "c@d.co", "operador", "corta"), ("Nombre Ok", "op1@x.com", "operador", "Operacion123")]:
        try:
            cli.create(bad[0], bad[1], bad[2], None, bad[3]); raise AssertionError("debió fallar")
        except ValueError:
            pass
    cli.set_password("op1@x.com", "NuevaClave456")
    with db.conn() as c:
        h = c.execute("SELECT pw_hash FROM users WHERE email='op1@x.com'").fetchone()[0]
    assert security.verify_password("NuevaClave456", h) and not security.verify_password("Operacion123", h)
    assert cli.main(["list-users"]) == 0
