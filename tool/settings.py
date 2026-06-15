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


def _bind_history(key: str, combo, max_items: int = 20):
    """Bind a ttk.Combobox to a persistent history list in _CFG."""
    hist = _CFG.get(key, [])
    if hist:
        combo["values"] = hist
        try:
            combo.set(hist[0])
        except Exception:
            pass

    def _save(*_):
        val = combo.get().strip()
        if not val:
            return
        h = list(_CFG.get(key, []))
        if val in h:
            h.remove(val)
        h.insert(0, val)
        _CFG[key] = h[:max_items]
        combo["values"] = _CFG[key]
        _cfg_save()

    combo.bind("<FocusOut>", _save)
    combo.bind("<Return>",   _save)
    combo.bind("<<ComboboxSelected>>", _save)


def _push_history(key: str, val: str, max_items: int = 20):
    """Push a value to a history list (call after filedialog pick)."""
    if not val:
        return
    h = list(_CFG.get(key, []))
    if val in h:
        h.remove(val)
    h.insert(0, val)
    _CFG[key] = h[:max_items]
    _cfg_save()


def _get_history(key: str) -> list:
    return list(_CFG.get(key, []))


_cfg_load()
