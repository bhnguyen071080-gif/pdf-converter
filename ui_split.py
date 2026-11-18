"""Giao diện tách trang PDF trực quan (R15–R18, R20)."""
from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

import pdf_splitter as sp
import preview_utils as pv

PER_ROW = 6  # số trang mỗi hàng


def _init(fid: str, pdf_bytes: bytes):
    if f"{fid}:order" in st.session_state:
        return
    thumbs = sp.make_thumbnails(pdf_bytes)
    st.session_state[f"{fid}:thumbs"] = thumbs
    st.session_state[f"{fid}:order"] = list(range(len(thumbs)))  # thứ tự hiện tại (chỉ số trang gốc)
    st.session_state[f"{fid}:deleted"] = []
    st.session_state[f"{fid}:rot"] = {}
    st.session_state[f"{fid}:brk"] = set()
    st.session_state[f"{fid}:tops"] = {}


def render(pdf_bytes: bytes, file_name: str, on_log=None):
    fid = hashlib.md5(pdf_bytes).hexdigest()[:10]
    _init(fid, pdf_bytes)
    S = st.session_state
    k = lambda x: f"{fid}:{x}"  # noqa: E731
    order: list[int] = S[k("order")]
    n = len(order)
    base = file_name.rsplit(".", 1)[0]

    if n == 0:
        st.warning("Đã xóa hết trang.")
        if st.button("Khôi phục tất cả trang đã xóa", key=k("restore0")):
            S[k("order")] = sorted(S[k("order")] + S[k("deleted")])
            S[k("deleted")] = []
            st.rerun()
        return

    # ------------------------------------------------ nút nhanh (R16)
    st.markdown("**Cách tách nhanh**")
    c1, c2, c3, c4 = st.columns([1.1, 1.6, 2.2, 1.1])
    with c1:
        if st.button("Tách từng trang một", key=k("all")):
            S[k("brk")] = sp.breaks_all(n)
        if st.button("Gộp thành 1 file", key=k("none")):
            S[k("brk")] = set()
    with c2:
        grp = st.number_input("Số trang mỗi nhóm", 1, max(1, n), 2, key=k("grp"))
        if st.button("Tách theo nhóm N trang", key=k("every")):
            S[k("brk")] = sp.breaks_every(int(grp), n)
    with c3:
        rng = st.text_input("Nhập dải trang", placeholder="1-3, 4, 5-8", key=k("rng"))
        if st.button("Áp dụng dải trang", key=k("applyr")):
            try:
                S[k("brk")] = sp.breaks_from_ranges(rng, n)
            except ValueError as e:
                st.error(str(e))
    with c4:
        st.caption("Bấm biểu tượng ✂ giữa hai trang để bật/tắt đường ngắt.")

    # ------------------------------------------------ gợi ý tự động (R20)
    with st.expander("Gợi ý tự động theo tiêu đề đầu trang (thử nghiệm)"):
        st.caption("Đọc phần đầu mỗi trang (OCR nếu là PDF scan, khoảng 2–3 giây/trang). Chỉ là gợi ý, bạn bấm sửa lại được.")
        need = [o for o in order if o not in S[k("tops")]]
        ca, cb = st.columns(2)
        run_a = ca.button("A. Mỗi biên bản một file", key=k("sugA"),
                          help="Ngắt trước mỗi trang có quốc hiệu/tiêu đề 'BIÊN BẢN…' ở đầu trang.")
        run_b = cb.button("B. Theo bộ hồ sơ lặp lại", key=k("sugB"),
                          help="Ngắt trước mỗi trang cùng loại biên bản với trang 1 (vd. mỗi lần gặp lại 'Biên bản kiểm tra').")
        if run_a or run_b:
            if need:
                bar = st.progress(0.0, text="Đang đọc đầu trang…")
                S[k("tops")].update(sp.read_page_tops(pdf_bytes, need, progress=lambda p, m: bar.progress(p, text=m)))
                bar.empty()
            tops = S[k("tops")]
            S[k("brk")] = sp.breaks_each_document(order, tops) if run_a else sp.breaks_repeating_set(order, tops)
            if not S[k("brk")]:
                st.info("Không tìm thấy điểm ngắt nào theo cách này.")
            else:
                st.rerun()

    brk: set[int] = {b for b in S[k("brk")] if b < n - 1}
    groups = sp.groups_from_breaks(brk, n)
    gid_of = {}
    for gi, (a, b) in enumerate(groups):
        for pos in range(a, b + 1):
            gid_of[pos] = gi

    # ------------------------------------------------ lưới ảnh thu nhỏ + đường ngắt (R15)
    # Mô phỏng như công cụ tách PDF trực quan: mỗi file là một dải nền màu liền nhau;
    # giữa hai trang là đường dọc - nét LIỀN đậm + nút ✂ tròn đặc = ĐANG CẮT, nét đứt nhạt = chưa cắt.
    st.markdown(f"**{n} trang → {len(groups)} file** · {len(brk)} điểm cắt. "
                "Bấm nút tròn giữa hai trang để cắt / bỏ cắt.")
    thumbs = S[k("thumbs")]
    rot = S[k("rot")]
    for start in range(0, n, PER_ROW):
        cols = st.columns([5, 1.2] * PER_ROW)
        with cols[0]:
            st.markdown('<span class="splitrow"></span>', unsafe_allow_html=True)
        for j in range(PER_ROW):
            pos = start + j
            if pos >= n:
                break
            gi = gid_of[pos]
            col = pv.group_color(gi)
            with cols[2 * j]:
                st.markdown(f'<span class="sp sp-g{gi % 8}"></span>', unsafe_allow_html=True)
                first = pos == groups[gi][0]
                st.markdown(pv.color_bar(col, f"File {gi + 1}" if first else "·"), unsafe_allow_html=True)
                st.image(pv.rotated_png(thumbs[order[pos]], rot.get(order[pos], 0)), width="stretch")
                st.caption(f"Trang {pos + 1}" + (f" (gốc {order[pos] + 1})" if order[pos] != pos else ""))
            if pos < n - 1:
                on = pos in brk
                with cols[2 * j + 1]:
                    st.markdown('<span class="sep sep-on"></span>' if on
                                else f'<span class="sep sep-off sp-g{gi % 8}"></span>', unsafe_allow_html=True)
                    if st.button("✂", key=k(f"b{pos}"), type="primary" if on else "secondary",
                                 help="Đang CẮT ở đây – bấm để bỏ" if on else "Bấm để cắt ở đây"):
                        S[k("brk")] = (brk - {pos}) if on else (brk | {pos})
                        st.rerun()

    # ------------------------------------------------ mô phỏng kết quả sau khi cắt
    with st.expander(f"Mô phỏng kết quả sau khi cắt ({len(groups)} file)", expanded=True):
        for gi, (ga, gb) in enumerate(groups):
            col = pv.group_color(gi)
            st.markdown(f'<div class="simhead" style="border-left-color:{col}"><b>File {gi + 1}</b> · '
                        f'{gb - ga + 1} trang (trang {ga + 1}' + (f"–{gb + 1}" if gb > ga else "") + ")</div>",
                        unsafe_allow_html=True)
            show = list(range(ga, min(gb, ga + 11) + 1))
            sc = st.columns(12)
            for ci, pos in enumerate(show):
                sc[ci].image(pv.rotated_png(thumbs[order[pos]], rot.get(order[pos], 0)), width="stretch")
            if gb - ga + 1 > 12:
                sc[11].caption(f"… +{gb - ga - 10}")

    # ------------------------------------------------ xoay / xóa / sắp xếp (R18)
    with st.expander("Xoay, xóa, sắp xếp lại trang"):
        pos = st.number_input("Trang số (theo thứ tự hiện tại)", 1, n, 1, key=k("selpos")) - 1
        orig = order[pos]
        b1, b2, b3, b4, b5 = st.columns(5)
        if b1.button("⟲ Xoay trái", key=k("rl")):
            rot[orig] = (rot.get(orig, 0) - 90) % 360
            st.rerun()
        if b2.button("⟳ Xoay phải", key=k("rr")):
            rot[orig] = (rot.get(orig, 0) + 90) % 360
            st.rerun()
        if b3.button("◀ Dời lên trước", key=k("mv_l"), disabled=pos == 0):
            order[pos - 1], order[pos] = order[pos], order[pos - 1]
            S[k("brk")] = set()  # đổi thứ tự thì đường ngắt cũ không còn đúng
            st.rerun()
        if b4.button("▶ Dời ra sau", key=k("mv_r"), disabled=pos == n - 1):
            order[pos + 1], order[pos] = order[pos], order[pos + 1]
            S[k("brk")] = set()
            st.rerun()
        if b5.button("🗑 Xóa trang", key=k("del"), disabled=n == 1):
            S[k("deleted")].append(order.pop(pos))
            S[k("brk")] = set()
            st.rerun()
        if S[k("deleted")]:
            st.caption(f"Đã xóa {len(S[k('deleted')])} trang (gốc: {', '.join(str(x + 1) for x in sorted(S[k('deleted')]))}).")
            if st.button("Khôi phục tất cả trang đã xóa", key=k("restore")):
                S[k("order")][:] = sorted(order + S[k("deleted")])
                S[k("deleted")] = []
                S[k("brk")] = set()
                st.rerun()

    # ------------------------------------------------ xem trước danh sách file (R17) + chọn nhóm cần tải (R23)
    st.subheader("Danh sách file sẽ tạo")
    sig = hashlib.md5(repr((groups, order)).encode()).hexdigest()[:8]
    df = pd.DataFrame({
        "Tải": [True] * len(groups),
        "Tên file": [f"{base}_{gi + 1:02d}" for gi in range(len(groups))],
        "Số trang": [b - a + 1 for a, b in groups],
        "Trang (thứ tự hiện tại)": [f"{a + 1}" if a == b else f"{a + 1}–{b + 1}" for a, b in groups],
    })
    edited = st.data_editor(df, key=k(f"ed{sig}"), hide_index=True, width="stretch",
                            disabled=["Số trang", "Trang (thứ tự hiện tại)"],
                            column_config={"Tải": st.column_config.CheckboxColumn(
                                "Tải", help="Bỏ tích những file không cần: sẽ không được tạo, không có trong file tải về.",
                                default=True)})
    flags = [bool(x) for x in edited["Tải"]]
    chosen = [gi for gi, on in enumerate(flags) if on]
    st.caption("Bỏ tích cột 'Tải' ở file không cần. Bấm đúp vào cột 'Tên file' để đổi tên. "
               "Đuôi .pdf tự thêm; tên trùng tự thêm số.")
    sel_sig = sig + "".join("1" if f else "0" for f in flags)

    if not chosen:
        st.warning("Chưa tích file nào để tải.")
    elif st.button(f"✂ Tách ({len(chosen)}/{len(groups)} PDF đã tích) → tạo file để tải", type="primary", key=k("make")):
        used: set[str] = set()
        names = [sp.safe_name(str(x), used) for x in edited["Tên file"]]
        parts = sp.split_pdf(pdf_bytes, order, rot, [groups[gi] for gi in chosen])
        files = [(names[gi], data) for gi, (data, _) in zip(chosen, parts)]
        if len(files) == 1:
            S[k("out")] = (files[0][0], files[0][1], "application/pdf", sel_sig)
        else:
            S[k("out")] = (f"{base}_tach.zip", sp.make_zip(files), "application/zip", sel_sig)
        if on_log:
            on_log("split_pdf", len(order), len(files))
    out = S.get(k("out"))
    if out and out[3] != sel_sig:
        st.caption("Bạn vừa đổi cách tách hoặc đổi ô tích 'Tải' – bấm 'Tạo file để tải' lại.")
    elif out:
        st.download_button(f"⬇️ Tải {out[0]} ({len(out[1]) / 1e6:.1f} MB)", out[1], file_name=out[0], mime=out[2],
                           key=k("dl"))

    # ------------------------------------------------ chuyển các nhóm đã tích sang Word / Excel (R24)
    st.subheader("Chuyển các file đã tích sang Word / Excel")
    pages = sp.selected_pages(groups, order, flags)
    if pages:
        txt = sp.pages_to_range_text(pages)
        st.caption(f"Sẽ chuyển {len(pages)} trang gốc: {txt}")
        if st.button("➡ Dùng các trang này để chuyển Word / Excel", key=k("toconv")):
            S[f"pages_text:{file_name}"] = txt
            st.success("Đã điền ô 'Trang cần chuyển'. Bấm sang thẻ **📊 PDF → Excel / Word** rồi bấm "
                       "'Chuyển đổi và xem trước'.")
    else:
        st.caption("Tích ít nhất một file ở bảng trên.")
