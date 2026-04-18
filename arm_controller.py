"""Compatibility shim for root-level imports of arm_controller."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent / "Arm Controller" / "arm_controller.py"
_spec = spec_from_file_location("arm_controller_impl", _MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load module from {_MODULE_PATH}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_module, _name)

__all__ = [n for n in globals() if not n.startswith("_")]
