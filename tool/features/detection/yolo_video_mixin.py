# yolo_video_mixin.py — YoloVideoMixin — dialog chọn nguồn video (file/RTSP/webcam/YouTube)
import os
import threading
import time
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
    import yt_dlp as _yt_dlp
    _YTDLP_OK = True
except ImportError:
    _YTDLP_OK = False


_YT_QUALITY_FORMATS = {
    "Tốt nhất (Best)": "best[ext=mp4][protocol^=http]/best[protocol^=http]/best",
    "1080p":           "best[height<=1080][ext=mp4][protocol^=http]/best[height<=1080][protocol^=http]/best[height<=1080]/best",
    "720p":            "best[height<=720][ext=mp4][protocol^=http]/best[height<=720][protocol^=http]/best[height<=720]/best",
    "480p":            "best[height<=480][ext=mp4][protocol^=http]/best[height<=480][protocol^=http]/best[height<=480]/best",
    "360p":            "best[height<=360][ext=mp4][protocol^=http]/best[height<=360][protocol^=http]/best[height<=360]/best",
    "240p":            "best[height<=240][ext=mp4][protocol^=http]/best[height<=240][protocol^=http]/best[height<=240]/best",
    "Thấp nhất (Worst)": "worst[ext=mp4][protocol^=http]/worst[protocol^=http]/worst",
}
_YT_QUALITY_DEFAULT = "Tốt nhất (Best)"


def _resolve_youtube_stream(url: str, quality_label: str = _YT_QUALITY_DEFAULT) -> tuple:
    """Dùng yt-dlp lấy direct stream URL (progressive mp4/HLS) + tiêu đề video.

    Trả về (stream_url, title, is_live). Ném exception nếu không lấy được.
    `is_live=True` (livestream/HLS đang phát) → không cho tua vì không có
    frame count cố định; VOD progressive mp4 → tua được như file thường.
    """
    fmt = _YT_QUALITY_FORMATS.get(quality_label, _YT_QUALITY_FORMATS[_YT_QUALITY_DEFAULT])
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "format": fmt,
    }
    with _yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if "entries" in info and info["entries"]:
            info = info["entries"][0]
        stream_url = info.get("url")
        if not stream_url:
            raise RuntimeError("Không tìm thấy stream URL khả dụng")
        title = info.get("title") or url
        is_live = bool(info.get("is_live") or info.get("live_status") == "is_live")
        return stream_url, title, is_live



class YoloVideoMixin:
    """Mixin: dialog mở nguồn video (file/RTSP/webcam/YouTube) trước khi launch cửa sổ detect."""

    # ====================================================== VIDEO DETECTION ==

    def _open_video_detect(self):
        """Dialog chọn nguồn video, sau đó mở cửa sổ detect liên tục."""
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _CV2_OK or not _PIL_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python Pillow", parent=self.root)
            return

        dlg = Toplevel(self.root)
        dlg.title("Chọn nguồn video")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        Label(dlg, text="Nhận dạng YOLO liên tục từ video",
              font=F_BOLD, bg=BG, fg=TEXT).pack(padx=24, pady=(16, 4))

        # File video row
        file_frame = Frame(dlg, bg=BG)
        file_frame.pack(fill=X, padx=16, pady=(8, 2))
        Label(file_frame, text="File video:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_vidpath = StringVar()
        hist_vals = _get_history("h.yolo.video_path")
        combo_vid = ttk.Combobox(file_frame, textvariable=v_vidpath,
                                  font=F_MAIN, width=36)
        combo_vid["values"] = hist_vals
        if hist_vals:
            combo_vid.set(hist_vals[0])
        combo_vid.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.yolo.video_path", combo_vid)

        def _pick_video():
            p = filedialog.askopenfilename(
                title="Chọn file video",
                filetypes=[("Video", "*.mp4 *.avi *.mkv *.mov *.wmv *.m4v *.ts *.flv"),
                           ("All files", "*.*")],
                parent=dlg)
            if p:
                v_vidpath.set(p)
                _push_history("h.yolo.video_path", p)
                combo_vid["values"] = _get_history("h.yolo.video_path")

        Button(file_frame, text="Duyệt…", command=_pick_video,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT)

        # Loop checkbox
        v_loop = BooleanVar(value=True)
        loop_row = Frame(dlg, bg=BG)
        loop_row.pack(fill=X, padx=16, pady=(2, 4))
        Label(loop_row, text="", bg=BG, width=14).pack(side=LEFT)
        Checkbutton(loop_row, text="Lặp lại (Loop) khi hết video",
                    variable=v_loop, bg=BG, fg=TEXT,
                    activebackground=BG, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT)

        # RTSP / HTTP stream row
        rtsp_row = Frame(dlg, bg=BG)
        rtsp_row.pack(fill=X, padx=16, pady=(8, 2))
        Label(rtsp_row, text="RTSP / HTTP:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_rtsp = StringVar()
        rtsp_hist = _get_history("h.yolo.rtsp_url")
        combo_rtsp = ttk.Combobox(rtsp_row, textvariable=v_rtsp,
                                   font=F_MAIN, width=36)
        combo_rtsp["values"] = rtsp_hist
        combo_rtsp.set(rtsp_hist[0] if rtsp_hist else "rtsp://")
        combo_rtsp.pack(side=LEFT, fill=X, expand=True)
        _bind_history("h.yolo.rtsp_url", combo_rtsp)

        # YouTube row
        yt_row = Frame(dlg, bg=BG)
        yt_row.pack(fill=X, padx=16, pady=(8, 2))
        Label(yt_row, text="YouTube URL:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_yt = StringVar()
        yt_hist = _get_history("h.yolo.youtube_url")
        combo_yt = ttk.Combobox(yt_row, textvariable=v_yt,
                                 font=F_MAIN, width=36)
        combo_yt["values"] = yt_hist
        if yt_hist:
            combo_yt.set(yt_hist[0])
        combo_yt.pack(side=LEFT, fill=X, expand=True)
        _bind_history("h.yolo.youtube_url", combo_yt)

        # Độ phân giải YouTube
        yt_q_row = Frame(dlg, bg=BG)
        yt_q_row.pack(fill=X, padx=16, pady=(2, 2))
        Label(yt_q_row, text="Độ phân giải:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_yt_quality = StringVar(value=_YT_QUALITY_DEFAULT)
        _bind_cfg("yolo.youtube_quality", v_yt_quality)
        if v_yt_quality.get() not in _YT_QUALITY_FORMATS:
            v_yt_quality.set(_YT_QUALITY_DEFAULT)
        combo_yt_q = ttk.Combobox(yt_q_row, textvariable=v_yt_quality,
                                   font=F_MAIN, width=18, state="readonly",
                                   values=list(_YT_QUALITY_FORMATS.keys()))
        combo_yt_q.pack(side=LEFT)

        yt_status_row = Frame(dlg, bg=BG)
        yt_status_row.pack(fill=X, padx=16, pady=(0, 2))
        Label(yt_status_row, text="", bg=BG, width=14).pack(side=LEFT)
        lbl_yt_status = Label(yt_status_row, text="", bg=BG, fg=DIM,
                               font=("Segoe UI", 8), anchor=W)
        lbl_yt_status.pack(side=LEFT, fill=X, expand=True)

        # Separator
        Frame(dlg, bg=DIM, height=1).pack(fill=X, padx=16, pady=4)

        # Webcam row
        cam_row = Frame(dlg, bg=BG)
        cam_row.pack(fill=X, padx=16, pady=(2, 16))
        Label(cam_row, text="Webcam index:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_cam = StringVar(value="0")
        Spinbox(cam_row, from_=0, to=9, textvariable=v_cam,
                width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MONO,
                ).pack(side=LEFT, padx=(0, 8))
        Label(cam_row, text="(0 = camera mặc định)", bg=BG, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)

        # Buttons
        btn_frame = Frame(dlg, bg=BG)
        btn_frame.pack(pady=(0, 16))

        _result = [None]

        def _start_file():
            path = v_vidpath.get().strip()
            if not path:
                messagebox.showwarning("Chưa chọn", "Vui lòng chọn file video.",
                                       parent=dlg)
                return
            if not os.path.isfile(path):
                messagebox.showwarning("Không tìm thấy",
                                       f"File không tồn tại:\n{path}", parent=dlg)
                return
            _push_history("h.yolo.video_path", path)
            combo_vid["values"] = _get_history("h.yolo.video_path")
            _result[0] = ("file", path, v_loop.get())
            dlg.destroy()

        def _start_cam():
            try:
                idx = int(v_cam.get())
            except ValueError:
                idx = 0
            _result[0] = ("cam", idx, False)
            dlg.destroy()

        def _start_rtsp():
            url = v_rtsp.get().strip()
            if not url or url in ("rtsp://", "http://"):
                messagebox.showwarning("Chưa nhập URL",
                                       "Vui lòng nhập RTSP hoặc HTTP URL.",
                                       parent=dlg)
                return
            _push_history("h.yolo.rtsp_url", url)
            combo_rtsp["values"] = _get_history("h.yolo.rtsp_url")
            _result[0] = ("rtsp", url, False)
            dlg.destroy()

        _dlg_open = [True]

        def _cancel_dlg():
            _dlg_open[0] = False
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _cancel_dlg)

        def _start_youtube():
            url = v_yt.get().strip()
            if not url:
                messagebox.showwarning("Chưa nhập URL",
                                       "Vui lòng nhập link YouTube.", parent=dlg)
                return
            if not _YTDLP_OK:
                messagebox.showerror("Thiếu thư viện",
                                     "pip install yt-dlp", parent=dlg)
                return
            _push_history("h.yolo.youtube_url", url)
            combo_yt["values"] = _get_history("h.yolo.youtube_url")
            quality_label = v_yt_quality.get()

            btn_yt.config(state="disabled")
            lbl_yt_status.config(text="⏳ Đang phân giải link YouTube…", fg=DIM)

            def _worker():
                try:
                    stream_url, title, is_live = _resolve_youtube_stream(url, quality_label)
                except Exception as ex:
                    msg = str(ex)
                    self.root.after(0, lambda: _on_yt_error(msg))
                    return
                self.root.after(0, lambda: _on_yt_success(stream_url, title, is_live))

            threading.Thread(target=_worker, daemon=True).start()

        def _on_yt_error(msg):
            if not _dlg_open[0]:
                return
            btn_yt.config(state="normal")
            lbl_yt_status.config(text="", fg=DIM)
            messagebox.showerror("Lỗi YouTube",
                                 f"Không lấy được stream:\n{msg}", parent=dlg)

        def _on_yt_success(stream_url, title, is_live):
            if not _dlg_open[0]:
                return
            _result[0] = ("youtube", (stream_url, title, is_live), False)
            _cancel_dlg()

        Button(btn_frame, text="▶ Mở File Video", command=_start_file,
               bg=ACCENT, fg="white", font=F_BOLD, relief="flat",
               padx=12, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="📡 Mở RTSP", command=_start_rtsp,
               bg="#1a6b3c", fg="white", font=F_BOLD, relief="flat",
               padx=12, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        btn_yt = Button(btn_frame, text="▶ Mở YouTube", command=_start_youtube,
               bg="#c4302b", fg="white", font=F_BOLD, relief="flat",
               padx=12, cursor="hand2")
        btn_yt.pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="📷 Mở Webcam", command=_start_cam,
               bg="#2e5fa3", fg="white", font=F_BOLD, relief="flat",
               padx=12, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="Hủy", command=_cancel_dlg,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT)

        # Center dialog
        dlg.update_idletasks()
        x = (self.root.winfo_x()
             + (self.root.winfo_width()  - dlg.winfo_width())  // 2)
        y = (self.root.winfo_y()
             + (self.root.winfo_height() - dlg.winfo_height()) // 2)
        dlg.geometry(f"+{x}+{y}")

        self.root.wait_window(dlg)
        if _result[0] is None:
            return

        src_type, src_val, do_loop = _result[0]
        if src_type == "file":
            self._launch_video_window(src_val, os.path.basename(src_val), do_loop)
        elif src_type == "rtsp":
            self._launch_video_window(src_val, src_val, False)
        elif src_type == "youtube":
            stream_url, yt_title, is_live = src_val
            self._launch_video_window(stream_url, f"YouTube: {yt_title}", False,
                                       enable_seek=not is_live)
        else:
            self._launch_video_window(src_val, f"Webcam #{src_val}", False)
