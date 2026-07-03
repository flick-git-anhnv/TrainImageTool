# yolo_video_window_mixin.py — YoloVideoWindowMixin — cửa sổ detect video trực tiếp (frame loop + overlay LPR)
import os
import threading
import time
import queue as _q
from datetime import datetime
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False
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
from .yolo_onnx import _contrast_text


class YoloVideoWindowMixin:
    """Mixin: cửa sổ detect video trực tiếp — frame loop, overlay LPR, lưu video/ảnh."""

    def _launch_video_window(self, source, source_name: str, loop_video: bool,
                              enable_seek: bool = False):
        """Cửa sổ detect video liên tục — worker thread gửi frame qua queue."""
        # speed map: label → multiplier (0.0 = tối đa, không sleep)
        _SPEED_MAP = {
            "0.25×": 0.25, "0.5×": 0.5, "1×": 1.0,
            "1.5×": 1.5,   "2×": 2.0,   "4×": 4.0, "Max": 0.0,
        }

        win = Toplevel(self.root)
        win.title(f"YOLO Video Detection — {source_name}")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.minsize(640, 400)
        win.geometry("960x580")

        _running  = [True]
        _paused   = [False]
        _after_id = [None]
        _last_pil = [None]
        frame_q   = _q.Queue(maxsize=2)
        v_speed   = StringVar(value="1×")

        def _stop_and_close():
            _running[0] = False
            if _after_id[0]:
                try:
                    win.after_cancel(_after_id[0])
                except Exception:
                    pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _stop_and_close)
        win.bind("<Escape>", lambda _: _stop_and_close())

        # ── Info bar ──────────────────────────────────────────────────────
        info_bar = Frame(win, bg=CARD, padx=8, pady=5)
        info_bar.pack(fill=X)

        Label(info_bar, text=f"▶ {source_name}",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=(0, 12))

        lbl_fps = Label(info_bar, text="FPS: —",
                        bg=CARD, fg=ACCENT, font=F_MONO)
        lbl_fps.pack(side=LEFT, padx=(0, 8))

        # Native FPS label — updated once cap opens
        lbl_src_fps = Label(info_bar, text="",
                            bg=CARD, fg=DIM, font=F_MONO)
        lbl_src_fps.pack(side=LEFT, padx=(0, 12))

        lbl_ndet = Label(info_bar, text="Đối tượng: —",
                         bg=CARD, fg=SUCCESS, font=F_MONO)
        lbl_ndet.pack(side=LEFT, padx=(0, 12))

        lbl_det_info = Label(info_bar, text="",
                             bg=CARD, fg=DIM, font=F_MONO)
        lbl_det_info.pack(side=LEFT, anchor=W, padx=(0, 12))

        lbl_lpr_info = Label(info_bar, text="",
                             bg=CARD, fg="#50dc64", font=F_MONO)
        lbl_lpr_info.pack(side=LEFT, expand=True, anchor=W)

        lbl_status = Label(info_bar, text="Đang khởi động...",
                           bg=CARD, fg=DIM, font=F_MAIN)
        lbl_status.pack(side=RIGHT)

        # ── Video canvas ── pack sau tất cả các bar để controls luôn hiển thị
        vid_label = Label(win, bg="#0d0d1a",
                          text="Đang khởi tạo...", fg=DIM,
                          font=("Segoe UI", 14))

        def _on_zoom(_e=None):
            if _last_pil[0] is not None:
                from ...core.ui_helpers import _zoom_image_window
                _zoom_image_window(win, _last_pil[0], source_name)

        vid_label.bind("<Double-Button-1>", _on_zoom)

        # ── Control bar ──────────────────────────────────────────────────
        ctrl_bar = Frame(win, bg=CARD, padx=8, pady=6)
        ctrl_bar.pack(fill=X)

        btn_pause = Button(ctrl_bar, text="⏸ Tạm dừng",
                           command=lambda: _toggle_pause(),
                           bg=ACCENT2, fg="white", font=F_MAIN,
                           relief="flat", padx=10, cursor="hand2")
        btn_pause.pack(side=LEFT, padx=(0, 8))

        Button(ctrl_bar, text="■ Dừng & Đóng",
               command=_stop_and_close,
               bg=ACCENT, fg="white", font=F_MAIN,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT)

        # Speed control
        Frame(ctrl_bar, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(12, 8))
        Label(ctrl_bar, text="Tốc độ:", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(side=LEFT)
        speed_combo = ttk.Combobox(
            ctrl_bar, textvariable=v_speed,
            values=list(_SPEED_MAP.keys()),
            state="readonly", font=F_MAIN, width=5)
        speed_combo.pack(side=LEFT, padx=(4, 0))

        # Keyboard shortcuts: [ = slower, ] = faster
        _speed_keys = list(_SPEED_MAP.keys())

        def _speed_step(delta: int):
            cur = v_speed.get()
            idx = _speed_keys.index(cur) if cur in _speed_keys else 2
            new_idx = max(0, min(len(_speed_keys) - 1, idx + delta))
            v_speed.set(_speed_keys[new_idx])

        win.bind("[", lambda _: _speed_step(-1))
        win.bind("]", lambda _: _speed_step(+1))

        # Conf / IoU read-only display
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()
        Frame(ctrl_bar, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(12, 8))
        Label(ctrl_bar, text=f"Conf: {conf_val:.2f}",
              bg=CARD, fg=DIM, font=F_MONO).pack(side=LEFT)
        Label(ctrl_bar, text=f"  IoU: {iou_val:.2f}",
              bg=CARD, fg=DIM, font=F_MONO).pack(side=LEFT, padx=(4, 0))
        if loop_video:
            Label(ctrl_bar, text="  [Loop]",
                  bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(8, 0))

        Label(ctrl_bar,
              text="Space=pause  [ ]=tốc độ  Dbl-click=zoom",
              bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack(side=RIGHT)

        win.bind("<space>", lambda _: _toggle_pause())

        # ── Seek bar (file video hoặc YouTube VOD; không cho webcam/RTSP/live) ──
        _total_frames   = [0]
        _seek_requested = [None]   # frame index cần seek, None = không seek
        _seeking        = [False]  # đang kéo slider (tạm dừng cập nhật tự động)

        is_file_source = (isinstance(source, str) and os.path.isfile(source)) or enable_seek
        if is_file_source:
            seek_bar = Frame(win, bg=CARD, padx=8, pady=4)
            seek_bar.pack(fill=X)

            v_seek_pos  = IntVar(value=0)
            lbl_pos     = Label(seek_bar, text="00:00 / 00:00",
                                bg=CARD, fg=DIM, font=F_MONO)
            lbl_pos.pack(side=LEFT, padx=(0, 8))

            seek_slider = ttk.Scale(seek_bar, from_=0, to=1000,
                                    orient="horizontal", variable=v_seek_pos)
            seek_slider.pack(side=LEFT, fill=X, expand=True)

            def _fmt_time(frames, fps):
                if fps <= 0:
                    return "—"
                secs = int(frames / fps)
                return f"{secs // 60:02d}:{secs % 60:02d}"

            def _on_seek_press(_e):
                _seeking[0] = True

            def _on_seek_release(_e):
                if _total_frames[0] > 0:
                    frac = v_seek_pos.get() / 1000.0
                    _seek_requested[0] = int(frac * _total_frames[0])
                _seeking[0] = False

            seek_slider.bind("<ButtonPress-1>",   _on_seek_press)
            seek_slider.bind("<ButtonRelease-1>", _on_seek_release)

            def _update_seek(cur_frame):
                if _seeking[0] or _total_frames[0] <= 0:
                    return
                try:
                    v_seek_pos.set(int(cur_frame / _total_frames[0] * 1000))
                    fps_n = cap_fps_ref[0]
                    lbl_pos.config(
                        text=f"{_fmt_time(cur_frame, fps_n)} / "
                             f"{_fmt_time(_total_frames[0], fps_n)}")
                except Exception:
                    pass
        else:
            _update_seek   = None
            _seek_requested = [None]
        cap_fps_ref = [25.0]   # actualFPS из cap, обновляется в worker

        def _toggle_pause():
            _paused[0] = not _paused[0]
            btn_pause.config(
                text="▶ Tiếp tục" if _paused[0] else "⏸ Tạm dừng",
                bg="#c0411a" if _paused[0] else ACCENT2)
            lbl_status.config(
                text="Tạm dừng" if _paused[0] else "Đang chạy...")

        # vid_names cần trước save_bar (dùng để build class checkboxes)
        vid_names = {}
        try:
            if self.model:
                if _vid_m1_type == "yolo" and hasattr(self.model, "names"):
                    vid_names = dict(self.model.names)
                else:
                    vid_names = dict(_vid_m1_names)
        except Exception:
            pass

        # ── Save-frame panel ─────────────────────────────────────────────
        save_bar = Frame(win, bg="#16162a", padx=8, pady=5)
        save_bar.pack(fill=X)

        v_save_enable  = BooleanVar(value=False)
        v_save_no_det  = BooleanVar(value=True)   # lưu khi không detect được gì
        v_save_classes = {}                        # {class_name: BooleanVar} — lưu khi class xuất hiện
        v_save_interval = IntVar(value=500)        # ms giữa 2 lần lưu
        v_save_folder  = StringVar(
            value=_get_history("h.yolo.vid_save_folder")[0]
            if _get_history("h.yolo.vid_save_folder") else "")
        lbl_save_count = [None]                    # ref label đếm số frame đã lưu
        _save_frame_count = [0]
        _last_save_ms = [0]                        # time.monotonic() * 1000

        # Row 1: enable + folder
        sv_r1 = Frame(save_bar, bg="#16162a")
        sv_r1.pack(fill=X, pady=(0, 3))
        Checkbutton(sv_r1, text="💾 Lưu frame", variable=v_save_enable,
                    bg="#16162a", fg=TEXT, selectcolor="#16162a",
                    activebackground="#16162a", font=F_BOLD,
                    cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Label(sv_r1, text="Thư mục:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        sv_combo_folder = ttk.Combobox(sv_r1, textvariable=v_save_folder,
                                        font=F_MAIN, width=30)
        sv_combo_folder["values"] = _get_history("h.yolo.vid_save_folder")
        sv_combo_folder.pack(side=LEFT, padx=(4, 4))
        _bind_history("h.yolo.vid_save_folder", sv_combo_folder)

        def _pick_save_folder():
            p = filedialog.askdirectory(title="Chọn thư mục lưu frame", parent=win)
            if p:
                v_save_folder.set(p)
                _push_history("h.yolo.vid_save_folder", p)
                sv_combo_folder["values"] = _get_history("h.yolo.vid_save_folder")
        Button(sv_r1, text="Duyệt…", command=_pick_save_folder,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT)
        lbl_save_count[0] = Label(sv_r1, text="Đã lưu: 0",
                                   bg="#16162a", fg=DIM, font=F_MONO)
        lbl_save_count[0].pack(side=LEFT, padx=(12, 0))
        Button(sv_r1, text="📂", command=lambda: (
                   os.startfile(v_save_folder.get())
                   if v_save_folder.get() and os.path.isdir(v_save_folder.get())
                   else None),
               bg="#16162a", fg=DIM, font=F_MAIN, relief="flat",
               cursor="hand2").pack(side=LEFT, padx=(4, 0))

        # Duration: lưu tối đa N giây sau mỗi lần trigger (0 = không giới hạn)
        v_save_duration = IntVar(value=0)

        # Row 2: điều kiện — checkbox theo từng label + cài đặt
        sv_r2 = Frame(save_bar, bg="#16162a")
        sv_r2.pack(fill=X, pady=(2, 0))
        Label(sv_r2, text="Lưu khi:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT, padx=(0, 6))

        # Label đặc biệt: "Không có label" (không detect được gì)
        _KEY_EMPTY = "__empty__"
        v_save_no_det = BooleanVar(value=True)   # giữ lại var cho logic cũ
        v_save_classes[_KEY_EMPTY] = v_save_no_det
        Checkbutton(sv_r2, text="Không có label",
                    variable=v_save_no_det,
                    bg="#16162a", fg="#9090c0", selectcolor="#16162a",
                    activebackground="#16162a",
                    font=("Segoe UI", 8), cursor="hand2").pack(
            side=LEFT, padx=(0, 4))

        # Checkbox từng class trong model
        for _cid, _cname in sorted(vid_names.items(), key=lambda x: x[1]):
            _v = BooleanVar(value=False)
            v_save_classes[_cname] = _v
            Checkbutton(sv_r2, text=_cname, variable=_v,
                        bg="#16162a", fg=TEXT, selectcolor="#16162a",
                        activebackground="#16162a",
                        font=("Segoe UI", 8), cursor="hand2").pack(
                side=LEFT, padx=(0, 4))

        Frame(sv_r2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))
        Label(sv_r2, text="Tần suất:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Spinbox(sv_r2, from_=100, to=10000, increment=100,
                textvariable=v_save_interval, width=5,
                bg="#0d0d1a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat",
                font=F_MONO).pack(side=LEFT, padx=(4, 2))
        Label(sv_r2, text="ms", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Frame(sv_r2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))
        Label(sv_r2, text="Lưu trong:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Spinbox(sv_r2, from_=0, to=3600, increment=1,
                textvariable=v_save_duration, width=4,
                bg="#0d0d1a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat",
                font=F_MONO).pack(side=LEFT, padx=(4, 2))
        Label(sv_r2, text="giây (0=∞)", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)

        # Video area — pack sau tất cả bars để chúng luôn hiện ở trên
        vid_label.pack(fill=BOTH, expand=True)

        # Capture params trên main thread
        sel_cls    = self._get_sel_classes()
        lw         = max(1, self.v_line_width.get())
        fs         = max(6, self.v_font_size.get())
        model2_vid       = self.model2            # snapshot tại thời điểm mở cửa sổ video
        _vid_m1_type     = self._model1_type
        _vid_m1_names    = dict(self._model1_names)
        _vid_m2_type     = self._model2_type
        _vid_m2_names    = dict(self._model2_names)
        check_lpr  = self.v_check_lpr.get() and _REQ_OK and _PIL_OK
        lpr_urls   = ([v.get().strip() for v in self._lpr_url_vars
                       if v.get().strip()] if check_lpr else [])
        lpr_timeout  = self._lpr_timeout_var.get() if check_lpr else 10
        lpr_fullimg  = [v.get() for v in self._lpr_fullimg_vars] if check_lpr else []
        lpr_font_sz  = max(12, self._lpr_font_size_var.get()) if check_lpr else 16
        do_lpr       = bool(check_lpr and lpr_urls)
        _LPR_EVERY    = 3          # gọi LPR mỗi N frame (tránh làm giảm FPS)
        lpr_skip_ctr  = [0]        # đếm frame skip LPR
        lpr_last_text = [""]       # kết quả LPR cuối để hiển thị info bar
        _lpr_vid_cache = [None]    # [(x1,y1,x2,y2,plates_tsv)...] từ lần gọi LPR mới nhất

        # Snapshot dict — worker đọc từ đây (thread-safe, không gọi Tkinter từ thread phụ)
        _snap = {
            "save_enable":   False,
            "save_interval": 500,
            "save_duration": 0,    # giây, 0 = không giới hạn
            "save_folder":   "",
            "save_classes":  {},   # {class_name: bool} — kể cả "__empty__"
        }
        _save_start_ms = [0.0]     # thời điểm bắt đầu lưu (monotonic ms), 0 = chưa bắt đầu

        def _refresh_snap():
            """Cập nhật snapshot từ Tkinter vars — chỉ gọi từ main thread."""
            if not _running[0]:
                return
            _snap["save_enable"]   = v_save_enable.get()
            _snap["save_interval"] = max(100, v_save_interval.get())
            _snap["save_duration"] = max(0, v_save_duration.get())
            _snap["save_folder"]   = v_save_folder.get().strip()
            _snap["save_classes"]  = {k: v.get() for k, v in v_save_classes.items()}
            win.after(200, _refresh_snap)   # refresh 5 lần/s — đủ nhanh

        win.after(100, _refresh_snap)  # bắt đầu refresh sau khi UI ổn định

        # ── Worker thread: read + detect ─────────────────────────────────
        def _worker():
          try:
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                self.root.after(0, lambda: messagebox.showerror(
                    "Lỗi mở video",
                    f"Không thể mở nguồn: {source}", parent=win))
                _running[0] = False
                return

            fps_native = cap.get(cv2.CAP_PROP_FPS)
            if fps_native <= 0:
                fps_native = 25.0
            cap_fps_ref[0] = fps_native

            total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_f > 0:
                _total_frames[0] = total_f

            # Show native fps in info bar
            self.root.after(0, lambda f=fps_native:
                            lbl_src_fps.config(text=f"(src {f:.0f}fps)"))

            t0          = time.time()
            frame_count = 0
            fps_disp    = 0.0

            self.root.after(0, lambda: lbl_status.config(text="Đang chạy..."))

            cur_frame_idx = [0]

            while _running[0]:
                if _paused[0]:
                    time.sleep(0.05)
                    continue

                # Seek nếu user kéo slider
                if _seek_requested[0] is not None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, _seek_requested[0])
                    cur_frame_idx[0] = _seek_requested[0]
                    _seek_requested[0] = None

                t_frame_start = time.time()

                ret, frame = cap.read()
                if not ret:
                    if loop_video and isinstance(source, str):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        cur_frame_idx[0] = 0
                        continue
                    self.root.after(0, lambda: lbl_status.config(
                        text="Video kết thúc"))
                    break

                cur_frame_idx[0] += 1
                if _update_seek is not None:
                    self.root.after(0, lambda f=cur_frame_idx[0]:
                                    _update_seek(f))

                # Detect
                boxes = None   # reset mỗi frame để điều kiện lưu không dùng kết quả cũ
                try:
                    _C1 = (0, 200, 255)    # cyan  — Model 1
                    _C2 = (240, 89, 34)    # cam KZTEK — Model 2

                    if _vid_m1_type == "yolo":
                      results = self.model.predict(
                        source=frame, classes=sel_cls,
                        conf=conf_val, iou=iou_val,
                        imgsz=640, agnostic_nms=True, verbose=False,
                      )
                      boxes = results[0].boxes
                      n_det = len(boxes) if boxes is not None else 0

                      if model2_vid is not None:
                        # Dual model — vẽ thủ công 2 màu cố định
                        boxes2, n_det2 = None, 0
                        dets2_sv = None
                        if _vid_m2_type == "yolo":
                            try:
                                results2 = model2_vid.predict(
                                    source=frame, classes=sel_cls,
                                    conf=conf_val, iou=iou_val,
                                    imgsz=640, agnostic_nms=True, verbose=False,
                                )
                                boxes2 = results2[0].boxes
                                n_det2 = len(boxes2) if boxes2 is not None else 0
                            except Exception:
                                pass
                        else:
                            try:
                                _pil_m2 = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                                dets2_sv = model2_vid.predict(_pil_m2, threshold=conf_val)
                                n_det2   = (len(dets2_sv.xyxy)
                                             if hasattr(dets2_sv, "xyxy") and dets2_sv.xyxy is not None
                                             else 0)
                            except Exception:
                                pass

                        from PIL import ImageFont as _IFont
                        _orig_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        _pil_vid  = Image.fromarray(_orig_rgb)
                        _draw_vid = ImageDraw.Draw(_pil_vid)
                        try:
                            _ifont = _IFont.truetype("arial.ttf", fs)
                        except Exception:
                            try:
                                _ifont = _IFont.load_default(size=fs)
                            except Exception:
                                _ifont = _IFont.load_default()

                        _names1 = (_vid_m1_names if _vid_m1_type != "yolo"
                                   else getattr(self.model, "names", {}) or {})
                        if boxes is not None and len(boxes):
                            for _b in boxes:
                                _x1, _y1, _x2, _y2 = (int(v) for v in _b.xyxy[0])
                                _cid  = int(_b.cls[0])
                                _cf   = float(_b.conf[0])
                                _lbl  = f"M1:{_names1.get(_cid, str(_cid))} {_cf:.2f}"
                                _draw_vid.rectangle([_x1, _y1, _x2, _y2],
                                                    outline=_C1, width=lw)
                                try:
                                    _tb = _draw_vid.textbbox((0, 0), _lbl, font=_ifont)
                                    _tw, _th = _tb[2]-_tb[0], _tb[3]-_tb[1]
                                    _ty = max(_y1-_th-4, 0)
                                    _draw_vid.rectangle([_x1, _ty, _x1+_tw+6, _ty+_th+4],
                                                        fill=_C1)
                                    _draw_vid.text((_x1+3, _ty+2), _lbl,
                                                   fill=_contrast_text(_C1), font=_ifont)
                                except Exception:
                                    _draw_vid.text((_x1, max(_y1-fs-2, 0)),
                                                   _lbl, fill=_C1, font=_ifont)

                        _names2 = (_vid_m2_names if _vid_m2_type != "yolo"
                                   else getattr(model2_vid, "names", {}) or {})
                        if _vid_m2_type == "yolo" and boxes2 is not None and len(boxes2):
                            for _b in boxes2:
                                _x1, _y1, _x2, _y2 = (int(v) for v in _b.xyxy[0])
                                _cid  = int(_b.cls[0])
                                _cf   = float(_b.conf[0])
                                _lbl  = f"M2:{_names2.get(_cid, str(_cid))} {_cf:.2f}"
                                _draw_vid.rectangle([_x1, _y1, _x2, _y2],
                                                    outline=_C2, width=lw)
                                try:
                                    _tb = _draw_vid.textbbox((0, 0), _lbl, font=_ifont)
                                    _tw, _th = _tb[2]-_tb[0], _tb[3]-_tb[1]
                                    _ty = max(_y1-_th-4, 0)
                                    _draw_vid.rectangle([_x1, _ty, _x1+_tw+6, _ty+_th+4],
                                                        fill=_C2)
                                    _draw_vid.text((_x1+3, _ty+2), _lbl,
                                                   fill=_contrast_text(_C2), font=_ifont)
                                except Exception:
                                    _draw_vid.text((_x1, max(_y1-fs-2, 0)),
                                                   _lbl, fill=_C2, font=_ifont)

                        # M2 non-YOLO (sv.Detections)
                        if dets2_sv is not None and hasattr(dets2_sv, "xyxy") and dets2_sv.xyxy is not None:
                            _confs2 = getattr(dets2_sv, "confidence", None)
                            _cids2  = getattr(dets2_sv, "class_id",  None)
                            for _i2, _b2 in enumerate(dets2_sv.xyxy):
                                _x1, _y1, _x2, _y2 = (int(v) for v in _b2)
                                _cid  = int(_cids2[_i2])  if _cids2  is not None else 0
                                _cf   = float(_confs2[_i2]) if _confs2 is not None else 0.0
                                _lbl  = f"M2:{_names2.get(_cid, str(_cid))} {_cf:.2f}"
                                _draw_vid.rectangle([_x1, _y1, _x2, _y2],
                                                    outline=_C2, width=lw)
                                try:
                                    _tb = _draw_vid.textbbox((0, 0), _lbl, font=_ifont)
                                    _tw, _th = _tb[2]-_tb[0], _tb[3]-_tb[1]
                                    _ty = max(_y1-_th-4, 0)
                                    _draw_vid.rectangle([_x1, _ty, _x1+_tw+6, _ty+_th+4],
                                                        fill=_C2)
                                    _draw_vid.text((_x1+3, _ty+2), _lbl,
                                                   fill=_contrast_text(_C2), font=_ifont)
                                except Exception:
                                    _draw_vid.text((_x1, max(_y1-fs-2, 0)),
                                                   _lbl, fill=_C2, font=_ifont)

                        annotated_bgr = cv2.cvtColor(np.array(_pil_vid),
                                                     cv2.COLOR_RGB2BGR)
                        _cnts: dict = {}
                        if boxes is not None:
                            for _cid in boxes.cls.tolist():
                                _k = f"M1:{_names1.get(int(_cid), str(int(_cid)))}"
                                _cnts[_k] = _cnts.get(_k, 0) + 1
                        if _vid_m2_type == "yolo" and boxes2 is not None:
                            for _cid in boxes2.cls.tolist():
                                _k = f"M2:{_names2.get(int(_cid), str(int(_cid)))}"
                                _cnts[_k] = _cnts.get(_k, 0) + 1
                        elif dets2_sv is not None and getattr(dets2_sv, "class_id", None) is not None:
                            for _cid in dets2_sv.class_id:
                                _k = f"M2:{_names2.get(int(_cid), str(int(_cid)))}"
                                _cnts[_k] = _cnts.get(_k, 0) + 1
                        n_det      = n_det + n_det2
                        det_summary = "  ".join(f"{k}:{v}" for k, v in _cnts.items())

                      else:
                        # Single YOLO model — dùng results[0].plot()
                        annotated_bgr = results[0].plot(line_width=lw, font_size=fs)
                        if n_det > 0 and boxes is not None:
                            _cnts = {}
                            _nm_m1 = getattr(self.model, "names", {}) or {}
                            for _cid in boxes.cls.tolist():
                                _nm_key = _nm_m1.get(int(_cid), str(int(_cid)))
                                _cnts[_nm_key] = _cnts.get(_nm_key, 0) + 1
                            det_summary = "  ".join(
                                f"{k}:{v}" for k, v in _cnts.items())
                        else:
                            det_summary = ""

                    else:
                      # Non-YOLO M1 (RF-DETR / ONNX)
                      _orig_rgb_nv = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                      _pil_nv = Image.fromarray(_orig_rgb_nv)
                      dets1_nv = self.model.predict(_pil_nv, threshold=conf_val)
                      n_det = (len(dets1_nv.xyxy)
                                if hasattr(dets1_nv, "xyxy") and dets1_nv.xyxy is not None
                                else 0)
                      # Dùng _draw_sv_on_pil — cần self method, gọi trực tiếp
                      _pil_nv_out = self._draw_sv_on_pil(_pil_nv, dets1_nv, _vid_m1_names)
                      if model2_vid is not None:
                          n_det2 = 0
                          try:
                              if _vid_m2_type == "rfdetr":
                                  _pil_m2_nv = Image.fromarray(_orig_rgb_nv)
                                  dets2_nv = model2_vid.predict(_pil_m2_nv, threshold=conf_val)
                              else:
                                  dets2_nv = model2_vid.predict(_pil_nv, threshold=conf_val)
                              n_det2 = (len(dets2_nv.xyxy)
                                         if hasattr(dets2_nv, "xyxy") and dets2_nv.xyxy is not None
                                         else 0)
                              _pil_nv_out = self._draw_sv_on_pil(
                                  _pil_nv_out, dets2_nv, _vid_m2_names, _C2, "M2:")
                          except Exception:
                              dets2_nv = None
                          _cnts = {}
                          _cls_nv = getattr(dets1_nv, "class_id", None)
                          if _cls_nv is not None:
                              for _c in _cls_nv:
                                  _k = f"M1:{_vid_m1_names.get(int(_c), str(int(_c)))}"
                                  _cnts[_k] = _cnts.get(_k, 0) + 1
                          n_det += n_det2
                      else:
                          _cnts = {}
                          _cls_nv = getattr(dets1_nv, "class_id", None)
                          if _cls_nv is not None:
                              for _c in _cls_nv:
                                  _nm_nv = _vid_m1_names.get(int(_c), str(int(_c)))
                                  _cnts[_nm_nv] = _cnts.get(_nm_nv, 0) + 1
                      det_summary   = "  ".join(f"{k}:{v}" for k, v in _cnts.items())
                      annotated_bgr = cv2.cvtColor(np.array(_pil_nv_out), cv2.COLOR_RGB2BGR)
                      # boxes = None (không hỗ trợ LPR overlay với non-YOLO video)

                except Exception:
                    annotated_bgr = frame
                    n_det         = 0
                    det_summary   = ""

                # FPS counter (actual throughput)
                frame_count += 1
                elapsed = time.time() - t0
                if elapsed >= 0.5:
                    fps_disp    = frame_count / elapsed
                    frame_count = 0
                    t0          = time.time()

                # BGR → PIL
                rgb       = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
                pil_frame = Image.fromarray(rgb)

                # ── LPR (mỗi _LPR_EVERY frame, chỉ khi có detect) ──────────
                if do_lpr and n_det > 0 and boxes is not None:
                    lpr_skip_ctr[0] = (lpr_skip_ctr[0] + 1) % _LPR_EVERY
                    if lpr_skip_ctr[0] == 0:
                        # Gọi LPR thật + cập nhật cache
                        try:
                            bwc = [(int(x1), int(y1), int(x2), int(y2), int(cid))
                                   for (x1, y1, x2, y2), cid in zip(
                                       boxes.xyxy.tolist(), boxes.cls.tolist())]
                            pil_orig_lpr = Image.fromarray(
                                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                            pil_frame = self._lpr_overlay_boxes_vid(
                                pil_frame, pil_orig_lpr, bwc, lpr_urls,
                                lpr_timeout, vid_names, lpr_fullimg, lpr_font_sz)
                            _lpr_vid_cache[0] = list(self._last_lpr_plates_result)
                            plates = [p for _, _, _, _, tsv in (_lpr_vid_cache[0] or [])
                                      for p in tsv.split("\t") if p]
                            lpr_last_text[0] = ("🔤 " + " | ".join(plates)
                                                 if plates else "")
                        except Exception:
                            pass
                    elif _lpr_vid_cache[0]:
                        # Frame skip: vẽ lại từ cache để không bị nháy
                        try:
                            from PIL import ImageDraw as _LDraw, ImageFont as _LFont
                            _draw = _LDraw.Draw(pil_frame)
                            _iw, _ih = pil_frame.size
                            try:
                                _font = _LFont.truetype("arial.ttf", lpr_font_sz)
                            except Exception:
                                try:
                                    _font = _LFont.load_default(size=lpr_font_sz)
                                except Exception:
                                    _font = _LFont.load_default()
                            for (cx1, cy1, cx2, cy2, _tsv) in _lpr_vid_cache[0]:
                                if _tsv:
                                    self._lpr_draw_lines(_draw, _font,
                                                         cx1, cy1, cx2, cy2,
                                                         _tsv, _iw, _ih, lpr_font_sz)
                        except Exception:
                            pass
                elif do_lpr and n_det == 0:
                    _lpr_vid_cache[0] = None
                    lpr_last_text[0] = ""

                # Push (drop if full — don't block worker)
                try:
                    frame_q.put_nowait((pil_frame, n_det, fps_disp,
                                        det_summary, lpr_last_text[0]))
                except _q.Full:
                    pass

                # ── Lưu frame theo điều kiện (dùng _snap, không đọc Tkinter) ──
                if _snap["save_enable"]:
                    now_ms    = time.monotonic() * 1000
                    interval  = _snap["save_interval"]
                    duration  = _snap["save_duration"]  # giây, 0 = không giới hạn
                    save_dir  = _snap["save_folder"]
                    # Kiểm tra duration: nếu đã lưu quá N giây kể từ lần trigger đầu → dừng
                    if (duration > 0 and _save_start_ms[0] > 0
                            and now_ms - _save_start_ms[0] > duration * 1000):
                        pass   # hết duration, không lưu
                    elif now_ms - _last_save_ms[0] >= interval and save_dir:
                        should_save = False
                        cls_map = _snap["save_classes"]
                        # "__empty__" = lưu khi không detect được gì
                        if n_det == 0 and cls_map.get("__empty__", False):
                            should_save = True
                        if not should_save and n_det > 0 and boxes is not None:
                            detected_cls = set()
                            for cid in boxes.cls.tolist():
                                nm = vid_names.get(int(cid), "")
                                if nm:
                                    detected_cls.add(nm)
                            for cname, enabled in cls_map.items():
                                if cname != "__empty__" and enabled and cname in detected_cls:
                                    should_save = True
                                    break
                        if should_save:
                            if _save_start_ms[0] == 0:
                                _save_start_ms[0] = now_ms  # ghi nhận lần trigger đầu
                            try:
                                import datetime as _dt
                                os.makedirs(save_dir, exist_ok=True)
                                ts = _dt.datetime.now().strftime(
                                    "%Y%m%d_%H%M%S_%f")[:21]
                                cv2.imwrite(
                                    os.path.join(save_dir, f"frame_{ts}.jpg"),
                                    frame)
                                _save_frame_count[0] += 1
                                cnt = _save_frame_count[0]
                                self.root.after(0, lambda c=cnt:
                                    lbl_save_count[0].config(
                                        text=f"Đã lưu: {c}", fg="#50dc64"))
                            except Exception:
                                pass
                            _last_save_ms[0] = now_ms
                        else:
                            _save_start_ms[0] = 0  # reset khi điều kiện không còn đúng

                # ── Speed throttle ────────────────────────────────────────
                speed_mul = _SPEED_MAP.get(v_speed.get(), 1.0)
                if speed_mul > 0 and fps_native > 0:
                    # target interval for this frame at the chosen multiplier
                    target_interval = 1.0 / (fps_native * speed_mul)
                    spent = time.time() - t_frame_start
                    sleep_dur = target_interval - spent
                    if sleep_dur > 0.001:
                        time.sleep(sleep_dur)
                # speed_mul == 0 → "Max": no sleep, run as fast as YOLO allows

            cap.release()
          except Exception as _worker_ex:
            import traceback as _tb
            _msg = _tb.format_exc()
            self.root.after(0, lambda m=_msg: messagebox.showerror(
                "Lỗi worker video", m[:1000], parent=win))
            _running[0] = False

        # ── Main-thread polling ──────────────────────────────────────────
        def _poll():
            try:
                item = frame_q.get_nowait()
                pil_frame = item[0]
                n_det      = item[1]
                fps_val    = item[2]
                det_summary = item[3]
                lpr_text   = item[4] if len(item) > 4 else ""
                _last_pil[0] = pil_frame

                cw = max(vid_label.winfo_width(),  640)
                ch = max(vid_label.winfo_height(), 360)
                img_w, img_h = pil_frame.size
                scale = min(cw / img_w, ch / img_h)
                new_w = max(1, int(img_w * scale))
                new_h = max(1, int(img_h * scale))
                display = pil_frame.resize(
                    (new_w, new_h), Image.Resampling.BILINEAR)

                tk_img = ImageTk.PhotoImage(display)
                vid_label.config(image=tk_img, text="")
                vid_label._tk_img = tk_img

                lbl_fps.config(text=f"FPS: {fps_val:.1f}")
                lbl_ndet.config(
                    text=f"Đối tượng: {n_det}",
                    fg=SUCCESS if n_det > 0 else DIM)
                lbl_det_info.config(text=det_summary)
                if do_lpr:
                    lbl_lpr_info.config(
                        text=lpr_text,
                        fg="#50dc64" if lpr_text else DIM)
            except _q.Empty:
                pass
            except Exception:
                pass

            if _running[0]:
                _after_id[0] = win.after(16, _poll)

        threading.Thread(target=_worker, daemon=True).start()
        win.after(200, _poll)
