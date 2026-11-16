"""Giao diện Word/Excel -> PDF (R12, R13) có xem trước trước khi tải (R6)."""
from __future__ import annotations

import time

import streamlit as st

import log_utils
import office_to_pdf as op


def render(secret) -> None:
    up = st.file_uploader("Chọn file Word hoặc Excel", type=[e.lstrip(".") for e in op.WORD_EXT + op.EXCEL_EXT],
                          key="office_up")
    if not up:
        st.info("Chọn file .docx / .xlsx để chuyển sang PDF.")
        return
    err = op.check_upload(up.name, up.size)
    if err:
        st.error(err)
        return
    kind = op.kind_of(up.name)
    st.success(f"{up.name} – {'Word' if kind == 'word' else 'Excel'}")
    if op.find_soffice() is None:
        st.error("Máy chưa có LibreOffice. Cài LibreOffice (miễn phí) rồi chạy lại – xem README.")
        return

    if st.button("Chuyển sang PDF và xem trước", type="primary", key="office_go"):
        with st.spinner("Đang chuyển bằng LibreOffice…"):
            t0 = time.time()
            try:
                data = up.getvalue()
                pdf = op.convert_to_pdf(data, up.name)
                info = op.inspect_pdf(pdf, op.source_text(data, up.name))
                st.session_state["office"] = {"name": up.name, "pdf": pdf, "info": info,
                                              "thumbs": op.render_thumbnails(pdf), "secs": time.time() - t0}
                ok, msg = log_utils.write_log(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), up.name,
                                              "word_to_pdf" if kind == "word" else "excel_to_pdf", "ok",
                                              {"pages": info["pages"]})
                st.session_state["office_log"] = None if ok else msg
            except Exception as e:  # noqa: BLE001
                log_utils.write_log(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), up.name,
                                    "word_to_pdf" if kind == "word" else "excel_to_pdf", f"loi: {e}"[:200])
                st.session_state.pop("office", None)
                st.error(f"Lỗi khi chuyển đổi: {e}")
                return

    store = st.session_state.get("office")
    if not store or store["name"] != up.name:
        return
    info = store["info"]
    st.subheader("Xem trước kết quả")
    st.caption(f"Xong trong {store['secs']:.0f} giây · {info['pages']} trang"
               + (f" (đang hiện {len(store['thumbs'])} trang đầu)" if info["pages"] > len(store["thumbs"]) else ""))
    if st.session_state.get("office_log"):
        st.caption(f"Nhật ký: {st.session_state['office_log']}")

    fonts = ", ".join(f"{n} ({'nhúng' if emb else 'KHÔNG nhúng'})" for n, emb in info["fonts"].items()) or "không có chữ"
    st.write(f"**Font trong PDF:** {fonts}")
    if info["missing_chars"]:
        st.warning("Các chữ có dấu trong file gốc không thấy trong PDF: " + " ".join(info["missing_chars"])
                   + ". Kiểm tra lại file gốc (font có thể thiếu chữ tiếng Việt).")
    elif info["fonts"]:
        st.caption("Đã đối chiếu: chữ có dấu tiếng Việt trong file gốc đều có trong PDF.")

    if any(n.startswith("DejaVu") for n in info["fonts"]):
        st.warning("Một số chữ có dấu dùng font thay thế (DejaVu) vì font trong file gốc thiếu chữ tiếng Việt. "
                   "Muốn đẹp đồng nhất: đổi font file gốc sang Times New Roman hoặc Arial rồi chuyển lại.")
    cols = st.columns(4)
    for i, png in enumerate(store["thumbs"]):
        cols[i % 4].image(png, caption=f"Trang {i + 1}", width="stretch")

    st.download_button("⬇️ Tải file PDF", store["pdf"], file_name=up.name.rsplit(".", 1)[0] + ".pdf",
                       mime="application/pdf", key="office_dl")
