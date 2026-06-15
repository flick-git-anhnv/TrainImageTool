import queue
import re
import threading
from pathlib import Path

_DATE_PAT = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_HH_PAT   = re.compile(r'^\d{2}$')
_TIME_PAT = re.compile(r'^\d{6}')


def migrate_image_structure(out_path: Path, log_fn, stop_event: threading.Event = None):
    """Di chuyển ảnh từ cấu trúc cũ sang cấu trúc mới (thêm thư mục giờ HH).

    Cũ: .../YYYY-MM-DD/HHmmss_xxx.jpg  (hoặc .../YYYY-MM-DD/<sub>/.../fname)
    Mới: .../YYYY-MM-DD/HH/HHmmss_xxx.jpg

    Hoạt động với mọi cấu trúc (ảnh thường + ảnh xấu) của cả 3 tab:
      LotteImage, Parkingv8, Parkingv6.

    Returns: (moved, skipped, errors)
    """
    moved = skipped = errors = 0

    all_imgs = sorted(out_path.rglob("*.jpg"))
    total = len(all_imgs)
    log_fn(f"Tìm thấy {total} ảnh .jpg")

    for i, img in enumerate(all_imgs, 1):
        if stop_event and stop_event.is_set():
            log_fn("Đã dừng.")
            break
        try:
            p = img.relative_to(out_path).parts

            # Tìm component đầu tiên dạng YYYY-MM-DD trong path (không tính fname)
            date_idx = None
            for idx, part in enumerate(p[:-1]):
                if _DATE_PAT.match(part):
                    date_idx = idx
                    break

            if date_idx is None:
                skipped += 1
                continue

            next_idx  = date_idx + 1
            next_part = p[next_idx]

            # Nếu component sau date đã là thư mục giờ (2 chữ số 00-23) → bỏ qua
            if _HH_PAT.match(next_part) and 0 <= int(next_part) <= 23:
                skipped += 1
                continue

            # Lấy giờ từ 2 ký tự đầu của tên file (HHmmss...)
            fname = p[-1]
            if not _TIME_PAT.match(fname):
                skipped += 1
                continue

            hour_s = fname[:2]
            if not (hour_s.isdigit() and 0 <= int(hour_s) <= 23):
                skipped += 1
                continue

            # Path mới: chèn thư mục HH ngay sau date
            new_parts = list(p[:next_idx]) + [hour_s] + list(p[next_idx:])
            new_path  = out_path.joinpath(*new_parts)

            if new_path.exists():
                skipped += 1
                continue

            new_path.parent.mkdir(parents=True, exist_ok=True)
            img.rename(new_path)
            moved += 1

        except Exception as e:
            errors += 1
            log_fn(f"  ✗ {img.name}: {e}")
            continue

        # Log ngoài try để lỗi hiển thị không tính vào error count
        if i <= 10 or moved % 200 == 0:
            tail_old = "/".join(p[-min(4, len(p)):])
            tail_new = "/".join(new_parts[-min(5, len(new_parts)):])
            log_fn(f"  [{i}/{total}] .../{tail_old}  →  .../{tail_new}")

    # Dọn thư mục rỗng
    removed_dirs = _remove_empty_dirs(out_path)
    if removed_dirs:
        log_fn(f"Đã xóa {removed_dirs} thư mục rỗng.")

    return moved, skipped, errors


def _remove_empty_dirs(root: Path) -> int:
    removed = 0
    for d in sorted(root.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            try:
                d.rmdir()
                removed += 1
            except Exception:
                pass
    return removed


def open_migrate_window(root_tk, out_path: Path):
    """Mở cửa sổ Toplevel chạy hiệu chỉnh cấu trúc thư mục ảnh.

    Returns: cửa sổ Toplevel (để caller lưu reference kiểm tra winfo_exists).
    """
    import tkinter as tk
    from tkinter import ttk

    # Đọc màu từ constants nếu có, fallback an toàn
    try:
        from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
    except ImportError:
        BG = "#1e1e2e"; CARD = "#2a2a3e"; ACCENT = "#F05922"
        ACCENT2 = "#4A3F8C"; TEXT = "#e0e0f0"; DIM = "#9090b0"
        F_MAIN = ("Segoe UI", 10); F_BOLD = ("Segoe UI Semibold", 10)
        F_MONO = ("Consolas", 9)

    win = tk.Toplevel(root_tk)
    win.title("Hiệu chỉnh cấu trúc thư mục → thêm thư mục giờ")
    win.configure(bg=BG)
    win.geometry("780x480")
    win.resizable(True, True)

    tk.Label(win, text=f"Thư mục: {out_path}", bg=BG, fg=TEXT,
             font=F_MAIN, anchor="w", wraplength=740).pack(
        fill=tk.X, padx=12, pady=(10, 2))
    tk.Label(win,
             text="Quét toàn bộ ảnh .jpg, di chuyển sang cấu trúc mới  "
                  "(.../YYYY-MM-DD/HH/HHmmss_...jpg).",
             bg=BG, fg=DIM, font=("Segoe UI", 8), anchor="w").pack(
        fill=tk.X, padx=12, pady=(0, 6))

    # Log area
    body = tk.Frame(win, bg=BG)
    body.pack(fill=tk.BOTH, expand=True, padx=8)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    log_txt = tk.Text(body, font=F_MONO, bg="#16162a", fg="#d4d4d4",
                      relief="flat", wrap=tk.WORD, state=tk.DISABLED)
    log_txt.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(body, command=log_txt.yview)
    sb.grid(row=0, column=1, sticky="ns")
    log_txt["yscrollcommand"] = sb.set

    # Bottom bar
    bot = tk.Frame(win, bg=BG, padx=8, pady=6)
    bot.pack(fill=tk.X)
    status_lbl = tk.Label(bot, text="Đang chuẩn bị...",
                          font=F_MAIN, fg=ACCENT, bg=BG, anchor="w")
    status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
    close_btn = tk.Button(
        bot, text="Đóng", command=win.destroy,
        bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
        padx=14, cursor="hand2", state=tk.DISABLED)
    close_btn.pack(side=tk.RIGHT)

    log_q    = queue.Queue()
    stop_ev  = threading.Event()
    win.protocol("WM_DELETE_WINDOW", lambda: (stop_ev.set(), win.destroy()))

    def _log(msg: str):
        log_q.put(msg)

    def _worker():
        moved, skipped, errors = migrate_image_structure(out_path, _log, stop_ev)
        log_q.put(f"__DONE__{moved}\t{skipped}\t{errors}")

    def _append(msg: str):
        log_txt.configure(state=tk.NORMAL)
        log_txt.insert(tk.END, msg + "\n")
        log_txt.see(tk.END)
        log_txt.configure(state=tk.DISABLED)

    def _poll():
        try:
            while True:
                msg = log_q.get_nowait()
                if msg.startswith("__DONE__"):
                    _, rest = msg.split("__DONE__", 1)
                    m, s, e = rest.split("\t")
                    color = "#4caf50" if int(e) == 0 else "#ff8844"
                    status_lbl.config(
                        text=f"Hoàn thành — Di chuyển: {m}   Bỏ qua: {s}   Lỗi: {e}",
                        fg=color)
                    close_btn.config(state=tk.NORMAL)
                    return
                _append(msg)
        except queue.Empty:
            pass
        win.after(120, _poll)

    threading.Thread(target=_worker, daemon=True).start()
    status_lbl.config(text="Đang xử lý...")
    win.after(120, _poll)
    win.lift()
    win.focus_set()
    return win
