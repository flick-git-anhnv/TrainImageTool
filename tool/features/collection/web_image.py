import queue
import re
import threading
import time
import unicodedata
from pathlib import Path

from ...core.imports import _DDGS_OK, _DDGS, _REQUESTS_OK, _req_mod

_DEFAULT_KEYWORDS = (
    "xe viettelpost\n"
    "xe giao hang viettelpost\n"
    "taxi mai linh\n"
    "xe taxi mai linh xanh"
)

_IMG_EXTS     = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_TIMEOUT      = 12   # giây timeout mỗi ảnh
_CHUNK        = 65536
_DDG_PAGE_SIZE = 100  # ddgs không tự phân trang nội bộ — phải tự lặp page=1,2,3…

_PEXELS_API_URL   = "https://api.pexels.com/v1/search"
_PEXELS_PAGE_SIZE = 80    # tối đa cho phép bởi Pexels API mỗi trang
_PEXELS_MAX_CAND  = 8000  # Pexels chỉ cho truy cập tối đa ~8000 kết quả/query (giới hạn của API, không phải bug)
_DDG_MAX_CAND     = 300   # giữ nguyên cap cũ cho DDG — tránh spam quá nhiều page (rủi ro bị chặn)


def _safe_name(kw: str) -> str:
    """Keyword tiếng Việt → tên thư mục ASCII-safe."""
    s = kw.strip().replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", errors="ignore").decode()
    s = re.sub(r"[^\w]", "_", s).strip("_")
    return re.sub(r"_+", "_", s).lower() or "keyword"


def _count_images(d: Path) -> int:
    if not d.exists():
        return 0
    return sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in _IMG_EXTS)


def _ext_from_url(url: str) -> str:
    path = url.split("?")[0].split("#")[0]
    sfx = Path(path).suffix.lower()
    return sfx if sfx in _IMG_EXTS else ".jpg"


class WebImageWorker:
    """Thu thập ảnh từ DuckDuckGo (Bing/Google) hoặc Pexels API theo keyword.

    Output: <output_dir>/anh_chua_co/<safe_keyword>/0001.jpg …
    """

    def __init__(self, cfg: dict, log_q: queue.Queue, stat_q: queue.Queue):
        self.cfg    = cfg
        self.log_q  = log_q
        self.stat_q = stat_q
        self._stop  = threading.Event()
        self.stats: dict = {
            "total_img": 0, "done_kw": 0, "total_kw": 0,
            "current_kw": "", "error": 0,
        }

    def stop(self):
        self._stop.set()

    def _log(self, msg: str):
        self.log_q.put(msg)

    def _push(self):
        self.stat_q.put(dict(self.stats))

    # ── main entry ─────────────────────────────────────────────────────────

    def run(self):
        engine = self.cfg.get("engine", "Bing")
        is_pexels = engine == "Pexels"

        if not _REQUESTS_OK:
            self._log("[LỖI] requests chưa cài. Chạy:")
            self._log("  python -m pip install requests")
            self.log_q.put("__DONE__")
            return
        if is_pexels:
            if not self.cfg.get("pexels_api_key", "").strip():
                self._log("[LỖI] Chưa nhập Pexels API Key. Lấy miễn phí tại https://www.pexels.com/api/")
                self.log_q.put("__DONE__")
                return
        elif not _DDGS_OK:
            self._log("[LỖI] duckduckgo_search chưa cài. Chạy:")
            self._log("  python -m pip install duckduckgo-search")
            self.log_q.put("__DONE__")
            return

        keywords = [k.strip() for k in self.cfg.get("keywords", "").splitlines() if k.strip()]
        if not keywords:
            self._log("[LỖI] Danh sách từ khóa trống.")
            self.log_q.put("__DONE__")
            return

        out_root = Path(self.cfg.get("output_dir", ".")) / "anh_chua_co"
        max_num  = max(1, int(self.cfg.get("max_per_kw", 100)))
        min_w    = max(1, int(self.cfg.get("min_w", 200)))
        min_h    = max(1, int(self.cfg.get("min_h", 200)))
        size_tag = self.cfg.get("size_tag", "Large")   # Small/Medium/Large/Wallpaper

        self.stats["total_kw"] = len(keywords)
        self._push()
        self._log(f"Thư mục lưu: {out_root}")
        self._log(f"Nguồn: {'Pexels' if is_pexels else 'DuckDuckGo'} | Max/keyword: {max_num} | Min size: {min_w}×{min_h}")
        self._log(f"Tổng {len(keywords)} từ khóa\n")

        for kw in keywords:
            if self._stop.is_set():
                self._log("⏹ Đã dừng.")
                break
            self.stats["current_kw"] = kw
            self._push()
            self._collect_keyword(kw, out_root, max_num, min_w, min_h, size_tag, is_pexels)
            self.stats["done_kw"] += 1
            self._push()

        self._log(f"{'─'*52}")
        self._log(
            f"Hoàn thành! {self.stats['done_kw']}/{self.stats['total_kw']} từ khóa"
            + (f" | {self.stats['error']} lỗi" if self.stats["error"] else "")
        )
        self._push()
        self.log_q.put("__DONE__")

    # ── helpers ────────────────────────────────────────────────────────────

    def _search_ddg(self, kw: str, max_results: int, size_tag) -> list | None:
        """Gọi DDG images search, tự lặp nhiều `page` để gom đủ max_results.

        Thư viện `ddgs` chỉ gửi đúng 1 request (page=1) mỗi lần gọi images()
        và không tự tăng page nội bộ — max_results chỉ cắt bớt kết quả của
        1 trang chứ không ép DDG trả nhiều hơn. Phải tự lặp page=1,2,3… và
        gộp (dedup theo URL ảnh) mới lấy được nhiều hơn ~35-100 URL/keyword.
        Trả None nếu lỗi ngay từ trang đầu, list (có thể rỗng) nếu có kết quả.
        """
        max_pages = max(1, -(-max_results // _DDG_PAGE_SIZE))  # ceil
        kwargs = {"max_results": _DDG_PAGE_SIZE}
        if size_tag:
            kwargs["size"] = size_tag

        collected: list = []
        seen_urls: set = set()
        try:
            with _DDGS() as ddgs:
                for page in range(1, max_pages + 1):
                    if self._stop.is_set() or len(collected) >= max_results:
                        break
                    try:
                        batch = list(ddgs.images(kw, page=page, **kwargs))
                    except Exception as e:
                        if page == 1:
                            raise
                        self._log(f"    [!] DDG trang {page} lỗi: {e} — dừng phân trang.")
                        break
                    new_items = [r for r in batch if r.get("image") and r.get("image") not in seen_urls]
                    if not new_items:
                        break
                    seen_urls.update(r["image"] for r in new_items)
                    collected.extend(new_items)
                    if page > 1:
                        self._log(f"    DDG trang {page}: +{len(new_items)} URL (tổng {len(collected)})")
        except Exception as e:
            self._log(f"  [LỖI] DuckDuckGo search: {e}")
            self.stats["error"] += 1
            return None
        return collected

    def _search_pexels(self, kw: str, max_results: int) -> list | None:
        """Gọi Pexels API `/v1/search`, tự lặp `page` để gom đủ max_results.

        Mỗi trang tối đa 80 ảnh (`_PEXELS_PAGE_SIZE`). Trả None nếu lỗi ngay
        từ trang đầu (key sai, hết quota…), list (có thể rỗng) nếu có kết quả.
        """
        api_key   = self.cfg.get("pexels_api_key", "").strip()
        max_pages = max(1, -(-max_results // _PEXELS_PAGE_SIZE))  # ceil
        headers   = {"Authorization": api_key}
        collected: list = []

        try:
            for page in range(1, max_pages + 1):
                if self._stop.is_set() or len(collected) >= max_results:
                    break
                params = {"query": kw, "per_page": _PEXELS_PAGE_SIZE, "page": page}
                resp = _req_mod.get(_PEXELS_API_URL, headers=headers, params=params, timeout=_TIMEOUT)
                if resp.status_code == 401:
                    self._log("  [LỖI] Pexels API Key không hợp lệ.")
                    self.stats["error"] += 1
                    return None
                if resp.status_code == 429:
                    self._log("  [!] Pexels: vượt hạn mức request/giờ — dừng lại.")
                    break
                if resp.status_code != 200:
                    if page == 1:
                        self._log(f"  [LỖI] Pexels HTTP {resp.status_code}: {resp.text[:200]}")
                        self.stats["error"] += 1
                        return None
                    self._log(f"  [!] Pexels trang {page} lỗi HTTP {resp.status_code} — dừng phân trang.")
                    break

                data   = resp.json()
                photos = data.get("photos", [])
                if not photos:
                    break
                for p in photos:
                    src = p.get("src", {})
                    url = src.get("large2x") or src.get("original") or src.get("large")
                    if not url:
                        continue
                    collected.append({
                        "image":  url,
                        "width":  p.get("width", 0),
                        "height": p.get("height", 0),
                    })
                if page > 1:
                    self._log(f"    Pexels trang {page}: +{len(photos)} ảnh (tổng {len(collected)})")
                if not data.get("next_page"):
                    break
        except Exception as e:
            self._log(f"  [LỖI] Pexels search: {e}")
            self.stats["error"] += 1
            return None
        return collected

    # ── per-keyword ────────────────────────────────────────────────────────

    def _collect_keyword(self, kw: str, out_root: Path,
                          max_num: int, min_w: int, min_h: int, size_tag: str,
                          is_pexels: bool = False):
        safe     = _safe_name(kw)
        save_dir = out_root / safe
        save_dir.mkdir(parents=True, exist_ok=True)
        existing = _count_images(save_dir)

        self._log(f"{'═'*52}")
        self._log(f'  Keyword: "{kw}"  →  anh_chua_co/{safe}/')

        if existing >= max_num:
            self._log(f"  ⏭ Đã có {existing} ảnh (≥ {max_num}) — bỏ qua")
            return
        if existing:
            self._log(f"  (Đã có {existing} ảnh — tiếp tục thêm)")

        need      = max_num - existing
        cand_cap  = _PEXELS_MAX_CAND if is_pexels else _DDG_MAX_CAND
        req_count = min(need * 3, cand_cap)

        if is_pexels:
            self._log(f"  Cần tải {need} ảnh | Yêu cầu Pexels tối đa {req_count} ảnh...")
            results = self._search_pexels(kw, req_count)
            if results is None:
                return
            if 0 < len(results) < need:
                self._log(
                    f"  [!] Pexels chỉ có {len(results)} ảnh khớp từ khóa này "
                    f"(thư viện Pexels là ảnh stock đã chọn lọc, không phải toàn bộ web — "
                    f"số ảnh thực tế thường ít hơn nhiều so với công cụ search ảnh như Bing/Google)."
                )
        else:
            self._log(f"  Cần tải {need} ảnh | Yêu cầu DDG tối đa {req_count} URL (filter: {size_tag})...")
            results = self._search_ddg(kw, req_count, size_tag)
            if results is None:
                return

            # Nếu DDG trả về quá ít, thử lại không có size filter để vớt thêm
            if len(results) < need and size_tag:
                self._log(f"  DDG trả {len(results)} URL (filter {size_tag}) — thử lại không filter size...")
                extra = self._search_ddg(kw, req_count, None)
                if extra:
                    seen = {r.get("image") for r in results}
                    new_results = [r for r in extra if r.get("image") not in seen]
                    results = results + new_results
                    self._log(f"  Sau fallback: {len(results)} URL tổng cộng")

        if not results:
            self._log("  [!] Không tìm được URL nào — thử từ khóa khác.")
            return

        self._log(f"  Tìm được {len(results)} URL — bắt đầu tải...")
        saved = 0
        session = _req_mod.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        })

        for r in results:
            if self._stop.is_set():
                break
            if saved >= need:
                break

            img_url = r.get("image", "")
            try:
                w = int(r.get("width",  0) or 0)
                h = int(r.get("height", 0) or 0)
            except (ValueError, TypeError):
                w = h = 0
            if w and h and (w < min_w or h < min_h):
                continue

            ext   = _ext_from_url(img_url)
            idx   = existing + saved + 1
            fpath = save_dir / f"{idx:04d}{ext}"

            if self._download(session, img_url, fpath):
                saved += 1
                self.stats["total_img"] = _count_images(save_dir)
                self._push()
                if saved % 5 == 0 or saved == 1:
                    self._log(f"    [{saved}/{need}] đã tải")
            else:
                self.stats["error"] += 1

        total = _count_images(save_dir)
        self._log(f"  ✓ Tổng {total} ảnh trong anh_chua_co/{safe}/")
        self.stats["total_img"] = total
        self._push()

    def _download(self, session, url: str, fpath: Path) -> bool:
        try:
            r = session.get(url, timeout=_TIMEOUT, stream=True)
            if r.status_code != 200:
                return False
            content_type = r.headers.get("Content-Type", "")
            if "image" not in content_type and "octet" not in content_type:
                return False
            data = b""
            for chunk in r.iter_content(chunk_size=_CHUNK):
                if self._stop.is_set():
                    return False
                data += chunk
            if len(data) < 4096:   # ảnh quá nhỏ / placeholder
                return False
            fpath.write_bytes(data)
            return True
        except Exception:
            return False
