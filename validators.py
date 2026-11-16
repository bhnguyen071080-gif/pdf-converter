"""Kiểm tra đầu vào và chuẩn hóa tiếng Việt."""
from __future__ import annotations

import re
import unicodedata

MAX_MB = 50
SAMPLE_VN = "Phiếu lĩnh vật tư – Đặng Thị Hương – Quyết định số 12/QĐ-TV"


def check_pdf_upload(name: str, size: int) -> str | None:
    """Trả về thông báo lỗi (str) hoặc None nếu hợp lệ."""
    if not name.lower().endswith(".pdf"):
        return "Chỉ nhận file .pdf"
    if size > MAX_MB * 1024 * 1024:
        return f"File lớn hơn {MAX_MB} MB"
    return None


def parse_page_ranges(text: str, total: int) -> list[int]:
    """'1-3, 5, 8-' -> [0,1,2,4,7,...] (chỉ số từ 0). Ném ValueError nếu sai cú pháp."""
    out: list[int] = []
    for part in re.split(r"[,;\s]+", text.strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d*))?", part)
        if not m:
            raise ValueError(f"Không hiểu '{part}'. Ví dụ đúng: 1-3, 5, 7-9")
        a = int(m[1])
        b = (int(m[2]) if m[2] else total) if "-" in part else a
        if not (1 <= a <= b <= total):
            raise ValueError(f"Dải '{part}' nằm ngoài 1-{total}")
        out += [i - 1 for i in range(a, b + 1) if (i - 1) not in out]
    if not out:
        raise ValueError("Chưa nhập trang nào")
    return out


def is_nfc(s: str) -> bool:
    return unicodedata.is_normalized("NFC", s)
