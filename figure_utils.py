"""Nhận diện HÌNH VẼ / ẢNH trong trang để giữ nguyên khi dịch (R28).

- Trang có lớp chữ: lấy ảnh nhúng + cụm nét vẽ vector (bản vẽ kỹ thuật) bằng PyMuPDF.
- Trang scan: tìm vùng mực lớn không phải chữ in, không phải bảng, không phải dấu/chữ ký.
Chữ nằm TRONG hình vẫn là một phần của ảnh (không dịch) nên hình giữ đúng như bản gốc.
Kết quả: item {"type":"image","figure":True,"x","y","w","h" (px ở 300 DPI),"png"}.
"""
from __future__ import annotations

import cv2
import numpy as np
import pymupdf

DPI = 300
FIG_DPI = 150          # độ nét ảnh hình vẽ lưu trong file (đủ rõ, file nhẹ)
MIN_PT = 36            # hình nhỏ hơn 36pt (~1,27 cm) bỏ qua
BIG_MARK = 400_000    # px² ở 300 DPI: dấu/chữ ký nhỏ hơn mức này
MAX_PAGE_FRAC = 0.6    # nét vẽ bao gần hết trang (khung viền) không tính là hình


def _inter(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _area(r) -> float:
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def _merge_rects(rects: list[tuple], gap: float = 6.0) -> list[tuple]:
    rects = [tuple(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out: list[tuple] = []
        for r in rects:
            for i, o in enumerate(out):
                if (r[0] - gap <= o[2] and o[0] - gap <= r[2] and r[1] - gap <= o[3] and o[1] - gap <= r[3]):
                    out[i] = (min(r[0], o[0]), min(r[1], o[1]), max(r[2], o[2]), max(r[3], o[3]))
                    changed = True
                    break
            else:
                out.append(r)
        rects = out
    return rects


def _png(page: "pymupdf.Page", rect: tuple) -> bytes:
    pix = page.get_pixmap(matrix=pymupdf.Matrix(FIG_DPI / 72, FIG_DPI / 72), clip=pymupdf.Rect(*rect), alpha=False)
    return pix.tobytes("png")


def figures_from_text_page(page: "pymupdf.Page", table_bboxes: list[tuple], scale: float = DPI / 72) -> list[dict]:
    """Hình trong trang PDF có lớp chữ. Tọa độ trả về nhân `scale` (cùng hệ với trang scan)."""
    pr = page.rect
    page_area = pr.width * pr.height
    cand: list[tuple] = []
    for info in page.get_image_info():
        b = info["bbox"]
        cand.append((b[0], b[1], b[2], b[3]))
    try:
        dr = [d for d in page.get_drawings() if _area(tuple(d["rect"])) < MAX_PAGE_FRAC * page_area]
        for r in page.cluster_drawings(drawings=dr):
            cand.append((r.x0, r.y0, r.x1, r.y1))
    except Exception:  # bản PyMuPDF cũ không có cluster_drawings
        pass
    out = []
    for r in _merge_rects(cand):
        w, h = r[2] - r[0], r[3] - r[1]
        if w < MIN_PT or h < MIN_PT or _area(r) > MAX_PAGE_FRAC * page_area:
            continue
        if any(_inter(r, t) > 0.5 * _area(r) for t in table_bboxes):
            continue  # là đường kẻ của bảng
        if w / h > 12 or h / w > 12:
            continue  # đường kẻ dài
        r = (max(pr.x0, r[0] - 2), max(pr.y0, r[1] - 2), min(pr.x1, r[2] + 2), min(pr.y1, r[3] + 2))
        out.append({"type": "image", "figure": True, "kind": "hình vẽ", "keep": True,
                    "x": int(r[0] * scale), "y": int(r[1] * scale),
                    "w": int((r[2] - r[0]) * scale), "h": int((r[3] - r[1]) * scale), "png": _png(page, r)})
    return out


def figures_from_scan_page(img: np.ndarray, binary: np.ndarray, lines: list[dict], tables: list[tuple],
                           marks: list[dict], hmask: np.ndarray, vmask: np.ndarray) -> list[dict]:
    """Hình trong trang scan: vùng mực lớn, nằm ngoài chữ đã OCR, bảng, dấu/chữ ký."""
    H, W = binary.shape
    ink = (255 - binary).copy()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)  # nét/mảng màu cũng là một phần của hình
    ink[(hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 50)] = 255
    # bỏ chữ đã đọc chắc, bảng, dấu/chữ ký
    for ln in lines:
        if ln["conf"] >= 60:
            ink[max(0, ln["y"] - 4): ln["y"] + ln["h"] + 4, max(0, ln["x"] - 4): ln["x"] + ln["w"] + 4] = 0
    for x, y, w, h in tables:
        ink[max(0, y - 6): y + h + 6, max(0, x - 6): x + w + 6] = 0
    for m in marks:
        if m["w"] * m["h"] < BIG_MARK:  # dấu/chữ ký nhỏ bỏ ra; vùng màu lớn là ảnh/hình nên giữ lại làm hình
            ink[m["y"]: m["y"] + m["h"], m["x"]: m["x"] + m["w"]] = 0
    k = max(15, W // 80)
    blob = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(blob, 8)
    out = []
    min_side = int(0.9 * 36 / 72 * DPI)  # ~ 36pt
    for i in range(1, n):
        x, y, w, h, _a = stats[i]
        if w < min_side or h < min_side or w * h > MAX_PAGE_FRAC * H * W:
            continue
        if w / h > 12 or h / w > 12:
            continue
        dens = (ink[y:y + h, x:x + w] > 0).mean()
        if dens < 0.01:
            continue  # chỉ là vài nét lẻ
        ok, png = cv2.imencode(".png", cv2.resize(img[y:y + h, x:x + w], None, fx=FIG_DPI / DPI, fy=FIG_DPI / DPI,
                                                  interpolation=cv2.INTER_AREA))
        out.append({"type": "image", "figure": True, "kind": "hình vẽ", "keep": True,
                    "x": int(x), "y": int(y), "w": int(w), "h": int(h), "png": png.tobytes()})
    # bỏ hình nằm lọt trong hình lớn hơn (vd. vòng tròn trong khung bản vẽ)
    out = [a for a in out if not any(b is not a and b["w"] * b["h"] > a["w"] * a["h"] and inside(
        (a["x"], a["y"], a["w"], a["h"]), b, 0.8) for b in out)]
    return out


def table_is_drawing(page: "pymupdf.Page", bbox: tuple, ncols: int) -> bool:
    """Vùng 'bảng' thực ra là bản vẽ: có nét cong (tròn, cung) hoặc chỉ có 1 cột."""
    if ncols < 2:
        return True
    r = pymupdf.Rect(*bbox)
    for d in page.get_drawings():
        if pymupdf.Rect(d["rect"]).intersects(r) and any(it[0] == "c" for it in d["items"]):
            return True
    return False


def inside(box: tuple, fig: dict, frac: float = 0.6) -> bool:
    """box=(x,y,w,h): phần lớn nằm trong hình?"""
    a = (box[0], box[1], box[0] + box[2], box[1] + box[3])
    f = (fig["x"], fig["y"], fig["x"] + fig["w"], fig["y"] + fig["h"])
    return _inter(a, f) > frac * max(1.0, _area(a))
