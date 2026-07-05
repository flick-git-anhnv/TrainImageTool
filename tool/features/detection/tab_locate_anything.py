"""Tab GUI cho locate-anything.cpp — open-vocabulary detection theo text prompt.

2 engine: locate-anything.cpp (CLI, subprocess, chính xác hơn nhưng chậm/nặng)
và YOLOE (Python in-process, nhẹ/nhanh hơn nhiều — dùng model có sẵn trong dự án).
Cả 2 engine trả cùng shape dict {detections, annotated, json_path, error} qua
_current_engine_runner() nên _single_worker/_batch_worker dùng chung 1 code path.

Business logic nằm ở tool/shared/{locate_anything_runner, yoloe_detect_runner};
layout UI nằm ở locate_anything_layout_mixin.py — file này chỉ orchestrate.
"""
import os
import threading
from tkinter import *
from tkinter import messagebox, filedialog

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from ...core.constants import BG, IMAGE_EXTENSIONS
from ...core.settings import _push_history, _get_history
from ...core.ui_helpers import _append_log, _zoom_image_window
from ...shared.locate_anything_runner import run_one, list_images
from .locate_anything_layout_mixin import LocateAnythingLayoutMixin


class LocateAnythingTab(Frame, LocateAnythingLayoutMixin):

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._cancel = False
        self._proc_holder = [None]
        self._pil_preview = None
        self._batch_files = {}   # iid -> {"file":..., "annotated":..., "detections":[...]}
        self._yoloe_model = None
        self._yoloe_model_path = None
        self._build()

    # ═══════════════════════════ ENGINE DISPATCH ══════════════════════════

    def _get_yoloe_model(self, model_path):
        if self._yoloe_model is None or self._yoloe_model_path != model_path:
            from ...shared.yoloe_utils import load_yoloe
            self._yoloe_model = load_yoloe(model_path)
            self._yoloe_model_path = model_path
        return self._yoloe_model

    def _current_engine_runner(self):
        """Trả về (callable(image_path)->result_dict, thông_báo_lỗi|None).

        Cả 2 engine trả cùng shape dict {detections, annotated, json_path, error}
        để _single_worker/_batch_worker không cần biết đang chạy engine nào."""
        prompt = self._prompt_var.get().strip()
        if not prompt:
            return None, "Chưa nhập prompt mô tả vật thể cần tìm."
        out_dir = self._outdir_var.get().strip() or None

        if self._engine_var.get() == "yoloe":
            model_path = self._yoloe_model_var.get().strip() or "yoloe-11s-seg.pt"
            prompts = [p.strip() for p in prompt.split(",") if p.strip()]
            if not prompts:
                return None, "Prompt YOLOE cần ít nhất 1 nhãn (cách nhau bằng dấu phẩy)."
            try:
                model = self._get_yoloe_model(model_path)
            except Exception as e:
                return None, f"Không load được model YOLOE: {e}"
            conf = self._yoloe_conf_var.get()

            def _runner(image_path):
                from ...shared.yoloe_detect_runner import run_yoloe_one
                return run_yoloe_one(model, image_path, prompts, conf=conf, out_dir=out_dir)
            return _runner, None

        cli = self._cli_var.get().strip()
        model = self._model_var.get().strip()
        if not cli or not os.path.isfile(cli):
            return None, "Chưa chọn locate-anything-cli.exe hợp lệ."
        if not model or not os.path.isfile(model):
            return None, "Chưa chọn model .gguf hợp lệ."
        kw = dict(mode=self._mode_var.get(), threads=self._threads_var.get() or None,
                  out_dir=out_dir, max_long_side=self._maxside_var.get() or None)

        def _runner(image_path):
            def _log(line):
                self.root.after(0, _append_log, self._log, line)
            return run_one(cli, model, image_path, prompt, on_log=_log,
                            proc_holder=self._proc_holder, **kw)
        return _runner, None

    # ═══════════════════════════ SINGLE DETECT ════════════════════════════

    def _detect_single(self):
        image = self._img_var.get().strip()
        if not image or not os.path.isfile(image):
            messagebox.showwarning("Thông báo", "Chưa chọn ảnh hợp lệ."); return
        runner, err = self._current_engine_runner()
        if err:
            messagebox.showwarning("Thông báo", err); return
        prompt = self._prompt_var.get().strip()
        _push_history("h.la.prompt", prompt)
        self._prompt_cb["values"] = _get_history("h.la.prompt")

        self._btn_single.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._cancel = False
        self._tree_single.delete(*self._tree_single.get_children())
        _append_log(self._log, f"⠿ [{self._engine_var.get()}] Detect: {os.path.basename(image)} — \"{prompt}\"")

        threading.Thread(target=self._single_worker, args=(runner, image), daemon=True).start()

    def _single_worker(self, runner, image):
        result = runner(image)
        self.root.after(0, self._on_single_done, result)

    def _on_single_done(self, result):
        self._btn_single.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        if result["error"]:
            _append_log(self._log, f"[LỖI] {result['error']}")
            return
        for det in result["detections"]:
            box = det.get("box", [])
            box_txt = ", ".join(f"{v:.1f}" for v in box) if box else "-"
            self._tree_single.insert("", END, values=(det.get("label", "?"), box_txt))
        if result["annotated"] and _PIL_OK:
            try:
                self._pil_preview = Image.open(result["annotated"])
                self._show_thumb(self._pic, self._pil_preview, 340, 260)
            except Exception:
                pass
        _append_log(self._log, f"✔ {len(result['detections'])} detections")

    # ═══════════════════════════ BATCH DETECT ═════════════════════════════

    def _detect_batch(self):
        folder = self._folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Thông báo", "Chưa chọn thư mục hợp lệ."); return
        files = list_images(folder, IMAGE_EXTENSIONS)
        if not files:
            messagebox.showinfo("Thông báo", "Không tìm thấy ảnh nào trong thư mục."); return
        runner, err = self._current_engine_runner()
        if err:
            messagebox.showwarning("Thông báo", err); return
        prompt = self._prompt_var.get().strip()
        _push_history("h.la.prompt", prompt)
        self._prompt_cb["values"] = _get_history("h.la.prompt")

        self._cancel = False
        self._batch_files.clear()
        self._tree_batch.delete(*self._tree_batch.get_children())
        self._btn_batch.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._pb.config(value=0, maximum=len(files))
        _append_log(self._log, f"⠿ [{self._engine_var.get()}] Batch: {len(files)} ảnh — \"{prompt}\"")

        threading.Thread(target=self._batch_worker, args=(runner, files), daemon=True).start()

    def _batch_worker(self, runner, files):
        total = len(files)
        for i, f in enumerate(files):
            if self._cancel:
                break
            result = runner(f)
            self.root.after(0, self._on_batch_item_done, i + 1, total, f, result)
        self.root.after(0, self._on_batch_finished)

    def _on_batch_item_done(self, i, total, fpath, result):
        self._pb["value"] = i
        self._prog_lbl.config(text=f"Đang xử lý: {i}/{total}  ({int(i/total*100)}%)")
        dets = result.get("detections", [])
        labels = ", ".join(sorted({d.get("label", "?") for d in dets})) or "-"
        iid = self._tree_batch.insert("", END, values=(os.path.basename(fpath), len(dets), labels))
        self._batch_files[iid] = {"file": fpath, "annotated": result.get("annotated"), "detections": dets}
        if result.get("error"):
            _append_log(self._log, f"[LỖI] {os.path.basename(fpath)}: {result['error']}")

    def _on_batch_finished(self):
        self._btn_batch.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        n = len(self._batch_files)
        msg = f"Hoàn thành: {n} ảnh" + (" (đã dừng giữa chừng)" if self._cancel else "")
        self._prog_lbl.config(text=msg)
        _append_log(self._log, f"✔ {msg}")

    def _on_batch_select(self, _=None):
        sel = self._tree_batch.selection()
        if not sel: return
        info = self._batch_files.get(sel[0])
        if info and info["annotated"] and _PIL_OK and os.path.isfile(info["annotated"]):
            try:
                self._pil_preview = Image.open(info["annotated"])
                self._show_thumb(self._pic, self._pil_preview, 340, 260)
            except Exception:
                pass

    def _on_batch_dbl(self, _=None):
        self._on_batch_select()
        if self._pil_preview:
            _zoom_image_window(self.root, self._pil_preview, "Locate Anything — kết quả")

    def _nav_batch(self, delta):
        children = self._tree_batch.get_children()
        if not children: return
        sel = self._tree_batch.selection()
        idx = children.index(sel[0]) if sel else -1
        idx = max(0, min(len(children) - 1, idx + delta))
        self._tree_batch.selection_set(children[idx])
        self._tree_batch.see(children[idx])

    # ═══════════════════════════ COMMON ═══════════════════════════════════

    def _stop(self):
        self._cancel = True
        proc = self._proc_holder[0]
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
        _append_log(self._log, "⚠ Đang dừng...")

    def _export_csv(self):
        if not self._batch_files:
            messagebox.showinfo("Thông báo", "Chưa có kết quả batch để xuất."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV", "*.csv")],
                                             initialfile="locate_anything_results.csv")
        if not path: return
        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["file", "count", "labels", "annotated"])
            for info in self._batch_files.values():
                labels = ", ".join(sorted({d.get("label", "?") for d in info["detections"]}))
                w.writerow([info["file"], len(info["detections"]), labels, info["annotated"] or ""])
        _append_log(self._log, f"✔ Đã xuất: {path}")

    def _show_thumb(self, widget, pil_img, max_w, max_h):
        from PIL import ImageTk
        img = pil_img.copy()
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        widget.configure(image=tk_img, text="")
        widget._tk_img = tk_img

    def select_all_batch(self):
        self._tree_batch.selection_set(self._tree_batch.get_children())
