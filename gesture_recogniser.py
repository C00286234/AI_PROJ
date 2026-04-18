"""Compatibility shim for root-level imports of gesture_recogniser."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent / "Camera Module" / "gesture_recogniser.py"
_spec = spec_from_file_location("gesture_recogniser_impl", _MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load module from {_MODULE_PATH}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_module, _name)

__all__ = [n for n in globals() if not n.startswith("_")]
