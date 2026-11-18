"""Bộ kiểm tra hồi quy. Chạy: python -m pytest tests -q   (hoặc: python tests/test_regression.py)"""
import io
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl
import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import ocr_utils as ou
import pdf_to_excel as pe
import validators as vd

SAMPLE = vd.SAMPLE_VN  # "Phiếu lĩnh vật tư – Đặng Thị Hương – Quyết định số 12/QĐ-TV"


def _make_text_pdf() -> bytes:
    """PDF có lớp chữ, nhúng font DejaVu (R3), có 1 bảng 3 cột và 1 dòng mẫu tiếng Việt."""
    pdfmetrics.registerFont(TTFont("DejaVu", str(ROOT / "fonts" / "DejaVuSans.ttf")))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("DejaVu", 12)
    c.drawString(60, 780, SAMPLE)
    rows = [["STT", "Tên vật tư", "Số lượng"], ["1", "Vòng bi 22210 CA", "04"], ["2", "Phớt 50x90x10", "12"]]
    x0, y0, cw, rh = 60, 700, [50, 250, 100], 28
    for i, row in enumerate(rows):
        x = x0
        for j, v in enumerate(row):
            c.rect(x, y0 - i * rh, cw[j], rh)
            c.drawString(x + 6, y0 - i * rh + 9, v)
            x += cw[j]
    c.save()
    return buf.getvalue()


def test_page_ranges():
    assert vd.parse_page_ranges("1-3, 5", 8) == [0, 1, 2, 4]
    assert vd.parse_page_ranges("6-", 8) == [5, 6, 7]
    for bad in ("0", "9", "a-b", ""):
        try:
            vd.parse_page_ranges(bad, 8)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_text_pdf_path_and_vietnamese():
    pdf = _make_text_pdf()
    kind, res = pe.convert_pdf(pdf)
    assert kind == "text" and res[0]["method"] == "text"
    texts = [t for it in res[0]["items"] if it["type"] == "text" for _, t in it["segments"]]
    assert SAMPLE in texts, texts
    tbl = [it for it in res[0]["items"] if it["type"] == "table"][0]
    assert tbl["cells"][1] == ["1", "Vòng bi 22210 CA", "04"], tbl["cells"]
    assert all(unicodedata.is_normalized("NFC", t) for t in texts)


def test_xlsx_numbers_dates_and_unicode():
    item = {"type": "table", "y": 0, "x": 0, "x_edges": [], "spans": [], "header_rows": 1,
            "cells": [["STT", "Tên", "Số lượng", "Ngày", "Đơn giá"],
                      ["1", SAMPLE, "04", "05/09/2026", "1.250.000"],
                      ["2", "Phớt", "12", "16/09/2026", "2.500,5"],
                      ["ổ", "= lỗi OCR", "12", "17/09/2026", "100"],
                      ["4", "Khuyết cáp", "12", "18/09/2026", "100"],
                      ["5", "Đầu cos", "12", "19/09/2026", "100"]]}
    data = pe.build_workbook([{"page": 1, "method": "ocr", "angle": 0, "width": 2480, "items": [item]}])
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    assert ws["A2"].value == 1 and isinstance(ws["A2"].value, int)           # số, không phải chữ
    assert ws["B2"].value == SAMPLE                                            # dấu tiếng Việt nguyên vẹn
    assert ws["C2"].value == 4 and ws["C2"].number_format == "00"             # giữ số 0 đầu
    assert ws["D2"].value.day == 5 and ws["D2"].number_format == "dd/mm/yyyy"  # ngày đúng định dạng
    assert ws["E2"].value == 1250000 and ws["E3"].value == 2500.5
    assert ws["B4"].value == "= lỗi OCR" and ws["B4"].data_type == "s"        # không bị hiểu là công thức
    assert ws["A4"].value == "ổ"                                               # ô OCR sai giữ chữ, không mất dữ liệu


def test_scan_detect_and_table_structure():
    """Mẫu scan thật (BM 02.08): nhận ra là scan, bảng 13x8, đọc đúng các giá trị chính."""
    sample = ROOT / "samples" / "mau_16-9.pdf"
    if not sample.exists():
        print("bỏ qua: thiếu file mẫu")
        return
    doc = pymupdf.open(str(sample))
    assert ou.detect_pdf_kind(doc) == "scan"
    kind, res = pe.convert_pdf(sample.read_bytes(), pages=[0])
    tbl = [it for it in res[0]["items"] if it["type"] == "table"][0]
    assert (len(tbl["cells"]), len(tbl["cells"][0])) == (13, 8), (len(tbl["cells"]), len(tbl["cells"][0]))
    body = [r[0] for r in tbl["cells"][1:]]
    assert body.count("1") + body.count("2") + body.count("3") >= 3, body
    qty = [r[3] for r in tbl["cells"][1:]]
    assert qty.count("04") >= 3 and qty.count("12") == 3, qty
    joined = " ".join(c for r in tbl["cells"] for c in r)
    assert "Phớt" in joined and "Vòng" in joined, joined


def _make_pages_pdf(n=6) -> bytes:
    """PDF n trang, mỗi trang ghi 'Trang k' để kiểm tra thứ tự sau khi tách."""
    import pymupdf
    d = pymupdf.open()
    for i in range(n):
        p = d.new_page()
        p.insert_text((72, 100), f"Trang {i + 1}", fontsize=24)
    return d.tobytes()


def test_splitter_groups_and_ranges():
    import pdf_splitter as sp
    assert sp.groups_from_breaks({1, 3}, 6) == [(0, 1), (2, 3), (4, 5)]
    assert sp.breaks_all(4) == {0, 1, 2}
    assert sp.breaks_every(3, 8) == {2, 5}
    assert sp.breaks_from_ranges("1-3, 4, 5-8", 8) == {2, 3}
    for bad in ("1-3, 5-8", "2-8", "1-3, 3-8", "1-9", "x"):
        try:
            sp.breaks_from_ranges(bad, 8)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_splitter_output_rotate_delete_reorder_zip():
    import zipfile
    import pymupdf
    import pdf_splitter as sp
    pdf = _make_pages_pdf(6)
    order = [0, 2, 1, 4, 5]  # đã xóa trang 4 (gốc), đổi chỗ trang 2 và 3
    parts = sp.split_pdf(pdf, order, {0: 90}, sp.groups_from_breaks({1}, len(order)))
    assert [c for _, c in parts] == [2, 3]
    d1 = pymupdf.open(stream=parts[0][0], filetype="pdf")
    assert "Trang 1" in d1[0].get_text() and "Trang 3" in d1[1].get_text()   # đúng thứ tự mới
    assert d1[0].rotation == 90 and d1[1].rotation == 0                       # xoay đúng trang
    d2 = pymupdf.open(stream=parts[1][0], filetype="pdf")
    assert [("Trang %d" % k) in d2[i].get_text() for i, k in enumerate((2, 5, 6))] == [True] * 3
    used = set()
    names = [sp.safe_name("Phiếu lĩnh vật tư – Đặng Thị Hương", used), sp.safe_name("Phiếu lĩnh vật tư – Đặng Thị Hương", used),
             sp.safe_name('a/b:c?.pdf', used)]
    assert names == ["Phiếu lĩnh vật tư – Đặng Thị Hương.pdf", "Phiếu lĩnh vật tư – Đặng Thị Hương_2.pdf", "a_b_c_.pdf"], names
    z = zipfile.ZipFile(io.BytesIO(sp.make_zip([(names[0], parts[0][0]), (names[1], parts[1][0])])))
    assert z.namelist()[0] == names[0]                                          # tên tiếng Việt trong zip nguyên vẹn


def test_select_groups_and_range_text():
    import pdf_splitter as sp
    import validators as vd
    groups = [(0, 1), (2, 3), (4, 5)]
    order = [0, 2, 1, 4, 5, 6]
    assert sp.selected_pages(groups, order, [True, False, True]) == [0, 2, 5, 6]   # R23/R24: chỉ nhóm được tích
    assert sp.selected_pages(groups, order, [False, False, False]) == []
    assert sp.pages_to_range_text([0, 1, 2, 4, 7, 8]) == "1-3, 5, 8-9"
    assert sp.pages_to_range_text([3]) == "4"
    assert vd.parse_page_ranges(sp.pages_to_range_text([0, 1, 2, 4]), 10) == [0, 1, 2, 4]   # khứ hồi với ô nhập trang


def test_title_key_fuzzy():
    import pdf_splitter as sp
    assert sp.title_key("CỘNG HÒA\nBIÊN BẢN KIỂM TRA\nXÁC ĐỊNH") == "KIEM TRA"
    assert sp.title_key("BUEN BẢN KIEM TRA XÁC") == "KIEM TRA"
    assert sp.looks_like_first_page("CỘNG HOA XÃ HỘI CHỦ NGHĨA")
    assert not sp.looks_like_first_page("Chức vụ: Nhân viên Ban KTVTAT\nSố lượng 04")


def _tiny_png() -> bytes:
    import cv2
    import numpy as np
    a = np.zeros((40, 80, 4), np.uint8)
    cv2.line(a, (5, 35), (75, 5), (160, 0, 0, 255), 3)
    return cv2.imencode(".png", a)[1].tobytes()


def _model_with_mark():
    return [{"page": 1, "method": "ocr", "angle": 0, "width": 2480, "items": [
        {"type": "text", "y": 200, "x": 600, "w": 1200, "h": 50, "conf": 95, "segments": [(600, SAMPLE.upper())]},
        {"type": "text", "y": 300, "x": 200, "w": 900, "h": 50, "conf": 95, "segments": [(200, SAMPLE)]},
        {"type": "table", "y": 400, "x": 200, "x_edges": [200, 500, 1500, 2000], "header_rows": 1, "spans": [],
         "cells": [["STT", "Tên vật tư", "Số lượng"], ["1", "Vòng bi 22210 CA", "04"], ["2", "Phớt", "12"]]},
        {"type": "image", "kind": "chữ ký", "y": 900, "x": 1500, "w": 80, "h": 40, "png": _tiny_png()},
    ]}]


def test_word_output_vietnamese_table_and_mark():
    import pdf_to_word as pw
    from docx import Document
    data = pw.build_docx(_model_with_mark())
    d = Document(io.BytesIO(data))
    texts = [p.text for p in d.paragraphs]
    assert SAMPLE in texts and SAMPLE.upper() in texts, texts                  # dấu tiếng Việt nguyên vẹn
    assert d.tables[0].cell(1, 1).text == "Vòng bi 22210 CA" and d.tables[0].cell(2, 2).text == "12"
    assert d.styles["Normal"].font.name == "Times New Roman"
    xml = d.element.xml
    assert "<wp:anchor" in xml and "w:eastAsia=\"Times New Roman\"" in xml     # ảnh nổi + font cho tiếng Việt
    off = pw.build_docx([{**_model_with_mark()[0], "items": [dict(i, keep=False) if i["type"] == "image" else i
                                                              for i in _model_with_mark()[0]["items"]]}])
    assert "<wp:anchor" not in Document(io.BytesIO(off)).element.xml          # bỏ chọn 'Giữ' thì không có ảnh


def test_excel_output_keeps_mark_image():
    data = pe.build_workbook(_model_with_mark())
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    assert len(ws._images) == 1 and ws["A3"].value is not None


def test_mark_detection_synthetic():
    """Con dấu đỏ và nét ký đen được tách thành ảnh; chữ in rõ ràng thì không."""
    import cv2
    import numpy as np
    import mark_utils as mk
    img = np.full((3000, 2400, 3), 255, np.uint8)
    cv2.circle(img, (800, 1500), 150, (30, 30, 220), 8)                       # con dấu đỏ (BGR)
    cv2.circle(img, (800, 1500), 90, (30, 30, 220), 5)
    pts = np.array([[1500, 1700], [1560, 1500], [1620, 1750], [1700, 1480], [1800, 1720], [1880, 1560]], np.int32)
    cv2.polylines(img, [pts], False, (20, 20, 20), 6)                         # nét ký đen
    cv2.putText(img, "GIAO", (300, 600), cv2.FONT_HERSHEY_TRIPLEX, 3.5, (0, 0, 0), 6)  # chữ in
    binary = cv2.threshold(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    z = np.zeros_like(binary)
    marks = mk.detect_marks(img, binary, [], [], z, z)
    kinds = sorted(m["kind"] for m in marks)
    assert len(marks) == 2 and any("màu" in k for k in kinds) and "chữ ký" in kinds, kinds
    assert all(m["png"][:4] == b"\x89PNG" for m in marks)


def test_office_to_pdf_vietnamese_fonts_embedded():
    """Word (Times New Roman) và Excel -> PDF: đủ dấu tiếng Việt, font được nhúng (R12, R13, R3)."""
    import office_to_pdf as op
    import pymupdf
    from docx import Document
    from docx.oxml.ns import qn
    d = Document()
    d.styles["Normal"].font.name = "Times New Roman"
    d.styles["Normal"].element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    d.add_paragraph(SAMPLE)
    d.add_paragraph("ƯƠẰẲẴẶỆỒỔỖỘỜỞỠỢỪỬỮỰ ưăâêôơ đ Đ ỳỷỹỵ")
    b = io.BytesIO()
    d.save(b)
    pdf = op.convert_to_pdf(b.getvalue(), "mau.docx")
    info = op.inspect_pdf(pdf, op.source_text(b.getvalue(), "mau.docx"))
    assert info["pages"] == 1 and info["all_embedded"] and not info["missing_chars"], info
    assert SAMPLE in pymupdf.open(stream=pdf, filetype="pdf")[0].get_text().replace("\n", " ")

    wb = openpyxl.Workbook()
    wb.active["A1"] = SAMPLE
    wb.active["A2"] = 1234.5
    x = io.BytesIO()
    wb.save(x)
    pdf2 = op.convert_to_pdf(x.getvalue(), "mau.xlsx")
    info2 = op.inspect_pdf(pdf2, op.source_text(x.getvalue(), "mau.xlsx"))
    assert info2["all_embedded"] and not info2["missing_chars"], info2
    assert SAMPLE in pymupdf.open(stream=pdf2, filetype="pdf")[0].get_text()
    assert op.check_upload("a.pdf", 10) and op.check_upload("a.docx", 10) is None


def test_roundtrip_word_pdf_word_text():
    """Word -> PDF (LibreOffice) rồi PDF -> Excel đường có lớp chữ: dấu không đổi."""
    import office_to_pdf as op
    from docx import Document
    d = Document()
    d.styles["Normal"].font.name = "Times New Roman"
    d.add_paragraph(SAMPLE)
    b = io.BytesIO()
    d.save(b)
    pdf = op.convert_to_pdf(b.getvalue(), "mau.docx")
    kind, res = pe.convert_pdf(pdf)
    assert kind == "text"
    txt = " ".join(t for it in res[0]["items"] if it["type"] == "text" for _, t in it["segments"])
    assert SAMPLE.split(" – ")[0] in txt, txt


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("Đạt:", name)
