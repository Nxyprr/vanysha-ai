import os
import sys
import tempfile
from pathlib import Path

# Datos de prueba aislados: se definen ANTES de importar la aplicación.
_tmp = tempfile.mkdtemp(prefix="vanysha-test-")
os.environ["VANYSHA_DATA_DIR"] = _tmp
os.environ["VANYSHA_DETECTOR"] = "demo"
os.environ["VANYSHA_ADMIN_PASSWORD"] = "ClaveDePrueba123"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
