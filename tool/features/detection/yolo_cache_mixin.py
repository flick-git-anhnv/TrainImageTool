# yolo_cache_mixin.py — YoloCacheMixin — cache kết quả detect (RAM + disk) và bộ lọc
import os
import threading
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
from .yolo_onnx import _THUMB_PALETTE


class YoloCacheMixin:
    """Mixin: cache kết quả Detect All (RAM + disk), bộ lọc theo class/kích thước."""

    def _cache_sv_result(self, img_path: str, dets):
        """Lưu sv.Detections / _OnnxDetResult vào _det_cache (dạng box tuple)."""
        if dets is None:
            return
        try:
            from PIL import Image as _Img
            iw, ih = _Img.open(img_path).size
        except Exception:
            iw = ih = 1
        box_list = []
        classes_count = {}
        try:
            xyxy_arr = dets.xyxy
            conf_arr = dets.confidence
            cls_arr  = dets.class_id
            if xyxy_arr is None or len(xyxy_arr) == 0:
                with self._det_cache_lock:
                    self._det_cache[img_path] = {"n": 0, "classes": {}, "boxes": []}
                return
            for i in range(len(xyxy_arr)):
                x1, y1, x2, y2 = float(xyxy_arr[i][0]), float(xyxy_arr[i][1]), \
                                  float(xyxy_arr[i][2]), float(xyxy_arr[i][3])
                cid  = int(cls_arr[i]) if cls_arr is not None and i < len(cls_arr) else 0
                conf = float(conf_arr[i]) if conf_arr is not None and i < len(conf_arr) else 1.0
                cx_n = ((x1 + x2) / 2) / iw
                cy_n = ((y1 + y2) / 2) / ih
                w_n  = (x2 - x1) / iw
                h_n  = (y2 - y1) / ih
                w_px = x2 - x1
                h_px = y2 - y1
                box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf))
                classes_count[cid] = classes_count.get(cid, 0) + 1
        except Exception:
            pass
        with self._det_cache_lock:
            self._det_cache[img_path] = {"n": len(box_list),
                                          "classes": classes_count,
                                          "boxes": box_list}

    def _sv_summary(self, dets, names: dict) -> str:
        """Tạo chuỗi tóm tắt 'name: count | ...' từ sv.Detections / _OnnxDetResult."""
        if dets is None:
            return ""
        try:
            cls_arr = dets.class_id
            if cls_arr is None or len(cls_arr) == 0:
                return ""
            cnt = {}
            for c in cls_arr:
                cid = int(c)
                cnt[cid] = cnt.get(cid, 0) + 1
            return "  |  ".join(f"{names.get(k, str(k))}: {v}" for k, v in cnt.items())
        except Exception:
            return ""

    def _update_class_filter_combo(self):
        if not hasattr(self, "_flt_class_combo"):
            return
        all_classes = {}
        with self._det_cache_lock:
            snapshot = list(self._det_cache.values())
        for data in snapshot:
            for cid in data["classes"]:
                name = (self.model.names.get(cid, str(cid))
                        if self.model and hasattr(self.model, "names") else str(cid))
                all_classes[cid] = name
        vals = (["Tất cả", "Không detect"] +
                [f"[{cid}] {name}" for cid, name in sorted(all_classes.items())])
        cur = self._flt_class_var.get()
        self._flt_class_combo["values"] = vals
        if cur not in vals:
            self._flt_class_var.set("Tất cả")
        self._update_must_have_lists()

    # ================================================= CACHE DISK PERSISTENCE ==

    def _save_det_cache_to_disk(self):
        """Lưu _det_cache ra file JSON trong folder (background thread, atomic write)."""
        folder = self._base_folder
        if not folder or not os.path.isdir(folder):
            return
        cache_file = os.path.join(folder, ".kztek_det_cache.json")
        model_path = self.v_model_path.get()
        conf = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou  = self.v_iou.get()

        # Snapshot toàn bộ cache trên main thread (thread-safe)
        try:
            with self._det_cache_lock:
                data = {
                    k: {
                        "n": v["n"],
                        "classes": {str(ck): cv for ck, cv in v["classes"].items()},
                        "boxes": [list(b) for b in v["boxes"]],
                    }
                    for k, v in self._det_cache.items()
                }
        except Exception as e:
            if hasattr(self, "v_status"):
                self.v_status.set(f"⚠ Snapshot cache lỗi: {e}")
            return

        payload = {
            "meta": {"model": model_path, "conf": round(conf, 4),
                     "iou": round(iou, 4), "version": 1},
            "data": data,
        }
        n = len(data)

        def _write():
            import json as _json
            tmp_file = cache_file + ".tmp"
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    _json.dump(payload, f, ensure_ascii=False)
                # Atomic rename — tránh corrupt nếu crash giữa chừng
                try:
                    os.replace(tmp_file, cache_file)
                except Exception:
                    os.rename(tmp_file, cache_file)
                self.root.after(0, lambda: (
                    hasattr(self, "lbl_cache_info") and
                    self.lbl_cache_info.config(text=f"✓{n} (đã lưu)")))
            except Exception as e:
                try:
                    if os.path.isfile(tmp_file):
                        os.remove(tmp_file)
                except Exception:
                    pass
                err = str(e)
                self.root.after(0, lambda msg=err: (
                    hasattr(self, "v_status") and
                    self.v_status.set(f"⚠ Lưu cache thất bại: {msg}")))

        threading.Thread(target=_write, daemon=True).start()

    def _load_det_cache_from_disk(self) -> bool:
        """Load _det_cache từ file JSON nếu model + iou khớp.
        Trả về True nếu load được ít nhất 1 ảnh."""
        import json as _json
        folder = self._base_folder
        if not folder or not os.path.isdir(folder):
            return False
        cache_file = os.path.join(folder, ".kztek_det_cache.json")
        if not os.path.isfile(cache_file):
            return False
        model_path = self.v_model_path.get()
        if not model_path:
            return False
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = _json.load(f)
            meta = payload.get("meta", {})
            # Invalidate nếu model hoặc iou thay đổi (conf có thể filter lại display-time)
            if meta.get("model") != model_path:
                return False
            if abs(meta.get("iou", 0.0) - self.v_iou.get()) > 0.005:
                return False
            data = payload.get("data", {})
            # Dùng set từ _all_images thay vì os.path.isfile() để tránh 16k I/O calls
            valid_nc = {os.path.normcase(p) for p in self._all_images} if self._all_images else None
            loaded = {}
            for img_path, v in data.items():
                if valid_nc is not None and os.path.normcase(img_path) not in valid_nc:
                    continue
                loaded[img_path] = {
                    "n": v["n"],
                    "classes": {int(ck): cv for ck, cv in v.get("classes", {}).items()},
                    "boxes": [tuple(b) for b in v.get("boxes", [])],
                }
            if not loaded:
                return False
            with self._det_cache_lock:
                self._det_cache.update(loaded)
            return True
        except Exception:
            return False

    def _clear_cache(self):
        """Xóa toàn bộ detect cache (memory + file disk)."""
        with self._det_cache_lock:
            self._det_cache.clear()
        self._grid_rendered_cache.clear()
        folder = self._base_folder
        if folder:
            cache_file = os.path.join(folder, ".kztek_det_cache.json")
            try:
                if os.path.isfile(cache_file):
                    os.remove(cache_file)
            except Exception:
                pass
        if hasattr(self, "lbl_cache_info"):
            self.lbl_cache_info.config(text="")
        self._schedule_grid_rebuild()

    def _schedule_det_filter(self):
        if self._flt_schedule_after:
            self.after_cancel(self._flt_schedule_after)
        self._flt_schedule_after = self.after(
            300, lambda: self._apply_filter(self._active_filter))

    def _clear_det_filters(self):
        self._flt_class_var.set("Tất cả")
        self._flt_ndet_min_var.set("")
        self._flt_ndet_max_var.set("")
        self._flt_area_min_var.set("")
        self._flt_area_max_var.set("")
        self._flt_w_min_var.set("")
        self._flt_w_max_var.set("")
        self._flt_h_min_var.set("")
        self._flt_h_max_var.set("")
        if hasattr(self, "_must_have_lb"):
            self._must_have_lb.selection_clear(0, END)
        if hasattr(self, "_must_not_lb"):
            self._must_not_lb.selection_clear(0, END)
        self._flt_lpr_var.set("Tất cả")
        self._apply_filter(self._active_filter)

    def _get_must_have_ids(self) -> set:
        if not hasattr(self, "_must_have_lb"):
            return set()
        try:
            return {int(self._must_have_lb.get(i).split("]")[0].lstrip("["))
                    for i in self._must_have_lb.curselection()}
        except Exception:
            return set()

    def _get_must_not_have_ids(self) -> set:
        if not hasattr(self, "_must_not_lb"):
            return set()
        try:
            return {int(self._must_not_lb.get(i).split("]")[0].lstrip("["))
                    for i in self._must_not_lb.curselection()}
        except Exception:
            return set()

    def _update_must_have_lists(self):
        """Điền danh sách class vào 2 listbox phải/không có nhãn."""
        if not hasattr(self, "_must_have_lb"):
            return
        all_classes: dict = {}
        if self.model and hasattr(self.model, "names"):
            all_classes = dict(self.model.names)
        elif self._det_cache:
            with self._det_cache_lock:
                snapshot = list(self._det_cache.values())
            for data in snapshot:
                for cid in data["classes"]:
                    all_classes.setdefault(cid, str(cid))
        mh_sel = set(self._must_have_lb.curselection())
        mn_sel = set(self._must_not_lb.curselection())
        self._must_have_lb.delete(0, END)
        self._must_not_lb.delete(0, END)
        for cid, name in sorted(all_classes.items()):
            color = _THUMB_PALETTE[cid % len(_THUMB_PALETTE)]
            label = f"[{cid}] {name}"
            self._must_have_lb.insert(END, label)
            self._must_have_lb.itemconfig(END, fg=color)
            self._must_not_lb.insert(END, label)
            self._must_not_lb.itemconfig(END, fg=color)
        # Khôi phục selection (nếu list không thay đổi)
        for i in mh_sel:
            if i < self._must_have_lb.size():
                self._must_have_lb.selection_set(i)
        for i in mn_sel:
            if i < self._must_not_lb.size():
                self._must_not_lb.selection_set(i)

    def _apply_det_filters(self, files: list) -> list:
        """Lọc ảnh theo detect cache (class, n_det, kích thước bbox)."""
        def _fv(var):
            v = var.get().strip()
            try: return float(v) if v else None
            except ValueError: return None

        cls_filter    = self._flt_class_var.get()
        ndet_min      = _fv(self._flt_ndet_min_var)
        ndet_max      = _fv(self._flt_ndet_max_var)
        area_min      = _fv(self._flt_area_min_var)
        area_max      = _fv(self._flt_area_max_var)
        w_min         = _fv(self._flt_w_min_var)
        w_max         = _fv(self._flt_w_max_var)
        h_min         = _fv(self._flt_h_min_var)
        h_max         = _fv(self._flt_h_max_var)
        must_have_ids = self._get_must_have_ids()
        must_not_ids  = self._get_must_not_have_ids()
        lpr_filter    = self._flt_lpr_var.get()

        has_det_filter = (
            cls_filter not in ("Tất cả", "") or
            any(v is not None for v in (ndet_min, ndet_max,
                                        area_min, area_max,
                                        w_min, w_max, h_min, h_max)) or
            bool(must_have_ids) or
            bool(must_not_ids)
        )
        has_lpr_filter = lpr_filter not in ("Tất cả", "")

        if not has_det_filter and not has_lpr_filter:
            return files
        if has_det_filter and not self._det_cache and not has_lpr_filter:
            return files

        result = []
        for f in files:
            data = self._det_cache.get(f)
            if data is None:
                # Chưa detect → ẩn nếu có filter detect tích cực
                if ndet_min is not None and ndet_min > 0:
                    continue
                if cls_filter not in ("Tất cả", ""):
                    continue
                if any(v is not None for v in (area_min, area_max,
                                               w_min, w_max, h_min, h_max)):
                    continue
                if must_have_ids or must_not_ids:
                    continue
                # Filter LPR cho ảnh chưa detect
                if has_lpr_filter:
                    with self._lpr_cache_lock:
                        _lpr_e = self._lpr_cache.get(f)
                    if lpr_filter == "Chưa nhận dạng":
                        if _lpr_e is not None:
                            continue
                    elif lpr_filter == "Có biển số":
                        if not (_lpr_e is not None
                                and any(p for _, _, _, _, p in _lpr_e)):
                            continue
                    elif lpr_filter == "Không biển số":
                        if not (_lpr_e is not None
                                and not any(p for _, _, _, _, p in _lpr_e)):
                            continue
                result.append(f)
                continue

            n = data["n"]
            detected_cls = set(data["classes"].keys())

            # Filter class (combobox)
            if cls_filter == "Không detect":
                if n > 0:
                    continue
            elif cls_filter not in ("Tất cả", ""):
                try:
                    flt_cid = int(cls_filter.split("]")[0].lstrip("["))
                    if flt_cid not in data["classes"]:
                        continue
                except (ValueError, IndexError):
                    pass

            # Filter số lượng detection
            if ndet_min is not None and n < ndet_min:
                continue
            if ndet_max is not None and n > ndet_max:
                continue

            # Filter kích thước bbox (ít nhất 1 bbox thỏa mãn)
            dim_on = any(v is not None for v in (area_min, area_max,
                                                  w_min, w_max, h_min, h_max))
            if dim_on:
                boxes = data.get("boxes", [])
                if not boxes:
                    continue
                match = False
                for box in boxes:
                    bw, bh = box[5], box[6]
                    area = bw * bh
                    if area_min is not None and area < area_min: continue
                    if area_max is not None and area > area_max: continue
                    if w_min is not None and bw < w_min: continue
                    if w_max is not None and bw > w_max: continue
                    if h_min is not None and bh < h_min: continue
                    if h_max is not None and bh > h_max: continue
                    match = True
                    break
                if not match:
                    continue

            # Filter must-have / must-not labels
            if must_have_ids and not must_have_ids.issubset(detected_cls):
                continue
            if must_not_ids and must_not_ids.intersection(detected_cls):
                continue

            # Filter LPR
            if has_lpr_filter:
                with self._lpr_cache_lock:
                    _lpr_entry = self._lpr_cache.get(f)  # None = chưa chạy
                if lpr_filter == "Chưa nhận dạng":
                    if _lpr_entry is not None:
                        continue
                elif lpr_filter == "Có biển số":
                    if not (_lpr_entry is not None
                            and any(p for _, _, _, _, p in _lpr_entry)):
                        continue
                elif lpr_filter == "Không biển số":
                    if not (_lpr_entry is not None
                            and not any(p for _, _, _, _, p in _lpr_entry)):
                        continue

            result.append(f)
        return result

    def _cache_single_result(self, img_path: str, results):
        """Ghi kết quả detect vào _det_cache và refresh grid cell tương ứng."""
        boxes_obj = results[0].boxes
        classes_count = {}
        box_list = []
        if boxes_obj is not None and len(boxes_obj):
            for box in boxes_obj:
                cid        = int(box.cls[0])
                conf_score = float(box.conf[0])
                classes_count[cid] = classes_count.get(cid, 0) + 1
                cx_n, cy_n, w_n, h_n = box.xywhn[0].tolist()
                w_px = float(box.xywh[0][2])
                h_px = float(box.xywh[0][3])
                box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score))
        with self._det_cache_lock:
            self._det_cache[img_path] = {
                "n": len(box_list), "classes": classes_count, "boxes": box_list
            }
        # Xóa thumbnail cache của ảnh này để render lại với bbox mới
        for key in list(self._grid_rendered_cache.keys()):
            if key[0] == img_path:
                del self._grid_rendered_cache[key]
        self._refresh_grid_cell(img_path)
