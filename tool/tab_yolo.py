# tab_yolo.py — YOLO Detection tab
import os
import threading
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from .constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from .settings import _bind_cfg

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

try:
    from ultralytics import YOLO
    _YOLO_OK = True
except ImportError:
    _YOLO_OK = False

try:
    from tkinterdnd2 import DND_FILES
    _DND_OK = True
except ImportError:
    _DND_OK = False


class YoloTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.current_image_path = None
        self.model = None
        self.model2 = None
        self.class_ids = []
        self.image_list = []
        self._photo_ref = None
        self._photo_ref2 = None
        self._last_annotated_bgr = None

        self.v_model_path = StringVar()
        self.v_model2_path = StringVar()
        _bind_cfg("yolo.model_path", self.v_model_path)

        self._build()
        self.after(200, self._auto_load_model)

    # ================================================================ BUILD ==

    def _build(self):
        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    def _build_toolbar(self):
        top = Frame(self, bg=CARD, padx=10, pady=8)
        top.pack(fill=X)

        # Row 0 — model 1 & file buttons
        r0 = Frame(top, bg=CARD)
        r0.pack(fill=X)

        Button(r0, text="Chọn Model 1 (.pt)", command=self._select_model,
               bg=ACCENT2, fg="white", font=F_BOLD, relief="flat",
               padx=10, cursor="hand2",
               activebackground=ACCENT, activeforeground="white",
               ).pack(side=LEFT)

        self.lbl_model = Label(r0, text="Chưa chọn model",
                               font=("Segoe UI", 9, "italic"),
                               bg=CARD, fg=DIM)
        self.lbl_model.pack(side=LEFT, padx=(6, 16))

        Button(r0, text="Chọn Ảnh", command=self._select_image,
               bg=ACCENT, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#c0411a", activeforeground="white",
               ).pack(side=LEFT, padx=(0, 4))

        Button(r0, text="Chọn Thư Mục", command=self._select_folder,
               bg="#2e5fa3", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=LEFT, padx=(0, 16))

        Button(r0, text="Tính mAP", command=self._start_map_calc,
               bg="#2e7d32", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=LEFT, padx=(0, 4))

        Button(r0, text="Lưu kết quả", command=self._save_result,
               bg="#555570", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=LEFT)

        # Row 0b — model 2
        r0b = Frame(top, bg=CARD)
        r0b.pack(fill=X, pady=(6, 0))

        Button(r0b, text="Chọn Model 2 (.pt)", command=self._select_model2,
               bg="#3a5a3a", fg="white", font=F_BOLD, relief="flat",
               padx=10, cursor="hand2",
               activebackground="#4a7a4a", activeforeground="white",
               ).pack(side=LEFT)

        self.lbl_model2 = Label(r0b, text="Chưa chọn model 2",
                                font=("Segoe UI", 9, "italic"),
                                bg=CARD, fg=DIM)
        self.lbl_model2.pack(side=LEFT, padx=(6, 8))

        Button(r0b, text="Xoá Model 2", command=self._clear_model2,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               ).pack(side=LEFT)

        # Row 1 — conf slider (new feature: Ngưỡng confidence with resolution 0.05)
        r1 = Frame(top, bg=CARD)
        r1.pack(fill=X, pady=(8, 0))

        Label(r1, text="Ngưỡng confidence:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.v_conf_thresh = DoubleVar(value=0.25)
        self.slider_conf_thresh = Scale(
            r1, from_=0.0, to=1.0, resolution=0.05,
            orient=HORIZONTAL, length=200,
            variable=self.v_conf_thresh,
            command=self._on_conf_thresh_change,
            bg=CARD, fg=TEXT, highlightthickness=0,
            troughcolor="#16162a", activebackground=ACCENT,
            relief="flat", bd=0, showvalue=False,
        )
        self.slider_conf_thresh.pack(side=LEFT, padx=(4, 2))
        self.lbl_conf_thresh_val = Label(r1, text="0.25", bg=CARD, fg=ACCENT,
                                         font=F_MONO, width=5)
        self.lbl_conf_thresh_val.pack(side=LEFT, padx=(0, 16))

        Label(r1, text="Conf:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_conf = ttk.Scale(r1, from_=0.01, to=1.0, value=0.30,
                                      orient=HORIZONTAL, length=160,
                                      command=self._on_slider_change)
        self.slider_conf.pack(side=LEFT, padx=(4, 2))
        self.lbl_conf = Label(r1, text="0.30", bg=CARD, fg=TEXT,
                               font=F_MONO, width=5)
        self.lbl_conf.pack(side=LEFT)

        Label(r1, text="  IoU:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_iou = ttk.Scale(r1, from_=0.01, to=1.0, value=0.45,
                                     orient=HORIZONTAL, length=160,
                                     command=self._on_slider_change)
        self.slider_iou.pack(side=LEFT, padx=(4, 2))
        self.lbl_iou = Label(r1, text="0.45", bg=CARD, fg=TEXT,
                              font=F_MONO, width=5)
        self.lbl_iou.pack(side=LEFT)

        # Row 2 — class filter
        r2 = Frame(top, bg=CARD)
        r2.pack(fill=X, pady=(8, 0))

        Label(r2, text="Lọc class (bỏ trống = tất cả):",
              font=F_MAIN, bg=CARD, fg=DIM).pack(anchor=W)

        cls_wrap = Frame(r2, bg=CARD)
        cls_wrap.pack(fill=X)
        sb = Scrollbar(cls_wrap, orient=VERTICAL)
        sb.pack(side=RIGHT, fill=Y)
        self.lb_classes = Listbox(cls_wrap, selectmode=MULTIPLE,
                                   yscrollcommand=sb.set,
                                   height=4, font=F_MONO,
                                   bg="#16162a", fg=TEXT,
                                   selectbackground=ACCENT2,
                                   activestyle="none",
                                   relief="flat", bd=0)
        self.lb_classes.pack(side=LEFT, fill=BOTH, expand=True)
        sb.config(command=self.lb_classes.yview)
        self.lb_classes.bind("<<ListboxSelect>>",
                              lambda _: self._detect_and_display())

    def _build_content(self):
        content = Frame(self, bg=BG)
        content.pack(fill=BOTH, expand=True)

        # Sidebar — image list
        sidebar = Frame(content, bg=CARD, width=180)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 2))
        sidebar.pack_propagate(False)

        Label(sidebar, text="Danh sách ảnh",
              font=F_BOLD, bg=CARD, fg=TEXT).pack(pady=(8, 3))

        sb2 = Scrollbar(sidebar, orient=VERTICAL)
        sb2.pack(side=RIGHT, fill=Y)
        self.lb_images = Listbox(sidebar, yscrollcommand=sb2.set,
                                  font=F_MAIN, selectmode=SINGLE,
                                  activestyle="dotbox",
                                  bg="#16162a", fg=TEXT,
                                  selectbackground=ACCENT2,
                                  relief="flat", bd=0)
        self.lb_images.pack(fill=BOTH, expand=True, padx=4, pady=(0, 6))
        sb2.config(command=self.lb_images.yview)
        self.lb_images.bind("<<ListboxSelect>>", self._on_image_select)

        # Right — result panels area
        right = Frame(content, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_result = Label(right, text="", font=F_BOLD,
                                 bg=BG, fg=TEXT, anchor=W)
        self.lbl_result.pack(fill=X, padx=6, pady=(4, 0))

        # Panel container for single/side-by-side display
        self.panels_frame = Frame(right, bg=BG)
        self.panels_frame.pack(fill=BOTH, expand=True)

        # Panel 1
        self.panel1_frame = Frame(self.panels_frame, bg=BG)
        self.panel1_frame.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_panel1_title = Label(self.panel1_frame, text="",
                                       font=F_BOLD, bg=CARD, fg=ACCENT2,
                                       anchor=CENTER, pady=3)
        self.lbl_panel1_title.pack(fill=X)

        self.canvas = Label(self.panel1_frame,
                             text="Chọn ảnh để nhận diện",
                             bg="#0d0d1a", fg=DIM,
                             font=("Segoe UI", 14),
                             compound="center",
                             relief="flat")
        self.canvas.pack(fill=BOTH, expand=True, padx=0, pady=2)

        # Panel 2 (hidden by default)
        self.panel2_frame = Frame(self.panels_frame, bg=BG)

        self.lbl_panel2_title = Label(self.panel2_frame, text="",
                                       font=F_BOLD, bg=CARD, fg="#4a8a4a",
                                       anchor=CENTER, pady=3)
        self.lbl_panel2_title.pack(fill=X)

        self.canvas2 = Label(self.panel2_frame,
                              text="",
                              bg="#0d0d1a", fg=DIM,
                              font=("Segoe UI", 14),
                              compound="center",
                              relief="flat")
        self.canvas2.pack(fill=BOTH, expand=True, padx=0, pady=2)

        if _DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _build_statusbar(self):
        self.v_status = StringVar(value="Sẵn sàng")
        Label(self, textvariable=self.v_status,
              font=F_MAIN, bg=CARD, fg=DIM, anchor=W, padx=8,
              ).pack(fill=X, side=BOTTOM)

    # ============================================================= DRAG-DROP ==

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self._load_folder(paths[0])
            return
        imgs = [p for p in paths
                if os.path.isfile(p)
                and os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS]
        if not imgs:
            messagebox.showwarning("Không hỗ trợ",
                                   "Chỉ hỗ trợ ảnh hoặc thư mục chứa ảnh.",
                                   parent=self.root)
            return
        if len(imgs) == 1:
            self.image_list = []
            self.lb_images.delete(0, END)
            self._open_image(imgs[0])
        else:
            self._load_image_list(sorted(imgs))

    # ============================================================ FILE LOAD ==

    def _select_model(self):
        path = filedialog.askopenfilename(
            title="Chọn file model YOLO 1 (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")],
            parent=self.root)
        if path:
            self._load_model(path)

    def _select_model2(self):
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return
        path = filedialog.askopenfilename(
            title="Chọn file model YOLO 2 (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")],
            parent=self.root)
        if not path:
            return
        try:
            self.model2 = YOLO(path)
            self.v_model2_path.set(path)
            self.lbl_model2.config(
                text=f"  {os.path.basename(path)}", fg="#4caf50")
            if self.current_image_path and self.model:
                self._detect_and_display()
        except Exception as e:
            messagebox.showerror("Lỗi load model 2", str(e), parent=self.root)

    def _clear_model2(self):
        self.model2 = None
        self.v_model2_path.set("")
        self.lbl_model2.config(text="Chưa chọn model 2", fg=DIM)
        self.panel2_frame.pack_forget()
        self.lbl_panel1_title.config(text="")
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _load_model(self, path: str):
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return
        try:
            self.model = YOLO(path)
            self.v_model_path.set(path)
            self.lbl_model.config(
                text=f"  {os.path.basename(path)}", fg=SUCCESS)
            self._update_class_list()
            if self.current_image_path:
                self._detect_and_display()
        except Exception as e:
            messagebox.showerror("Lỗi load model", str(e), parent=self.root)

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

    def _update_class_list(self):
        self.lb_classes.delete(0, END)
        self.class_ids.clear()
        if self.model and hasattr(self.model, "names"):
            for cid, cname in sorted(self.model.names.items()):
                self.class_ids.append(cid)
                self.lb_classes.insert(END, f"[{cid}] {cname}")

    def _select_image(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            filetypes=[("Image Files",
                         "*.jpg *.jpeg *.png *.bmp *.webp")],
            parent=self.root)
        if path:
            self.image_list = []
            self.lb_images.delete(0, END)
            self._open_image(path)

    def _select_folder(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        folder = filedialog.askdirectory(
            title="Chọn thư mục ảnh", parent=self.root)
        if folder:
            self._load_folder(folder)

    def _load_folder(self, folder: str):
        files = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])
        if not files:
            messagebox.showinfo("Thông báo",
                                "Không tìm thấy ảnh trong thư mục!", parent=self.root)
            return
        self._load_image_list(files)

    def _load_image_list(self, files: list):
        self.image_list = files
        self.lb_images.delete(0, END)
        for f in files:
            self.lb_images.insert(END, os.path.basename(f))
        self.lb_images.selection_set(0)
        self._open_image(files[0])

    def _open_image(self, path: str):
        self.current_image_path = path
        if path in self.image_list:
            idx = self.image_list.index(path)
            self.lb_images.selection_clear(0, END)
            self.lb_images.selection_set(idx)
            self.lb_images.see(idx)
        n = len(self.image_list)
        label = (f"{self.image_list.index(path)+1}/{n}  " if n else "")
        self.v_status.set(f"{label}{os.path.basename(path)}")
        self._detect_and_display()

    def _on_image_select(self, _event=None):
        sel = self.lb_images.curselection()
        if sel and self.image_list:
            path = self.image_list[sel[0]]
            if path != self.current_image_path:
                self._open_image(path)

    # =========================================================== DETECTION ==

    def _on_conf_thresh_change(self, _=None):
        val = self.v_conf_thresh.get()
        self.lbl_conf_thresh_val.config(text=f"{val:.2f}")
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _on_slider_change(self, _=None):
        self.lbl_conf.config(text=f"{self.slider_conf.get():.2f}")
        self.lbl_iou.config( text=f"{self.slider_iou.get():.2f}")
        if self.current_image_path:
            self._detect_and_display()

    def _get_sel_classes(self):
        sel_idx = self.lb_classes.curselection()
        return [self.class_ids[i] for i in sel_idx] if sel_idx else None

    def _run_model(self, mdl, image_path, sel_cls):
        conf = max(self.v_conf_thresh.get(), self.slider_conf.get())
        return mdl.predict(
            source=image_path,
            classes=sel_cls,
            conf=conf,
            iou=self.slider_iou.get(),
            imgsz=640,
            agnostic_nms=True,
            verbose=False,
        )

    def _results_summary(self, results, model_names):
        boxes = results[0].boxes
        n_det = len(boxes) if boxes is not None else 0
        if n_det > 0:
            counts = {}
            for cls_id in boxes.cls.tolist():
                name = model_names[int(cls_id)]
                counts[name] = counts.get(name, 0) + 1
            summary = "  |  ".join(f"{n}: {c}" for n, c in counts.items())
            return n_det, summary
        return 0, ""

    def _annotated_to_pil(self, results):
        annotated = results[0].plot(line_width=2, font_size=11)
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb), annotated

    def _resize_pil(self, pil_img, w, h):
        pil_img.thumbnail((w - 10, h - 10), Image.Resampling.LANCZOS)
        return pil_img

    def _detect_and_display(self):
        if not self.current_image_path or not self.model:
            return
        if not _PIL_OK or not _CV2_OK:
            self.lbl_result.config(
                text="Cần cài: pip install Pillow opencv-python", fg=ACCENT)
            return
        try:
            sel_cls = self._get_sel_classes()
            results1 = self._run_model(self.model, self.current_image_path, sel_cls)
            n_det, summary = self._results_summary(results1, self.model.names)

            pil1, ann1_bgr = self._annotated_to_pil(results1)
            self._last_annotated_bgr = ann1_bgr

            self.root.update_idletasks()

            if self.model2 is not None:
                # Side-by-side mode
                self.panel2_frame.pack(side=LEFT, fill=BOTH, expand=True)
                m1_name = os.path.basename(self.v_model_path.get())
                m2_name = os.path.basename(self.v_model2_path.get())

                results2 = self._run_model(self.model2, self.current_image_path, sel_cls)
                n_det2, summary2 = self._results_summary(results2, self.model2.names)
                pil2, _ = self._annotated_to_pil(results2)

                self.lbl_panel1_title.config(
                    text=f"Model 1: {m1_name}  ({n_det} obj)")
                self.lbl_panel2_title.config(
                    text=f"Model 2: {m2_name}  ({n_det2} obj)")

                half_w = max(self.panels_frame.winfo_width() // 2, 400)
                ph = max(self.panels_frame.winfo_height(), 400)

                pil1r = self._resize_pil(pil1, half_w, ph)
                pil2r = self._resize_pil(pil2, half_w, ph)

                self._photo_ref = ImageTk.PhotoImage(image=pil1r)
                self._photo_ref2 = ImageTk.PhotoImage(image=pil2r)
                self.canvas.config(image=self._photo_ref, text="")
                self.canvas2.config(image=self._photo_ref2, text="")

                txt = (f"Model1: {n_det} obj"
                       + (f"  [{summary}]" if summary else "")
                       + f"    Model2: {n_det2} obj"
                       + (f"  [{summary2}]" if summary2 else ""))
                self.lbl_result.config(text=txt, fg=SUCCESS if n_det or n_det2 else DIM)
            else:
                # Single panel mode
                self.panel2_frame.pack_forget()
                self.lbl_panel1_title.config(text="")

                w = max(self.canvas.winfo_width(), 800)
                h = max(self.canvas.winfo_height(), 400)
                pil1r = self._resize_pil(pil1, w, h)

                self._photo_ref = ImageTk.PhotoImage(image=pil1r)
                self.canvas.config(image=self._photo_ref, text="")

                if n_det > 0:
                    self.lbl_result.config(
                        text=f"Phát hiện {n_det} đối tượng  —  {summary}",
                        fg=SUCCESS)
                else:
                    self.lbl_result.config(
                        text="Không phát hiện đối tượng nào", fg=DIM)

        except Exception as e:
            self.lbl_result.config(text=f"Lỗi: {e}", fg=ACCENT)

    # ======================================================= SAVE RESULT ==

    def _save_result(self):
        if self._last_annotated_bgr is None:
            messagebox.showwarning("Chưa có kết quả",
                                   "Vui lòng chạy detection trước.", parent=self.root)
            return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python", parent=self.root)
            return

        save_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả", parent=self.root)
        if not save_dir:
            return

        base = os.path.splitext(os.path.basename(self.current_image_path))[0]
        img_out = os.path.join(save_dir, f"{base}_detected.jpg")
        cv2.imwrite(img_out, self._last_annotated_bgr)

        save_txt = messagebox.askyesno(
            "Lưu nhãn YOLO",
            "Bạn có muốn lưu file nhãn .txt định dạng YOLO không?",
            parent=self.root)

        if save_txt and self.model and self.current_image_path:
            try:
                sel_cls = self._get_sel_classes()
                results = self._run_model(self.model, self.current_image_path, sel_cls)
                boxes = results[0].boxes
                txt_out = os.path.join(save_dir, f"{base}_detected.txt")
                orig_h, orig_w = self._last_annotated_bgr.shape[:2]
                with open(txt_out, "w", encoding="utf-8") as f:
                    if boxes is not None and len(boxes):
                        for box in boxes:
                            cls_id = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            cx, cy, bw, bh = xywhn
                            f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                messagebox.showinfo(
                    "Đã lưu",
                    f"Ảnh: {img_out}\nNhãn: {txt_out}",
                    parent=self.root)
            except Exception as e:
                messagebox.showerror("Lỗi lưu nhãn", str(e), parent=self.root)
        else:
            messagebox.showinfo("Đã lưu", f"Ảnh: {img_out}", parent=self.root)

    # ========================================================== MAP CALC ==

    def _start_map_calc(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return

        folder = filedialog.askdirectory(
            title="Chọn thư mục chứa ảnh + nhãn .txt (YOLO format)",
            parent=self.root)
        if not folder:
            return

        img_files = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])
        if not img_files:
            messagebox.showinfo("Thông báo",
                                "Không tìm thấy ảnh trong thư mục!", parent=self.root)
            return

        popup = Toplevel(self.root)
        popup.title("Tính mAP@50")
        popup.configure(bg=BG)
        popup.geometry("680x480")

        Label(popup, text="Đang tính mAP@50 ...",
              font=F_BOLD, bg=BG, fg=TEXT).pack(pady=(10, 4))

        pb = ttk.Progressbar(popup, mode="determinate", maximum=len(img_files))
        pb.pack(fill=X, padx=16, pady=(0, 6))

        self.v_map_progress = StringVar(value="0 / 0")
        Label(popup, textvariable=self.v_map_progress,
              font=F_MONO, bg=BG, fg=DIM).pack()

        txt_frame = Frame(popup, bg=BG)
        txt_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        sb_txt = Scrollbar(txt_frame, orient=VERTICAL)
        sb_txt.pack(side=RIGHT, fill=Y)
        result_text = Text(txt_frame, bg="#0d0d1a", fg=TEXT,
                           font=F_MONO, relief="flat", bd=0,
                           yscrollcommand=sb_txt.set, state=DISABLED)
        result_text.pack(fill=BOTH, expand=True)
        sb_txt.config(command=result_text.yview)

        def append(line):
            result_text.config(state=NORMAL)
            result_text.insert(END, line + "\n")
            result_text.see(END)
            result_text.config(state=DISABLED)

        def run():
            conf_val = max(self.v_conf_thresh.get(), self.slider_conf.get())
            iou_val = self.slider_iou.get()
            iou_thresh = 0.5

            tp_total = 0
            fp_total = 0
            fn_total = 0
            per_class_tp = {}
            per_class_fp = {}
            per_class_fn = {}

            processed = 0
            skipped = 0

            for i, img_path in enumerate(img_files):
                base = os.path.splitext(img_path)[0]
                lbl_path = base + ".txt"

                self.root.after(0, lambda v=i: pb.config(value=v))
                self.root.after(0, lambda v=i+1, t=len(img_files):
                                self.v_map_progress.set(f"{v} / {t}"))

                if not os.path.isfile(lbl_path):
                    skipped += 1
                    continue

                try:
                    gt_boxes = []
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 5:
                                cls_id = int(parts[0])
                                cx, cy, bw, bh = map(float, parts[1:])
                                gt_boxes.append((cls_id, cx, cy, bw, bh))

                    results = self.model.predict(
                        source=img_path,
                        conf=conf_val,
                        iou=iou_val,
                        imgsz=640,
                        agnostic_nms=True,
                        verbose=False,
                    )
                    pred_boxes = []
                    boxes_res = results[0].boxes
                    if boxes_res is not None:
                        for box in boxes_res:
                            cls_id = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            pred_boxes.append((cls_id, *xywhn))

                    matched_gt = set()
                    matched_pred = set()

                    for pi, pb_box in enumerate(pred_boxes):
                        p_cls = pb_box[0]
                        p_cx, p_cy, p_bw, p_bh = pb_box[1:]
                        best_iou = 0.0
                        best_gi = -1
                        for gi, gb_box in enumerate(gt_boxes):
                            if gi in matched_gt:
                                continue
                            g_cls = gb_box[0]
                            if g_cls != p_cls:
                                continue
                            g_cx, g_cy, g_bw, g_bh = gb_box[1:]
                            iou_v = _iou_xywhn(p_cx, p_cy, p_bw, p_bh,
                                               g_cx, g_cy, g_bw, g_bh)
                            if iou_v > best_iou:
                                best_iou = iou_v
                                best_gi = gi
                        if best_iou >= iou_thresh and best_gi >= 0:
                            matched_gt.add(best_gi)
                            matched_pred.add(pi)
                            tp_total += 1
                            per_class_tp[p_cls] = per_class_tp.get(p_cls, 0) + 1
                        else:
                            fp_total += 1
                            per_class_fp[p_cls] = per_class_fp.get(p_cls, 0) + 1

                    for gi, gb_box in enumerate(gt_boxes):
                        if gi not in matched_gt:
                            g_cls = gb_box[0]
                            fn_total += 1
                            per_class_fn[g_cls] = per_class_fn.get(g_cls, 0) + 1

                    processed += 1
                except Exception as ex:
                    self.root.after(0, lambda m=str(ex): append(f"  Lỗi: {m}"))

            precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
            recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)
                  if (precision + recall) > 0 else 0.0)
            map50 = precision * recall

            lines = [
                "=" * 52,
                f"Kết quả mAP@50 (IoU >= 0.5)",
                f"Thư mục: {folder}",
                f"Tổng ảnh: {len(img_files)}  |  Có nhãn: {processed}  |  Bỏ qua: {skipped}",
                "-" * 52,
                f"TP={tp_total}  FP={fp_total}  FN={fn_total}",
                f"Precision : {precision:.4f}",
                f"Recall    : {recall:.4f}",
                f"F1-Score  : {f1:.4f}",
                f"mAP@50    : {map50:.4f}",
                "-" * 52,
                "Chi tiết theo class:",
            ]
            all_cls = set(list(per_class_tp.keys())
                          + list(per_class_fp.keys())
                          + list(per_class_fn.keys()))
            for cls_id in sorted(all_cls):
                cname = self.model.names.get(cls_id, str(cls_id))
                tp_c = per_class_tp.get(cls_id, 0)
                fp_c = per_class_fp.get(cls_id, 0)
                fn_c = per_class_fn.get(cls_id, 0)
                p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                lines.append(
                    f"  [{cls_id}] {cname:<20}  P={p_c:.3f}  R={r_c:.3f}"
                    f"  TP={tp_c} FP={fp_c} FN={fn_c}")
            lines.append("=" * 52)

            self.root.after(0, lambda: pb.config(value=len(img_files)))
            for ln in lines:
                self.root.after(0, lambda l=ln: append(l))

        threading.Thread(target=run, daemon=True).start()


def _iou_xywhn(cx1, cy1, w1, h1, cx2, cy2, w2, h2):
    x1_min = cx1 - w1 / 2; x1_max = cx1 + w1 / 2
    y1_min = cy1 - h1 / 2; y1_max = cy1 + h1 / 2
    x2_min = cx2 - w2 / 2; x2_max = cx2 + w2 / 2
    y2_min = cy2 - h2 / 2; y2_max = cy2 + h2 / 2
    inter_x = max(0.0, min(x1_max, x2_max) - max(x1_min, x2_min))
    inter_y = max(0.0, min(y1_max, y2_max) - max(y1_min, y2_min))
    inter = inter_x * inter_y
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0.0
