# yolo_nav_mixin.py — YoloNavMixin — điều hướng ảnh, phím tắt, autoplay
import os
import time
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


class YoloNavMixin:
    """Mixin: mở ảnh, điều hướng prev/next, bind phím tắt, autoplay."""

    def _open_image(self, path: str):
        self.current_image_path = path
        iid = self._path_to_iid.get(path)
        if iid:
            self.tree_images.selection_set(iid)
            self.tree_images.see(iid)
        n = len(self.image_list)
        try:
            pos = self.image_list.index(path) + 1
        except ValueError:
            pos = 0
        label = f"{pos}/{n}  " if n else ""
        self.v_status.set(f"{label}{os.path.basename(path)}")
        self._zoom_factor = 0.0
        self._img_pos   = [0, 0]
        self._pan_start = None
        self._zoomtest_boxes  = []
        self._zoomtest_active = False
        self._update_filmstrip()
        self._detect_and_display()
        # Lưu ảnh đang xem vào session
        _CFG["yolo.session.image"] = path
        _cfg_save()

    def _is_active(self):
        """Trả về True nếu YOLO tab đang được chọn trong Notebook."""
        try:
            w = self
            while w is not None:
                p = getattr(w, "master", None)
                if p is None:
                    break
                if isinstance(p, ttk.Notebook):
                    return p.select() == str(w)
                w = p
        except Exception:
            pass
        return False

    def _bind_keys(self):
        """Chỉ bind các phím đặc thù YOLO; dùng guard _is_active để không
        override binding của tab khác (BBox Editor, Checker…).
        ←/→ KHÔNG bind ở đây — app.py đã xử lý qua _prev_image/_next_image."""
        def _guard(fn):
            def _inner(*_):
                if self._is_active():
                    fn()
                    return "break"
            return _inner

        _INPUT_TYPES = (Entry, Text, Spinbox, ttk.Combobox, ttk.Entry, ttk.Spinbox)

        def _input_focused():
            try:
                return isinstance(self.root.focus_get(), _INPUT_TYPES)
            except Exception:
                return False

        def _space_handler(*_):
            if not self._is_active() or _input_focused():
                return
            self._toggle_autoplay()
            return "break"

        self.root.bind("<Return>",    _guard(lambda: self._mark_review("correct")), "+")
        self.root.bind("<Delete>",    _guard(lambda: self._mark_review("incorrect")), "+")
        self.root.bind("<space>",     _space_handler, "+")
        def _copy_handler(*_):
            if self._is_active() and not _input_focused():
                self._copy_path()
                return "break"
        self.root.bind("<Control-c>", _copy_handler, "+")

    def _prev_image(self): self._nav_image(-1)

    def _next_image(self): self._nav_image(+1)

    def select_image(self):
        """Alias không underscore — Ctrl+O routing từ app.py."""
        self._select_image()

    def _run_detect(self):
        """F5 routing từ app.py — detect ảnh hiện tại nếu đã load."""
        if self.current_image_path and self.model:
            self._open_image(self.current_image_path)

    def _on_delete(self):
        """Delete routing từ app.py — mark ảnh hiện tại là incorrect."""
        if self._is_active():
            self._mark_review("incorrect")

    def _on_return(self):
        """Return routing từ app.py — mark ảnh hiện tại là correct."""
        if self._is_active():
            self._mark_review("correct")

    def _copy_path(self):
        """Copy ảnh hiện tại vào clipboard (Ctrl+C) — cả 2 định dạng cùng lúc:
        CF_HDROP (file thật, để Paste ra Explorer/folder khác) + CF_DIB
        (bitmap, để Paste vào Paint/Word/app chat như ảnh). Trước đây chỉ set
        CF_DIB nên Paste vào Explorer không copy được file (Windows Explorer
        cần CF_HDROP)."""
        path = self.current_image_path
        if not path:
            return
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            user32   = ctypes.windll.user32

            kernel32.GlobalAlloc.argtypes  = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype   = ctypes.c_void_p
            kernel32.GlobalLock.argtypes   = [ctypes.c_void_p]
            kernel32.GlobalLock.restype    = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype  = ctypes.c_bool
            kernel32.GlobalFree.argtypes   = [ctypes.c_void_p]
            kernel32.GlobalFree.restype    = ctypes.c_void_p
            user32.OpenClipboard.argtypes  = [ctypes.c_void_p]
            user32.OpenClipboard.restype   = ctypes.c_bool
            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype  = ctypes.c_bool
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype  = ctypes.c_void_p
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype  = ctypes.c_bool

            GMEM_MOVEABLE = 0x0002
            GMEM_ZEROINIT = 0x0040
            CF_HDROP = 15
            CF_DIB   = 8

            # ── CF_HDROP: DROPFILES + tên file (UTF-16, double-null-terminated) ──
            class _DROPFILES(ctypes.Structure):
                _fields_ = [
                    ("pFiles", ctypes.c_uint32),
                    ("pt_x",   ctypes.c_long),
                    ("pt_y",   ctypes.c_long),
                    ("fNC",    ctypes.c_int32),
                    ("fWide",  ctypes.c_int32),
                ]
            hdr_size = ctypes.sizeof(_DROPFILES)
            names = (path + "\0").encode("utf-16-le") + b"\x00\x00"
            h_drop = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT,
                                          hdr_size + len(names))
            if not h_drop:
                self.v_status.set("Lỗi copy: không cấp phát được bộ nhớ")
                return
            p_drop = kernel32.GlobalLock(h_drop)
            if not p_drop:
                kernel32.GlobalFree(h_drop)
                self.v_status.set("Lỗi copy: GlobalLock thất bại")
                return
            df = _DROPFILES.from_address(p_drop)
            df.pFiles = hdr_size
            df.fWide  = 1
            ctypes.memmove(p_drop + hdr_size, names, len(names))
            kernel32.GlobalUnlock(h_drop)

            # ── CF_DIB: bitmap ảnh (best-effort — không có PIL vẫn copy file được) ──
            h_dib = None
            if _PIL_OK:
                try:
                    import io
                    img = Image.open(path).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, "BMP")
                    data = buf.getvalue()[14:]  # bỏ 14-byte BMP file header, giữ DIB
                    buf.close()
                    h_dib = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                    if h_dib:
                        p_dib = kernel32.GlobalLock(h_dib)
                        ctypes.memmove(p_dib, data, len(data))
                        kernel32.GlobalUnlock(h_dib)
                except Exception:
                    h_dib = None

            # Clipboard có thể tạm bị lock bởi app khác → retry tối đa 5 lần
            opened = False
            for _ in range(5):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.05)
            if not opened:
                kernel32.GlobalFree(h_drop)
                if h_dib:
                    kernel32.GlobalFree(h_dib)
                self.v_status.set("Lỗi copy: clipboard đang bị chiếm (thử lại)")
                return

            user32.EmptyClipboard()
            # Sau SetClipboardData thành công, Windows sở hữu handle — không GlobalFree nữa
            ok_drop = user32.SetClipboardData(CF_HDROP, h_drop)
            if not ok_drop:
                kernel32.GlobalFree(h_drop)
            if h_dib:
                if not user32.SetClipboardData(CF_DIB, h_dib):
                    kernel32.GlobalFree(h_dib)
            user32.CloseClipboard()

            if not ok_drop:
                self.v_status.set("Lỗi copy: SetClipboardData thất bại")
                return

            self.lbl_result.config(
                text=f"📋 Đã copy file: {os.path.basename(path)}  "
                     f"(Paste được vào Explorer hoặc app ảnh)",
                fg=DIM)
            self.after(2500, self._restore_result_label)
        except Exception as e:
            self.v_status.set(f"Lỗi copy ảnh: {e}")

    def _restore_result_label(self):
        if self._last_n_det < 0:
            return
        if self._last_n_det > 0:
            self.lbl_result.config(
                text=f"Phát hiện {self._last_n_det} đối tượng", fg=SUCCESS)
        else:
            self.lbl_result.config(text="Không phát hiện đối tượng nào", fg=DIM)

    def _nav_image(self, step: int):
        if not self.image_list:
            return
        if self.current_image_path in self.image_list:
            idx = self.image_list.index(self.current_image_path)
        else:
            idx = 0
        new_idx = (idx + step) % len(self.image_list)
        self._open_image(self.image_list[new_idx])

    def _on_image_select(self, _event=None):
        sel = self.tree_images.selection()
        if not sel:
            return
        iid = sel[0]
        path = self._tree_iid_map.get(iid)
        if path and path != self.current_image_path:
            self._open_image(path)

    # ======================================================== AUTO-PLAY ==

    def _toggle_autoplay(self):
        if self._autoplay_id is not None:
            self.root.after_cancel(self._autoplay_id)
            self._autoplay_id = None
            self.btn_autoplay.config(text="▶ Auto", bg="#2e5fa3")
        else:
            self.btn_autoplay.config(text="■ Stop", bg=ACCENT)
            self._schedule_autoplay()

    def _schedule_autoplay(self):
        try:
            interval = float(self.spin_interval.get())
        except ValueError:
            interval = 2.0
        ms = max(200, int(interval * 1000))
        self._autoplay_id = self.root.after(ms, self._autoplay_step)

    def _autoplay_step(self):
        if self._autoplay_id is None:
            return
        self._nav_image(+1)
        self._schedule_autoplay()
