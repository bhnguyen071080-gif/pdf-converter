"""Dò con dấu và chữ ký trên trang scan để GIỮ NGUYÊN DẠNG ẢNH (R22), không để OCR đọc thành chữ rác.

Hai nguồn:
1. Màu: mực đỏ/xanh (con dấu, chữ ký bút bi xanh) – dò theo độ bão hòa màu.
2. Mực đen: nét mực KHÔNG thuộc dòng chữ in nào mà OCR đọc chắc chắn, không thuộc đường kẻ/khung/bảng.
Mỗi vùng được cắt thành ảnh PNG nền trong suốt (chỉ giữ nét mực) để đặt chồng lên văn bản như bản gốc.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytesseract

import ocr_utils as ou

CONF_COVERED = 70      # dòng OCR đạt độ tin cậy này coi là "chữ in", nét mực trong đó không phải chữ ký
TOP_EDGE = 190         # mép trên ~1,6 cm: kẹp giấy, ghim, số trang
EDGE = 130             # bỏ vật thể sát mép trang ~1 cm (vệt màu máy quét, kẹp giấy)
CONF_WORD = 65         # từ OCR đạt độ tin cậy này được coi là chữ in
MIN_INK_COLOR = 300    # số điểm ảnh mực tối thiểu của vùng màu
MIN_INK_BLACK = 700    # số điểm ảnh mực tối thiểu của vùng mực đen (cao hơn để tránh bụi, nét đứt)


def _components(mask: np.ndarray, dilate: int):
    dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate, dilate)))
    n, _, st, _ = cv2.connectedComponentsWithStats(dil)
    return [tuple(int(v) for v in st[k][:4]) for k in range(1, n)]


def _overlap(a, b) -> float:
    """Phần diện tích của a nằm trong b (0–1)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy / float(max(1, aw * ah))


def _looks_like_text(mask_crop: np.ndarray, min_comps: int = 6, max_cv: float = 0.45) -> bool:
    """Vùng chứa >= 6 ký tự tách rời, cao gần bằng nhau là chữ in (ví dụ 'ĐẠI DIỆN BÊN A', khung 'Mẫu: BM'),
    chữ ký thường chỉ có vài nét liền."""
    n, _, st, _ = cv2.connectedComponentsWithStats((mask_crop > 0).astype(np.uint8))
    hs = [int(st[k][3]) for k in range(1, n) if st[k][4] >= 40 and 12 <= st[k][3] <= 110]
    if len(hs) < min_comps:
        return False
    hs = np.array(hs, float)
    return hs.std() / hs.mean() < max_cv


def _reads_as_word(ink_crop: np.ndarray) -> bool:
    """Đọc riêng nét mực của vùng (đen trên nền trắng, không dính chữ kế bên): nếu ra một từ rõ ràng
    (>= 2 chữ cái, độ tin cậy cao) thì đó là chữ in, không phải chữ ký."""
    img = cv2.copyMakeBorder(255 - ink_crop, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    d = pytesseract.image_to_data(img, lang=ou.LANG, config="--oem 1 --psm 8", output_type=pytesseract.Output.DICT)
    for t, c in zip(d["text"], d["conf"]):
        t = t.strip()
        if len(t) >= 2 and float(c) >= 75 and t.replace(" ", "").isalpha():
            return True
    return False


def _merge(boxes: list[tuple], gap: int = 30) -> list[tuple]:
    """Gộp các hộp chạm/chồng nhau (dấu tròn + chữ ký đè lên nhau thành một khối)."""
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        out = []
        for b in boxes:
            for o in out:
                if b[0] < o[0] + o[2] + gap and o[0] < b[0] + b[2] + gap and \
                        b[1] < o[1] + o[3] + gap and o[1] < b[1] + b[3] + gap:
                    x1, y1 = min(b[0], o[0]), min(b[1], o[1])
                    x2, y2 = max(b[0] + b[2], o[0] + o[2]), max(b[1] + b[3], o[1] + o[3])
                    o[:] = [x1, y1, x2 - x1, y2 - y1]
                    changed = True
                    break
            else:
                out.append(b)
        boxes = out
    return [tuple(b) for b in boxes]


def detect_marks(img: np.ndarray, binary: np.ndarray, lines: list[dict], tables: list[tuple],
                 hmask: np.ndarray, vmask: np.ndarray) -> list[dict]:
    """Trả danh sách {x, y, w, h, kind, ink, png}. img = ảnh màu đã xoay thẳng; lines = các dòng OCR ngoài bảng."""
    H, W = binary.shape
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    color = (((hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 50)).astype(np.uint8)) * 255
    color = cv2.morphologyEx(color, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    boxes: list[tuple] = []
    # --- 1) vùng màu
    for x, y, w, h in _components(color, 35):
        ink = int((color[y:y + h, x:x + w] > 0).sum())
        if ink < MIN_INK_COLOR or not (w >= 70 or h >= 70):
            continue
        if x < EDGE or y < TOP_EDGE or x + w > W - EDGE or y + h > H - EDGE:
            continue  # vệt màu sát mép trang
        if w / max(1, h) > 8 or h / max(1, w) > 8:
            continue  # vạch mảnh
        boxes.append((x, y, w, h))

    # --- 2) mực đen không thuộc chữ in / đường kẻ / bảng
    ink = (255 - binary).copy()
    ink[cv2.dilate(color, np.ones((9, 9), np.uint8)) > 0] = 0                    # phần màu đã xử lý ở trên
    ink[cv2.dilate(cv2.bitwise_or(hmask, vmask), np.ones((7, 7), np.uint8)) > 0] = 0  # đường kẻ, khung
    for x, y, w, h in tables:
        ink[max(0, y - 6): y + h + 6, max(0, x - 6): x + w + 6] = 0              # trong bảng đã có OCR từng ô
    covered = np.zeros_like(binary)
    for ln in lines:
        pad = 8
        y1, y2 = max(0, ln["y"] - pad), ln["y"] + ln["h"] + pad
        for (t, xa, xb), c in zip(ln["words"], ln.get("wconf", [ln["conf"]] * len(ln["words"]))):
            if c >= CONF_WORD:  # chỉ che những TỪ đọc chắc chắn; nét lạ nằm cạnh chữ (chữ ký) vẫn được giữ lại
                covered[y1:y2, max(0, xa - pad): xb + pad] = 255
    ink[covered > 0] = 0
    ink[:TOP_EDGE, :] = 0
    ink[-EDGE:, :] = 0
    ink[:, :EDGE] = 0
    ink[:, -EDGE:] = 0
    ink_kept = np.zeros_like(ink)  # chỉ giữ nét mực của các vùng được chấp nhận (không kèm chữ in)
    band_lines = [ln for ln in lines if ln["conf"] >= 30]
    for x, y, w, h in _components(ink, 30):
        n_ink = int((ink[y:y + h, x:x + w] > 0).sum())
        if n_ink < MIN_INK_BLACK or not (w >= 80 or h >= 80):
            continue
        if w / max(1, h) > 7 or h / max(1, w) > 7:
            continue
        crop = ink[y:y + h, x:x + w]
        if _looks_like_text(crop):
            continue
        # nằm trọn trong dải một dòng chữ in, cao xấp xỉ dòng, vài ký tự tách rời -> là chữ in đọc kém (chữ đậm, in hoa)
        cy = y + h / 2
        inband = [ln for ln in band_lines if ln["y"] - 10 <= cy <= ln["y"] + ln["h"] + 10
                  and ln["x"] - 10 <= x and x + w <= ln["x"] + ln["w"] + 10]
        if inband and h <= 1.35 * max(ln["h"] for ln in inband) + 8 and _looks_like_text(crop, 2, 0.5):
            continue
        if _reads_as_word(crop):
            continue
        boxes.append((x, y, w, h))
        ink_kept[y:y + h, x:x + w] = ink[y:y + h, x:x + w]

    marks = []
    for x, y, w, h in _merge(boxes):
        pad = 6
        x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
        crop = img[y0:y1, x0:x1]
        sel = ((color[y0:y1, x0:x1] > 0) | (ink_kept[y0:y1, x0:x1] > 0)).astype(np.uint8) * 255
        alpha = cv2.dilate(sel, np.ones((5, 5), np.uint8))
        rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = alpha
        ok, png = cv2.imencode(".png", rgba)
        is_color = int((color[y0:y1, x0:x1] > 0).sum()) > 0.35 * int((sel > 0).sum())
        marks.append({"type": "image", "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
                      "kind": "con dấu / chữ ký màu" if is_color else "chữ ký", "png": png.tobytes()})
    return marks


CONF_DROP = 40  # từ OCR dưới ngưỡng này nằm trong vùng dấu/chữ ký là chữ rác do nét ký đọc nhầm


def word_in_marks(xa: int, xb: int, ln: dict, marks: list[dict]) -> bool:
    box = (xa, ln["y"], max(1, xb - xa), ln["h"])
    return any(_overlap(box, (m["x"], m["y"], m["w"], m["h"])) > 0.5 for m in marks)
