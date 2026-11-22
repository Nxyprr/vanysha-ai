#!/usr/bin/env python3
"""Enciende Vanysha AI (backend + frontend) con un solo comando o doble clic.

Hace todo solo: crea el entorno, instala lo necesario (la primera vez), busca un puerto libre,
arranca el servidor, espera a que esté listo y abre el navegador.
Usa únicamente la biblioteca estándar de Python.

Opciones:  --yolo        instala también YOLO (IA con más clases; descarga más)
           --port N      puerto inicial (por defecto 8000)
           --no-browser  no abrir el navegador
"""
import argparse
import hashlib
import os
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACK = ROOT / "backend"
VENV = BACK / ".venv"


def say(msg: str = "") -> None:
    print(msg, flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def files_hash(files) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(Path(f).read_bytes())
    return h.hexdigest()


def ensure_venv() -> None:
    if venv_python().exists():
        return
    say("1/3  Preparando el entorno (solo la primera vez)...")
    venv.EnvBuilder(with_pip=True).create(str(VENV))


def ensure_deps(with_yolo: bool) -> bool:
    files = [BACK / "requirements.txt"] + ([BACK / "requirements-yolo.txt"] if with_yolo else [])
    digest = files_hash(files)
    marker = VENV / ".deps"
    if marker.exists() and marker.read_text() == digest:
        return True
    say("2/3  Instalando las librerias (puede tardar unos minutos; necesita internet)...")
    cmd = [str(venv_python()), "-m", "pip", "install", "--disable-pip-version-check", "-q"]
    for f in files:
        cmd += ["-r", str(f)]
    if subprocess.run(cmd).returncode != 0:
        say("")
        say("No se pudieron instalar las librerias. Revisa tu conexion a internet y vuelve a intentarlo.")
        return False
    marker.write_text(digest)
    return True


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


def pick_port(start: int = 8000, tries: int = 11):
    for p in range(start, start + tries):
        if port_free(p):
            return p
    return None


def wait_ready(port: int, proc=None, timeout: float = 90.0) -> bool:
    url = "http://127.0.0.1:%d/api/health" % port
    end = time.time() + timeout
    while time.time() < end:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yolo", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    say("=" * 50)
    say("   Vanysha AI")
    say("=" * 50)
    if sys.version_info < (3, 10):
        say("Necesitas Python 3.10 o superior. Tienes %d.%d. Instala una version nueva desde python.org" % sys.version_info[:2])
        return 1
    try:
        ensure_venv()
        if not ensure_deps(a.yolo):
            return 1
    except Exception as e:  # noqa: BLE001
        say("No se pudo preparar el entorno: %s" % e)
        return 1

    port = pick_port(a.port)
    if port is None:
        say("No encontre un puerto libre entre %d y %d. Cierra otros programas e intenta de nuevo." % (a.port, a.port + 10))
        return 1
    if port != a.port:
        say("El puerto %d estaba ocupado; usare el %d." % (a.port, port))

    say("3/3  Encendiendo el servidor...")
    proc = subprocess.Popen([str(venv_python()), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=str(BACK))
    try:
        if not wait_ready(port, proc):
            say("")
            say("El servidor no pudo iniciar. Lee los mensajes de arriba para ver el motivo.")
            proc.terminate()
            return 1
        url = "http://localhost:%d" % port
        say("")
        say("Vanysha AI esta encendido:  " + url)
        say("Correo:      admin@vanysha.ai")
        say("Contrasena:  Vanysha2026   (cambiala antes de mostrar el proyecto)")
        say("")
        say("Para APAGAR: cierra esta ventana o pulsa Ctrl + C.")
        if not a.no_browser:
            webbrowser.open(url)
        proc.wait()
    except KeyboardInterrupt:
        say("\nApagando Vanysha AI...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
