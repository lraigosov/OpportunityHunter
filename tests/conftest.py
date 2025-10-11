import sys
from pathlib import Path

# Agregar {repo}/licitaciones (contiene la carpeta 'src') al sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
