"""Tiện ích OCR cho PDF scan: dựng ảnh 300 DPI, khử nghiêng, nhị phân hóa, OCR Tesseract vie+eng."""
from __future__ import annotations

import os
import re
from pathlib import Path

import cv2
import numpy as np
import pymupdf  # PyMuPDF
import pytesseract

LANG = "vie+eng"
DPI = 300

# Dùng model Tesseract "best" đi kèm dự án (tessdata/) cho dấu tiếng Việt chính xác hơn
# model "fast" cài theo apt. Nếu thiếu thư mục thì dùng model hệ thống.
_TESS = Path(__file__).parent / "tessdata"
if (_TESS / "vie.traineddata").exists():
    os.environ["TESSDATA_PREFIX"] = str(_TESS)

# Windows: tìm tesseract.exe ở nơi cài mặc định nếu chưa có trong PATH
for _p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
    if os.name == "nt" and Path(_p).exists():
        pytesseract.pytesseract.tesseract_cmd = _p
        break


# ---------- Nhận biết loại PDF (R7) ----------
def page_has_text_layer(page: "pymupdf.Page", min_chars: int = 30) -> bool:
    """True nếu trang có lớp chữ thật (trích trực tiếp được)."""
    return len(page.get_text("text").strip()) >= min_chars


def detect_pdf_kind(doc: "pymupdf.Document", sample: int = 5) -> str:
    """Trả về 'text' (có lớp chữ), 'scan' (ảnh quét) hoặc 'mixed'."""
    n = min(len(doc), sample)
    flags = [page_has_text_layer(doc[i]) for i in range(n)]
    if all(flags):
        return "text"
    if not any(flags):
        return "scan"
    return "mixed"


# ---------- Dựng ảnh và tiền xử lý (R5) ----------
def render_page(page: "pymupdf.Page", dpi: int = DPI) -> np.ndarray:
    """Dựng trang PDF thành ảnh BGR ở 300 DPI."""
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def remove_color_marks(img: np.ndarray) -> np.ndarray:
    """Xóa mực màu (con dấu đỏ, chữ ký bút bi xanh) khỏi ảnh dùng cho OCR để không sinh chữ rác.
    Con dấu/chữ ký được giữ riêng dưới dạng ảnh (mark_utils)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 55) & (hsv[:, :, 2] > 40)).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    out = img.copy()
    out[mask > 0] = 255
    return out


def to_binary(img: np.ndarray) -> np.ndarray:
    """Ảnh xám -> nhị phân (chữ đen = 0, nền trắng = 255), có khử nhiễu nhẹ."""
    gray = cv2.cvtColor(remove_color_marks(img), cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, 41, 15)


def estimate_skew(binary: np.ndarray) -> float:
    """Ước lượng góc nghiêng (độ) bằng các đoạn thẳng dài; giới hạn ±5°."""
    inv = 255 - binary
    lines = cv2.HoughLinesP(inv, 1, np.pi / 1800, threshold=400,
                            minLineLength=binary.shape[1] // 4, maxLineGap=20)
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(a) < 5:  # chỉ lấy đường gần ngang
            angles.append(a)
    return float(np.median(angles)) if angles else 0.0


def rotate(img: np.ndarray, angle: float, border=255) -> np.ndarray:
    if abs(angle) < 0.05:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def preprocess(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Trả về (ảnh màu đã xoay thẳng, ảnh nhị phân đã xoay thẳng, góc đã sửa)."""
    binary = to_binary(img)
    angle = estimate_skew(binary)
    if abs(angle) >= 0.05:
        img = rotate(img, angle, border=(255, 255, 255))
        binary = rotate(binary, angle, border=255)
    return img, binary, angle


# ---------- OCR ----------
SCALE = 1.5  # phóng ảnh trước khi OCR giúp Tesseract đọc dấu chồng (ê, ệ, ả...) tốt hơn


def gray_of(img: np.ndarray) -> np.ndarray:
    """Ảnh xám đã loại dấu màu; dùng cho OCR (Tesseract tự nhị phân hóa tốt hơn ảnh đã cắt cứng)."""
    return cv2.cvtColor(remove_color_marks(img), cv2.COLOR_BGR2GRAY)


def make_variants(gray: np.ndarray, scale: float = SCALE) -> list[np.ndarray]:
    """Hai biến thể: xám phóng to và Otsu phóng to. Chọn kết quả tin cậy nhất ở bước sau."""
    g = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    otsu = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return [g, otsu]


def _group_lines(d: dict, scale: float) -> list[dict]:
    rows: dict[tuple, list] = {}
    for i, t in enumerate(d["text"]):
        if not t.strip() or float(d["conf"][i]) < 0:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        rows.setdefault(key, []).append(i)
    lines = []
    for idxs in rows.values():
        idxs.sort(key=lambda i: d["left"][i])
        x1 = min(d["left"][i] for i in idxs)
        y1 = min(d["top"][i] for i in idxs)
        x2 = max(d["left"][i] + d["width"][i] for i in idxs)
        y2 = max(d["top"][i] + d["height"][i] for i in idxs)
        wts = [max(1, len(d["text"][i].strip())) for i in idxs]
        conf = sum(float(d["conf"][i]) * w for i, w in zip(idxs, wts)) / sum(wts)
        words = [(d["text"][i].strip(), int(d["left"][i] / scale), int((d["left"][i] + d["width"][i]) / scale))
                 for i in idxs]
        lines.append({"text": " ".join(w[0] for w in words), "x": int(x1 / scale), "y": int(y1 / scale),
                      "w": int((x2 - x1) / scale), "h": int((y2 - y1) / scale), "words": words, "conf": conf,
                      "wconf": [float(d["conf"][i]) for i in idxs]})
    lines.sort(key=lambda r: (r["y"], r["x"]))
    return lines


def _ocr_variant(img: np.ndarray, psm: int, scale: float, extra: str = "") -> list[dict]:
    cfg = f"--oem 1 --psm {psm} -c preserve_interword_spaces=1 {extra}"
    d = pytesseract.image_to_data(img, lang=LANG, config=cfg, output_type=pytesseract.Output.DICT)
    return _group_lines(d, scale)


GOOD_CONF = 88  # dòng/ô đạt ngưỡng này thì không cần OCR lại bằng biến thể khác


def _merge_lines(lines: list[dict], ox: int = 0, oy: int = 0) -> dict | None:
    """Gộp các dòng nhận được từ một vùng cắt thành một dòng, cộng lại tọa độ gốc."""
    if not lines:
        return None
    words = [(t, a + ox, b + ox) for l in lines for (t, a, b) in l["words"]]
    wconf = [c for l in lines for c in l["wconf"]]
    n = sum(len(l["text"]) for l in lines) or 1
    return {"text": " ".join(l["text"] for l in lines), "words": words, "wconf": wconf,
            "x": min(l["x"] for l in lines) + ox, "y": min(l["y"] for l in lines) + oy,
            "w": max(l["x"] + l["w"] for l in lines) - min(l["x"] for l in lines),
            "h": max(l["y"] + l["h"] for l in lines) - min(l["y"] for l in lines),
            "conf": sum(l["conf"] * len(l["text"]) for l in lines) / n}


def _refine_line(gray: np.ndarray, ln: dict) -> dict:
    """Dòng có độ tin cậy thấp: cắt riêng dòng đó, OCR lại bằng 2 biến thể, giữ bản tốt nhất."""
    pad = 10
    H, W = gray.shape
    x0, y0 = max(0, ln["x"] - pad), max(0, ln["y"] - pad)
    crop = gray[y0: min(H, ln["y"] + ln["h"] + pad), x0: min(W, ln["x"] + ln["w"] + pad)]
    best = ln
    for v in make_variants(crop):
        m = _merge_lines(_ocr_variant(v, 7, SCALE), x0, y0)
        if m and m["conf"] > best["conf"] + 2:
            best = m
    return best


def ocr_lines(gray: np.ndarray, psm: int = 6) -> list[dict]:
    """OCR cả vùng; các dòng tin cậy thấp được OCR lại riêng từng dòng."""
    lines = _ocr_variant(make_variants(gray)[0], psm, SCALE)
    out = [l if l["conf"] >= GOOD_CONF else _refine_line(gray, l) for l in lines]
    out.sort(key=lambda r: (r["y"], r["x"]))
    return out


def ocr_text(gray: np.ndarray, psm: int = 6, extra: str = "") -> str:
    """OCR một vùng nhỏ (ô bảng): thử biến thể xám trước; chỉ thử Otsu khi độ tin cậy thấp."""
    best_txt, best_conf = "", -1.0
    for v in make_variants(gray):
        lines = _ocr_variant(v, psm, SCALE, extra)
        if not lines:
            continue
        conf = sum(l["conf"] * len(l["text"]) for l in lines) / max(1, sum(len(l["text"]) for l in lines))
        if conf > best_conf:
            best_conf, best_txt = conf, "\n".join(l["text"] for l in lines)
        if best_conf >= GOOD_CONF:
            break
    return best_txt


def quick_text(gray: np.ndarray, psm: int = 6) -> str:
    """OCR nhanh một lần (không chọn biến thể) cho việc cần tốc độ, ví dụ đọc đầu trang."""
    g = make_variants(gray)[0]
    return pytesseract.image_to_string(g, lang=LANG, config=f"--oem 1 --psm {psm}")


def ocr_digits(gray: np.ndarray) -> str:
    """Ô chỉ chứa số (STT, số lượng...): chỉ cho phép ký tự 0-9 . , -"""
    extra = "-c tessedit_char_whitelist=0123456789.,-"
    return ocr_text(gray, psm=7, extra=extra) or ocr_text(gray, psm=10, extra=extra)  # psm 10 = một ký tự


def clean_text(s: str) -> str:
    """Chuẩn hóa Unicode NFC, bỏ ký tự rác do OCR."""
    import unicodedata
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[|¦]+", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return "\n".join(l.strip() for l in s.splitlines() if l.strip()).strip()
