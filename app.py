"""Ứng dụng chuyển đổi PDF (Streamlit): tách trang, PDF -> Excel/Word, Word/Excel -> PDF."""
from __future__ import annotations

import time

import pandas as pd
import pymupdf
import streamlit as st

import log_utils
import ocr_utils as ou
import ui_split
import style
import ui_office
import pdf_to_excel as pe
import pdf_to_word as pw
import validators as vd

st.set_page_config(page_title="Chuyển đổi PDF", page_icon="📄", layout="wide")
style.inject()
style.banner()

KIND_TEXT = {"text": "PDF có lớp chữ (trích trực tiếp, không cần OCR)",
             "scan": "PDF scan/ảnh chụp (dùng OCR Tesseract vie+eng)",
             "mixed": "PDF hỗn hợp (trang nào có chữ thì trích, trang scan thì OCR)"}


def secret(name: str):
    try:
        return st.secrets.get(name)
    except Exception:  # chưa có secrets.toml
        return None


def pdf_side():
    up = st.file_uploader("Chọn file PDF", type=["pdf"])
    if not up:
        st.info("Chọn một file PDF để bắt đầu.")
        return

    err = vd.check_pdf_upload(up.name, up.size)
    if err:
        st.error(err)
        return

    pdf_bytes = up.getvalue()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    kind = ou.detect_pdf_kind(doc)
    st.success(f"{up.name} – {total} trang – **{KIND_TEXT[kind]}**")



    def page_excel():
        # ---- Tùy chọn (R10, R19)
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            page_text = st.text_input("Trang cần chuyển (để trống = tất cả)", placeholder="Ví dụ: 1-3, 5, 8-",
                                      key=f"pages_text:{up.name}")
        with c2:
            mode = st.radio("Cách xuất Excel", ["Mỗi trang một sheet", "Gộp tất cả vào một sheet"], horizontal=False)
        with c3:
            force_ocr = st.checkbox("Ép dùng OCR cho mọi trang", value=False,
                                    help="Dùng khi PDF có lớp chữ nhưng bị lỗi font/lỗi dấu.")

        pages = None
        if page_text.strip():
            try:
                pages = vd.parse_page_ranges(page_text, total)
            except ValueError as e:
                st.error(str(e))
                return

        n_do = len(pages) if pages else total
        if kind != "text" or force_ocr:
            st.caption(f"Ước tính: OCR khoảng 20–40 giây mỗi trang → {n_do} trang ≈ {n_do * 30 // 60 + 1} phút.")

        if st.button("Chuyển đổi và xem trước", type="primary"):
            bar = st.progress(0.0, text="Đang xử lý…")
            t0 = time.time()
            try:
                k, results = pe.convert_pdf(pdf_bytes, pages, progress=lambda p, m: bar.progress(p, text=m),
                                            force_ocr=force_ocr)
                st.session_state["res"] = {"name": up.name, "results": results, "secs": time.time() - t0}
                log_ok, log_msg = log_utils.write_log(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), up.name,
                                                      "pdf_to_excel", "ok", {"pages": len(results)})
                st.session_state["log_msg"] = log_msg if not log_ok else None
            except Exception as e:  # noqa: BLE001
                log_utils.write_log(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), up.name, "pdf_to_excel",
                                    f"loi: {e}"[:200])
                st.error(f"Lỗi khi chuyển đổi: {e}")
                return
            bar.empty()

        store = st.session_state.get("res")
        if not store or store["name"] != up.name:
            return

        # ---- Xem trước và sửa tay (R6)
        st.subheader("Xem trước kết quả – có thể sửa trực tiếp trước khi tải")
        st.caption(f"Xử lý trong {store['secs']:.0f} giây. Bảng bên dưới sửa được; sửa xong bấm 'Tạo file Excel' hoặc 'Tạo file Word'.")
        if st.session_state.get("log_msg"):
            st.caption(f"Nhật ký: {st.session_state['log_msg']}")

        results = store["results"]
        tabs = st.tabs([f"Trang {r['page']}" for r in results])
        for tab, r in zip(tabs, results):
            with tab:
                st.caption(f"Cách xử lý: **{'trích lớp chữ' if r['method'] == 'text' else 'OCR'}**"
                           + (f" · đã khử nghiêng {r['angle']}°" if r["method"] == "ocr" and abs(r["angle"]) >= 0.05 else ""))
                for k, it in enumerate(r["items"]):
                    if it["type"] == "text":
                        txt = " | ".join(t for _, t in it["segments"])
                        new = st.text_input("dòng", txt, key=f"t{r['page']}_{k}", label_visibility="collapsed")
                        if new != txt:  # người dùng sửa -> gộp thành một đoạn
                            it["segments"] = [(it["segments"][0][0], new)]
                    elif it["type"] == "image":
                        ci, cj = st.columns([1, 5])
                        ci.image(it["png"], width="stretch")
                        it["keep"] = cj.checkbox(f"Giữ {it['kind']} (ảnh nguyên trạng) – vị trí gần dòng y={it['y']}",
                                                 value=it.get("keep", True), key=f"i{r['page']}_{k}")
                    else:
                        st.markdown("**Bảng**")
                        df = pd.DataFrame(it["cells"])
                        hdr = it["header_rows"]
                        edited = st.data_editor(df, key=f"d{r['page']}_{k}", width="stretch",
                                                hide_index=True, num_rows="fixed")
                        it["cells"] = edited.fillna("").astype(str).values.tolist()
                        if it["spans"] and any(rs > 1 or cs > 1 for _, _, rs, cs in it["spans"]):
                            st.caption("Các ô gộp trong bản gốc sẽ được gộp lại khi xuất Excel.")

        st.divider()
        base = up.name.rsplit(".", 1)[0]
        cx, cw = st.columns(2)
        with cx:
            if st.button("Tạo file Excel"):
                st.session_state["xlsx"] = pe.build_workbook(results, "per_page" if mode.startswith("Mỗi") else "merged")
            if st.session_state.get("xlsx"):
                st.download_button("⬇️ Tải file Excel", st.session_state["xlsx"], file_name=base + ".xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with cw:
            if st.button("Tạo file Word"):
                st.session_state["docx"] = pw.build_docx(results)
            if st.session_state.get("docx"):
                st.download_button("⬇️ Tải file Word", st.session_state["docx"], file_name=base + ".docx",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.caption("Sửa lại ở bảng xem trước thì bấm 'Tạo file' lần nữa để file mới có nội dung đã sửa. "
                   "Con dấu, chữ ký giữ nguyên dạng ảnh; bỏ chọn 'Giữ' nếu không muốn đưa ảnh đó vào file.")


    tab_split, tab_excel = st.tabs(["✂ Tách / sắp xếp trang", "📊 PDF → Excel / Word"])
    with tab_split:
        ui_split.render(pdf_bytes, up.name,
                        on_log=lambda action, pages, files: log_utils.write_log(
                            secret("SUPABASE_URL"), secret("SUPABASE_KEY"), up.name, action, f"ok:{files} file",
                            {"pages": pages}))
    with tab_excel:
        page_excel()


tab_from, tab_to = st.tabs(["📄 PDF → Word / Excel, tách trang", "🖨 Word / Excel → PDF"])
with tab_to:
    ui_office.render(secret)
with tab_from:
    pdf_side()
