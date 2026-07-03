# yolo_lpr_mixin.py — YoloLprMixin — tích hợp API LPR (nhận dạng biển số) + lưu ảnh sai
import os
import re
import shutil
import threading
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
try:
    import requests as _requests
    _REQ_OK = True
except ImportError:
    _REQ_OK = False
from .yolo_onnx import _REVIEW_ICON


class YoloLprMixin:
    """Mixin: gọi API LPR để nhận dạng biển số, vẽ overlay, lưu ảnh lỗi/wrong folder."""

    # ============================================================= LPR CONFIG ==

    def _test_lpr_connection(self):
        """Test kết nối LPR server bằng cách gửi ảnh 4×4 pixel."""
        if not _REQ_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install requests", parent=self.root)
            return
        if not _PIL_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install Pillow", parent=self.root)
            return
        # Test tất cả URL có giá trị
        urls_to_test = [(i, v.get().strip())
                        for i, v in enumerate(self._lpr_url_vars)
                        if v.get().strip()]
        if not urls_to_test:
            messagebox.showwarning("Chưa nhập URL",
                                    "Vui lòng nhập ít nhất 1 URL LPR.", parent=self.root)
            return
        _HIST_KEYS = ["h.yolo.lpr_url1", "h.yolo.lpr_url2", "h.yolo.lpr_url3"]
        for i, url in urls_to_test:
            _push_history(_HIST_KEYS[i], url)
            if self._lpr_url_combos[i]:
                self._lpr_url_combos[i]["values"] = _get_history(_HIST_KEYS[i])
        if self._lpr_conn_lbl:
            self._lpr_conn_lbl.config(text="Đang kiểm tra…", fg="#f0c040")

        def _do():
            from io import BytesIO
            buf = BytesIO()
            Image.new("RGB", (4, 4), (0, 0, 0)).save(buf, "JPEG")
            data = buf.getvalue()
            parts = []
            for i, url in urls_to_test:
                try:
                    resp = _requests.post(
                        url,
                        files={"upload": ("test.jpg", data, "image/jpeg")},
                        timeout=5)
                    ok = resp.status_code < 500
                    parts.append(f"LPR{i+1}:{'✔' if ok else '✗'}{resp.status_code}")
                except Exception as ex:
                    parts.append(f"LPR{i+1}:✗{str(ex)[:12]}")
            msg   = "  ".join(parts)
            color = SUCCESS if all("✔" in p for p in parts) else ACCENT
            self.root.after(0, lambda m=msg, c=color: (
                self._lpr_conn_lbl and
                self._lpr_conn_lbl.config(text=m, fg=c)
            ))

        threading.Thread(target=_do, daemon=True).start()

    # ============================================= LPR OVERLAY HELPERS ==

    def _lpr_parse_plate(self, raw) -> str:
        """Trích biển số từ JSON response của LPR server."""
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        if not isinstance(raw, dict):
            return str(raw)[:30] if raw else ""
        for rk in ("Results", "results"):
            sub = raw.get(rk)
            if isinstance(sub, list) and sub:
                item = sub[0]
                for pk in ("Plate", "plate", "PlateNumber", "plate_number"):
                    if item.get(pk):
                        return str(item[pk]).strip()
        for k in ("plate", "PlateNumber", "license_plate", "plateNumber", "text"):
            if raw.get(k):
                return str(raw[k]).strip()
        return ""

    def _lpr_call_crop(self, crop_pil, url: str, timeout: int) -> str:
        """Gửi ảnh crop lên LPR server, trả về biển số hoặc ''."""
        if not _REQ_OK or not _PIL_OK:
            return ""
        try:
            from io import BytesIO
            buf = BytesIO()
            img = crop_pil if crop_pil.mode == "RGB" else crop_pil.convert("RGB")
            img.save(buf, "JPEG", quality=90)
            data = buf.getvalue()
            resp = _requests.post(
                url,
                files={"upload": ("crop.jpg", data, "image/jpeg")},
                timeout=timeout)
            resp.raise_for_status()
            try:
                raw = resp.json()
            except Exception:
                return resp.text.strip()[:50]
            return self._lpr_parse_plate(raw)
        except Exception:
            return ""

    # ── Màu nền mỗi dòng LPR ──────────────────────────────────────────────
    # Màu prefix LPR1/2/3 — dùng làm text color trên nền tối
    _LPR_LINE_COLORS = [(80, 220, 100), (80, 160, 255), (255, 185, 60)]
    _LPR_BG          = (15, 15, 25, 210)   # nền tối bán trong suốt (RGBA)

    @staticmethod
    def _lpr_draw_lines(draw, font, x1: int, y1: int, x2: int, y2: int,
                        plates_tsv: str, iw: int, ih: int, fs: int):
        """Vẽ từng dòng kết quả LPR — nền tối, prefix màu riêng, diff màu vàng."""
        _COLORS = [(80, 220, 100), (80, 160, 255), (255, 185, 60)]
        _BG     = (15, 15, 25)
        _DIFF   = (255, 220, 0)    # vàng — dễ thấy trên nền tối
        _WHITE  = (255, 255, 255)

        raw = [p.upper() for p in plates_tsv.split("\t")] if plates_tsv else []
        ref = next((p for p in raw if p), "")
        multi = sum(1 for p in raw if p) > 1

        lines = []
        for i, p in enumerate(raw):
            if not p:
                continue
            prefix = f"LPR{i+1}: " if multi else ""
            lines.append((prefix, p, _COLORS[i % len(_COLORS)]))

        if not lines:
            return

        pad = 5
        line_gap = 2

        def _text_w(txt):
            try:
                return draw.textbbox((0, 0), txt, font=font)[2]
            except Exception:
                return len(txt) * 9

        def _text_h(txt):
            try:
                tb = draw.textbbox((0, 0), txt, font=font)
                return tb[3] - tb[1]
            except Exception:
                return fs

        # Tính max width để biết tx cần dịch vào bao nhiêu
        line_sizes = []
        for prefix, plate_text, pfx_color in lines:
            full  = prefix + plate_text
            tw    = _text_w(full)
            th    = _text_h(full)
            line_sizes.append((tw, th))

        max_tw   = max(tw for tw, _ in line_sizes) if line_sizes else 0
        row_h    = max(th for _, th in line_sizes) if line_sizes else fs
        total_h  = len(lines) * (row_h + pad * 2 + line_gap)

        # Vị trí Y: ưu tiên dưới bbox, nếu tràn thì đẩy lên trên
        ty = y2 + 3
        if ty + total_h > ih:
            ty = max(0, y1 - total_h - 3)

        # Vị trí X: căn theo x1 của bbox, dịch trái nếu tràn cạnh phải
        tx = min(x1, iw - max_tw - pad * 2 - 1)
        tx = max(0, tx)

        for (tw2, th2), (prefix, plate_text, pfx_color) in zip(line_sizes, lines):
            draw.rectangle([tx, ty, tx + tw2 + pad * 2, ty + th2 + pad * 2],
                           fill=_BG)
            cx, cy = tx + pad, ty + pad
            # Prefix màu riêng
            if prefix:
                draw.text((cx, cy), prefix, font=font, fill=pfx_color)
                cx += _text_w(prefix)
            # Từng ký tự: trắng nếu đúng, vàng nếu khác LPR1
            for pi, ch in enumerate(plate_text):
                ref_ch = ref[pi] if pi < len(ref) else None
                fill = _DIFF if (ref_ch is not None and ch != ref_ch) else _WHITE
                draw.text((cx, cy), ch, font=font, fill=fill)
                cx += _text_w(ch)
            ty += th2 + pad * 2 + line_gap

    def _lpr_draw_from_results(self, draw_pil, results: list):
        """Vẽ nhãn biển số từ results đã cache — không gọi API.
        results: [(x1,y1,x2,y2,plate), ...]
        """
        if not results or not _PIL_OK:
            return draw_pil
        from PIL import ImageDraw as _Draw, ImageFont
        iw, ih = draw_pil.size
        draw = _Draw.Draw(draw_pil)
        fs = max(1, int(self._lpr_font_size_var.get()))
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()
        self._last_lpr_plates_result = []
        for (x1, y1, x2, y2, plates_tsv) in results:
            self._last_lpr_plates_result.append((x1, y1, x2, y2, plates_tsv))
            if not plates_tsv:
                continue
            x1c = max(0, x1); y1c = max(0, y1)
            x2c = min(iw - 1, x2); y2c = min(ih - 1, y2)
            self._lpr_draw_lines(draw, font, x1c, y1c, x2c, y2c,
                                 plates_tsv, iw, ih, fs)
        return draw_pil

    def _lpr_batch_for_path(self, img_path: str, boxes: list,
                             urls, timeout: int,
                             use_full: list = None) -> list:
        """Gọi LPR song song tất cả URL cho từng bbox của 1 ảnh (dùng trong batch detect).

        boxes   : list[(cid, cx_n, cy_n, w_n, h_n, ...)] — format det_cache.
        urls    : str hoặc list[str].
        use_full: list[bool] tương ứng từng URL — True = gửi ảnh gốc, False = crop.
        Returns : [(x1,y1,x2,y2,plates_tsv), ...]  (rỗng nếu lỗi).
        """
        if isinstance(urls, str):
            urls = [urls] if urls else []
        if not _REQ_OK or not _PIL_OK or not boxes or not urls:
            return []
        use_full = list(use_full) if use_full else [False] * len(urls)
        while len(use_full) < len(urls):
            use_full.append(False)
        try:
            from PIL import Image as _PILImg
            pil = _PILImg.open(img_path).convert("RGB")
            iw, ih = pil.size
        except Exception:
            return []
        # Filter plate class
        names = {}
        try:
            if self.model:
                names = dict(self.model.names)
        except Exception:
            pass
        _PLATE_KW = {"plate", "lp", "bsx", "bien", "license", "bienso"}
        plate_cids = {
            cid for cid, name in names.items()
            if any(kw in str(name).lower() for kw in _PLATE_KW)
        }
        if plate_cids:
            to_proc = [b for b in boxes if int(b[0]) in plate_cids]
            if not to_proc:
                return []   # model có plate class nhưng ảnh không detect ra → không gọi LPR
        else:
            to_proc = boxes
        import concurrent.futures as _cf
        results = []
        for b in to_proc:
            cx_n, cy_n, w_n, h_n = float(b[1]), float(b[2]), float(b[3]), float(b[4])
            x1 = max(0, int((cx_n - w_n / 2) * iw))
            y1 = max(0, int((cy_n - h_n / 2) * ih))
            x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
            y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            crop = pil.crop((x1, y1, x2, y2))
            plates = [""] * len(urls)
            def _call(idx, u):
                img = pil if use_full[idx] else crop
                return self._lpr_call_crop(img, u, timeout)
            if len(urls) == 1:
                plates[0] = _call(0, urls[0])
            else:
                with _cf.ThreadPoolExecutor(max_workers=len(urls)) as ex:
                    futs = {ex.submit(_call, i, u): i
                            for i, u in enumerate(urls)}
                    for fut in _cf.as_completed(futs):
                        plates[futs[fut]] = fut.result() or ""
            plates_tsv = "\t".join(p.upper() for p in plates)
            results.append((x1, y1, x2, y2, plates_tsv))
        return results

    def _lpr_overlay_boxes_vid(self, draw_pil, source_pil, boxes_with_cls,
                               urls, timeout, model_names, use_full, font_size):
        """Wrapper thread-safe cho video — nhận font_size trực tiếp, không đọc Tkinter var."""
        import contextlib
        class _FakeIntVar:
            def get(self): return font_size
        old = self._lpr_font_size_var
        self._lpr_font_size_var = _FakeIntVar()
        try:
            return self._lpr_overlay_boxes(draw_pil, source_pil, boxes_with_cls,
                                            urls, timeout, model_names, use_full)
        finally:
            self._lpr_font_size_var = old

    def _lpr_overlay_boxes(self, draw_pil, source_pil, boxes_with_cls: list,
                            urls, timeout: int, model_names: dict = None,
                            use_full: list = None):
        """Crop bbox biển số → gọi song song tất cả LPR URL → vẽ kết quả lên ảnh.

        draw_pil       : PIL Image đã annotated — vẽ text lên đây.
        source_pil     : PIL Image gốc để crop — None → dùng draw_pil.
        boxes_with_cls : list[(x1,y1,x2,y2,cid)] tọa độ pixel + class id.
        urls           : str hoặc list[str] — LPR server URL(s).
        model_names    : dict {cid: name} từ model.names để lọc plate class.
        use_full       : list[bool] tương ứng từng URL — True = gửi ảnh gốc.
        """
        if isinstance(urls, str):
            urls = [urls] if urls else []
        if not _PIL_OK:
            return draw_pil
        use_full = list(use_full) if use_full else [False] * len(urls)
        while len(use_full) < len(urls):
            use_full.append(False)
        from PIL import ImageDraw as _Draw, ImageFont

        # ── Lọc plate class nếu model có class biển số ──────────────────
        _PLATE_KW = {"plate", "lp", "bsx", "bien", "license", "bienso"}
        names = model_names or {}
        plate_cids = {
            cid for cid, name in names.items()
            if any(kw in str(name).lower() for kw in _PLATE_KW)
        }
        if plate_cids:
            to_process = [b for b in boxes_with_cls if b[4] in plate_cids]
            if not to_process:
                # Model có plate class nhưng ảnh không detect ra biển số → không gọi LPR
                self._last_lpr_plates_result = []
                return draw_pil
        else:
            to_process = boxes_with_cls      # model không có plate class → dùng tất cả bbox

        self._last_lpr_plates_result = []
        if not to_process:
            return draw_pil

        iw, ih = draw_pil.size
        draw = _Draw.Draw(draw_pil)
        fs = max(12, int(self._lpr_font_size_var.get()))
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()

        src = (source_pil if (source_pil is not None
                               and source_pil.size == draw_pil.size)
               else draw_pil)

        import concurrent.futures as _cf
        for (x1, y1, x2, y2, _cid) in to_process:
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(iw - 1, x2); y2 = min(ih - 1, y2)
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            crop = src.crop((x1, y1, x2, y2))
            # Gọi song song tất cả LPR URL — mỗi URL dùng crop hoặc ảnh gốc
            plates = [""] * len(urls)
            def _call(idx, u):
                img = src if use_full[idx] else crop
                return self._lpr_call_crop(img, u, timeout)
            if len(urls) == 1:
                plates[0] = _call(0, urls[0])
            else:
                with _cf.ThreadPoolExecutor(max_workers=len(urls)) as ex:
                    futs = {ex.submit(_call, i, u): i
                            for i, u in enumerate(urls)}
                    for fut in _cf.as_completed(futs):
                        plates[futs[fut]] = fut.result() or ""

            plates_tsv = "\t".join(p.upper() for p in plates)
            self._last_lpr_plates_result.append((x1, y1, x2, y2, plates_tsv))
            if not any(plates):
                continue
            self._lpr_draw_lines(draw, font, x1, y1, x2, y2,
                                 plates_tsv, iw, ih, fs)
        return draw_pil

    # ================================================ WRONG FOLDER SAVE ==

    def _update_wrong_path(self):
        """Ghép 5 ô thành v_wrong_folder."""
        parts = [sv.get().strip() for sv in self._v_wf_segs]
        parts = [p for p in parts if p]
        if not parts:
            self.v_wrong_folder.set("")
            return
        # Dùng string join (không dùng os.path.join) để tránh lỗi drive letter Windows
        path = parts[0].rstrip("/\\")
        for p in parts[1:]:
            path = path + "/" + p.strip("/\\")
        self.v_wrong_folder.set(path)

    def _browse_wrong_folder(self):
        cur = self.v_wrong_folder.get().strip()
        init = (cur if cur and os.path.isdir(cur)
                else os.path.dirname(cur) if cur else None)
        folder = filedialog.askdirectory(
            title="Chọn thư mục lưu ảnh sai",
            initialdir=init,
            parent=self.root)
        if not folder:
            return
        # Chia path thành 5 ô: 4 phần cuối → ô 2-5, phần còn lại → ô 1
        folder = folder.replace("\\", "/")
        raw = folder.split("/")
        # Xử lý drive letter Windows (e.g. "K:" → giữ nguyên trong raw[0])
        if len(raw) >= 5:
            s1 = "/".join(raw[:-4])
            segs = [s1] + raw[-4:]
        else:
            segs = raw + [""] * (5 - len(raw))
        for i, (sv, cb) in enumerate(zip(self._v_wf_segs, self._wf_combos)):
            val = segs[i] if i < len(segs) else ""
            sv.set(val)
            if val:
                _push_history(f"h.yolo.wf.s{i+1}", val)
                cb["values"] = _get_history(f"h.yolo.wf.s{i+1}")

    def _open_wrong_folder(self):
        p = self.v_wrong_folder.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)

    def _save_wrong_image(self):
        """Copy ảnh + label hiện tại vào folder lưu ảnh sai đã cấu hình."""
        path = self.current_image_path
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn ảnh trước.", parent=self.root)
            return
        dest_dir = self.v_wrong_folder.get().strip()
        if not dest_dir:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai (ô phía trên).",
                                   parent=self.root)
            return
        try:
            os.makedirs(dest_dir, exist_ok=True)
            base     = os.path.splitext(os.path.basename(path))[0]
            dest_img = os.path.join(dest_dir, os.path.basename(path))
            dest_lbl = os.path.join(dest_dir, f"{base}.txt")

            shutil.copy2(path, dest_img)

            # 1) Ưu tiên: ghi label từ det_cache (boxes đã detect)
            with self._det_cache_lock:
                det = self._det_cache.get(path)
            if det is not None:
                conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
                with open(dest_lbl, "w", encoding="utf-8") as f:
                    for box_t in det.get("boxes", []):
                        if len(box_t) > 7 and float(box_t[7]) < conf_thresh:
                            continue
                        cid, cx, cy, bw, bh = (box_t[0], box_t[1],
                                                box_t[2], box_t[3], box_t[4])
                        f.write(f"{int(cid)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            # 2) Fallback: kết quả detect trực tiếp (_last_results1)
            elif self._last_results1 is not None:
                boxes = self._last_results1[0].boxes
                with open(dest_lbl, "w", encoding="utf-8") as f:
                    if boxes is not None and len(boxes):
                        for box in boxes:
                            cid = int(box.cls[0])
                            cx, cy, bw, bh = box.xywhn[0].tolist()
                            f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            # 3) Fallback cuối: copy file .txt gốc nếu tồn tại
            else:
                src_lbl = os.path.splitext(path)[0] + ".txt"
                if os.path.isfile(src_lbl):
                    shutil.copy2(src_lbl, dest_lbl)

            # Tự động đánh dấu sai
            self._review_state[path] = "incorrect"
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            iid = self._path_to_iid.get(path)
            if iid:
                try:
                    if self.tree_images.exists(iid):
                        icon = _REVIEW_ICON["incorrect"]
                        old_text = self.tree_images.item(iid, "text")
                        bare = old_text[2:] if len(old_text) > 2 else old_text
                        self.tree_images.item(iid,
                                              text=f"{icon} {bare}",
                                              tags=("incorrect",))
                except Exception:
                    pass
            self._update_filter_counts()

            self.lbl_mark_state.config(
                text=f"✗💾 {os.path.basename(path)}", fg="#ffaa55")
            self.after(3000, lambda: self.lbl_mark_state.config(text=""))
            lbl_note = " + label" if os.path.isfile(dest_lbl) else ""
            self.v_status.set(f"✗💾 Lưu ảnh sai{lbl_note} → {dest_dir}")
        except Exception as e:
            messagebox.showerror("Lỗi lưu ảnh", str(e), parent=self.root)

    def _save_wrong_page(self):
        """Copy toàn bộ ảnh trang grid hiện tại + label vào wrong_folder."""
        if not self._grid_cells:
            messagebox.showwarning("Chưa có ảnh",
                                   "Trang hiện tại không có ảnh.", parent=self.root)
            return
        dest_dir = self.v_wrong_folder.get().strip()
        if not dest_dir:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai (ô phía trên).",
                                   parent=self.root)
            return

        paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not paths:
            return

        conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Lỗi tạo thư mục", str(e), parent=self.root)
            return

        saved = 0
        errors = 0
        for p in paths:
            if not os.path.isfile(p):
                continue
            try:
                base     = os.path.splitext(os.path.basename(p))[0]
                dest_img = os.path.join(dest_dir, os.path.basename(p))
                dest_lbl = os.path.join(dest_dir, f"{base}.txt")

                shutil.copy2(p, dest_img)

                # Ghi label — ưu tiên det_cache → file .txt gốc
                with self._det_cache_lock:
                    det = self._det_cache.get(p)
                if det is not None:
                    with open(dest_lbl, "w", encoding="utf-8") as f:
                        for box_t in det.get("boxes", []):
                            if len(box_t) > 7 and float(box_t[7]) < conf_thresh:
                                continue
                            cid, cx, cy, bw, bh = (box_t[0], box_t[1],
                                                    box_t[2], box_t[3], box_t[4])
                            f.write(f"{int(cid)} {cx:.6f} {cy:.6f}"
                                    f" {bw:.6f} {bh:.6f}\n")
                else:
                    src_lbl = os.path.splitext(p)[0] + ".txt"
                    if os.path.isfile(src_lbl):
                        shutil.copy2(src_lbl, dest_lbl)

                # Tự động đánh dấu sai
                self._review_state[p] = "incorrect"
                iid = self._path_to_iid.get(p)
                if iid:
                    try:
                        if self.tree_images.exists(iid):
                            icon = _REVIEW_ICON["incorrect"]
                            old_text = self.tree_images.item(iid, "text")
                            bare = old_text[2:] if len(old_text) > 2 else old_text
                            self.tree_images.item(iid,
                                                  text=f"{icon} {bare}",
                                                  tags=("incorrect",))
                    except Exception:
                        pass
                saved += 1
            except Exception:
                errors += 1

        if saved:
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            self._update_filter_counts()

        msg = f"✗💾 {saved}/{len(paths)} ảnh → {dest_dir}"
        if errors:
            msg += f" ({errors} lỗi)"
        self.lbl_mark_state.config(text=f"✗💾 {saved} ảnh sai", fg="#ffaa55")
        self.after(3000, lambda: self.lbl_mark_state.config(text=""))
        self.v_status.set(msg)

    # ============================================ LPR ERROR SAVE + GT ==

    @staticmethod
    def _extract_plate_from_filename(fname: str) -> str:
        """Trích biển số từ tên file dạng sub_<biển số>[_...].
        VD: sub_29A12345_001 → '29A12345'
        """
        import re
        m = re.match(r'^sub_([A-Za-z0-9]+)', fname, re.IGNORECASE)
        return m.group(1).upper() if m else ""

    @staticmethod
    def _update_gt(gt_path: str, filename: str, plate: str):
        """Thêm hoặc cập nhật dòng 'filename\\tplate' trong gt.txt."""
        lines = []
        updated = False
        if os.path.isfile(gt_path):
            with open(gt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    parts = line.split("\t", 1)
                    if parts[0] == filename:
                        lines.append(f"{filename}\t{plate}")
                        updated = True
                    else:
                        lines.append(line)
        if not updated:
            lines.append(f"{filename}\t{plate}")
        with open(gt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _save_lpr_error_image(self):
        """Lưu ảnh lỗi kèm crop biển số + GT.

        1. Ảnh full (annotated nếu đã detect, else bản gốc) → wrong_folder/
        2. Crops từng bbox biển số → wrong_folder/crops/
        3. GT: wrong_folder/gt.txt  format: filename\\tplate
           Plate GT ưu tiên: tên file sub_<plate> → kết quả LPR
        """
        path = self.current_image_path
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn ảnh trước.", parent=self.root)
            return
        dest_dir = self.v_wrong_folder.get().strip()
        if not dest_dir:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai (ô phía trên).",
                                   parent=self.root)
            return

        fname   = os.path.basename(path)
        base    = os.path.splitext(fname)[0]
        lpr_res = list(self._last_lpr_plates_result)  # snapshot

        # Plate GT: tên file → LPR (lấy plate đầu tiên có giá trị từ tab-separated)
        plate_gt = self._extract_plate_from_filename(base)
        if not plate_gt:
            plate_gt = next(
                (p for _, _, _, _, tsv in lpr_res
                 for p in tsv.split("\t") if p),
                ""
            )

        try:
            os.makedirs(dest_dir, exist_ok=True)

            # ── 1. Lưu ảnh full ──────────────────────────────────────────
            dest_full = os.path.join(dest_dir, fname)
            pil_full  = getattr(self, "_pil1_full", None)
            if pil_full is not None:
                pil_full.save(dest_full, quality=95)
            else:
                shutil.copy2(path, dest_full)

            # ── 2. Lưu crops bbox biển số ─────────────────────────────────
            n_crops  = 0
            pil_src  = getattr(self, "_pil1_orig", None)
            if pil_src is None:
                try:
                    from PIL import ImageOps
                    pil_src = Image.open(path).convert("RGB")
                    pil_src = ImageOps.exif_transpose(pil_src)
                except Exception:
                    pil_src = pil_full

            crop_gt_entries = []   # [(crop_fname, plate_str), ...]
            if pil_src is not None and lpr_res:
                crops_dir = os.path.join(dest_dir, "crops")
                os.makedirs(crops_dir, exist_ok=True)
                iw, ih = pil_src.size
                for i, (x1, y1, x2, y2, plates_tsv) in enumerate(lpr_res):
                    x1 = max(0, x1); y1 = max(0, y1)
                    x2 = min(iw - 1, x2); y2 = min(ih - 1, y2)
                    if x2 - x1 < 4 or y2 - y1 < 4:
                        continue
                    crop_img  = pil_src.crop((x1, y1, x2, y2))
                    crop_fname = f"{base}_crop{i:02d}.jpg"
                    crop_img.save(os.path.join(crops_dir, crop_fname), quality=95)
                    n_crops += 1
                    # GT cho crop: lấy plate đầu tiên có giá trị (ưu tiên LPR1)
                    crop_plate = plate_gt or next(
                        (p for p in plates_tsv.split("\t") if p), "")
                    if crop_plate:
                        crop_gt_entries.append((crop_fname, crop_plate))

            # ── 3. GT ─────────────────────────────────────────────────────
            gt_path = os.path.join(dest_dir, "gt.txt")
            if plate_gt:
                self._update_gt(gt_path, fname, plate_gt)
            # GT cho từng crop
            crops_gt_path = os.path.join(dest_dir, "crops", "gt.txt")
            for crop_fname, crop_plate in crop_gt_entries:
                self._update_gt(crops_gt_path, crop_fname, crop_plate)

            # Feedback
            gt_note = f"  GT={plate_gt}" if plate_gt else "  GT=—"
            crop_gt_note = f"+{len(crop_gt_entries)}crop" if crop_gt_entries else ""
            msg = f"📋 {fname}  crop={n_crops}{gt_note}{crop_gt_note}"
            self.lbl_mark_state.config(text=msg[:56], fg="#4cdf80")
            self.after(3000, lambda: self.lbl_mark_state.config(text=""))
            self.v_status.set(f"📋 Lưu lỗi+GT → {dest_dir}  {gt_note.strip()}")

        except Exception as e:
            messagebox.showerror("Lỗi lưu lỗi+GT", str(e), parent=self.root)

    def _open_gt_folder(self):
        p = self.v_wrong_folder.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)
        elif p:
            messagebox.showwarning("Thư mục không tồn tại",
                                   f"Chưa có thư mục:\n{p}", parent=self.root)
        else:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai trước.",
                                   parent=self.root)
