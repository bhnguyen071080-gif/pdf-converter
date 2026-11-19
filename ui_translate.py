"""Tab "Dịch tài liệu" (R25–R29): chọn ngôn ngữ gốc/đích, OCR đúng ngôn ngữ, dịch, xem trước/sửa, xuất Word hoặc PDF."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

import log_utils
import office_to_pdf as op
import pdf_to_excel as pe
import translate_doc as td
import translate_utils as tu
import validators as vd

NAMES = {k: v[0] for k, v in tu.LANGS.items()}


def _fmt(c: str) -> str:
    return NAMES[c]


def render(pdf_bytes: bytes, file_name: str, total: int, secret) -> None:
    st.markdown("Dịch tài liệu kỹ thuật sang ngôn ngữ khác, **giữ nguyên hình vẽ/ảnh**, xuất Word hoặc PDF.")
    c1, c2, c3 = st.columns(3)
    with c1:
        src = st.selectbox("Ngôn ngữ của tài liệu (gốc)", list(NAMES), index=1, format_func=_fmt, key="tr_src")
    with c2:
        tgt = st.selectbox("Dịch sang", list(NAMES), index=0, format_func=_fmt, key="tr_tgt")
    with c3:
        page_text = st.text_input("Trang cần dịch (trống = tất cả)", placeholder="Ví dụ: 1-3, 5", key=f"tr_pages:{file_name}")
    c4, c5 = st.columns(2)
    with c4:
        engine = st.radio("Dịch vụ dịch (miễn phí)", ["auto", "mymemory", "google"], horizontal=True, key="tr_engine",
                          format_func={"auto": "Tự động (MyMemory, hết hạn mức thì Google)", "mymemory": "Chỉ MyMemory",
                                       "google": "Chỉ Google (web)"}.get)
    with c5:
        email = st.text_input("Email (tùy chọn – MyMemory tăng hạn mức ngày từ 5.000 lên 50.000 ký tự)", key="tr_email")
    keep_fig = st.checkbox("Giữ nguyên hình vẽ/ảnh trong bản dịch (chữ trong hình không dịch)", value=True, key="tr_fig")
    force_ocr = st.checkbox("Ép dùng OCR (khi PDF có lớp chữ nhưng lỗi font)", value=False, key="tr_ocr")
    with st.expander("Từ điển thuật ngữ (thiết bị cảng biển) – xem/bổ sung"):
        st.caption("Khi dịch sang tiếng Việt, các thuật ngữ trong từ điển có sẵn (Anh, Đức) được thay trước để không bị dịch sai "
                   "(vd. rubber tyred gantry crane → cẩu khung bánh lốp (RTG)). Bổ sung thêm: mỗi dòng `gốc = dịch`; "
                   "mục của bạn ưu tiên hơn mục có sẵn.")
        user_gl = st.text_area("Thuật ngữ của bạn", placeholder="spreader beam = xà nâng\nreach stacker = xe nâng container", key="tr_gl")
    with st.expander("Dịch thử một đoạn (kiểm tra dịch vụ hoạt động và chất lượng)"):
        sample = st.text_area("Đoạn cần thử", "Check the wire rope and the hydraulic cylinder before operation.", key="tr_sample")
        if st.button("Dịch thử", key="tr_try"):
            try:
                out, stt = tu.translate_strings([sample], src, tgt, engine, email.strip(), tu.parse_glossary(user_gl))
                st.success(out[0])
                st.caption(f"Dịch vụ: {', '.join(stt.engines) or 'đã có trong bộ nhớ'}")
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

    st.warning("Văn bản sẽ được gửi tới dịch vụ dịch miễn phí trên Internet (MyMemory / Google). "
               "Không dùng cho tài liệu mật, nội bộ cần giữ kín.")
    agree = st.checkbox("Tôi đồng ý gửi nội dung văn bản của tài liệu này ra ngoài để dịch", key="tr_agree")
    if src == tgt:
        st.error("Ngôn ngữ gốc và ngôn ngữ đích đang trùng nhau.")
        return

    pages = None
    if page_text.strip():
        try:
            pages = vd.parse_page_ranges(page_text, total)
        except ValueError as e:
            st.error(str(e))
            return
    n_do = len(pages) if pages else total
    st.caption(f"Sẽ xử lý {n_do} trang. Trang scan cần OCR (khoảng 20–40 giây/trang).")

    if st.button("Dịch tài liệu", type="primary", disabled=not agree, key="tr_go"):
        bar = st.progress(0.0, text="Đang đọc tài liệu…")
        t0 = time.time()
        try:
            kind, results = pe.convert_pdf(pdf_bytes, pages, progress=lambda p, m: bar.progress(p * 0.6, text=m),
                                           force_ocr=force_ocr, lang=src, figures=keep_fig)
            blocks, strings = td.extract(results)
            cache = st.session_state.setdefault("tr_cache", {})
            texts = [s["src"] for s in strings]
            n_chars = sum(len(t) for t in texts if tu.needs_translation(t))
            bar.progress(0.6, text=f"Đang dịch {n_chars:,} ký tự…")
            out, stt = tu.translate_strings(texts, src, tgt, engine, email.strip(), tu.parse_glossary(user_gl), cache,
                                            progress=lambda p, m: bar.progress(0.6 + p * 0.4, text=m))
            for s, o in zip(strings, out):
                s["dst"] = o
            figs = sum(1 for p in blocks for b in p if b["t"] == "fig")
            st.session_state["tr"] = {"name": file_name, "src": src, "tgt": tgt, "blocks": blocks, "strings": strings,
                                      "stats": stt, "methods": sorted({r["method"] for r in results}), "figs": figs,
                                      "secs": time.time() - t0, "docx": None, "pdf": None, "kw": (engine, email.strip(), user_gl)}
            ok, msg = log_utils.write_log(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), file_name,
                                          f"translate_{src}_{tgt}", "ok", {"pages": len(results)})
            st.session_state["tr_log"] = None if ok else msg
        except tu.QuotaExceeded as e:
            st.error(str(e) + " Phần đã dịch được giữ lại; bấm 'Dịch tài liệu' lần nữa sau khi nhập email hoặc đổi dịch vụ.")
            return
        except Exception as e:  # noqa: BLE001
            log_utils.write_log(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), file_name, f"translate_{src}_{tgt}",
                                f"loi: {e}"[:200])
            st.error(f"Lỗi: {e}")
            return
        finally:
            bar.empty()

    store = st.session_state.get("tr")
    if not store or store["name"] != file_name:
        return
    _preview(store, secret)


def _preview(store: dict, secret) -> None:
    stt = store["stats"]
    strings = store["strings"]
    st.subheader("Xem trước bản dịch – sửa trực tiếp trước khi xuất")
    how = {"text": "trích lớp chữ", "ocr": "OCR"}
    st.caption(f"{NAMES[store['src']]} → {NAMES[store['tgt']]} · xử lý {store['secs']:.0f} giây · cách đọc: "
               + ", ".join(how[m] for m in store["methods"]) + f" · {store['figs']} hình giữ nguyên · "
               f"đã gửi {stt.chars_sent:,} ký tự ({stt.cached} đoạn lấy từ bộ nhớ) · dịch vụ: {', '.join(sorted(stt.engines)) or '—'}"
               + (" (đã chuyển sang Google do MyMemory hết hạn mức)" if stt.fallback else ""))
    if st.session_state.get("tr_log"):
        st.caption(f"Nhật ký: {st.session_state['tr_log']}")
    if store["figs"]:
        with st.expander(f"Hình giữ nguyên ({store['figs']})"):
            cols = st.columns(4)
            k = 0
            for p in store["blocks"]:
                for b in p:
                    if b["t"] == "fig":
                        cols[k % 4].image(b["png"], width="stretch")
                        k += 1

    df = pd.DataFrame({"Trang": [s["page"] for s in strings], "Gốc": [s["src"] for s in strings],
                       "Bản dịch": [s["dst"] for s in strings], "Dịch lại": [False] * len(strings)})
    ed = st.data_editor(df, key=f"tr_ed:{store['name']}", hide_index=True, width="stretch", num_rows="fixed",
                        disabled=["Trang"], column_config={"Trang": st.column_config.NumberColumn(width="small"),
                                                           "Gốc": st.column_config.TextColumn(width="large"),
                                                           "Bản dịch": st.column_config.TextColumn(width="large"),
                                                           "Dịch lại": st.column_config.CheckboxColumn(width="small")})
    for s, (_, row) in zip(strings, ed.iterrows()):
        s["src"], s["dst"] = row["Gốc"] or "", row["Bản dịch"] or ""
    redo = [i for i, r in enumerate(ed["Dịch lại"].tolist()) if r]
    c1, c2 = st.columns(2)
    with c1:
        if redo and st.button(f"Dịch lại {len(redo)} dòng đã tích (theo cột Gốc)", key="tr_redo"):
            engine, email, gl = store["kw"]
            try:
                out, _ = tu.translate_strings([strings[i]["src"] for i in redo], store["src"], store["tgt"], engine, email,
                                              tu.parse_glossary(gl), st.session_state.setdefault("tr_cache", {}))
                for i, o in zip(redo, out):
                    strings[i]["dst"] = o
                st.session_state.pop(f"tr_ed:{store['name']}", None)
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
    st.divider()
    base = store["name"].rsplit(".", 1)[0] + f"_{store['tgt']}"
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Tạo file Word", key="tr_mkdocx"):
            store["docx"] = td.build_docx(store["blocks"], strings, store["tgt"])
        if store.get("docx"):
            st.download_button("⬇️ Tải file Word", store["docx"], file_name=base + ".docx", key="tr_dldocx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    with b2:
        if st.button("Tạo file PDF và xem trước", key="tr_mkpdf"):
            if op.find_soffice() is None:
                st.error("Máy chưa có LibreOffice – xem README.")
            else:
                with st.spinner("Đang tạo PDF bằng LibreOffice…"):
                    docx = td.build_docx(store["blocks"], strings, store["tgt"])
                    store["docx"] = docx
                    pdf = op.convert_to_pdf(docx, base + ".docx")
                    store["pdf"] = pdf
                    store["info"] = op.inspect_pdf(pdf)
                    store["thumbs"] = op.render_thumbnails(pdf)
        if store.get("pdf"):
            info = store["info"]
            if info["missing_chars"]:
                st.warning("Một số ký tự không có trong font của PDF: " + " ".join(info["missing_chars"]))
            cols = st.columns(4)
            for i, png in enumerate(store["thumbs"]):
                cols[i % 4].image(png, caption=f"Trang {i + 1}", width="stretch")
            st.download_button("⬇️ Tải file PDF", store["pdf"], file_name=base + ".pdf", mime="application/pdf",
                               key="tr_dlpdf")
    st.caption("Sửa bản dịch ở bảng rồi bấm 'Tạo file' lần nữa để file mới có nội dung đã sửa. Con dấu, chữ ký không đưa vào bản dịch.")
