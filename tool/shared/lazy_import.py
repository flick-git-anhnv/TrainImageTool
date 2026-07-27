# lazy_import.py — nạp thư viện nặng theo yêu cầu, không nạp lúc khởi động app
#
# Lý do tồn tại: `torch` (~8s) và `rfdetr` (~11s) trước đây được import ở mức module
# trong các tab detection, nên MỞ APP là phải chờ nạp xong dù user chưa hề bấm Detect.
# Module này tách 2 việc ra:
#   - "thư viện có cài không?"  → module_available()  — chỉ tra sys.path, KHÔNG nạp
#   - "lấy class ra dùng"       → lazy_callable()     — chỉ nạp ở lần gọi đầu tiên
import importlib
import importlib.util

_attr_cache: dict = {}
_avail_cache: dict = {}


def module_available(name: str) -> bool:
    """True nếu module đã được cài — KHÔNG import nó.

    Dùng thay cho pattern `try: import X; _X_OK = True except ImportError: ...`
    ở mức module. Lưu ý: hàm này chỉ khẳng định module TỒN TẠI trên sys.path;
    nếu bản cài bị hỏng thì lỗi sẽ nổ lúc gọi thật — nơi gọi vẫn cần try/except
    như trước.
    """
    if name in _avail_cache:
        return _avail_cache[name]
    try:
        ok = importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        ok = False
    _avail_cache[name] = ok
    return ok


def load_attr(module: str, attr: str):
    """Import module (nếu chưa) rồi trả về thuộc tính — có cache."""
    key = (module, attr)
    obj = _attr_cache.get(key)
    if obj is None:
        obj = getattr(importlib.import_module(module), attr)
        _attr_cache[key] = obj
    return obj


class _LazyCallable:
    """Proxy gọi được — chỉ import module thật ở lần dùng đầu tiên.

    Thay thế trực tiếp cho `from ultralytics import YOLO`: `YOLO(path)` vẫn viết
    y như cũ, `YOLO.some_attr` cũng chuyển tiếp đúng.
    """

    __slots__ = ("_module_name", "_attr_name")

    def __init__(self, module: str, attr: str):
        self._module_name = module
        self._attr_name = attr

    def __call__(self, *args, **kwargs):
        return load_attr(self._module_name, self._attr_name)(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(load_attr(self._module_name, self._attr_name), name)

    def __repr__(self):
        return f"<lazy {self._module_name}.{self._attr_name}>"


def lazy_callable(module: str, attr: str) -> _LazyCallable:
    return _LazyCallable(module, attr)


_mpl_tk = None


def matplotlib_tk():
    """Nạp matplotlib với backend TkAgg, trả về (Figure, FigureCanvasTkAgg).

    `matplotlib.use("TkAgg")` phải chạy TRƯỚC khi import backend — gói chung ở đây
    để mọi nơi dùng biểu đồ đều đi qua đúng một đường, thay vì mỗi tab tự
    `matplotlib.use(...)` ở mức module (kéo matplotlib vào lúc khởi động app).
    """
    global _mpl_tk
    if _mpl_tk is None:
        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        _mpl_tk = (Figure, FigureCanvasTkAgg)
    return _mpl_tk
