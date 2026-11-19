"""PDF -> Word (.docx) từ mô hình trung gian của pdf_to_excel (đoạn chữ, bảng có ô gộp, ảnh dấu/chữ ký).

- Font mặc định Times New Roman (gán cả vùng ascii/hAnsi/eastAsia để không lỗi dấu tiếng Việt).
- Dòng nhiều đoạn (vd. hai cột tiêu đề) dùng tab theo đúng vị trí gốc; dòng ở giữa trang được canh giữa.
- Dấu và chữ ký (R22) là ảnh PNG nền trong suốt, đặt nổi tại vị trí gốc, bám theo đoạn văn gần nhất.
"""
from __future__ import annotations

import io
import re
import statistics

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Emu, Inches, Pt

DPI = 300
FONT = "Times New Roman"
SIZE = 12
MARGIN_L = 0.6  # inch
MARGIN_R = 0.6
PAGE_W = 8.27
TEXT_W = PAGE_W - MARGIN_L - MARGIN_R
EMU_IN = 914400


import contextvars

EAST = contextvars.ContextVar("east_font", default=None)  # font Đông Á (Nhật/Trung) khi dựng bản dịch


def _set_font(run_or_style, name=FONT, size=None, bold=None):
    f = run_or_style.font
    f.name = name
    rpr = run_or_style.element.get_or_add_rPr() if hasattr(run_or_style, "element") and hasattr(
        run_or_style.element, "get_or_add_rPr") else run_or_style.element.rPr
    rfonts = rpr.rFonts if rpr.rFonts is not None else rpr._add_rFonts()
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(a), (EAST.get() or name) if a == "w:eastAsia" else name)
    if size:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold


def _is_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.7


def _line_pitch_pt(items: list[dict]) -> float:
    ys = [it["y"] for it in items if it["type"] == "text"]
    gaps = [b - a for a, b in zip(ys, ys[1:]) if 30 < b - a < 120]
    return (statistics.median(gaps) / DPI * 72) if gaps else 15.0


def _add_text_item(doc, it: dict, page_w_px: int, prev_bottom_px: int | None, pitch_pt: float):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(0)
    pf.line_spacing = Pt(pitch_pt)  # giữ nhịp dòng như bản gốc để trang không bị tràn
    if prev_bottom_px is not None:
        gap_pt = (it["y"] - prev_bottom_px) / DPI * 72
        pf.space_before = Pt(max(0, min(40, gap_pt - (pitch_pt - 12))))
    segs = [(x, t) for x, t in it["segments"] if t]
    w = it.get("w", 0)
    if len(segs) == 1:
        x, t = segs[0]
        center_px = x + w / 2
        if w and abs(center_px - page_w_px / 2) < 0.035 * page_w_px and x > 0.12 * page_w_px:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            pf.left_indent = Inches(max(0.0, x / DPI - MARGIN_L))
        r = p.add_run(t)
        _set_font(r, size=SIZE, bold=_is_upper(t) or None)
    else:
        text, first = [], True
        for x, t in segs:
            pos = min(TEXT_W - 0.1, max(0.0, x / DPI - MARGIN_L))
            if first and pos < 0.05:
                text.append(t)
            else:
                pf.tab_stops.add_tab_stop(Inches(pos))
                text.append("\t" + t)
            first = False
        r = p.add_run("".join(text))
        _set_font(r, size=SIZE, bold=_is_upper(" ".join(t for _, t in segs)) or None)
    return p


_NUMLIKE = re.compile(r"^[\d.,\-/\s]+$")


def _add_table(doc, it: dict):
    cells = it["cells"]
    nr, nc = len(cells), len(cells[0])
    tbl = doc.add_table(rows=nr, cols=nc)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl._tbl.tblPr.append(parse_xml(  # lề ô gọn như bản scan (đơn vị twip)
        f'<w:tblCellMar {nsdecls("w")}><w:top w:w="0" w:type="dxa"/><w:left w:w="50" w:type="dxa"/>'
        '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="50" w:type="dxa"/></w:tblCellMar>'))
    edges = it.get("x_edges") or []
    if len(edges) == nc + 1:
        widths = [(edges[i + 1] - edges[i]) / DPI for i in range(nc)]
        k = min(1.0, TEXT_W / sum(widths))
        widths = [w * k for w in widths]
    else:
        widths = [TEXT_W / nc] * nc
    for c in range(nc):
        tbl.columns[c].width = Inches(widths[c])  # lưới cột (LibreOffice/Word đọc từ đây)
        for r in range(nr):
            tbl.cell(r, c).width = Inches(widths[c])
    spans = it.get("spans") or [(r, c, 1, 1) for r in range(nr) for c in range(nc)]
    hdr = it.get("header_rows", 1)
    for r, c, rs, cs in spans:
        cell = tbl.cell(r, c)
        if rs > 1 or cs > 1:
            cell = cell.merge(tbl.cell(r + rs - 1, c + cs - 1))
        txt = cells[r][c]
        cell.text = ""
        parts = txt.split("\n") if txt else [""]
        for k, part in enumerate(parts):
            p = cell.paragraphs[0] if k == 0 else cell.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(part)
            _set_font(run, size=SIZE - 2, bold=(r < hdr))
            short_num = bool(part.strip()) and bool(_NUMLIKE.match(part.strip())) and len(part.strip()) <= 12
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if (r < hdr or short_num) else WD_ALIGN_PARAGRAPH.LEFT
        cell.vertical_alignment = 1  # giữa
    return tbl


_ids = [1000]


def _add_floating_picture(paragraph, png: bytes, x_px: int, y_off_px: int, w_px: int, h_px: int):
    """Chèn ảnh PNG nổi (không đẩy chữ): gốc ngang theo trang, gốc dọc theo đoạn văn neo."""
    run = paragraph.add_run()
    cx, cy = int(w_px / DPI * EMU_IN), int(h_px / DPI * EMU_IN)
    pic = run.add_picture(io.BytesIO(png), width=Emu(cx), height=Emu(cy))
    inline = pic._inline
    _ids[0] += 1
    anchor = parse_xml(
        f'<wp:anchor {nsdecls("wp", "a", "pic")} distT="0" distB="0" distL="0" distR="0" simplePos="0" '
        f'relativeHeight="{251658240 + _ids[0]}" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
        '<wp:simplePos x="0" y="0"/>'
        f'<wp:positionH relativeFrom="page"><wp:posOffset>{int(x_px / DPI * EMU_IN)}</wp:posOffset></wp:positionH>'
        f'<wp:positionV relativeFrom="paragraph"><wp:posOffset>{int(y_off_px / DPI * EMU_IN)}</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
        f'<wp:docPr id="{_ids[0]}" name="Dau-chu-ky {_ids[0]}"/><wp:cNvGraphicFramePr/></wp:anchor>')
    anchor.append(inline.graphic)
    drawing = inline.getparent()
    drawing.remove(inline)
    drawing.append(anchor)


def build_docx(results: list[dict], keep_marks: bool = True) -> bytes:
    """results: kết quả convert_pdf. Mỗi trang nguồn bắt đầu một trang Word mới."""
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(PAGE_W), Inches(11.69)
    sec.left_margin, sec.right_margin = Inches(MARGIN_L), Inches(MARGIN_R)
    sec.top_margin = sec.bottom_margin = Inches(0.5)
    st = doc.styles["Normal"]
    _set_font(st, size=SIZE)
    st.paragraph_format.space_after = Pt(0)

    for n, res in enumerate(results):
        items = sorted(res["items"], key=lambda i: (i["y"], i["x"]))
        pitch = _line_pitch_pt(items)
        anchors: list[tuple[int, object]] = []  # (y, đoạn văn) để neo ảnh
        prev_bottom = None
        first_par = None
        for it in items:
            if it["type"] == "image":
                continue
            if it["type"] == "table":
                tbl = _add_table(doc, it)
                last_y = it["y"]
                sp = doc.add_paragraph()  # đoạn trống nhỏ sau bảng
                sp.paragraph_format.line_spacing = Pt(4)
                _set_font(sp.add_run(""), size=3)
                anchors.append((it["y"], sp))
                prev_bottom = it["y"] + sum(len(r[0].split("\n")) for r in it["cells"]) * 55
                continue
            p = _add_text_item(doc, it, res["width"], prev_bottom, pitch)
            anchors.append((it["y"], p))
            prev_bottom = it["y"] + it.get("h", 50)
            if first_par is None:
                first_par = p
        if not anchors:
            first_par = doc.add_paragraph()
            anchors.append((0, first_par))
        if first_par is None:
            first_par = anchors[0][1]
        if n > 0:
            first_par.paragraph_format.page_break_before = True
        if keep_marks:
            for m in [i for i in items if i["type"] == "image" and i.get("keep", True)]:
                above = [a for a in anchors if a[0] <= m["y"]]
                ay, ap = above[-1] if above else anchors[0]
                _add_floating_picture(ap, m["png"], m["x"], m["y"] - ay, m["w"], m["h"])
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
