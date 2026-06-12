import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
from ultralytics import YOLO
import os

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class YoloApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YOLO11 - Nhận diện với NMS & Dynamic Classes")
        self.root.geometry("1280x900")
        self.root.configure(bg="#f5f5f5")

        self.current_image_path = None
        self.model_path = "yolo11n.pt"
        self.model = None
        self.class_ids = []
        self.image_list = []

        self._build_ui()
        self.load_default_model()

    # ─────────────────────── BUILD UI ───────────────────────

    def _build_ui(self):
        # ── TOP: Control panel ──
        ctrl = tk.LabelFrame(self.root, text=" Bảng điều khiển ",
                             font=("Arial", 11, "bold"), bg="#f5f5f5", padx=15, pady=10)
        ctrl.pack(side=tk.TOP, fill=tk.X, padx=15, pady=10)

        # Buttons row
        btn_frame = tk.Frame(ctrl, bg="#f5f5f5")
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="📁 Chọn Model (.pt)", command=self.select_model,
                  font=("Arial", 11), bg="#4CAF50", fg="white", bd=0, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🖼️ Chọn Ảnh", command=self.select_image,
                  font=("Arial", 11), bg="#2196F3", fg="white", bd=0, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📂 Chọn Thư Mục", command=self.select_folder,
                  font=("Arial", 11), bg="#FF9800", fg="white", bd=0, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        self.lbl_model_info = tk.Label(btn_frame, text="Đang dùng: ...",
                                       font=("Arial", 10, "italic"), bg="#f5f5f5", fg="#666")
        self.lbl_model_info.pack(side=tk.LEFT, padx=15)

        # Sliders row
        sf = tk.Frame(ctrl, bg="#f5f5f5")
        sf.pack(fill=tk.X, pady=5)
        tk.Label(sf, text="Ngưỡng tin cậy (Conf):", font=("Arial", 10, "bold"), bg="#f5f5f5").grid(row=0, column=0, sticky="w", padx=5)
        self.slider_conf = ttk.Scale(sf, from_=0.01, to=1.0, value=0.30, orient=tk.HORIZONTAL, command=self.on_slider_change)
        self.slider_conf.grid(row=0, column=1, sticky="ew", padx=10)
        self.lbl_conf_val = tk.Label(sf, text="0.30", bg="#f5f5f5", width=5)
        self.lbl_conf_val.grid(row=0, column=2, padx=5)

        tk.Label(sf, text="Ngưỡng NMS (IoU):", font=("Arial", 10, "bold"), bg="#f5f5f5").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.slider_iou = ttk.Scale(sf, from_=0.01, to=1.0, value=0.45, orient=tk.HORIZONTAL, command=self.on_slider_change)
        self.slider_iou.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        self.lbl_iou_val = tk.Label(sf, text="0.45", bg="#f5f5f5", width=5)
        self.lbl_iou_val.grid(row=1, column=2, padx=5)
        sf.columnconfigure(1, weight=1)

        # Classes listbox
        cf = tk.Frame(ctrl, bg="#f5f5f5")
        cf.pack(fill=tk.X, pady=5)
        tk.Label(cf, text="Lọc Class (Click chọn nhiều. Bỏ trống = Nhận diện tất cả):",
                 font=("Arial", 10, "bold"), bg="#f5f5f5").pack(anchor="w", pady=(0, 3))
        sb = tk.Scrollbar(cf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox_classes = tk.Listbox(cf, selectmode=tk.MULTIPLE, yscrollcommand=sb.set,
                                          height=4, font=("Consolas", 10))
        self.listbox_classes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.listbox_classes.yview)
        self.listbox_classes.bind("<<ListboxSelect>>", lambda e: self.detect_and_display())

        # ── MAIN content area ──
        content = tk.Frame(self.root, bg="#f5f5f5")
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

        # Sidebar – image list
        self.sidebar = tk.Frame(content, bg="#ececec", width=190)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="Danh sách ảnh", font=("Arial", 10, "bold"),
                 bg="#ececec", fg="#444").pack(pady=(8, 3))
        sb2 = tk.Scrollbar(self.sidebar)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox_images = tk.Listbox(self.sidebar, yscrollcommand=sb2.set,
                                         font=("Arial", 9), selectmode=tk.SINGLE, activestyle="dotbox")
        self.listbox_images.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 8))
        sb2.config(command=self.listbox_images.yview)
        self.listbox_images.bind("<<ListboxSelect>>", self.on_image_select)

        # Right panel
        right = tk.Frame(content, bg="#f5f5f5")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.lbl_result = tk.Label(right, text="", font=("Arial", 10, "bold"),
                                   bg="#f5f5f5", anchor="w")
        self.lbl_result.pack(fill=tk.X, pady=(0, 3))

        # Drop-zone / display panel
        hint = ("⬇  Kéo & thả ảnh hoặc thư mục vào đây\n"
                "hoặc dùng nút bên trên để chọn") if HAS_DND else \
               "Dùng nút bên trên để chọn ảnh / thư mục\n(cài tkinterdnd2 để dùng kéo thả)"
        self.panel = tk.Label(right, text=hint, bg="#e8e8e8", fg="#aaa",
                              font=("Arial", 14), compound="center",
                              bd=2, relief="groove", wraplength=700, justify="center")
        self.panel.pack(fill=tk.BOTH, expand=True)

        if HAS_DND:
            self.panel.drop_target_register(DND_FILES)
            self.panel.dnd_bind("<<Drop>>", self.on_drop)

        # ── STATUS BAR ──
        self.status_bar = tk.Label(self.root, text="Sẵn sàng", font=("Arial", 9),
                                   bg="#ddd", fg="#555", anchor="w", padx=8)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ─────────────────────── DnD ───────────────────────

    def on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        # Single folder
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self.load_folder(paths[0])
            return
        # One or more image files
        images = [p for p in paths
                  if os.path.isfile(p) and os.path.splitext(p)[1].lower() in IMAGE_EXTS]
        if not images:
            messagebox.showwarning("Không hỗ trợ",
                                   "Chỉ hỗ trợ ảnh .jpg/.jpeg/.png/.bmp/.webp hoặc thư mục chứa ảnh.")
            return
        if len(images) == 1:
            self.image_list = []
            self.listbox_images.delete(0, tk.END)
            self._open_image(images[0])
        else:
            self._load_image_list(sorted(images))

    # ─────────────────────── FOLDER / IMAGE LOADING ───────────────────────

    def load_folder(self, folder_path):
        files = sorted([
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTS
        ])
        if not files:
            messagebox.showinfo("Thông báo", "Không tìm thấy ảnh trong thư mục!")
            return
        self._load_image_list(files)

    def _load_image_list(self, files):
        self.image_list = files
        self.listbox_images.delete(0, tk.END)
        for f in files:
            self.listbox_images.insert(tk.END, os.path.basename(f))
        self.listbox_images.selection_set(0)
        self._open_image(files[0])

    def _open_image(self, path):
        self.current_image_path = path
        # Sync sidebar selection
        if path in self.image_list:
            idx = self.image_list.index(path)
            self.listbox_images.selection_clear(0, tk.END)
            self.listbox_images.selection_set(idx)
            self.listbox_images.see(idx)
        n = len(self.image_list)
        label = f"{self.image_list.index(path)+1}/{n}  " if n else ""
        self.status_bar.config(text=f"{label}{os.path.basename(path)}")
        self.detect_and_display()

    def on_image_select(self, event):
        sel = self.listbox_images.curselection()
        if sel and self.image_list:
            path = self.image_list[sel[0]]
            if path != self.current_image_path:
                self._open_image(path)

    def select_folder(self):
        if self.model is None:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn model trước!")
            return
        folder = filedialog.askdirectory(title="Chọn thư mục ảnh")
        if folder:
            self.load_folder(folder)

    def select_image(self):
        if self.model is None:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn model trước!")
            return
        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if path:
            self.image_list = []
            self.listbox_images.delete(0, tk.END)
            self._open_image(path)

    # ─────────────────────── MODEL ───────────────────────

    def update_ui_model_info(self, filename):
        self.lbl_model_info.config(text=f"Đang dùng: {filename}")
        self.listbox_classes.delete(0, tk.END)
        self.class_ids.clear()
        if self.model and hasattr(self.model, "names"):
            for cid, cname in self.model.names.items():
                self.class_ids.append(cid)
                self.listbox_classes.insert(tk.END, f"[{cid}] {cname}")

    def load_default_model(self):
        try:
            self.model = YOLO(self.model_path)
            self.update_ui_model_info(self.model_path)
        except Exception as e:
            print(f"Chưa có model mặc định: {e}")

    def select_model(self):
        path = filedialog.askopenfilename(
            title="Chọn file model",
            filetypes=[("PyTorch Model", "*.pt")])
        if path:
            try:
                self.model_path = path
                self.model = YOLO(self.model_path)
                self.update_ui_model_info(os.path.basename(path))
                if self.current_image_path:
                    self.detect_and_display()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể load model:\n{e}")

    # ─────────────────────── SLIDERS ───────────────────────

    def on_slider_change(self, _):
        self.lbl_conf_val.config(text=f"{self.slider_conf.get():.2f}")
        self.lbl_iou_val.config(text=f"{self.slider_iou.get():.2f}")
        if self.current_image_path:
            self.detect_and_display()

    # ─────────────────────── DETECTION ───────────────────────

    def detect_and_display(self):
        if not self.current_image_path or not self.model:
            return
        try:
            selected_indices = self.listbox_classes.curselection()
            selected_classes = [self.class_ids[i] for i in selected_indices] if selected_indices else None

            results = self.model.predict(
                source=self.current_image_path,
                classes=selected_classes,
                conf=self.slider_conf.get(),
                iou=self.slider_iou.get(),
                imgsz=640,
                agnostic_nms=True,
                verbose=False
            )

            # ── Result summary ──
            boxes = results[0].boxes
            n_det = len(boxes) if boxes is not None else 0
            if n_det > 0:
                counts = {}
                for cls_id in boxes.cls.tolist():
                    name = self.model.names[int(cls_id)]
                    counts[name] = counts.get(name, 0) + 1
                summary = "  |  ".join(f"{n}: {c}" for n, c in counts.items())
                self.lbl_result.config(text=f"✅ Phát hiện {n_det} đối tượng  ─  {summary}", fg="#1a7a1a")
            else:
                self.lbl_result.config(text="❌ Không phát hiện đối tượng nào", fg="#cc0000")

            # ── Draw & display ──
            annotated = results[0].plot(line_width=2, font_size=11)
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)

            self.root.update_idletasks()
            w = max(self.panel.winfo_width(), 800)
            h = max(self.panel.winfo_height(), 400)
            pil_img.thumbnail((w - 10, h - 10), Image.Resampling.LANCZOS)

            imgtk = ImageTk.PhotoImage(image=pil_img)
            self.panel.config(image=imgtk, text="")
            self.panel.image = imgtk

        except Exception as e:
            print(f"Lỗi render: {e}")
            self.lbl_result.config(text=f"Lỗi: {e}", fg="#cc0000")


if __name__ == "__main__":
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    app = YoloApp(root)
    root.mainloop()
