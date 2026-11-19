"""Dịch tài liệu: từ kết quả convert_pdf -> các khối (đoạn văn, dòng chia tab, bảng, hình) + danh sách chuỗi cần dịch,
rồi dựng Word (.docx) từ bản dịch (người dùng có thể sửa từng chuỗi trước khi xuất). PDF = Word -> LibreOffice.

- Hình vẽ/ảnh (R28) chèn nguyên bản như ảnh, chữ trong hình giữ nguyên.
- Nhiều dòng liền nhau của cùng một đoạn được gộp lại để dịch đúng ngữ cảnh.
"""
from __future__ import annotations

import io
import statistics

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

import pdf_to_word as pw
import translate_utils as tu

SENT_END = tuple(".!?:;。！？：；")


def _is_centered(it: dict, page_w: int) -> bool:
    segs = it["segments"]
    if len(segs) != 1 or not it.get("w") and not it.get("xr"):
        return False
    x = segs[0][0]
    w = it.get("w") or (it["xr"] - x)
    return abs(x + w / 2 - page_w / 2) < 0.035 * page_w and x > 0.12 * page_w


def extract(results: list[dict]) -> tuple[list[list[dict]], list[dict]]:
    """Trả (pages, strings). pages[p] = danh sách khối; strings[i] = {'src','dst','page'}."""
    strings: list[dict] = []

    def sid(text: str, page: int) -> int:
        strings.append({"src": text, "dst": "", "page": page})
        return len(strings) - 1

    pages = []
    for res in results:
        pg = res["page"]
        items = sorted(res["items"], key=lambda i: (i["y"], i["x"]))
        ys = [i["y"] for i in items if i["type"] == "text"]
        gaps = [b - a for a, b in zip(ys, ys[1:]) if 25 < b - a < 120]
        pitch = statistics.median(gaps) if gaps else 60
        blocks: list[dict] = []
        cur = None  # đoạn đang gộp
        last_y = None
        for it in items:
            if it["type"] == "image":
                if it.get("figure"):
                    cur = None
                    blocks.append({"t": "fig", "png": it["png"], "w": it["w"], "h": it["h"], "x": it["x"]})
                    last_y = it["y"] + it["h"]
                continue  # dấu/chữ ký không đưa vào bản dịch
            if it["type"] == "table":
                cur = None
                cells = it["cells"]
                ids = [[sid(c, pg) if c.strip() else None for c in row] for row in cells]
                blocks.append({"t": "table", "ids": ids, "spans": it.get("spans") or [], "x_edges": it.get("x_edges") or [],
                               "header_rows": it.get("header_rows", 1), "ncols": len(cells[0]), "nrows": len(cells)})
                last_y = it["y"] + len(cells) * 55
                continue
            segs = [(x, t) for x, t in it["segments"] if t]
            if not segs:
                continue
            if len(segs) > 1:  # dòng nhiều cột -> dịch từng ô, giữ vị trí tab
                cur = None
                blocks.append({"t": "tabs", "ids": [sid(t, pg) for _, t in segs], "xs": [x for x, _ in segs],
                               "gap": 0 if last_y is None else (it["y"] - last_y)})
                last_y = it["y"] + it.get("h", pitch)
                continue
            x, t = segs[0]
            center = _is_centered(it, res["width"])
            if (cur is not None and not center and not cur["center"] and abs(x - cur["x"]) < 70
                    and last_y is not None and it["y"] - last_y < 0.9 * pitch
                    and not strings[cur["ids"][-1]]["src"].rstrip().endswith(SENT_END)
                    and not pw._is_upper(strings[cur["ids"][-1]]["src"])):
                strings[cur["ids"][-1]]["src"] += " " + t  # nối dòng vào đoạn
            else:
                cur = {"t": "para", "ids": [sid(t, pg)], "x": x, "center": center, "upper": pw._is_upper(t),
                       "gap": 0 if last_y is None else (it["y"] - last_y)}
                blocks.append(cur)
            last_y = it["y"] + it.get("h", pitch * 0.8)
        pages.append(blocks)
    for b in [b for p in pages for b in p if b["t"] == "para"]:
        b["upper"] = pw._is_upper(strings[b["ids"][0]]["src"])
    return pages, strings


def build_docx(pages: list[list[dict]], strings: list[dict], tgt: str, size: int = 12) -> bytes:
    """Dựng Word từ bản dịch (strings[i]['dst']; trống thì dùng bản gốc)."""
    tok = pw.EAST.set(tu.LANGS.get(tgt, ("", "", pw.FONT))[2])
    try:
        text = lambda i: strings[i]["dst"].strip() or strings[i]["src"]
        doc = Document()
        sec = doc.sections[0]
        sec.page_width, sec.page_height = Inches(pw.PAGE_W), Inches(11.69)
        sec.left_margin, sec.right_margin = Inches(pw.MARGIN_L), Inches(pw.MARGIN_R)
        sec.top_margin = sec.bottom_margin = Inches(0.6)
        st = doc.styles["Normal"]
        pw._set_font(st, size=size)
        st.paragraph_format.space_after = Pt(0)
        for n, blocks in enumerate(pages):
            first = None
            for b in blocks:
                if b["t"] in ("para", "tabs"):
                    p = doc.add_paragraph()
                    pf = p.paragraph_format
                    pf.space_after = Pt(2)
                    pf.space_before = Pt(max(0, min(24, b.get("gap", 0) / pw.DPI * 72 * 0.6)))
                    if b["t"] == "para":
                        if b["center"]:
                            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        else:
                            pf.left_indent = Inches(max(0.0, min(2.5, b["x"] / pw.DPI - pw.MARGIN_L)))
                            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if tgt not in tu.CJK_LANGS else WD_ALIGN_PARAGRAPH.LEFT
                        r = p.add_run(text(b["ids"][0]))
                        pw._set_font(r, size=size, bold=b["upper"] or None)
                    else:
                        parts = []
                        for k, (i, x) in enumerate(zip(b["ids"], b["xs"])):
                            pos = min(pw.TEXT_W - 0.1, max(0.0, x / pw.DPI - pw.MARGIN_L))
                            if k == 0 and pos < 0.05:
                                parts.append(text(i))
                            else:
                                pf.tab_stops.add_tab_stop(Inches(pos))
                                parts.append("\t" + text(i))
                        r = p.add_run("".join(parts))
                        pw._set_font(r, size=size)
                elif b["t"] == "table":
                    it = {"cells": [[text(i) if i is not None else "" for i in row] for row in b["ids"]],
                          "spans": b["spans"], "x_edges": b["x_edges"], "header_rows": b["header_rows"]}
                    pw._add_table(doc, it)
                    p = doc.add_paragraph()
                    p.paragraph_format.line_spacing = Pt(4)
                else:  # hình: chèn nguyên bản, vừa bề rộng trang
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    w_in = min(pw.TEXT_W, b["w"] / pw.DPI)
                    h_in = w_in * b["h"] / b["w"]
                    if h_in > 8.8:  # không cao quá một trang
                        w_in, h_in = w_in * 8.8 / h_in, 8.8
                    p.add_run().add_picture(io.BytesIO(b["png"]), width=Inches(w_in))
                if first is None:
                    first = p
            if first is None:
                first = doc.add_paragraph()
            if n > 0:
                first.paragraph_format.page_break_before = True
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        pw.EAST.reset(tok)
