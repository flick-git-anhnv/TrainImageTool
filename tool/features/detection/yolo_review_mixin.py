# yolo_review_mixin.py — YoloReviewMixin — lưu ảnh/nhãn, đánh dấu review đúng/sai
import os
import shutil
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
from .yolo_onnx import _REVIEW_ICON


class YoloReviewMixin:
    """Mixin: lưu ảnh + nhãn, đánh dấu review (correct/incorrect)."""

    def _save_image_and_label(self, path: str, state: str) -> bool:
        """Move image + write detection label vào true/ hoặc false/ subfolder.
        Trả về True nếu di chuyển thành công."""
        if not os.path.isfile(path):
            return False
        sub = "true" if state == "correct" else "false"
        # Luôn dùng _base_folder; nếu ảnh đang ở true/ hoặc false/ thì dùng grandparent
        parent_name = os.path.basename(os.path.dirname(path))
        if parent_name in ("true", "false"):
            root = os.path.dirname(os.path.dirname(path))
        else:
            root = self._base_folder or os.path.dirname(path)
        dest_dir = os.path.join(root, sub)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_img = os.path.join(dest_dir, os.path.basename(path))
            shutil.move(path, dest_img)

            base = os.path.splitext(os.path.basename(path))[0]
            boxes = (self._last_results1[0].boxes
                     if self._last_results1 is not None else None)
            with open(os.path.join(dest_dir, f"{base}.txt"), "w", encoding="utf-8") as f:
                if boxes is not None and len(boxes):
                    for box in boxes:
                        cid = int(box.cls[0])
                        cx, cy, bw, bh = box.xywhn[0].tolist()
                        f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

            icon = "✓" if state == "correct" else "✗"
            self.v_status.set(
                f"{icon} Đã chuyển vào {sub}/: {os.path.basename(path)}")
            return True
        except Exception as e:
            self.v_status.set(f"Lỗi di chuyển: {e}")
            return False

    def _save_page_image(self, path: str) -> bool:
        """Move 1 ảnh vào true/ + ghi label từ _det_cache (không dùng _last_results1)."""
        if not os.path.isfile(path):
            return False
        parent_name = os.path.basename(os.path.dirname(path))
        if parent_name in ("true", "false"):
            root = os.path.dirname(os.path.dirname(path))
        else:
            root = self._base_folder or os.path.dirname(path)
        dest_dir = os.path.join(root, "true")
        try:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(path, os.path.join(dest_dir, os.path.basename(path)))
            base = os.path.splitext(os.path.basename(path))[0]
            with self._det_cache_lock:
                det = self._det_cache.get(path)
            with open(os.path.join(dest_dir, f"{base}.txt"), "w", encoding="utf-8") as f:
                if det and det.get("boxes"):
                    for box_t in det["boxes"]:
                        cid, cx, cy, bw, bh = box_t[0], box_t[1], box_t[2], box_t[3], box_t[4]
                        f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            return True
        except Exception:
            return False

    def _mark_page_correct(self):
        """Batch-đánh dấu đúng toàn trang — move file + ghi label, không navigate."""
        if not self._grid_cells:
            return
        paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not paths:
            return

        do_move  = bool(self._base_folder)
        moved    = []
        marked   = []
        icon     = _REVIEW_ICON.get("correct", "✓")

        # Unbind TreeviewSelect để tránh trigger navigation khi update tree items
        self.tree_images.unbind("<<TreeviewSelect>>")
        try:
            for p in paths:
                if do_move:
                    ok = self._save_page_image(p)
                    if ok:
                        moved.append(p)
                    else:
                        # Move thất bại → chỉ mark in-memory
                        self._review_state[p] = "correct"
                        marked.append(p)
                else:
                    self._review_state[p] = "correct"
                    marked.append(p)

                # Cập nhật tree icon (ảnh đã move sẽ biến mất sau _apply_filter)
                iid = self._path_to_iid.get(p)
                if iid:
                    try:
                        if self.tree_images.exists(iid):
                            old  = self.tree_images.item(iid, "text")
                            bare = old[2:] if len(old) > 2 else old
                            self.tree_images.item(iid,
                                                  text=f"{icon} {bare}",
                                                  tags=("correct",))
                    except Exception:
                        pass
        finally:
            self.tree_images.bind("<<TreeviewSelect>>", self._on_image_select)

        # Cập nhật tracking structures cho ảnh đã move
        for p in moved:
            self._review_state.pop(p, None)
            if p in self._all_images:
                self._all_images.remove(p)
            if p in self._det_cache:
                with self._det_cache_lock:
                    self._det_cache.pop(p, None)

        changed = len(moved) + len(marked)
        if changed:
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            # Refresh list + counts một lần duy nhất
            self._apply_filter(self._active_filter)
            self._update_filter_counts()

        self.lbl_mark_state.config(text=f"✓ {changed} ảnh", fg=SUCCESS)
        self.after(2500, lambda: self.lbl_mark_state.config(text=""))

    def _mark_page_incorrect(self):
        """Batch-đánh dấu sai toàn trang — move file vào false/ + ghi label."""
        if not self._grid_cells:
            return
        paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not paths:
            return

        icon  = _REVIEW_ICON.get("incorrect", "✗")
        moved = []
        marked = []

        self.tree_images.unbind("<<TreeviewSelect>>")
        try:
            for p in paths:
                if self._base_folder:
                    ok = self._save_image_and_label(p, "incorrect")
                    if ok:
                        moved.append(p)
                    else:
                        self._review_state[p] = "incorrect"
                        marked.append(p)
                else:
                    self._review_state[p] = "incorrect"
                    marked.append(p)

                iid = self._path_to_iid.get(p)
                if iid:
                    try:
                        if self.tree_images.exists(iid):
                            old  = self.tree_images.item(iid, "text")
                            bare = old[2:] if len(old) > 2 else old
                            self.tree_images.item(iid,
                                                  text=f"{icon} {bare}",
                                                  tags=("incorrect",))
                    except Exception:
                        pass
        finally:
            self.tree_images.bind("<<TreeviewSelect>>", self._on_image_select)

        for p in moved:
            self._review_state.pop(p, None)
            if p in self._all_images:
                self._all_images.remove(p)
            with self._det_cache_lock:
                self._det_cache.pop(p, None)

        changed = len(moved) + len(marked)
        if changed:
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            self._apply_filter(self._active_filter)
            self._update_filter_counts()

        self.lbl_mark_state.config(text=f"✗ {changed} ảnh", fg=ACCENT)
        self.after(2500, lambda: self.lbl_mark_state.config(text=""))

    def _mark_review(self, state: str):
        path = self.current_image_path
        if not path:
            return

        # Update status label
        icons = {"correct": "✓ Đúng", "incorrect": "✗ Sai", "": "↺ Đã xóa"}
        self.lbl_mark_state.config(
            text=icons.get(state, ""),
            fg=("#4caf50" if state == "correct"
                else ACCENT if state == "incorrect" else DIM))

        if state in ("correct", "incorrect"):
            moved = self._save_image_and_label(path, state)
            if moved:
                # Remove from all tracking data structures
                self._review_state.pop(path, None)
                _CFG["yolo.review_states"] = self._review_state
                _cfg_save()

                old_idx = (self.image_list.index(path)
                           if path in self.image_list else 0)
                # Remove from unreviewed list if it was there
                if path in self._all_images:
                    self._all_images.remove(path)
                self.current_image_path = None
                self._last_results1 = None

                self._apply_filter(self._active_filter)
                self._update_filter_counts()
                if self.image_list:
                    next_idx = min(old_idx, len(self.image_list) - 1)
                    self._open_image(self.image_list[next_idx])
                return

        # No move (unmark or move failed) — update state + tag only
        if state:
            self._review_state[path] = state
        else:
            self._review_state.pop(path, None)
        _CFG["yolo.review_states"] = self._review_state
        _cfg_save()

        iid = self._path_to_iid.get(path)
        if iid and self.tree_images.exists(iid):
            icon = _REVIEW_ICON[state]
            old_text = self.tree_images.item(iid, "text")
            bare = old_text[2:] if len(old_text) > 2 else old_text
            self.tree_images.item(iid,
                                  text=f"{icon} {bare}",
                                  tags=(state or "unreviewed",))
        self._update_filter_counts()
