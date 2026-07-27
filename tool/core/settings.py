import sys
import json
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    # Chay tu EXE (PyInstaller): luu config canh file .exe
    _SETTINGS_FILE = Path(sys.executable).parent / ".kztek_tools_settings.json"
else:
    # Chay tu script: luu config trong thu muc package `tool/`
    # (Path(__file__).parent = tool/core  ->  .parent.parent = tool/)
    _SETTINGS_FILE = Path(__file__).parent.parent / ".kztek_tools_settings.json"
_CFG: dict = {}

# Loi ghi settings gan nhat — de UI co the hoi va bao cho user biet, thay vi
# nuot im lang roi user mat toan bo cau hinh ma khong hieu tai sao.
_LAST_SAVE_ERROR: str = ""

_save_timer: "threading.Timer | None" = None
_save_lock = threading.Lock()
_SAVE_DELAY = 0.5      # giay — gom nhieu lan goi lien tiep thanh 1 lan ghi dia


def _cfg_load():
    global _CFG
    try:
        if _SETTINGS_FILE.exists():
            _CFG = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        _CFG = {}


def last_save_error() -> str:
    """Thong bao loi cua lan ghi settings gan nhat ("" neu khong co loi)."""
    return _LAST_SAVE_ERROR


def _cfg_save() -> bool:
    """Ghi settings ra dia ngay lap tuc. Tra ve True neu thanh cong."""
    global _LAST_SAVE_ERROR
    try:
        _SETTINGS_FILE.write_text(
            json.dumps(_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
        _LAST_SAVE_ERROR = ""
        return True
    except Exception as exc:
        _LAST_SAVE_ERROR = f"{type(exc).__name__}: {exc}"
        return False


def _cfg_save_soon():
    """Hen ghi settings sau _SAVE_DELAY giay, huy lan hen truoc do.

    Dung cho duong `trace_add("write")` cua _bind_cfg: truoc day MOI ky tu user
    go vao mot Entry deu serialize + ghi lai toan bo file JSON (hang tram key).
    """
    global _save_timer
    with _save_lock:
        if _save_timer is not None:
            _save_timer.cancel()
        _save_timer = threading.Timer(_SAVE_DELAY, _cfg_save)
        _save_timer.daemon = True
        _save_timer.start()


def _cfg_flush():
    """Ghi ngay phan dang cho (goi luc dong app)."""
    global _save_timer
    with _save_lock:
        if _save_timer is not None:
            _save_timer.cancel()
            _save_timer = None
    return _cfg_save()


def _bind_cfg(key: str, var):
    if key in _CFG:
        try:
            var.set(_CFG[key])
        except Exception:
            pass

    def _cb(*_):
        try:
            _CFG[key] = var.get()
            _cfg_save_soon()   # debounce — xem _cfg_save_soon()
        except Exception:
            pass

    var.trace_add("write", _cb)


def _cfg_dir(key: str) -> str:
    v = _CFG.get(key, "")
    return v if v and Path(v).exists() else ""


def _bind_history(key: str, combo, max_items: int = 20):
    """Bind a ttk.Combobox to a persistent history list in _CFG.

    Nhấn phím Delete khi đang mở dropdown (item đang highlight) sẽ xóa mục đó
    khỏi lịch sử VÀ lưu lại ngay (trước đây chỉ xóa khỏi hiển thị, mở lại app
    hoặc combobox khác dùng chung key vẫn thấy mục cũ vì _CFG chưa được cập nhật).
    """
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

    def _delete_selected():
        try:
            popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
            lb = f"{popdown}.f.l"
            sel = combo.tk.call(lb, "curselection")
            sel = combo.tk.splitlist(sel) if sel else ()
            if not sel:
                return
            idx = int(sel[0])
            values = list(combo["values"])
            if idx >= len(values):
                return
            removed = values[idx]
            del values[idx]
            combo["values"] = values
            _CFG[key] = [v for v in _CFG.get(key, []) if v != removed]
            _cfg_save()
            combo.tk.call(lb, "delete", idx)
            if combo.get() == removed:
                combo.set(values[0] if values else "")
        except Exception:
            pass

    # Popdown listbox được tạo lazy khi post lần đầu — tạo ngay để bind Delete.
    try:
        popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
        lb = f"{popdown}.f.l"
        combo.tk.call("bind", lb, "<Delete>", combo.register(_delete_selected))
    except Exception:
        pass


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
