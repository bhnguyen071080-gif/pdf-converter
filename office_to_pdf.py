"""Word/Excel -> PDF bằng LibreOffice chế độ headless (miễn phí). R12, R13, R3.

LibreOffice tự nhúng (subset) mọi font dùng trong tài liệu. Times New Roman/Arial được thay bằng
Liberation Serif/Sans (cùng kích thước chữ, có đủ dấu tiếng Việt). Sau khi chuyển, hàm `inspect_pdf`
kiểm tra: font nào được nhúng và chữ có dấu trong file gốc có còn đủ trong PDF không.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import pymupdf

WORD_EXT = (".docx", ".doc", ".odt", ".rtf")
EXCEL_EXT = (".xlsx", ".xls", ".ods", ".csv")
MAX_MB = 50


def find_soffice() -> str | None:
    """Tìm LibreOffice trên Linux/Streamlit Cloud và Windows."""
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.exists(p):
            return p
    return None


def kind_of(name: str) -> str | None:
    n = name.lower()
    if n.endswith(WORD_EXT):
        return "word"
    if n.endswith(EXCEL_EXT):
        return "excel"
    return None


def check_upload(name: str, size: int) -> str | None:
    if kind_of(name) is None:
        return "Chỉ nhận file Word (.docx, .doc, .odt, .rtf) hoặc Excel (.xlsx, .xls, .ods, .csv)"
    if size > MAX_MB * 1024 * 1024:
        return f"File lớn hơn {MAX_MB} MB"
    return None


def convert_to_pdf(data: bytes, file_name: str, timeout: int = 180) -> bytes:
    """Chuyển một file văn phòng sang PDF. Ném RuntimeError nếu LibreOffice lỗi/không có."""
    exe = find_soffice()
    if not exe:
        raise RuntimeError("Chưa cài LibreOffice (xem README: cài LibreOffice trên Windows, "
                           "hoặc thêm 'libreoffice' vào packages.txt khi chạy online).")
    ext = Path(file_name).suffix.lower() or ".docx"
    with tempfile.TemporaryDirectory(prefix="o2p_") as tmp:
        tmp_p = Path(tmp)
        src = tmp_p / f"in{ext}"  # tên cố định ASCII, tránh lỗi ký tự lạ trong đường dẫn
        src.write_bytes(data)
        profile = (tmp_p / "profile").as_uri()  # hồ sơ riêng -> nhiều người dùng cùng lúc không tranh khóa
        flt = "pdf:writer_pdf_Export" if kind_of(file_name) == "word" else "pdf:calc_pdf_Export"
        cmd = [exe, f"-env:UserInstallation={profile}", "--headless", "--norestore",
               "--convert-to", flt, "--outdir", str(tmp_p / "out"), str(src)]
        try:
            run = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"LibreOffice chạy quá {timeout} giây, đã dừng.") from e
        out = tmp_p / "out" / "in.pdf"
        if not out.exists():
            msg = (run.stderr or run.stdout or b"").decode("utf-8", "ignore").strip()[:300]
            raise RuntimeError(f"LibreOffice không tạo được PDF. {msg}")
        return out.read_bytes()


def _vn_chars(text: str) -> set[str]:
    """Các ký tự tiếng Việt có dấu (chuẩn NFC) trong chuỗi."""
    t = unicodedata.normalize("NFC", text)
    return {c for c in t if c.isalpha() and ord(c) > 127}


def source_text(data: bytes, file_name: str) -> str:
    """Lấy chữ từ file gốc để đối chiếu dấu (chỉ .docx/.xlsx; loại khác trả chuỗi rỗng)."""
    n = file_name.lower()
    try:
        if n.endswith(".docx"):
            from docx import Document
            d = Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    parts += [c.text for c in row.cells]
            return "\n".join(parts)
        if n.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
            return "\n".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row
                             if isinstance(c.value, str))
    except Exception:  # noqa: BLE001 - file hỏng thì bỏ qua đối chiếu
        return ""
    return ""


def inspect_pdf(pdf: bytes, src_text: str = "") -> dict:
    """Báo cáo PDF kết quả: số trang, font (đã nhúng chưa), ký tự có dấu bị mất so với file gốc."""
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    fonts: dict[str, bool] = {}
    text = []
    for page in doc:
        for f in page.get_fonts():
            base = f[3].split("+")[-1]
            fonts[base] = fonts.get(base, True) and f[1] not in ("", "n/a")
        text.append(page.get_text())
    out_chars = _vn_chars("\n".join(text))
    missing = sorted(_vn_chars(src_text) - out_chars) if src_text else []
    return {"pages": len(doc), "fonts": fonts, "missing_chars": missing,
            "all_embedded": all(fonts.values()) if fonts else True}


def render_thumbnails(pdf: bytes, max_pages: int = 8, dpi: int = 70) -> list[bytes]:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return [p.get_pixmap(dpi=dpi).tobytes("png") for p in list(doc)[:max_pages]]
