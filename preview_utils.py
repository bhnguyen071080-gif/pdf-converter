"""Tiện ích hiển thị xem trước: màu nhóm, ảnh thu nhỏ có xoay."""
from __future__ import annotations

import io

from PIL import Image

# Bảng màu nhóm (nền nhạt, viền đậm) – nhóm kế tiếp luôn khác màu nhau
PALETTE = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2", "#be185d", "#65a30d"]


def group_color(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def rotated_png(png: bytes, degrees: int) -> bytes:
    """Xoay ảnh thu nhỏ theo chiều kim đồng hồ (bội số 90) để xem trước đúng hướng."""
    degrees %= 360
    if degrees == 0:
        return png
    img = Image.open(io.BytesIO(png)).rotate(-degrees, expand=True)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def color_bar(color: str, label: str) -> str:
    """HTML thanh màu phía trên ảnh thu nhỏ, ghi tên nhóm."""
    return (f'<div style="background:{color};color:#fff;font-size:12px;font-weight:600;'
            f'padding:1px 6px;border-radius:4px 4px 0 0;text-align:center">{label}</div>')
