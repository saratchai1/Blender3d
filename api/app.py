from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).with_name('auto-boq.py')
_spec = importlib.util.spec_from_file_location('auto_boq_runtime_api', _MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f'Cannot load Automatic BOQ API module: {_MODULE_PATH}')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
app = _module.app
