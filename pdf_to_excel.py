"""PDF -> Excel. Hỗ trợ PDF có lớp chữ (pdfplumber) và PDF scan (OCR + nhận diện bảng bằng đường kẻ).

Mô hình dữ liệu trung gian (dùng chung cho xem trước và xuất xlsx):
    PageResult = {"page": int, "method": "text"|"ocr", "angle": float, "items": [Item]}
    Item văn bản: {"type": "text", "y": int, "x": int, "segments": [(x, str)]}
    Item bảng:    {"type": "table", "y": int, "x": int, "x_edges": [..], "cells": [[str]],
                   "spans": [(r, c, rowspan, colspan)], "header_rows": int}
"""
from __future__ import annotations

import os
import time

import io
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import cv2
import numpy as np
import pymupdf
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
from openpyxl.drawing.xdr import XDRPositiveSize2D
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

import mark_utils as mk
import ocr_utils as ou

# ---------------------------------------------------------------- nhận diện bảng
def _cluster(vals: list[int], gap: int = 10) -> list[int]:
    """Gộp các vị trí gần nhau thành một đường (lấy trung bình)."""
    if not len(vals):
        return []
    vals = sorted(vals)
    groups, cur = [], [vals[0]]
    for v in vals[1:]:
        if v - cur[-1] <= gap:
            cur.append(v)
        else:
            groups.append(cur)
            cur = [v]
    groups.append(cur)
    return [int(round(sum(g) / len(g))) for g in groups]


def _line_masks(binary: np.ndarray):
    inv = 255 - binary
    h, w = inv.shape
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(60, w // 40), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(40, h // 80)))
    hmask = cv2.morphologyEx(inv, cv2.MORPH_OPEN, hk)
    vmask = cv2.morphologyEx(inv, cv2.MORPH_OPEN, vk)
    return hmask, vmask


def find_table_regions(binary: np.ndarray, hmask, vmask) -> list[tuple[int, int, int, int]]:
    """Tìm khung bảng (x, y, w, h) từ giao của đường ngang và dọc."""
    grid = cv2.dilate(cv2.bitwise_or(hmask, vmask), np.ones((7, 7), np.uint8))
    cnts, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    H, W = binary.shape
    regs = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w > W * 0.25 and h > 120:
            # phải có đủ cả đường dọc lẫn ngang bên trong mới là bảng
            if cv2.countNonZero(vmask[y:y + h, x:x + w]) > 100 and cv2.countNonZero(hmask[y:y + h, x:x + w]) > 300:
                regs.append((x, y, w, h))
    regs.sort(key=lambda r: r[1])
    return regs


def _edges(proj: np.ndarray, thresh: float, gap: int = 12) -> list[int]:
    idx = np.where(proj >= thresh)[0]
    return _cluster(list(idx), gap)


def build_grid(region, hmask, vmask):
    """Dựng lưới ô và gộp ô (merge) theo việc có đường kẻ ngăn cách hay không."""
    x, y, w, h = region
    hm = hmask[y:y + h, x:x + w]
    vm = vmask[y:y + h, x:x + w]
    ys = _edges((hm > 0).sum(axis=1), w * 0.30)
    xs = _edges((vm > 0).sum(axis=0), 35)
    if len(ys) < 2 or len(xs) < 2:
        return None
    nr, nc = len(ys) - 1, len(xs) - 1

    def has_vline(r, c):  # đường dọc bên phải ô (r, c)
        xx = xs[c + 1]
        seg = vm[ys[r] + 6: ys[r + 1] - 6, max(0, xx - 6): xx + 7]
        return seg.size and (seg.max(axis=1) > 0).mean() > 0.6

    def has_hline(r, c):  # đường ngang phía dưới ô (r, c)
        yy = ys[r + 1]
        seg = hm[max(0, yy - 6): yy + 7, xs[c] + 6: xs[c + 1] - 6]
        return seg.size and (seg.max(axis=0) > 0).mean() > 0.6

    parent = {(r, c): (r, c) for r in range(nr) for c in range(nc)}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for r in range(nr):
        for c in range(nc):
            if c + 1 < nc and not has_vline(r, c):
                parent[find((r, c))] = find((r, c + 1))
            if r + 1 < nr and not has_hline(r, c):
                parent[find((r, c))] = find((r + 1, c))
    groups: dict = {}
    for k in parent:
        groups.setdefault(find(k), []).append(k)
    spans = []
    for cells in groups.values():
        rs = [a for a, _ in cells]
        cs = [b for _, b in cells]
        spans.append((min(rs), min(cs), max(rs) - min(rs) + 1, max(cs) - min(cs) + 1))
    spans.sort()
    return {"ys": [y + v for v in ys], "xs": [x + v for v in xs], "spans": spans}


def _cell_crop(gray, lines_mask, box):
    x1, y1, x2, y2 = box
    pad = 5
    crop = gray[y1 + pad:y2 - pad, x1 + pad:x2 - pad].copy()
    lm = lines_mask[y1 + pad:y2 - pad, x1 + pad:x2 - pad]
    crop[lm > 0] = 255  # xóa đường kẻ để Tesseract không đọc thành "|"
    if crop.size == 0 or (crop < 140).sum() < 30:
        return None
    return cv2.copyMakeBorder(crop, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)


def _ocr_cell(crop) -> str:
    if crop is None:
        return ""
    single = crop.shape[0] < 130
    txt = ou.ocr_text(crop, psm=7 if single else 6)
    if not txt:
        txt = ou.ocr_text(crop, psm=8 if single else 6)
    return ou.clean_text(txt).replace("\n", " ") if single else ou.clean_text(txt)


_NUMLIKE = re.compile(r"^[\d.,\-\s]+$")


_DIGIT_FIX = str.maketrans({"]": "1", "[": "1", "|": "1", "l": "1", "I": "1", "O": "0", "o": "0", "S": "5", "ổ": "8", "B": "8"})


def _fix_numeric_columns(cells, spans, crops, hdr):
    """Cột mà đa số ô là số (STT, số lượng...): ô còn lại đọc lại bằng chế độ chỉ-chữ-số."""
    nc = len(cells[0])
    for c in range(nc):
        body = [(r, c) for (r, cc, rs, cs) in spans if cc == c and cs == 1 and r >= hdr]
        if len(body) < 3:
            continue
        ok = sum(1 for r, cc in body if cells[r][cc].strip() and _NUMLIKE.match(cells[r][cc].strip()))
        if ok / len(body) < 0.6:
            continue
        for r, cc in body:
            if crops.get((r, cc)) is not None and not (cells[r][cc].strip() and _NUMLIKE.match(cells[r][cc].strip())):
                d = ou.clean_text(ou.ocr_digits(crops[(r, cc)]))
                if not d and len(cells[r][cc].strip()) <= 3:  # sửa nhầm ký tự thường gặp trong cột số
                    d = cells[r][cc].strip().translate(_DIGIT_FIX)
                if d and _NUMLIKE.match(d):
                    cells[r][cc] = d


def extract_table_scan(gray, region, hmask, vmask, pool) -> dict | None:
    g = build_grid(region, hmask, vmask)
    if not g:
        return None
    ys, xs, spans = g["ys"], g["xs"], g["spans"]
    lines_mask = cv2.dilate(cv2.bitwise_or(hmask, vmask), np.ones((5, 5), np.uint8))
    boxes = [(xs[c], ys[r], xs[c + cs], ys[r + rs]) for r, c, rs, cs in spans]
    crops_l = [_cell_crop(gray, lines_mask, b) for b in boxes]
    lang = ou.cur_lang()
    texts = list(pool.map(lambda c: _in_lang(lang, _ocr_cell, c), crops_l))
    nr, nc = len(ys) - 1, len(xs) - 1
    cells = [["" for _ in range(nc)] for _ in range(nr)]
    crops = {}
    for (r, c, rs, cs), t, cr in zip(spans, texts, crops_l):
        cells[r][c] = t
        crops[(r, c)] = cr
    # dòng tiêu đề: dòng đầu, cộng thêm dòng kế nếu dòng đầu có ô gộp ngang
    header_rows = 1
    if any(cs > 1 and r == 0 for r, c, rs, cs in spans) or any(rs > 1 and r == 0 for r, c, rs, cs in spans):
        header_rows = max([r + rs for r, c, rs, cs in spans if r == 0] + [1])
    _fix_numeric_columns(cells, spans, crops, header_rows)
    return {"type": "table", "y": ys[0], "x": xs[0], "x_edges": xs, "cells": cells,
            "spans": spans, "header_rows": header_rows}


# ---------------------------------------------------------------- xử lý trang scan
def process_scan_page(page, pool, dpi: int = 300, img=None, figures: bool = False) -> dict:
    """img: ảnh trang đã dựng sẵn (dùng khi xử lý song song; dựng ảnh phải làm ở luồng chính vì PyMuPDF không an toàn đa luồng)."""
    if img is None:
        img = ou.render_page(page, dpi)
    img, binary, angle = ou.preprocess(img)
    gray = ou.gray_of(img)
    hmask, vmask = _line_masks(binary)  # cấu trúc bảng dò trên ảnh nhị phân
    regions = find_table_regions(binary, hmask, vmask)
    real_regions = list(regions)
    items = []
    text_img = gray.copy()
    for reg in regions:
        t = extract_table_scan(gray, reg, hmask, vmask, pool)
        x, y, w, h = reg
        if figures and t and _mostly_empty(t):  # khung bản vẽ bị nhận nhầm là bảng -> xử lý như hình
            real_regions.remove(reg)
            continue
        text_img[max(0, y - 4): y + h + 4, max(0, x - 4): x + w + 4] = 255  # che bảng, OCR phần còn lại
        if t:
            items.append(t)
    lines = ou.ocr_lines(text_img, psm=6)
    # Dấu và chữ ký: giữ nguyên dạng ảnh (R22); bỏ các TỪ rác do nét ký bị đọc nhầm thành chữ
    marks = mk.detect_marks(img, binary, lines, regions, hmask, vmask)
    for ln in lines:
        words = [(t, a, b) for (t, a, b), c in zip(ln["words"], ln["wconf"])
                 if not (c < mk.CONF_DROP and mk.word_in_marks(a, b, ln, marks))]
        segs = split_segments(words) if words else []
        if not segs:
            continue  # dòng chỉ toàn nhiễu -> bỏ
        x0, x1 = words[0][1], max(b for _, _, b in words)
        items.append({"type": "text", "y": ln["y"], "x": x0, "w": x1 - x0, "h": ln["h"],
                      "conf": round(ln["conf"]), "segments": segs})
    items += marks
    if figures:  # hình vẽ giữ nguyên (R28): chữ OCR nằm trong hình bị bỏ vì đã nằm trong ảnh
        import figure_utils as fu
        figs = fu.figures_from_scan_page(img, binary, lines, real_regions, marks, hmask, vmask)
        items = [i for i in items if not (i["type"] == "text" and any(
            fu.inside((i["x"], i["y"], i.get("w", 0) or 1, i.get("h", 40)), f) for f in figs))] + figs
    items.sort(key=lambda i: (i["y"], i["x"]))
    return {"method": "ocr", "angle": round(angle, 2), "items": items, "width": binary.shape[1]}


def _mostly_empty(t: dict) -> bool:
    """Bảng gần như không có chữ (≤2 ô có nội dung và <40% số ô) -> khung bản vẽ, không phải bảng thật."""
    cells = [c for row in t["cells"] for c in row]
    n = sum(bool(c.strip()) for c in cells)
    return not cells or (n <= 2 and n / len(cells) < 0.4)


def split_segments(words, gap: int = 130):
    """Tách dòng thành các đoạn khi có khoảng trống lớn (vd. 2 cột tiêu đề)."""
    segs, cur, last_end, start = [], [], None, None
    for t, x1, x2 in words:
        if last_end is not None and x1 - last_end > gap:
            segs.append((start, ou.clean_text(" ".join(cur))))
            cur, start = [], None
        if start is None:
            start = x1
        cur.append(t)
        last_end = x2
    if cur:
        segs.append((start, ou.clean_text(" ".join(cur))))
    # bỏ đoạn rác ngắn do chữ ký, dấu mộc (ví dụ "<", "//©")
    return [(x, t) for x, t in segs if len(re.sub(r"\W", "", t)) >= 2]


# ---------------------------------------------------------------- xử lý trang có lớp chữ
def _fix_cid(text: str, pm_page, bbox) -> str:
    """pdfplumber không đọc được vài chữ có dấu (hiện '(cid:N)') ở PDF tạo từ LibreOffice/Word.
    Đọc lại đúng vùng đó bằng PyMuPDF."""
    if "(cid:" not in text or bbox is None:
        return text
    fixed = pm_page.get_text("text", clip=pymupdf.Rect(*bbox)).replace("\n", " ").strip()
    return fixed if fixed and "(cid:" not in fixed else text


def process_text_page(page_idx: int, pdf_bytes: bytes, scale: float = 300 / 72, figures: bool = False) -> dict:
    """Trang có lớp chữ: dùng pdfplumber; tọa độ nhân scale để cùng hệ với trang scan."""
    import pdfplumber
    items = []
    pm_page = pymupdf.open(stream=pdf_bytes, filetype="pdf")[page_idx]
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pg = pdf.pages[page_idx]
        tables = pg.find_tables()
        if figures:  # bản vẽ kỹ thuật (có đường cong / chỉ 1 cột) hay bị nhận nhầm là bảng -> coi là hình
            import figure_utils as fu
            tables = [t for t in tables if not fu.table_is_drawing(pm_page, t.bbox, len(t.rows[0].cells) if t.rows else 0)]
        bboxes = [t.bbox for t in tables]
        for t in tables:
            rows = t.extract()
            cells = [[(c or "").replace("\n", " ").strip() for c in row] for row in rows]
            for ri, trow in enumerate(t.rows):  # sửa ô có (cid:N)
                for ci, box in enumerate(trow.cells):
                    if ri < len(cells) and ci < len(cells[ri]):
                        cells[ri][ci] = _fix_cid(cells[ri][ci], pm_page, box)
            nc = max(len(r) for r in cells)
            cells = [r + [""] * (nc - len(r)) for r in cells]
            items.append({"type": "table", "y": int(t.bbox[1] * scale), "x": int(t.bbox[0] * scale),
                          "x_edges": [], "cells": cells, "spans": [], "header_rows": 1})
        rest = pg.filter(lambda o: o.get("object_type") != "char" or not any(
            b[0] - 1 <= o["x0"] and o["x1"] <= b[2] + 1 and b[1] - 1 <= o["top"] and o["bottom"] <= b[3] + 1
            for b in bboxes))
        for ln in rest.extract_text_lines():
            items.append({"type": "text", "y": int(ln["top"] * scale), "x": int(ln["x0"] * scale),
                          "xr": int(ln["x1"] * scale), "h": int((ln["bottom"] - ln["top"]) * scale),
                          "segments": [(int(ln["x0"] * scale), ou.clean_text(
                              _fix_cid(ln["text"], pm_page, (ln["x0"], ln["top"], ln["x1"], ln["bottom"]))))]})
    if figures:
        import figure_utils as fu
        figs = fu.figures_from_text_page(pm_page, bboxes, scale)
        items = [i for i in items if not (i["type"] == "text" and any(
            fu.inside((i["x"], i["y"], 1, 40), f, 0.5) for f in figs))] + figs
    items.sort(key=lambda i: (i["y"], i["x"]))
    return {"method": "text", "angle": 0.0, "items": items, "width": int(595 * scale)}


# ---------------------------------------------------------------- điều phối
def _page_workers() -> int:
    """Số trang xử lý cùng lúc: theo số nhân CPU, tối đa 4 (máy chủ miễn phí thường 2 nhân)."""
    return max(1, min(4, os.cpu_count() or 2))


def _in_lang(lang: str, fn, *a):
    """Chạy fn trong luồng con với đúng ngôn ngữ OCR của yêu cầu."""
    ou.set_lang(lang)
    return fn(*a)


def convert_pdf(pdf_bytes: bytes, pages: list[int] | None = None, progress=None, force_ocr: bool = False,
                lang: str | None = None, figures: bool = False):
    """Trả (kind, [PageResult]). pages: chỉ số trang từ 0; None = tất cả.
    Các trang xử lý song song (kết quả vẫn đúng thứ tự trang); thuật toán từng trang không đổi."""
    if lang:
        ou.set_lang(lang)  # 'vi','en','de','ja','zh-CN','zh-TW'
    ocr_lang = ou.cur_lang()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    kind = ou.detect_pdf_kind(doc)
    pages = list(range(len(doc))) if pages is None else pages
    use_text = {i: (not force_ocr) and ou.page_has_text_layer(doc[i]) for i in pages}
    results: dict[int, dict] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=4) as cell_pool, ThreadPoolExecutor(max_workers=_page_workers()) as page_pool:
        futs = {}
        for i in pages:
            if use_text[i]:
                futs[i] = page_pool.submit(_in_lang, ocr_lang, process_text_page, i, pdf_bytes, 300 / 72, figures)
            else:  # dựng ảnh ở luồng chính, phần nặng (khử nghiêng, OCR) chạy song song
                futs[i] = page_pool.submit(_in_lang, ocr_lang, process_scan_page, None, cell_pool, 300, ou.render_page(doc[i], 300), figures)
            while len([f for f in futs.values() if not f.done()]) >= _page_workers() + 1:
                time.sleep(0.05)  # giới hạn số ảnh lớn nằm chờ trong bộ nhớ
        for i in pages:
            res = futs[i].result()
            res["page"] = i + 1
            results[i] = res
            done += 1
            if progress:
                progress(done / len(pages), f"Xong trang {i + 1} ({'lớp chữ' if use_text[i] else 'OCR'}) – {done}/{len(pages)}")
    return kind, [results[i] for i in pages]


# ---------------------------------------------------------------- kiểu dữ liệu: số, ngày
_NUM = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$|^-?\d+(,\d+)?$|^-?\d+\.\d+$")
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

def parse_number(s: str):
    s = s.strip()
    if not _NUM.match(s):
        return None
    if re.match(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$", s):  # 1.234,5 (định dạng Việt)
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    f = float(s)
    return int(f) if f.is_integer() else f


def parse_date(s: str):
    m = _DATE.match(s.strip())
    if not m:
        return None
    try:
        return datetime(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


# ---------------------------------------------------------------- xuất xlsx
_THIN = Side(style="thin", color="000000")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
FONT = "Times New Roman"


def _write_table(ws, row0: int, item: dict, col_off: int = 0) -> int:
    cells, spans, hdr = item["cells"], item["spans"], item["header_rows"]
    nr, nc = len(cells), len(cells[0])
    # cột nào toàn số/ngày (không tính dòng tiêu đề) -> ghi dạng số/ngày
    col_kind = {}
    for c in range(nc):
        vals = [cells[r][c].strip() for r in range(hdr, nr) if cells[r][c].strip()]
        if len(vals) >= 3 and sum(parse_number(v) is not None for v in vals) / len(vals) >= 0.8:
            col_kind[c] = "num"  # ô nào không phải số (do OCR sai) vẫn giữ nguyên dạng chữ để người dùng sửa
        elif vals and all(parse_date(v) for v in vals):
            col_kind[c] = "date"
    covered = set()
    span_list = spans or [(r, c, 1, 1) for r in range(nr) for c in range(nc)]
    for r, c, rs, cs in span_list:
        for rr in range(r, r + rs):
            for cc in range(c, c + cs):
                covered.add((rr, cc))
        cell = ws.cell(row=row0 + r, column=col_off + c + 1)
        txt = cells[r][c]
        kind = col_kind.get(c) if r >= hdr else None
        val, fmt = txt, None
        if kind == "num" and txt.strip() and parse_number(txt) is not None:
            val = parse_number(txt)
            raw = txt.strip()
            if raw.isdigit() and raw.startswith("0") and len(raw) > 1:
                fmt = "0" * len(raw)  # giữ số 0 đầu: 04 -> 04
        elif kind == "date" and txt.strip():
            val, fmt = parse_date(txt), "dd/mm/yyyy"
        cell.value = val
        if isinstance(val, str):
            cell.data_type = "s"  # luôn là chữ: tránh "=..." bị Excel hiểu là công thức (#NAME?)
        if fmt:
            cell.number_format = fmt
        cell.font = Font(name=FONT, size=12, bold=(r < hdr))
        cell.alignment = Alignment(horizontal="center" if (r < hdr or kind) else "left",
                                   vertical="center", wrap_text=True)
        if rs > 1 or cs > 1:
            ws.merge_cells(start_row=row0 + r, start_column=col_off + c + 1,
                           end_row=row0 + r + rs - 1, end_column=col_off + c + cs)
    for r in range(nr):
        for c in range(nc):
            ws.cell(row=row0 + r, column=col_off + c + 1).border = _BORDER
    return row0 + nr


def _col_grid(page_res: dict, ncols_default: int = 8) -> list[int]:
    """Lưới cột của trang: lấy theo bảng đầu tiên, nếu không có bảng thì chia đều."""
    for it in page_res["items"]:
        if it["type"] == "table" and len(it["x_edges"]) > 2:
            return it["x_edges"]
    w = page_res["width"]
    return [int(w * i / ncols_default) for i in range(ncols_default + 1)]


def _col_index(x: int, grid: list[int]) -> int:
    for i in range(len(grid) - 1):
        if x < grid[i + 1] - 5:
            return i
    return len(grid) - 2


def _add_image(ws, m: dict, grid: list[int], row_of: list[tuple[int, int]]):
    """Neo ảnh dấu/chữ ký (PNG nền trong suốt) tại ô gần vị trí gốc, giữ nguyên kích thước thật."""
    emu = lambda px: int(px / 300 * 914400)  # noqa: E731
    col = _col_index(m["x"], grid)
    above = [r for y, r in row_of if y <= m["y"]]
    row = above[-1] if above else 1
    row_y = [y for y, r in row_of if r == row]
    img = XLImage(io.BytesIO(m["png"]))
    marker = AnchorMarker(col=col, colOff=emu(max(0, m["x"] - grid[col])), row=row - 1,
                          rowOff=emu(max(0, m["y"] - (row_y[0] if row_y else m["y"]))))
    img.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(emu(m["w"]), emu(m["h"])))
    ws.add_image(img)


def build_workbook(results: list[dict], mode: str = "per_page", keep_marks: bool = True) -> bytes:
    """mode: 'per_page' = mỗi trang một sheet; 'merged' = gộp tất cả vào một sheet."""
    wb = Workbook()
    wb.remove(wb.active)
    ws = None
    row = 1
    for res in results:
        if mode == "per_page" or ws is None:
            ws = wb.create_sheet(f"Trang {res['page']}" if mode == "per_page" else "Tổng hợp")
            row = 1
        elif mode == "merged":
            row += 1
            ws.cell(row=row, column=1, value=f"--- Trang {res['page']} ---").font = Font(name=FONT, italic=True, size=10)
            row += 1
        grid = _col_grid(res)
        for i in range(len(grid) - 1):  # độ rộng cột theo tỉ lệ pixel trang
            letter = get_column_letter(i + 1)
            width = max(4.0, (grid[i + 1] - grid[i]) / res["width"] * 105)
            if ws.column_dimensions[letter].width is None or ws.column_dimensions[letter].width < width:
                ws.column_dimensions[letter].width = width
        row_of: list[tuple[int, int]] = []
        for it in res["items"]:
            if it["type"] == "image":
                continue
            row_of.append((it["y"], row))
            if it["type"] == "table":
                row = _write_table(ws, row, it) + 1
            else:
                for x, txt in it["segments"]:
                    if txt:
                        c = ws.cell(row=row, column=_col_index(x, grid) + 1, value=txt)
                        c.data_type = "s"
                        c.font = Font(name=FONT, size=12)
                        c.alignment = Alignment(vertical="center")
                row += 1
        if keep_marks:
            for m in [i for i in res["items"] if i["type"] == "image" and i.get("keep", True)]:
                _add_image(ws, m, grid, row_of)
    for sh in wb.worksheets:
        sh.page_setup.paperSize = sh.PAPERSIZE_A4
        sh.page_setup.fitToWidth = 1
        sh.page_setup.fitToHeight = 0
        sh.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
