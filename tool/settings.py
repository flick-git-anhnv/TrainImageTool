import json
from pathlib import Path

# Settings file lives next to train-image-tool.py (parent of this package)
_SETTINGS_FILE = Path(__file__).parent.parent / ".kztek_tools_settings.json"
_CFG: dict = {}


def _cfg_load():
    global _CFG
    try:
        if _SETTINGS_FILE.exists():
            _CFG = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        _CFG = {}


def _cfg_save():
    try:
        _SETTINGS_FILE.write_text(
            json.dumps(_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _bind_cfg(key: str, var):
    if key in _CFG:
        try:
            var.set(_CFG[key])
        except Exception:
            pass

    def _cb(*_):
        _CFG[key] = var.get()
        _cfg_save()

    var.trace_add("write", _cb)


def _cfg_dir(key: str) -> str:
    v = _CFG.get(key, "")
    return v if v and Path(v).exists() else ""


_cfg_load()
