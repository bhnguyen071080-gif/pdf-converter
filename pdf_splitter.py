"""Tách / xoay / xóa / sắp xếp trang PDF (giai đoạn 1) và gợi ý điểm ngắt tự động (R20).

Quy ước: "điểm ngắt i" = ngắt GIỮA vị trí i và i+1 (đếm từ 0, theo thứ tự trang HIỆN TẠI sau khi xóa/sắp xếp).
"""
from __future__ import annotations

import difflib
import io
import re
import unicodedata
import zipfile

import pymupdf

import ocr_utils as ou


# ---------------------------------------------------------------- nhóm trang
def groups_from_breaks(breaks: set[int], n: int) -> list[tuple[int, int]]:
    """Danh sách nhóm (vị trí đầu, vị trí cuối) bao gồm cả hai đầu, từ tập điểm ngắt."""
    groups, start = [], 0
    for i in range(n):
        if i in breaks or i == n - 1:
            groups.append((start, i))
            start = i + 1
    return groups


def breaks_all(n: int) -> set[int]:
    """Tách từng trang một."""
    return set(range(n - 1))


def breaks_every(k: int, n: int) -> set[int]:
    """Tách theo nhóm k trang."""
    k = max(1, k)
    return {i for i in range(k - 1, n - 1, k)}


def breaks_from_ranges(text: str, n: int) -> set[int]:
    """'1-3, 4, 5-8' -> điểm ngắt cuối mỗi dải. Phải phủ kín các trang, đúng thứ tự, không chồng lấn."""
    ranges = []
    for part in re.split(r"[,;]+", text):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*(?:-\s*(\d*))?", part)
        if not m:
            raise ValueError(f"Không hiểu '{part}'. Ví dụ đúng: 1-3, 4, 5-8")
        a = int(m[1])
        b = (int(m[2]) if m[2] else n) if "-" in part else a
        if not (1 <= a <= b <= n):
            raise ValueError(f"Dải '{part}' nằm ngoài 1-{n}")
        ranges.append((a, b))
    if not ranges:
        raise ValueError("Chưa nhập dải trang")
    expect = 1
    for a, b in ranges:
        if a != expect:
            raise ValueError(f"Dải phải liền nhau: sau trang {expect - 1} cần bắt đầu ở trang {expect}, nhưng nhập {a}")
        expect = b + 1
    if expect != n + 1:
        raise ValueError(f"Còn thiếu trang {expect}-{n} chưa nằm trong dải nào")
    return {b - 1 for _, b in ranges[:-1]}


# ---------------------------------------------------------------- ảnh thu nhỏ
def make_thumbnails(pdf_bytes: bytes, width_px: int = 260) -> list[bytes]:
    """PNG thu nhỏ của mọi trang (theo thứ tự gốc)."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = []
    for page in doc:
        zoom = width_px / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csRGB, alpha=False)
        out.append(pix.tobytes("png"))
    return out


# ---------------------------------------------------------------- tách file
def split_pdf(pdf_bytes: bytes, order: list[int], rotations: dict[int, int],
              groups: list[tuple[int, int]]) -> list[tuple[bytes, int]]:
    """Trả [(nội dung PDF, số trang)] cho từng nhóm. order = chỉ số trang gốc theo thứ tự hiện tại;
    rotations = {chỉ số trang gốc: độ xoay cộng thêm (bội số 90)}."""
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    outs = []
    for a, b in groups:
        dst = pymupdf.open()
        for pos in range(a, b + 1):
            orig = order[pos]
            dst.insert_pdf(src, from_page=orig, to_page=orig)
            rot = rotations.get(orig, 0) % 360
            if rot:
                pg = dst[-1]
                pg.set_rotation((pg.rotation + rot) % 360)
        outs.append((dst.tobytes(garbage=3, deflate=True), b - a + 1))
        dst.close()
    return outs


_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str, used: set[str]) -> str:
    """Tên file hợp lệ trên Windows, đuôi .pdf, không trùng (giữ nguyên dấu tiếng Việt, dạng NFC)."""
    name = unicodedata.normalize("NFC", _BAD.sub("_", name.strip())).strip(". ") or "tai_lieu"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    base, ext = name[:-4], name[-4:]
    cand, k = name, 2
    while cand.lower() in used:
        cand = f"{base}_{k}{ext}"
        k += 1
    used.add(cand.lower())
    return cand


def make_zip(files: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            z.writestr(name, data)  # tên tiếng Việt được lưu UTF-8
    return buf.getvalue()


# ---------------------------------------------------------------- gợi ý điểm ngắt (R20)
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("Đ", "D").replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper()


def _has(tokens: list[str], word: str, cutoff: float = 0.74) -> bool:
    return bool(difflib.get_close_matches(word, tokens, n=1, cutoff=cutoff))


def _upper_tokens(text: str) -> list[str]:
    """Chỉ lấy các từ VIẾT HOA (tiêu đề), bỏ dấu; chữ thường như 'Nhân viên Ban…' không bị nhầm là tiêu đề."""
    return [_norm(w) for w in re.findall(r"[^\W\d_]{2,}", text) if w.isupper()]


def looks_like_first_page(top_text: str) -> bool:
    """Phần đầu trang có quốc hiệu 'CỘNG HÒA…' hoặc tiêu đề 'BIÊN BẢN…' thì coi là trang đầu của văn bản mới.
    So khớp mờ để chịu được lỗi OCR (BUEN BẢN, CONG HOA…)."""
    toks = _upper_tokens(top_text)
    return (_has(toks, "CONG") and _has(toks, "HOA")) or (_has(toks, "BIEN") and _has(toks, "BAN")) \
        or (_has(toks, "PHIEU") and _has(toks, "LINH"))


TOP_FRACTION = 0.30  # chỉ đọc 30% phía trên của trang


def page_top_text(page: "pymupdf.Page") -> str:
    """Chữ ở phần đầu trang: lấy từ lớp chữ nếu có, không thì OCR đúng vùng đầu trang (nhanh)."""
    r = page.rect
    clip = pymupdf.Rect(r.x0, r.y0, r.x1, r.y0 + r.height * TOP_FRACTION)
    if ou.page_has_text_layer(page):
        return page.get_text("text", clip=clip)
    pix = page.get_pixmap(dpi=200, clip=clip, colorspace=pymupdf.csRGB, alpha=False)
    import cv2
    import numpy as np
    img = cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3), cv2.COLOR_RGB2BGR)
    return ou.quick_text(ou.gray_of(img))


def read_page_tops(pdf_bytes: bytes, pages: list[int], progress=None) -> dict[int, str]:
    """Đọc phần đầu của các trang gốc `pages`. Kết quả dùng chung cho mọi chế độ gợi ý."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    tops = {}
    for k, orig in enumerate(pages):
        tops[orig] = page_top_text(doc[orig])
        if progress:
            progress((k + 1) / len(pages), f"Đọc đầu trang {k + 1}/{len(pages)}")
    return tops


def title_key(top_text: str) -> str | None:
    """Hai từ đầu tiên sau 'BIÊN BẢN' (đã bỏ dấu), vd. 'KIEM TRA', 'BAN GIAO', 'NGHIEM THU'."""
    toks = _upper_tokens(top_text)
    for i in range(len(toks) - 3):
        if difflib.SequenceMatcher(None, toks[i], "BIEN").ratio() >= 0.7 and \
                difflib.SequenceMatcher(None, toks[i + 1], "BAN").ratio() >= 0.7:
            return " ".join(toks[i + 2:i + 4])
    return None


def breaks_each_document(order: list[int], tops: dict[int, str]) -> set[int]:
    """Chế độ A – mỗi biên bản một file: ngắt trước mỗi trang có quốc hiệu/tiêu đề ở đầu trang."""
    return {pos - 1 for pos, o in enumerate(order) if pos > 0 and looks_like_first_page(tops[o])}


def breaks_repeating_set(order: list[int], tops: dict[int, str]) -> set[int]:
    """Chế độ B – theo bộ hồ sơ lặp lại: ngắt trước mỗi trang có cùng loại biên bản với trang đầu tiên.
    Ví dụ trang 1 là 'Biên bản kiểm tra…' thì mỗi lần gặp lại loại này là bắt đầu một bộ mới."""
    lead = title_key(tops[order[0]])
    if not lead:
        return set()
    out = set()
    for pos, o in enumerate(order):
        k = title_key(tops[o])
        if pos > 0 and k and difflib.SequenceMatcher(None, k, lead).ratio() >= 0.75:
            out.add(pos - 1)
    return out


def selected_pages(groups: list[tuple[int, int]], order: list[int], flags: list[bool]) -> list[int]:
    """Chỉ số trang GỐC (từ 0) của các nhóm được tích chọn, theo thứ tự trang gốc tăng dần (R23, R24)."""
    out: set[int] = set()
    for (a, b), on in zip(groups, flags):
        if on:
            out.update(order[a:b + 1])
    return sorted(out)


def pages_to_range_text(pages: list[int]) -> str:
    """[0,1,2,4] -> '1-3, 5' (số trang từ 1) để điền vào ô 'Trang cần chuyển'."""
    parts, i = [], 0
    ps = sorted(set(pages))
    while i < len(ps):
        j = i
        while j + 1 < len(ps) and ps[j + 1] == ps[j] + 1:
            j += 1
        parts.append(str(ps[i] + 1) if i == j else f"{ps[i] + 1}-{ps[j] + 1}")
        i = j + 1
    return ", ".join(parts)
