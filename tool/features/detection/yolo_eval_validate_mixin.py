# yolo_eval_validate_mixin.py — YoloEvalValidateMixin — validate thư mục true/false (positive/negative)
import os
import threading
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
from ...shared.lazy_import import module_available, lazy_callable

_YOLO_OK = module_available("ultralytics")   # lazy — xem shared/lazy_import.py
YOLO     = lazy_callable("ultralytics", "YOLO")
from .yolo_utils import _iou_xywhn


class YoloEvalValidateMixin:
    """Mixin: validate thư mục true/false (positive/negative) — 1 hàm lớn duy nhất."""

    # ====================================================== VALIDATE TRUE/ ==

    def _validate_true_folder(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return

        # Xác định thư mục true/
        base = self._base_folder
        if not base:
            # Thử lấy từ ô path
            p = self.v_check_folder.get().strip()
            if os.path.isfile(p):
                base = os.path.dirname(p)
            elif os.path.isdir(p):
                base = p

        true_dir = os.path.join(base, "true") if base else None
        if not true_dir or not os.path.isdir(true_dir):
            # Fallback: hỏi người dùng chọn thư mục true/
            true_dir = filedialog.askdirectory(
                title="Chọn thư mục true/ (ảnh đã đánh dấu đúng)",
                parent=self.root)
            if not true_dir:
                return

        img_files = sorted([
            os.path.join(true_dir, f) for f in os.listdir(true_dir)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])
        if not img_files:
            messagebox.showinfo("Thông báo",
                                f"Không tìm thấy ảnh trong:\n{true_dir}",
                                parent=self.root)
            return

        # ── Tạo cửa sổ kết quả ──
        popup = Toplevel(self.root)
        popup.title(f"Validate Model — {os.path.basename(true_dir)}")
        popup.configure(bg=BG)
        popup.geometry("820x620")
        popup.resizable(True, True)

        # Header
        Label(popup, text=f"🔍 Validate: {true_dir}",
              font=F_BOLD, bg=BG, fg=TEXT, anchor=W).pack(fill=X, padx=10, pady=(8, 2))

        pb = ttk.Progressbar(popup, mode="determinate", maximum=len(img_files))
        pb.pack(fill=X, padx=10, pady=(0, 2))
        v_prog = StringVar(value=f"0 / {len(img_files)}")
        Label(popup, textvariable=v_prog, font=F_MONO, bg=BG, fg=DIM).pack()

        # Summary frame
        sum_frame = Frame(popup, bg=CARD, padx=10, pady=6)
        sum_frame.pack(fill=X, padx=10, pady=(4, 2))
        lbl_sum = Label(sum_frame, text="Đang xử lý...",
                        font=F_MONO, bg=CARD, fg=TEXT, justify=LEFT, anchor=W)
        lbl_sum.pack(fill=X)

        # Assessment frame (hiện sau khi có kết quả)
        assess_frame = Frame(popup, bg="#0d0d1a", padx=10, pady=6)
        assess_frame.pack(fill=X, padx=10, pady=(0, 4))
        lbl_verdict = Label(assess_frame, text="",
                            font=F_BOLD, bg="#0d0d1a", fg=TEXT, justify=LEFT, anchor=W)
        lbl_verdict.pack(fill=X)
        lbl_advice = Label(assess_frame, text="",
                           font=F_MAIN, bg="#0d0d1a", fg=DIM, justify=LEFT, anchor=W,
                           wraplength=780)
        lbl_advice.pack(fill=X)

        # Notebook: per-class table | per-image list | glossary
        nb = ttk.Notebook(popup)
        nb.pack(fill=BOTH, expand=True, padx=10, pady=(4, 8))

        # Tab 1 — Per-class
        tab_cls = Frame(nb, bg=BG)
        nb.add(tab_cls, text="Theo Class")

        cls_style = ttk.Style()
        cls_style.configure("Val.Treeview",
                            background="#0d0d1a", foreground=TEXT,
                            fieldbackground="#0d0d1a", rowheight=22, font=F_MONO)
        cls_style.configure("Val.Treeview.Heading", background=CARD, foreground=TEXT)
        cls_style.map("Val.Treeview", background=[("selected", ACCENT2)])

        cls_cols = ("class", "tp", "fp", "fn", "precision", "recall", "f1")
        cls_tree = ttk.Treeview(tab_cls, columns=cls_cols, show="headings",
                                 style="Val.Treeview")
        for col, hd, w in [
            ("class",     "Class",     160),
            ("tp",        "TP",         50),
            ("fp",        "FP",         50),
            ("fn",        "FN",         50),
            ("precision", "Precision",  90),
            ("recall",    "Recall",     80),
            ("f1",        "F1",         70),
        ]:
            cls_tree.heading(col, text=hd)
            cls_tree.column(col, width=w, anchor=CENTER if col != "class" else W)
        sb_cls = Scrollbar(tab_cls, orient=VERTICAL, command=cls_tree.yview)
        cls_tree.configure(yscrollcommand=sb_cls.set)
        sb_cls.pack(side=RIGHT, fill=Y)
        cls_tree.pack(fill=BOTH, expand=True)
        cls_tree.tag_configure("good",   foreground="#4caf50")
        cls_tree.tag_configure("medium", foreground="#ffcc00")
        cls_tree.tag_configure("bad",    foreground=ACCENT)

        # Tab 2 — Per-image
        tab_img = Frame(nb, bg=BG)
        nb.add(tab_img, text="Theo Ảnh")

        img_cols = ("name", "gt", "pred", "tp", "fp", "fn", "status")
        img_tree = ttk.Treeview(tab_img, columns=img_cols, show="headings",
                                 style="Val.Treeview")
        for col, hd, w in [
            ("name",   "Tên ảnh",  200),
            ("gt",     "GT",        40),
            ("pred",   "Pred",      40),
            ("tp",     "TP",        40),
            ("fp",     "FP",        40),
            ("fn",     "FN",        40),
            ("status", "Trạng thái",100),
        ]:
            img_tree.heading(col, text=hd)
            img_tree.column(col, width=w, anchor=CENTER if col != "name" else W)
        sb_img_v = Scrollbar(tab_img, orient=VERTICAL, command=img_tree.yview)
        sb_img_h = Scrollbar(tab_img, orient=HORIZONTAL, command=img_tree.xview)
        img_tree.configure(yscrollcommand=sb_img_v.set, xscrollcommand=sb_img_h.set)
        sb_img_v.pack(side=RIGHT, fill=Y)
        sb_img_h.pack(side=BOTTOM, fill=X)
        img_tree.pack(fill=BOTH, expand=True)
        img_tree.tag_configure("perfect", foreground="#4caf50")
        img_tree.tag_configure("partial", foreground="#ffcc00")
        img_tree.tag_configure("bad",     foreground=ACCENT)
        img_tree.tag_configure("nolabel", foreground=DIM)

        # Tab 3 — Thuật ngữ
        tab_term = Frame(nb, bg=BG)
        nb.add(tab_term, text="Thuật ngữ")

        term_data = [
            ("TP  —  True Positive", "#4caf50",
             "Model phát hiện ĐÚNG một object: đúng class VÀ bbox chồng lấp ≥ 50% (IoU ≥ 0.5).",
             "Càng cao càng tốt."),
            ("FP  —  False Positive", ACCENT,
             "Model phát hiện THỪA: báo có object nhưng thực tế không có "
             "(hoặc detect sai class, hoặc trùng lặp).",
             "Càng thấp càng tốt.  Khắc phục: tăng Conf Threshold."),
            ("FN  —  False Negative", "#ff9800",
             "Model BỎ SÓT: có object trong label nhưng không detect được.",
             "Càng thấp càng tốt.  Khắc phục: giảm Conf Threshold hoặc thêm dữ liệu train."),
            ("GT  —  Ground Truth", "#90caf9",
             "Số bbox chuẩn được ghi trong file label .txt — dùng làm chuẩn để so sánh.",
             "Chuẩn tham chiếu, không đánh giá cao thấp."),
            ("Pred  —  Prediction", "#90caf9",
             "Số bbox model dự đoán ra trong ảnh.",
             "Lý tưởng: Pred ≈ GT.  Pred >> GT → nhiều FP.  Pred << GT → nhiều FN."),
            ("Precision", "#ce93d8",
             "= TP / (TP + FP)\n"
             "Tỷ lệ detect ĐÚNG trong tổng số lần model phát hiện.\n"
             "Ví dụ: Precision = 0.97  →  97% dự đoán của model là chính xác.",
             "≥ 0.90 là tốt."),
            ("Recall", "#ce93d8",
             "= TP / (TP + FN)\n"
             "Tỷ lệ tìm thấy trong tổng số object THỰC TẾ có trong ảnh.\n"
             "Ví dụ: Recall = 0.78  →  model tìm thấy 78%, bỏ sót 22%.",
             "≥ 0.80 là tốt."),
            ("F1-Score", "#ce93d8",
             "= 2 × Precision × Recall / (Precision + Recall)\n"
             "Chỉ số TỔNG HỢP cân bằng giữa Precision và Recall.\n"
             "F1 = 1.0 là hoàn hảo.  F1 = 0 là không detect được gì.",
             "≥ 0.85 là tốt.  Dùng F1 khi P và R lệch nhau."),
            ("IoU  —  Intersection over Union", "#80cbc4",
             "Độ chồng lấp giữa bbox dự đoán và bbox chuẩn.\n"
             "IoU = Diện tích phần giao / Diện tích phần hợp  (0 → 1).\n"
             "Công cụ này dùng ngưỡng IoU = 0.5 để xác định TP hay FP.",
             "0.5 là ngưỡng tiêu chuẩn (mAP@50).  0.75 là tiêu chuẩn nghiêm."),
        ]

        sb_term = Scrollbar(tab_term, orient=VERTICAL)
        sb_term.pack(side=RIGHT, fill=Y)
        term_txt = Text(tab_term, bg="#0d0d1a", fg=TEXT,
                        font=("Segoe UI", 10), relief="flat", bd=0,
                        wrap=WORD, padx=14, pady=8, state=NORMAL,
                        yscrollcommand=sb_term.set, cursor="arrow")
        term_txt.pack(fill=BOTH, expand=True)
        sb_term.config(command=term_txt.yview)

        # Cấu hình tag màu
        term_txt.tag_configure("term",    font=("Segoe UI", 11, "bold"), spacing1=10)
        term_txt.tag_configure("body",    font=("Segoe UI", 10),         lmargin1=20, lmargin2=20)
        term_txt.tag_configure("good",    font=("Segoe UI", 9, "italic"), lmargin1=20,
                                foreground="#aaaacc", spacing3=8)
        term_txt.tag_configure("divider", foreground="#333355", spacing1=2, spacing3=2)

        for term_name, term_color, meaning, good_when in term_data:
            term_txt.tag_configure(f"t_{term_name}", foreground=term_color)
            term_txt.insert(END, f"▌ {term_name}\n", ("term", f"t_{term_name}"))
            term_txt.insert(END, f"{meaning}\n", "body")
            term_txt.insert(END, f"  → Tốt khi: {good_when}\n", "good")
            term_txt.insert(END, "─" * 90 + "\n", "divider")

        term_txt.config(state=DISABLED)

        def _term_scroll(e):
            term_txt.yview_scroll(int(-1*(e.delta/120)), "units")
        term_txt.bind("<MouseWheel>", _term_scroll)

        # ── Capture params trên main thread trước khi spawn thread ──
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()

        # ── Background thread ──
        def run():
            iou_thresh = 0.5

            per_class_tp = {}; per_class_fp = {}; per_class_fn = {}
            img_results = []
            img_detail = {}
            tp_total = fp_total = fn_total = 0
            processed = skipped = 0

            for i, img_path in enumerate(img_files):
                self.root.after(0, lambda v=i+1: (
                    pb.config(value=v),
                    v_prog.set(f"{v} / {len(img_files)}"),
                ))

                base_name = os.path.splitext(os.path.basename(img_path))[0]
                lbl_path = os.path.join(os.path.dirname(img_path), base_name + ".txt")

                if not os.path.isfile(lbl_path):
                    img_results.append((img_path, None, None, None, None, None))
                    skipped += 1
                    continue

                try:
                    gt_boxes = []
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 5:
                                cid = int(parts[0])
                                cx, cy, bw, bh = map(float, parts[1:])
                                gt_boxes.append((cid, cx, cy, bw, bh))

                    results = self.model.predict(
                        source=img_path, conf=conf_val, iou=iou_val,
                        imgsz=640, agnostic_nms=True, verbose=False,
                    )
                    pred_boxes = []
                    boxes_res = results[0].boxes
                    if boxes_res is not None:
                        for box in boxes_res:
                            cid = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            pred_boxes.append((cid, *xywhn))

                    matched_gt = set()
                    tp_img = fp_img = fn_img = 0
                    tp_pred_idx = set()

                    for pi, pb_box in enumerate(pred_boxes):
                        p_cls = pb_box[0]
                        p_cx, p_cy, p_bw, p_bh = pb_box[1:]
                        best_iou = 0.0; best_gi = -1
                        for gi, gb_box in enumerate(gt_boxes):
                            if gi in matched_gt or gb_box[0] != p_cls:
                                continue
                            iou_v = _iou_xywhn(p_cx, p_cy, p_bw, p_bh,
                                               gb_box[1], gb_box[2], gb_box[3], gb_box[4])
                            if iou_v > best_iou:
                                best_iou = iou_v; best_gi = gi
                        if best_iou >= iou_thresh and best_gi >= 0:
                            matched_gt.add(best_gi)
                            tp_pred_idx.add(pi)
                            tp_img += 1
                            per_class_tp[p_cls] = per_class_tp.get(p_cls, 0) + 1
                        else:
                            fp_img += 1
                            per_class_fp[p_cls] = per_class_fp.get(p_cls, 0) + 1

                    for gi, gb_box in enumerate(gt_boxes):
                        if gi not in matched_gt:
                            g_cls = gb_box[0]
                            fn_img += 1
                            per_class_fn[g_cls] = per_class_fn.get(g_cls, 0) + 1

                    img_detail[img_path] = {
                        "gt": list(gt_boxes),
                        "pred": list(pred_boxes),
                        "tp_pred": set(tp_pred_idx),
                        "matched_gt": set(matched_gt),
                    }
                    tp_total += tp_img; fp_total += fp_img; fn_total += fn_img
                    img_results.append((img_path, len(gt_boxes), len(pred_boxes),
                                        tp_img, fp_img, fn_img))
                    processed += 1

                except Exception as ex:
                    img_results.append((img_path, None, None, None, None, str(ex)))

            # ── Cập nhật UI từ main thread ──
            def _update_ui():
                pb.config(value=len(img_files))

                # Summary
                prec = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
                rec  = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
                f1   = (2*prec*rec / (prec+rec)) if (prec+rec) > 0 else 0.0
                lbl_sum.config(
                    text=(f"Thư mục: {true_dir}\n"
                          f"Tổng ảnh: {len(img_files)}  |  Có label: {processed}  |  Bỏ qua: {skipped}\n"
                          f"TP={tp_total}  FP={fp_total}  FN={fn_total}"
                          f"    Precision={prec:.4f}  Recall={rec:.4f}  F1={f1:.4f}")
                )

                # Đánh giá tổng thể
                if f1 >= 0.90:
                    verdict_text = "★★★★★  XUẤT SẮC"
                    verdict_color = "#4caf50"
                elif f1 >= 0.80:
                    verdict_text = "★★★★  TỐT — Model đáp ứng yêu cầu sử dụng"
                    verdict_color = "#8bc34a"
                elif f1 >= 0.65:
                    verdict_text = "★★★  KHÁ — Cần cải thiện thêm"
                    verdict_color = "#ffcc00"
                elif f1 >= 0.50:
                    verdict_text = "★★  TRUNG BÌNH — Chưa ổn định"
                    verdict_color = "#ff9800"
                else:
                    verdict_text = "★  YẾU — Cần train lại hoặc bổ sung dữ liệu"
                    verdict_color = ACCENT

                advice_lines = []
                if prec < 0.85:
                    advice_lines.append(
                        f"• Precision={prec:.3f} thấp → model detect nhầm nhiều (FP cao) "
                        "→ Tăng Conf Threshold hoặc lọc thêm dữ liệu nhiễu khi train.")
                if rec < 0.80:
                    advice_lines.append(
                        f"• Recall={rec:.3f} thấp → model bỏ sót object (FN cao) "
                        "→ Giảm Conf Threshold, hoặc thêm ảnh train đa dạng hơn.")

                # Cảnh báo class yếu
                all_cls_check = set(list(per_class_tp) + list(per_class_fp) + list(per_class_fn))
                weak_classes = []
                for cid in sorted(all_cls_check):
                    tp_c = per_class_tp.get(cid, 0)
                    fp_c = per_class_fp.get(cid, 0)
                    fn_c = per_class_fn.get(cid, 0)
                    p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                    r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                    f1_c = (2*p_c*r_c / (p_c+r_c)) if (p_c+r_c) > 0 else 0.0
                    cname = self.model.names.get(cid, str(cid))
                    if f1_c < 0.5:
                        weak_classes.append(f"[{cid}]{cname}(F1={f1_c:.2f})")
                if weak_classes:
                    advice_lines.append(
                        f"• Class yếu cần bổ sung dữ liệu: {', '.join(weak_classes)}")

                if not advice_lines:
                    advice_lines.append("Không có điểm yếu đáng kể. Model hoạt động ổn định.")

                lbl_verdict.config(text=f"Đánh giá: {verdict_text}  "
                                        f"(F1={f1:.4f}  P={prec:.4f}  R={rec:.4f})",
                                   fg=verdict_color)
                lbl_advice.config(text="\n".join(advice_lines))

                # Per-class table
                all_cls = set(list(per_class_tp) + list(per_class_fp) + list(per_class_fn))
                for cid in sorted(all_cls):
                    cname = self.model.names.get(cid, str(cid))
                    tp_c = per_class_tp.get(cid, 0)
                    fp_c = per_class_fp.get(cid, 0)
                    fn_c = per_class_fn.get(cid, 0)
                    p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                    r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                    f1_c = (2*p_c*r_c / (p_c+r_c)) if (p_c+r_c) > 0 else 0.0
                    tag = "good" if f1_c >= 0.8 else ("medium" if f1_c >= 0.5 else "bad")
                    cls_tree.insert("", END, values=(
                        f"[{cid}] {cname}", tp_c, fp_c, fn_c,
                        f"{p_c:.3f}", f"{r_c:.3f}", f"{f1_c:.3f}",
                    ), tags=(tag,))

                # Per-image table (sắp xếp: ảnh tệ nhất lên đầu)
                def sort_key(r):
                    if r[3] is None:  return (3, 0)
                    fp_i, fn_i = r[4] or 0, r[5] or 0
                    return (0 if (fp_i + fn_i) == 0 else 1 if (fp_i + fn_i) <= 2 else 2,
                            -(fp_i + fn_i))
                img_results.sort(key=sort_key)

                for row in img_results:
                    img_path, n_gt, n_pred, tp_i, fp_i, fn_i = row
                    fname = os.path.basename(img_path)
                    if n_gt is None and isinstance(fn_i, str):
                        img_tree.insert("", END,
                            values=(fname, "?", "?", "?", "?", "?", f"Lỗi: {fn_i}"),
                            tags=("bad",))
                    elif n_gt is None:
                        img_tree.insert("", END,
                            values=(fname, "-", "-", "-", "-", "-", "Không có label"),
                            tags=("nolabel",))
                    else:
                        if fp_i + fn_i == 0:
                            status, tag = "✓ Hoàn hảo", "perfect"
                        elif fp_i + fn_i <= 2:
                            status, tag = f"△ FP={fp_i} FN={fn_i}", "partial"
                        else:
                            status, tag = f"✗ FP={fp_i} FN={fn_i}", "bad"
                        img_tree.insert("", END,
                            values=(fname, n_gt, n_pred, tp_i, fp_i, fn_i, status),
                            tags=(tag,))

                # ── Click row → xem ảnh với bbox màu TP/FP/FN ──
                fname_to_path = {os.path.basename(p): p for p in img_detail}

                def _on_row_select(e, _tree=img_tree, _ftp=fname_to_path,
                                   _detail=img_detail, _pop=popup):
                    sel = _tree.selection()
                    if not sel:
                        return
                    vals = _tree.item(sel[0], "values")
                    if not vals:
                        return
                    ipath = _ftp.get(vals[0])
                    if not ipath or ipath not in _detail:
                        return
                    _show_img_detail(ipath, _detail[ipath], _pop)

                def _show_img_detail(ipath, detail, parent_win):
                    if not _PIL_OK:
                        messagebox.showerror("Lỗi", "Cần cài Pillow để xem ảnh",
                                             parent=parent_win)
                        return
                    try:
                        pil_src = Image.open(ipath).convert("RGB")
                    except Exception as ex:
                        messagebox.showerror("Lỗi ảnh", str(ex), parent=parent_win)
                        return

                    W, H = pil_src.size
                    pil_ann = pil_src.copy()
                    drw = ImageDraw.Draw(pil_ann)
                    mnames = self.model.names if self.model else {}
                    lw = max(2, int(min(W, H) / 250))

                    def _box_px(cx, cy, bw, bh):
                        return (max(0, int((cx-bw/2)*W)), max(0, int((cy-bh/2)*H)),
                                min(W-1, int((cx+bw/2)*W)), min(H-1, int((cy+bh/2)*H)))

                    def _label(x, y, text, color):
                        try:
                            drw.text((x, y), text, fill=color,
                                     stroke_width=1, stroke_fill="#000000")
                        except TypeError:
                            drw.text((x, y), text, fill=color)

                    # FN: missed GT — vàng, vẽ trước (lớp dưới)
                    for gi, gb in enumerate(detail["gt"]):
                        if gi not in detail["matched_gt"]:
                            cid, cx, cy, bw, bh = gb
                            x1, y1, x2, y2 = _box_px(cx, cy, bw, bh)
                            drw.rectangle([x1, y1, x2, y2], outline="#ffcc00", width=lw)
                            _label(x1+2, y1+2,
                                   f"FN [{cid}]{mnames.get(cid,str(cid))}", "#ffcc00")

                    # Pred boxes: TP=xanh, FP=cam — vẽ sau (lớp trên)
                    for pi, pb in enumerate(detail["pred"]):
                        cid, cx, cy, bw, bh = pb
                        x1, y1, x2, y2 = _box_px(cx, cy, bw, bh)
                        cname = mnames.get(cid, str(cid))
                        if pi in detail["tp_pred"]:
                            color, lbl = "#4caf50", f"TP [{cid}]{cname}"
                        else:
                            color, lbl = "#F05922", f"FP [{cid}]{cname}"
                        drw.rectangle([x1+lw, y1+lw, x2-lw, y2-lw],
                                      outline=color, width=lw)
                        ty = min(H-14, y2-lw-14)
                        _label(x1+lw+2, ty, lbl, color)

                    # Cửa sổ hiển thị
                    dwin = Toplevel(parent_win)
                    dwin.title(f"Chi tiết: {os.path.basename(ipath)}")
                    dwin.configure(bg=BG)
                    dwin.resizable(True, True)
                    dwin.protocol("WM_DELETE_WINDOW", dwin.destroy)

                    # Legend + stats
                    leg = Frame(dwin, bg=CARD, padx=8, pady=4)
                    leg.pack(fill=X)
                    n_tp = len(detail["tp_pred"])
                    n_fp = len(detail["pred"]) - n_tp
                    n_fn = len(detail["gt"]) - len(detail["matched_gt"])
                    for txt, col in [("■ TP (Đúng)", "#4caf50"),
                                     ("■ FP (Thừa)", "#F05922"),
                                     ("■ FN (Bỏ sót)", "#ffcc00")]:
                        Label(leg, text=txt, fg=col, bg=CARD,
                              font=F_MONO).pack(side=LEFT, padx=10)
                    Label(leg,
                          text=f"GT={len(detail['gt'])}  TP={n_tp}  FP={n_fp}  FN={n_fn}",
                          fg=DIM, bg=CARD, font=F_MONO).pack(side=RIGHT, padx=10)

                    # Scale ảnh vừa màn hình
                    sw2 = dwin.winfo_screenwidth()
                    sh2 = dwin.winfo_screenheight()
                    img_disp = pil_ann.copy()
                    img_disp.thumbnail((int(sw2*0.85), int(sh2*0.80)), Image.LANCZOS)

                    frm = Frame(dwin, bg="#0d0d1a")
                    frm.pack(fill=BOTH, expand=True)
                    det_canvas = Canvas(frm, bg="#0d0d1a", highlightthickness=0)
                    sb_dv = Scrollbar(frm, orient=VERTICAL, command=det_canvas.yview)
                    sb_dh = Scrollbar(dwin, orient=HORIZONTAL, command=det_canvas.xview)
                    det_canvas.configure(yscrollcommand=sb_dv.set,
                                         xscrollcommand=sb_dh.set)
                    sb_dh.pack(side=BOTTOM, fill=X)
                    sb_dv.pack(side=RIGHT, fill=Y)
                    det_canvas.pack(fill=BOTH, expand=True)

                    def _render_det(_c=det_canvas, _img=img_disp):
                        _tk = ImageTk.PhotoImage(_img)
                        _c.create_image(0, 0, anchor=NW, image=_tk)
                        _c.configure(scrollregion=(0, 0, _img.width, _img.height))
                        _c._tk_img = _tk

                    dwin.after(30, _render_det)
                    dwin.geometry(f"{min(img_disp.width+20, int(sw2*0.85))}"
                                  f"x{min(img_disp.height+60, int(sh2*0.80))}")
                    dwin.lift()
                    dwin.focus_set()
                    det_canvas.bind("<MouseWheel>",
                                    lambda e, c=det_canvas:
                                    c.yview_scroll(int(-1*(e.delta/120)), "units"))
                    dwin.bind("<Escape>", lambda _: dwin.destroy())

                img_tree.bind("<<TreeviewSelect>>", _on_row_select)

            self.root.after(0, _update_ui)

        threading.Thread(target=run, daemon=True).start()
