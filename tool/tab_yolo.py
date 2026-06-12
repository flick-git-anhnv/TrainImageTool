# tab_yolo.py — YOLO Detection tab (adapted from app.py)
import os
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
        self.class_ids = []
        self.image_list = []
        self._photo_ref = None

        self.v_model_path = StringVar()
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

        # Row 0 — model & file buttons
        r0 = Frame(top, bg=CARD)
        r0.pack(fill=X)

        Button(r0, text="Chọn Model (.pt)", command=self._select_model,
               bg=ACCENT2, fg="white", font=F_BOLD, relief="flat",
               padx=10, cursor="hand2",
               activebackground=ACCENT, activeforeground="white",
               ).pack(side=LEFT)

        self.lbl_model = Label(r0, text="Chưa chọn model",
                               font=("Segoe UI", 9, "italic"),
                               bg=CARD, fg=DIM)
        self.lbl_model.pack(side=LEFT, padx=(10, 20))

        Button(r0, text="Chọn Ảnh", command=self._select_image,
               bg=ACCENT, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#c0411a", activeforeground="white",
               ).pack(side=LEFT, padx=(0, 4))

        Button(r0, text="Chọn Thư Mục", command=self._select_folder,
               bg="#2e5fa3", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=LEFT)

        # Row 1 — sliders
        r1 = Frame(top, bg=CARD)
        r1.pack(fill=X, pady=(8, 0))

        Label(r1, text="Conf:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_conf = ttk.Scale(r1, from_=0.01, to=1.0, value=0.30,
                                      orient=HORIZONTAL, length=180,
                                      command=self._on_slider_change)
        self.slider_conf.pack(side=LEFT, padx=(4, 2))
        self.lbl_conf = Label(r1, text="0.30", bg=CARD, fg=TEXT,
                               font=F_MONO, width=5)
        self.lbl_conf.pack(side=LEFT)

        Label(r1, text="  IoU:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_iou = ttk.Scale(r1, from_=0.01, to=1.0, value=0.45,
                                     orient=HORIZONTAL, length=180,
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

        # Right — result label + image canvas
        right = Frame(content, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_result = Label(right, text="", font=F_BOLD,
                                 bg=BG, fg=TEXT, anchor=W)
        self.lbl_result.pack(fill=X, padx=6, pady=(4, 0))

        self.canvas = Label(right,
                             text="Chọn ảnh để nhận diện",
                             bg="#0d0d1a", fg=DIM,
                             font=("Segoe UI", 14),
                             compound="center",
                             relief="flat")
        self.canvas.pack(fill=BOTH, expand=True, padx=0, pady=2)

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
            title="Chọn file model YOLO (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")],
            parent=self.root)
        if path:
            self._load_model(path)

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
            # try default yolo11n.pt next to train-image-tool.py
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

    def _on_slider_change(self, _=None):
        self.lbl_conf.config(text=f"{self.slider_conf.get():.2f}")
        self.lbl_iou.config( text=f"{self.slider_iou.get():.2f}")
        if self.current_image_path:
            self._detect_and_display()

    def _detect_and_display(self):
        if not self.current_image_path or not self.model:
            return
        if not _PIL_OK or not _CV2_OK:
            self.lbl_result.config(
                text="Cần cài: pip install Pillow opencv-python", fg=ACCENT)
            return
        try:
            sel_idx = self.lb_classes.curselection()
            sel_cls = ([self.class_ids[i] for i in sel_idx]
                       if sel_idx else None)

            results = self.model.predict(
                source=self.current_image_path,
                classes=sel_cls,
                conf=self.slider_conf.get(),
                iou=self.slider_iou.get(),
                imgsz=640,
                agnostic_nms=True,
                verbose=False,
            )

            boxes  = results[0].boxes
            n_det  = len(boxes) if boxes is not None else 0
            if n_det > 0:
                counts = {}
                for cls_id in boxes.cls.tolist():
                    name = self.model.names[int(cls_id)]
                    counts[name] = counts.get(name, 0) + 1
                summary = "  |  ".join(f"{n}: {c}" for n, c in counts.items())
                self.lbl_result.config(
                    text=f"Phát hiện {n_det} đối tượng  —  {summary}",
                    fg=SUCCESS)
            else:
                self.lbl_result.config(
                    text="Không phát hiện đối tượng nào", fg=DIM)

            annotated = results[0].plot(line_width=2, font_size=11)
            rgb       = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            pil_img   = Image.fromarray(rgb)

            self.root.update_idletasks()
            w = max(self.canvas.winfo_width(),  800)
            h = max(self.canvas.winfo_height(), 400)
            pil_img.thumbnail((w - 10, h - 10), Image.Resampling.LANCZOS)

            self._photo_ref = ImageTk.PhotoImage(image=pil_img)
            self.canvas.config(image=self._photo_ref, text="")

        except Exception as e:
            self.lbl_result.config(text=f"Lỗi: {e}", fg=ACCENT)
