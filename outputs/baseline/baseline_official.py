# Runs docs/official_results.py unchanged, but writes into outputs/baseline/ instead of outputs/.
import sys, importlib.util
from pathlib import Path
ROOT = Path("/media/shruti/3E2AA2792AA22E39/web_dev/fairdeal")
spec = importlib.util.spec_from_file_location("official_results", ROOT / "docs/official_results.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.OUT = ROOT / "outputs/baseline"
m.main()
