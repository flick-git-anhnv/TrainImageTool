# yolo_imagelist_mixin.py — YoloImageListMixin — scan/lọc/hiển thị danh sách ảnh trong thư mục
import os
import fnmatch
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
from .yolo_onnx import _REVIEW_ICON
from .yolo_utils import _path_review_state


class YoloImageListMixin:
    """Mixin: quét thư mục, load danh sách ảnh, lọc/tìm kiếm, drag-drop."""

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
        self._load_image_list(sorted(imgs))

    def _load_path_input(self):
        p = self.v_check_folder.get().strip()
        if not p:
            return
        if not self.model:
            messagebox.showwarning("Chưa có model", "Vui lòng chọn model trước.",
                                   parent=self.root)
            return
        if os.path.isdir(p):
            _push_history("h.yolo.path", p)
            self.combo_path["values"] = _get_history("h.yolo.path")
            self._load_folder(p)
        elif os.path.isfile(p):
            _push_history("h.yolo.path", p)
            self.combo_path["values"] = _get_history("h.yolo.path")
            self._load_image_list([p])
        else:
            messagebox.showwarning("Không tìm thấy",
                                   f"Đường dẫn không hợp lệ:\n{p}", parent=self.root)

    def _select_image(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        cur = self.v_check_folder.get().strip()
        init = (os.path.dirname(cur) if cur and os.path.isfile(cur)
                else cur if cur and os.path.isdir(cur)
                else _cfg_dir("yolo.last_image_dir") or None)
        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            initialdir=init,
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp")],
            parent=self.root)
        if path:
            self._update_path_combo(path)
            self._load_image_list([path])

    def _open_check_folder(self):
        p = self.v_check_folder.get().strip()
        d = p if os.path.isdir(p) else os.path.dirname(p) if p else ""
        if d and os.path.isdir(d):
            os.startfile(d)

    def _select_folder(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        cur = self.v_check_folder.get().strip()
        init = (cur if cur and os.path.isdir(cur)
                else os.path.dirname(cur) if cur
                else _cfg_dir("yolo.check_folder") or None)
        folder = filedialog.askdirectory(
            title="Chọn thư mục kiểm tra",
            initialdir=init,
            parent=self.root)
        if folder:
            self._update_path_combo(folder)
            self._load_folder(folder)

    def _scan_images(self, folder: str) -> list:
        """Trả về list ảnh trực tiếp trong folder (không đệ quy vào true/false)."""
        if not folder or not os.path.isdir(folder):
            return []
        return sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])

    def _load_folder(self, folder: str):
        self._base_folder = folder
        _SKIP = {"true", "false"}
        if self.v_subfolder.get():
            files = sorted([
                os.path.join(root, f)
                for root, dirs, fnames in os.walk(folder)
                for f in fnames
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
                and os.path.basename(root) not in _SKIP
            ])
            # prune true/false from os.walk in-place
        else:
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
        self._all_images = list(files)
        self._det_cache.clear()
        with self._lpr_cache_lock:
            self._lpr_cache.clear()
        self._grid_rendered_cache.clear()
        self._grid_page = 0
        if hasattr(self, "lbl_cache_info"):
            self.lbl_cache_info.config(text="")
        if hasattr(self, "_flt_class_combo"):
            self._flt_class_combo["values"] = ["Tất cả", "Không detect"]
            self._flt_class_var.set("Tất cả")
        if not self._base_folder and files:
            self._base_folder = os.path.dirname(files[0])
        # Thử load cache từ disk (nếu model đã load và iou khớp)
        _cache_loaded = self._load_det_cache_from_disk()
        if hasattr(self, "lbl_cache_info") and _cache_loaded:
            n_cached = len(self._det_cache)
            self.lbl_cache_info.config(text=f"✓{n_cached}/{len(files)} (disk)")
            self.after(0, self._update_class_filter_combo)
        self._active_filter = "all"
        for code, btn in self._filter_btns.items():
            btn.config(relief="sunken" if code == "all" else "flat",
                       bg="#252540" if code == "all" else CARD)
        self._rebuild_tree(files)
        self._update_filter_counts()
        if files:
            # Lưu folder vào session
            _CFG["yolo.session.folder"] = self._base_folder or os.path.dirname(files[0])
            _cfg_save()
            self._open_image(files[0])

    def _rebuild_tree(self, files: list):
        """Rebuild the sidebar tree from a (possibly filtered) file list."""
        self.image_list = list(files)
        self._tree_iid_map = {}
        self._path_to_iid = {}
        tree = self.tree_images
        tree.delete(*tree.get_children())

        use_hierarchy = (len(self._all_images) > 1
                         and self.v_subfolder.get()
                         and self._all_images)
        base_dir = os.path.commonpath(self._all_images) if use_hierarchy else None

        if base_dir and files:
            folder_iids = {}
            for f in files:
                state = _path_review_state(f)
                tag = state or "unreviewed"
                icon = _REVIEW_ICON[state]
                try:
                    rel = os.path.relpath(f, base_dir)
                    parts = rel.replace("\\", "/").split("/")
                except ValueError:
                    parts = [os.path.basename(f)]
                parent_iid = ""
                for depth, part in enumerate(parts[:-1]):
                    folder_key = "/".join(parts[:depth + 1])
                    if folder_key not in folder_iids:
                        iid = tree.insert(parent_iid, END,
                                          text=f"\U0001f4c1 {part}",
                                          open=True, tags=("folder",))
                        folder_iids[folder_key] = iid
                    parent_iid = folder_iids[folder_key]
                iid = tree.insert(parent_iid, END,
                                  text=f"{icon} {parts[-1]}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f] = iid
        else:
            for f in files:
                state = _path_review_state(f)
                tag = state or "unreviewed"
                icon = _REVIEW_ICON[state]
                iid = tree.insert("", END,
                                  text=f"{icon} {os.path.basename(f)}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f] = iid

        # Re-select current image if still in this list
        iid = self._path_to_iid.get(self.current_image_path)
        if iid:
            tree.selection_set(iid)
            tree.see(iid)

        self._schedule_grid_rebuild()

    def _schedule_search(self):
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(300,
            lambda: self._apply_filter(self._active_filter))

    def _toggle_search_hint(self):
        if self._hint_shown:
            self._hint_frame.pack_forget()
            self._hint_toggle_btn.config(text="?", fg="#6060a0")
        else:
            self._hint_frame.pack(fill=X, padx=4, pady=(0, 3),
                                   after=self._search_row_ref)
            self._hint_toggle_btn.config(text="▲", fg=ACCENT2)
        self._hint_shown = not self._hint_shown

    def _do_search(self):
        """Push keyword vào history rồi áp dụng filter."""
        val = self._v_search.get().strip()
        if val:
            _push_history("h.yolo.search", val)
            self._search_combo["values"] = _get_history("h.yolo.search")
        self._apply_filter(self._active_filter)

    def _apply_filter(self, filter_type: str):
        self._active_filter = filter_type
        for code, btn in self._filter_btns.items():
            btn.config(relief="sunken" if code == filter_type else "flat",
                       bg="#252540" if code == filter_type else CARD)
        base = self._base_folder
        if filter_type == "correct":
            filtered = self._scan_images(os.path.join(base, "true")) if base else []
        elif filter_type == "incorrect":
            filtered = self._scan_images(os.path.join(base, "false")) if base else []
        elif filter_type == "unreviewed":
            filtered = list(self._all_images)
        else:  # "all"
            true_imgs  = self._scan_images(os.path.join(base, "true"))  if base else []
            false_imgs = self._scan_images(os.path.join(base, "false")) if base else []
            filtered = list(self._all_images) + true_imgs + false_imgs
        search = self._v_search.get().strip().lower()
        if search:
            terms = search.split()
            _base = self._base_folder or ""
            def _matches(f, ts=terms, b=_base):
                name = os.path.basename(f).lower()
                try:
                    rel = os.path.relpath(f, b).replace("\\", "/").lower() if b else f.lower()
                except ValueError:
                    rel = f.lower()
                for t in ts:
                    if "*" in t or "?" in t:
                        if not fnmatch.fnmatch(name, t):
                            return False
                    else:
                        if t not in rel:
                            return False
                return True
            filtered = [f for f in filtered if _matches(f)]
        filtered = self._apply_det_filters(filtered)
        self._rebuild_tree(filtered)

    def _update_filter_counts(self):
        if not hasattr(self, "_filter_btns"):
            return
        base = self._base_folder
        # Đếm từ _review_state (in-memory marks) + filesystem (moved files)
        n_mem_ok  = sum(1 for p in self._all_images
                        if self._review_state.get(p) == "correct")
        n_mem_bad = sum(1 for p in self._all_images
                        if self._review_state.get(p) == "incorrect")
        n_unmarked = len(self._all_images) - n_mem_ok - n_mem_bad
        n_fs_ok  = len(self._scan_images(os.path.join(base, "true")))  if base else 0
        n_fs_bad = len(self._scan_images(os.path.join(base, "false"))) if base else 0
        n_ok  = n_mem_ok  + n_fs_ok
        n_bad = n_mem_bad + n_fs_bad
        n_all = len(self._all_images) + n_fs_ok + n_fs_bad
        for code, label in [("all",        f"All({n_all})"),
                             ("correct",    f"✓({n_ok})"),
                             ("incorrect",  f"✗({n_bad})"),
                             ("unreviewed", f"?({n_unmarked})")]:
            self._filter_btns[code].config(text=label)
