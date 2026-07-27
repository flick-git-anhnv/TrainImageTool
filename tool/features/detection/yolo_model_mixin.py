# yolo_model_mixin.py — YoloModelMixin — load/select model1/2/3 (YOLO, RF-DETR, ONNX)
import os
import threading
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
from ...shared.lazy_import import module_available, lazy_callable

# Lazy: chỉ nạp ultralytics/rfdetr khi thật sự load model (xem shared/lazy_import.py)
_YOLO_OK    = module_available("ultralytics")
_RFDETR_OK  = module_available("rfdetr")
YOLO        = lazy_callable("ultralytics", "YOLO")
_RFDETRBase = lazy_callable("rfdetr", "RFDETRBase")
from .yolo_onnx import _OnnxRunner


class YoloModelMixin:
    """Mixin: load/chọn model YOLO/RF-DETR/ONNX cho model1, model2, model3."""

    # ============================================================ FILE LOAD ==

    def _select_model(self):
        path = filedialog.askopenfilename(
            title="Chọn file model YOLO 1 (.pt / .onnx)",
            filetypes=[("Model files", "*.pt *.onnx"),
                       ("PyTorch Model", "*.pt"),
                       ("ONNX Model", "*.onnx"),
                       ("All files", "*.*")],
            initialdir=_cfg_dir("yolo.model_dir") or None,
            parent=self.root)
        if path:
            _push_history("h.yolo.model", path)
            self._load_model(path)

    def _select_model2(self):
        if not _YOLO_OK and not _RFDETR_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics  hoặc  pip install rfdetr",
                                  parent=self.root)
            return
        path = filedialog.askopenfilename(
            title="Chọn file model 2 (.pt / .onnx)",
            filetypes=[("Model files", "*.pt *.onnx"),
                       ("PyTorch Model", "*.pt"),
                       ("ONNX Model", "*.onnx"),
                       ("All files", "*.*")],
            initialdir=_cfg_dir("yolo.model_dir") or None,
            parent=self.root)
        if not path:
            return
        _push_history("h.yolo.model2", path)
        self.lbl_model2.config(text=f"  ⏳ Đang load…", fg=DIM)
        self.root.update_idletasks()

        def _do_load():
            try:
                mdl, names, mtype = self._auto_load_pt(path)
                self.root.after(0, lambda: self._on_model2_loaded(path, mdl, names, mtype, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_model2_loaded(path, None, {}, "yolo", err))

        threading.Thread(target=_do_load, daemon=True).start()

    def _on_model2_loaded(self, path: str, mdl, names: dict, mtype: str, err):
        if err:
            messagebox.showerror("Lỗi load model 2", err, parent=self.root)
            self.lbl_model2.config(text="  ✗ Lỗi load", fg=ACCENT)
            return
        self.model2 = mdl
        self._model2_type  = mtype
        self._model2_names = names
        self.v_model2_path.set(path)
        tag = {"rfdetr": " [DETR]", "onnx": " [ONNX]"}.get(mtype, "")
        if mtype == "yolo" and self._is_seg_model(mdl):
            tag = " [SEG]"
        self.lbl_model2.config(text=f"  {os.path.basename(path)}{tag}", fg=SUCCESS)
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _clear_model2(self):
        self.model2 = None
        self._model2_type  = "yolo"
        self._model2_names = {}
        self.v_model2_path.set("")
        self.lbl_model2.config(text="Chưa chọn", fg=DIM)
        self.panel2_frame.pack_forget()
        self.lbl_panel1_title.config(text="")
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _select_model3(self):
        if not _RFDETR_OK and not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics  (YOLO .pt/.onnx)\n"
                                  "pip install rfdetr  (RF-DETR .pt)",
                                  parent=self.root)
            return
        path = filedialog.askopenfilename(
            title="Chọn file model 3 (.pt YOLO/RF-DETR hoặc .onnx)",
            filetypes=[("Model files", "*.pt *.onnx"),
                       ("PyTorch Model", "*.pt"),
                       ("ONNX Model", "*.onnx"),
                       ("All files", "*.*")],
            initialdir=_cfg_dir("yolo.model_dir") or None,
            parent=self.root)
        if not path:
            return
        _push_history("h.yolo.model3", path)
        self.lbl_model3.config(text="  ⏳ Đang load…", fg=DIM)
        self.root.update_idletasks()

        def _do_load():
            try:
                mdl, names, mtype = self._auto_load_pt(path)
                self.root.after(0, lambda: self._on_model3_loaded(path, mdl, names, mtype, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_model3_loaded(path, None, {}, "rfdetr", err))

        threading.Thread(target=_do_load, daemon=True).start()

    def _on_model3_loaded(self, path: str, mdl, names: dict, mtype: str, err):
        if err:
            messagebox.showerror("Lỗi load model 3", err, parent=self.root)
            self.lbl_model3.config(text="  ✗ Lỗi load", fg=ACCENT)
            return
        self.model3        = mdl
        self._model3_names = names
        self._model3_type  = mtype
        self.v_model3_path.set(path)
        ext_tag = {"onnx": " [ONNX]", "rfdetr": " [DETR]"}.get(mtype, "")
        if mtype == "yolo" and self._is_seg_model(mdl):
            ext_tag = " [SEG]"
        self.lbl_model3.config(text=f"  {os.path.basename(path)}{ext_tag}", fg=SUCCESS)
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _clear_model3(self):
        self.model3        = None
        self._model3_names = {}
        self._model3_type  = "rfdetr"
        self.v_model3_path.set("")
        self.lbl_model3.config(text="Chưa chọn", fg=DIM)
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _auto_load_pt(self, path: str):
        """Tự phân biệt YOLO / RF-DETR / ONNX và trả về (model, names, mtype).
        Thứ tự ưu tiên: .onnx → OnnxRunner; .pt → YOLO trước, RF-DETR nếu lỗi."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".onnx":
            try:
                import onnxruntime  # noqa
            except ImportError:
                raise ImportError("pip install onnxruntime  (hoặc onnxruntime-gpu)")
            mdl = _OnnxRunner(path)
            return mdl, mdl.names, "onnx"
        # .pt: thử YOLO trước
        yolo_err = None
        if _YOLO_OK:
            try:
                mdl = YOLO(path)
                names = dict(mdl.names) if hasattr(mdl, "names") else {}
                return mdl, names, "yolo"
            except Exception as e:
                yolo_err = e
        # Thử RF-DETR
        if _RFDETR_OK:
            try:
                mdl = _RFDETRBase(pretrain_weights=path)
                names = {}
                if hasattr(mdl, "model") and hasattr(mdl.model, "names"):
                    raw = mdl.model.names
                    names = ({i: n for i, n in enumerate(raw)}
                             if isinstance(raw, (list, tuple)) else dict(raw))
                return mdl, names, "rfdetr"
            except Exception as e:
                if yolo_err:
                    raise ValueError(f"YOLO: {yolo_err}\nRF-DETR: {e}")
                raise
        if yolo_err:
            raise yolo_err
        raise ImportError("pip install ultralytics  (YOLO)  hoặc  pip install rfdetr  (RF-DETR)")

    def _load_model(self, path: str):
        if not _YOLO_OK and not _RFDETR_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics  hoặc  pip install rfdetr",
                                  parent=self.root)
            return
        self.lbl_model.config(text=f"  ⏳ Đang load {os.path.basename(path)}…", fg=DIM)
        self.root.update_idletasks()

        def _do_load():
            try:
                mdl, names, mtype = self._auto_load_pt(path)
                self.root.after(0, lambda: self._on_model_loaded(path, mdl, names, mtype, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_model_loaded(path, None, {}, "yolo", err))

        threading.Thread(target=_do_load, daemon=True).start()

    def _on_model_loaded(self, path: str, mdl, names: dict, mtype: str, err: str | None):
        if err:
            messagebox.showerror("Lỗi load model", err, parent=self.root)
            self.lbl_model.config(text="  ✗ Lỗi load model", fg=ACCENT)
            return
        self.model = mdl
        self._model1_type  = mtype
        self._model1_names = names
        self.v_model_path.set(path)
        tag = {"rfdetr": " [DETR]", "onnx": " [ONNX]"}.get(mtype, "")
        if mtype == "yolo" and self._is_seg_model(mdl):
            tag = " [SEG]"
        self.lbl_model.config(text=f"  {os.path.basename(path)}{tag}", fg=SUCCESS)
        self._update_class_list()
        if self.current_image_path:
            self._detect_and_display()
        elif not self._session_restored:
            # Model vừa load xong (lần đầu) → thử restore session
            self.after(100, self._auto_restore_session)

    def _auto_load_model(self):
        saved = self.v_model_path.get()
        if saved and os.path.isfile(saved):
            self._load_model(saved)
        else:
            default = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "yolo11n.pt")
            if os.path.isfile(default):
                self._load_model(default)

    def _auto_restore_session(self):
        """Tự động load lại folder + ảnh từ phiên làm việc trước."""
        if self._session_restored:
            return
        if not self.model:
            return
        self._session_restored = True

        folder   = _CFG.get("yolo.session.folder", "")
        last_img = _CFG.get("yolo.session.image", "")

        if not folder or not os.path.isdir(folder):
            return

        # Update path combo nhưng không trigger _load_path_input
        self.v_check_folder.set(folder)

        # Load folder (sẽ mở ảnh đầu tiên mặc định)
        self._load_folder(folder)

        # Nếu có ảnh được lưu và tồn tại → navigate tới đó
        if last_img and os.path.isfile(last_img) and last_img in self.image_list:
            self._open_image(last_img)

    def _update_class_list(self):
        self.lb_classes.delete(0, END)
        self.class_ids.clear()
        names = {}
        if self.model:
            if self._model1_type == "yolo" and hasattr(self.model, "names"):
                names = self.model.names
            else:
                names = self._model1_names
        for cid, cname in sorted(names.items()):
            self.class_ids.append(cid)
            self.lb_classes.insert(END, f"[{cid}] {cname}")
        self._update_must_have_lists()

    def _update_path_combo(self, path: str):
        self.v_check_folder.set(path)
        _push_history("h.yolo.path", path)
        self.combo_path["values"] = _get_history("h.yolo.path")
