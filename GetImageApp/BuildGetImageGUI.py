"""
KZTEK - Build Get Parking Image (GUI)
Chay PyInstaller va hien thi progress trong cua so Tkinter.
"""
import sys
import subprocess
import threading
import shutil
from pathlib import Path
from tkinter import *
from tkinter import ttk, messagebox

# ── Duong dan ──────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent           # GetImageApp/
PARENT_DIR  = SCRIPT_DIR.parent               # 3.Tools/  (chua package 'tool')
PY_FILE     = SCRIPT_DIR / "RunGetParkingImage.py"
APP_NAME    = "GetParkingImage"
DIST_DIR    = SCRIPT_DIR / "dist"
BUILD_DIR   = SCRIPT_DIR / "build"
SPEC_FILE   = SCRIPT_DIR / f"{APP_NAME}.spec"

# ── Mau KZTEK ─────────────────────────────────────────────────────────────────
BG      = "#1e1e2e"
CARD    = "#2a2a3e"
ACCENT  = "#F05922"
ACCENT2 = "#4A3F8C"
TEXT    = "#e0e0f0"
DIM     = "#9090b0"
GREEN   = "#4caf50"
RED     = "#f44336"
YELLOW  = "#ffb74d"
BLUE    = "#4fc3f7"
F_MAIN  = ("Segoe UI", 10)
F_BOLD  = ("Segoe UI", 10, "bold")
F_MONO  = ("Consolas", 9)

# ── Lenh PyInstaller FULL (lan dau hoac clean rebuild) ────────────────────────
_PYINSTALLER_FULL = [
    sys.executable, "-m", "PyInstaller",
    "--onefile", "--noconsole", "--noconfirm",
    "--name",        APP_NAME,
    "--distpath",    str(DIST_DIR),
    "--workpath",    str(BUILD_DIR),
    "--specpath",    str(SCRIPT_DIR),
    "--paths",       str(PARENT_DIR),
    # PIL
    "--hidden-import", "PIL._tkinter_finder",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageTk",
    "--hidden-import", "PIL.BmpImagePlugin",
    "--hidden-import", "PIL.JpegImagePlugin",
    "--hidden-import", "PIL.PngImagePlugin",
    # cv2 / numpy
    "--hidden-import", "cv2",
    "--hidden-import", "numpy",
    "--hidden-import", "numpy.core._multiarray_umath",
    "--hidden-import", "numpy.core._multiarray_tests",
    # requests
    "--hidden-import", "requests",
    "--hidden-import", "requests.adapters",
    "--hidden-import", "requests.auth",
    # matplotlib
    "--hidden-import", "matplotlib",
    "--hidden-import", "matplotlib.figure",
    "--hidden-import", "matplotlib.backends.backend_tkagg",
    # tkinterdnd2
    "--hidden-import", "tkinterdnd2",
    "--hidden-import", "collections.abc",
    # tool package
    "--hidden-import", "tool",
    "--hidden-import", "tool.core.imports",
    "--hidden-import", "tool.core.settings",
    "--hidden-import", "tool.core.constants",
    "--hidden-import", "tool.core.ui_helpers",
    "--hidden-import", "tool.features.collection.lotte_image",
    "--hidden-import", "tool.features.collection.parkingv8_image",
    "--hidden-import", "tool.features.collection.parkingv6_image",
    "--hidden-import", "tool.features.collection.lotte_consolidate",
    "--hidden-import", "tool.features.collection.tab_iparking_image",
    "--hidden-import", "tool.utils.bad_image_viewer",
    "--hidden-import", "tool.utils.migrate_structure",
    "--collect-all", "tkinterdnd2",
    "--collect-all", "matplotlib",
    # ── Loai bo ML framework nang (khong can cho IParkingImage) ──────────────
    "--exclude-module", "paddle",
    "--exclude-module", "paddlepaddle",
    "--exclude-module", "torch",
    "--exclude-module", "torchvision",
    "--exclude-module", "torchaudio",
    "--exclude-module", "tensorflow",
    "--exclude-module", "keras",
    "--exclude-module", "sklearn",
    "--exclude-module", "ultralytics",
    "--exclude-module", "onnxruntime",
    "--exclude-module", "onnx",
    "--exclude-module", "jax",
    "--exclude-module", "flax",
    # ── Loai bo cac package khong can ────────────────────────────────────────
    "--exclude-module", "pandas",
    "--exclude-module", "scipy",
    "--exclude-module", "IPython",
    "--exclude-module", "jupyter",
    "--exclude-module", "notebook",
    "--exclude-module", "matplotlib.tests",
    "--exclude-module", "matplotlib.testing",
    "--exclude-module", "numpy.tests",
    "--exclude-module", "PIL.tests",
    "--exclude-module", "cv2.gapi",
    "--exclude-module", "pytest",
    "--exclude-module", "_pytest",
    "--exclude-module", "setuptools",
    "--exclude-module", "distutils",
    "--exclude-module", "doctest",
    "--exclude-module", "unittest",
    "--exclude-module", "pydoc",
    "--exclude-module", "xmlrpc",
    str(PY_FILE),
]

# ── Lenh PyInstaller QUICK (dung lai .spec da co) ─────────────────────────────
def _make_quick_cmd():
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        str(SPEC_FILE),
    ]

# ── Cac buoc xap xi de cap nhat progress bar ──────────────────────────────────
_STEPS = [
    ("analyzing",            10),
    ("processing",           30),
    ("building pyz",         55),
    ("building pkg",         75),
    ("building exe",         90),
    ("completed successfully", 100),
]


def _tag_for_line(line: str) -> str:
    lo = line.lower()
    if any(w in lo for w in ("error", "exception", "traceback", "failed")):
        return "err"
    if any(w in lo for w in ("warning", "warn")):
        return "warn"
    if "info:" in lo:
        return "info"
    return ""


class BuildApp(Tk):
    def __init__(self):
        super().__init__()
        self.title(f"KZTEK - Build {APP_NAME}")
        self.geometry("960x660")
        self.minsize(720, 500)
        self.configure(bg=BG)
        try:
            self.state("zoomed")
        except Exception:
            pass

        self._proc     = None
        self._running  = False
        self._progress = 0
        self._build_cmd: list = []

        self._setup_style()
        self._build_ui()
        self._refresh_cache_status()
        self._log_info(f"Source : {PY_FILE}")
        self._log_info(f"Output : {DIST_DIR / (APP_NAME + '.exe')}")
        self._log_info(f"Parent : {PARENT_DIR}")
        self._log_dim("-" * 70)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Style ──────────────────────────────────────────────────────────────────

    def _setup_style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Build.Horizontal.TProgressbar",
                    troughcolor=CARD, background=ACCENT,
                    darkcolor=ACCENT, lightcolor=ACCENT,
                    bordercolor=CARD, thickness=6)
        s.configure("TScrollbar",
                    troughcolor=BG, background=CARD,
                    darkcolor=CARD, lightcolor=CARD,
                    arrowcolor=DIM)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = Frame(self, bg=ACCENT2, height=46)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text="  KZTEK  -  Build Get Parking Image",
              bg=ACCENT2, fg="white",
              font=("Segoe UI", 12, "bold")).pack(side=LEFT, padx=10)
        Label(hdr, text="kztek.net",
              bg=ACCENT2, fg="#b8b3d6",
              font=("Segoe UI", 9)).pack(side=RIGHT, padx=12)

        # Status bar
        sb = Frame(self, bg=CARD, padx=12, pady=5)
        sb.pack(fill=X)
        self._lbl_status = Label(sb, text="San sang build",
                                  bg=CARD, fg=TEXT, font=F_BOLD)
        self._lbl_status.pack(side=LEFT)
        self._lbl_size = Label(sb, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._lbl_size.pack(side=RIGHT)

        # Cache status
        cache_row = Frame(self, bg=BG, padx=12, pady=3)
        cache_row.pack(fill=X)
        Label(cache_row, text="Cache:", bg=BG, fg=DIM,
              font=("Segoe UI", 9)).pack(side=LEFT)
        self._lbl_spec  = Label(cache_row, text="spec", bg=BG,
                                 font=("Segoe UI", 9))
        self._lbl_spec.pack(side=LEFT, padx=(6, 0))
        self._lbl_build = Label(cache_row, text="build/", bg=BG,
                                 font=("Segoe UI", 9))
        self._lbl_build.pack(side=LEFT, padx=(8, 0))
        btn_clean = Button(cache_row, text="Xoa cache",
                           bg=CARD, fg=DIM, relief=FLAT,
                           font=("Segoe UI", 8), cursor="hand2",
                           activebackground=CARD, activeforeground=RED,
                           command=self._clean_cache)
        btn_clean.pack(side=RIGHT)

        # Progress bar
        pb_wrap = Frame(self, bg=BG, padx=12, pady=4)
        pb_wrap.pack(fill=X)
        self._pb = ttk.Progressbar(pb_wrap,
                                    style="Build.Horizontal.TProgressbar",
                                    mode="determinate", maximum=100)
        self._pb.pack(fill=X)
        self._lbl_step = Label(pb_wrap, text="", bg=BG, fg=DIM,
                                font=("Segoe UI", 8))
        self._lbl_step.pack(anchor=E, pady=(2, 0))

        # Log box
        log_wrap = Frame(self, bg=BG, padx=12, pady=4)
        log_wrap.pack(fill=BOTH, expand=True)

        log_hdr = Frame(log_wrap, bg=CARD, pady=2)
        log_hdr.pack(fill=X)
        Label(log_hdr, text="  Build Log", bg=CARD, fg=DIM,
              font=("Segoe UI", 9)).pack(side=LEFT)
        Button(log_hdr, text="Clear", bg=CARD, fg=DIM, relief=FLAT,
               font=("Segoe UI", 8), cursor="hand2",
               activebackground=CARD, activeforeground=TEXT,
               command=self._clear_log).pack(side=RIGHT, padx=6)

        inner = Frame(log_wrap, bg=BG)
        inner.pack(fill=BOTH, expand=True)
        self._log = Text(inner, bg="#0a0a14", fg=TEXT, font=F_MONO,
                          relief=FLAT, wrap=WORD, state=DISABLED,
                          selectbackground=ACCENT2)
        vsb = ttk.Scrollbar(inner, command=self._log.yview)
        self._log.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self._log.pack(fill=BOTH, expand=True)
        self._log.tag_config("ok",   foreground=GREEN)
        self._log.tag_config("err",  foreground=RED)
        self._log.tag_config("warn", foreground=YELLOW)
        self._log.tag_config("info", foreground=BLUE)
        self._log.tag_config("dim",  foreground=DIM)

        # Buttons
        btn_row = Frame(self, bg=CARD, pady=8, padx=12)
        btn_row.pack(fill=X, side=BOTTOM)

        self._btn_open = Button(
            btn_row, text="Mo thu muc dist",
            bg=ACCENT2, fg="white", activebackground="#6b5fb0",
            activeforeground="white", relief=FLAT,
            padx=12, pady=5, font=F_MAIN, cursor="hand2",
            state=DISABLED, command=self._open_dist)
        self._btn_open.pack(side=RIGHT, padx=(4, 0))

        self._btn_stop = Button(
            btn_row, text="Dung",
            bg="#444455", fg=TEXT, activebackground="#555566",
            relief=FLAT, padx=12, pady=5, font=F_MAIN, cursor="hand2",
            state=DISABLED, command=self._stop_build)
        self._btn_stop.pack(side=RIGHT, padx=6)

        # Full rebuild (luon clean)
        self._btn_full = Button(
            btn_row, text="Full Rebuild",
            bg=CARD, fg=TEXT, activebackground=ACCENT2,
            activeforeground="white", relief=FLAT,
            padx=12, pady=5, font=F_MAIN, cursor="hand2",
            command=self._start_full)
        self._btn_full.pack(side=RIGHT, padx=4)

        # Quick build (dung lai cache)
        self._btn_quick = Button(
            btn_row, text="Quick Build  (F5)",
            bg=ACCENT, fg="white", activebackground="#d04510",
            activeforeground="white", relief=FLAT,
            padx=16, pady=5, font=F_BOLD, cursor="hand2",
            command=self._start_quick)
        self._btn_quick.pack(side=RIGHT, padx=6)

        self.bind("<F5>",     lambda e: self._start_quick())
        self.bind("<Escape>", lambda e: self._stop_build())

    # ── Cache status ───────────────────────────────────────────────────────────

    def _refresh_cache_status(self):
        has_spec  = SPEC_FILE.exists()
        has_build = BUILD_DIR.exists()
        self._lbl_spec.configure(
            text=f"spec: {'co' if has_spec  else 'chua co'}",
            fg=GREEN if has_spec  else DIM)
        self._lbl_build.configure(
            text=f"build/: {'co' if has_build else 'chua co'}",
            fg=GREEN if has_build else DIM)
        # Quick build chi kha dung khi co spec
        if has_spec and not self._running:
            self._btn_quick.configure(
                text="Quick Build  (F5)  [dung spec]", bg=ACCENT)
        elif not self._running:
            self._btn_quick.configure(
                text="Quick Build  (F5)  [full]", bg=ACCENT2)

    def _clean_cache(self):
        if self._running:
            return
        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR, ignore_errors=True)
        if SPEC_FILE.exists():
            SPEC_FILE.unlink(missing_ok=True)
        self._log_dim("[INFO] Da xoa cache (build/ va spec).")
        self._refresh_cache_status()

    # ── Log helpers ────────────────────────────────────────────────────────────

    def _log_write(self, text: str, tag: str = ""):
        self._log.configure(state=NORMAL)
        self._log.insert(END, text, tag)
        self._log.see(END)
        self._log.configure(state=DISABLED)

    def _log_ok(self, msg):   self._log_write(msg + "\n", "ok")
    def _log_err(self, msg):  self._log_write(msg + "\n", "err")
    def _log_warn(self, msg): self._log_write(msg + "\n", "warn")
    def _log_info(self, msg): self._log_write(msg + "\n", "info")
    def _log_dim(self, msg):  self._log_write(msg + "\n", "dim")

    def _clear_log(self):
        self._log.configure(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.configure(state=DISABLED)

    # ── Build logic ────────────────────────────────────────────────────────────

    def _start_quick(self):
        """Dung lai spec + build cache neu co, ngược lai full build."""
        if self._running:
            return
        if SPEC_FILE.exists():
            self._build_cmd = _make_quick_cmd()
            self._run(mode="Quick (spec cache)")
        else:
            self._build_cmd = _PYINSTALLER_FULL
            self._run(mode="Full (lan dau)")

    def _start_full(self):
        """Luon xoa cache va build lai tu dau."""
        if self._running:
            return
        self._clean_cache()
        self._build_cmd = _PYINSTALLER_FULL
        self._run(mode="Full Rebuild (clean)")

    def _run(self, mode: str):
        if not PY_FILE.exists():
            messagebox.showerror("Loi", f"Khong tim thay:\n{PY_FILE}")
            return

        self._running  = True
        self._progress = 0
        self._pb["value"] = 0
        self._pb["mode"] = "indeterminate"
        self._pb.start(12)
        self._lbl_step.configure(text="Khoi dong PyInstaller...")
        self._set_status(f"Dang build  [{mode}]...", BLUE)
        self._lbl_size.configure(text="")
        self._btn_quick.configure(state=DISABLED)
        self._btn_full.configure(state=DISABLED)
        self._btn_stop.configure(state=NORMAL)
        self._btn_open.configure(state=DISABLED)

        self._clear_log()
        self._log_info(f"Mode   : {mode}")
        self._log_info(f"Source : {PY_FILE}")
        self._log_info(f"Output : {DIST_DIR / (APP_NAME + '.exe')}")
        self._log_dim("-" * 70)

        threading.Thread(target=self._run_pyinstaller, daemon=True).start()

    def _run_pyinstaller(self):
        try:
            self._proc = subprocess.Popen(
                self._build_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(PARENT_DIR),
            )

            for raw_line in self._proc.stdout:
                line = raw_line.rstrip("\n")
                tag  = _tag_for_line(line)
                self.after(0, self._log_write, line + "\n", tag)
                for keyword, pct in _STEPS:
                    if keyword in line.lower() and pct > self._progress:
                        self._progress = pct
                        self.after(0, self._update_progress, pct, keyword)
                        break

            self._proc.wait()
            rc = self._proc.returncode
            self.after(0, self._on_done, rc)

        except Exception as ex:
            self.after(0, self._log_err, f"\n[LOI] {ex}")
            self.after(0, self._on_done, 1)

    def _update_progress(self, pct: int, label: str):
        self._pb.stop()
        self._pb["mode"] = "determinate"
        self._pb["value"] = pct
        self._lbl_step.configure(text=f"{pct}%  -  {label}...")

    def _on_done(self, rc: int):
        self._running = False
        self._pb.stop()
        self._pb["mode"] = "determinate"
        self._btn_quick.configure(state=NORMAL)
        self._btn_full.configure(state=NORMAL)
        self._btn_stop.configure(state=DISABLED)
        self._refresh_cache_status()

        exe = DIST_DIR / f"{APP_NAME}.exe"
        if rc == 0 and exe.exists():
            size_mb = exe.stat().st_size / 1048576
            self._pb["value"] = 100
            self._lbl_step.configure(text="100%  -  Hoan thanh!")
            self._set_status("BUILD THANH CONG!", GREEN)
            self._lbl_size.configure(text=f"{size_mb:.1f} MB", fg=GREEN)
            self._log_dim("-" * 70)
            self._log_ok(f"BUILD THANH CONG!  ({size_mb:.1f} MB)")
            self._log_ok(f"EXE: {exe}")
            self._btn_open.configure(state=NORMAL)
        else:
            self._pb["value"] = 0
            self._lbl_step.configure(text="")
            self._set_status("BUILD THAT BAI!", RED)
            self._log_dim("-" * 70)
            self._log_err(f"BUILD THAT BAI  (exit code: {rc})")

    def _set_status(self, text: str, color: str = TEXT):
        self._lbl_status.configure(text=text, fg=color)

    def _stop_build(self):
        if self._proc and self._running:
            self._proc.terminate()
            self._log_warn("\n[WARN] Da dung build.")
            self._on_done(-1)

    def _open_dist(self):
        subprocess.Popen(["explorer", str(DIST_DIR)])

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("Xac nhan", "Build dang chay. Thoat va huy?"):
                return
            self._stop_build()
        self.destroy()


if __name__ == "__main__":
    BuildApp().mainloop()
