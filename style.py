"""Giao diện: màu tương phản, tiêu đề nổi bật, thẻ, nút lớn (chỉ CSS, miễn phí)."""
from __future__ import annotations

import streamlit as st

NAVY = "#0B2545"
BLUE = "#1363DF"
ORANGE = "#E8590C"
GREEN = "#12805C"

CSS = f"""
<style>
/* nền và chữ */
.stApp {{ background: linear-gradient(180deg, #EAF1FB 0%, #F6F9FD 320px); }}
.block-container {{ padding-top: 4rem; max-width: 1200px; }}
h1, h2, h3 {{ color: {NAVY}; }}
h3 {{ border-left: 6px solid {ORANGE}; padding-left: .6rem; }}

/* biểu ngữ đầu trang */
.hero {{ background: linear-gradient(120deg, {NAVY} 0%, #134A9C 60%, {BLUE} 100%);
  color: #fff; padding: 1.3rem 1.6rem; border-radius: 16px; margin-bottom: 1rem;
  box-shadow: 0 6px 18px rgba(11,37,69,.25); border-bottom: 5px solid {ORANGE}; }}
.hero h1 {{ color: #fff !important; margin: 0; font-size: 2rem; padding: 0; }}
.hero p {{ color: #CFE0FA; margin: .25rem 0 .7rem; font-size: 1rem; }}
.chip {{ display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.35);
  color: #fff; padding: .15rem .7rem; border-radius: 999px; margin: 0 .35rem .3rem 0; font-size: .85rem; }}

/* thẻ tab lớn */
[role="tablist"] {{ gap: .4rem; border-bottom: 3px solid {ORANGE}; }}
[data-testid="stTab"] {{ background: #DCE7F7; color: {NAVY}; border-radius: 10px 10px 0 0; padding: .55rem 1.2rem;
  height: auto; }}
[data-testid="stTab"] p {{ font-weight: 700; font-size: 1rem; color: {NAVY}; }}
[data-testid="stTab"]:hover {{ background: #BFD3F0; }}
[data-testid="stTab"][aria-selected="true"] {{ background: {NAVY}; }}
[data-testid="stTab"][aria-selected="true"] p {{ color: #fff; }}
[data-baseweb="tab-highlight"] {{ display: none; }}

/* khung tải file */
[data-testid="stFileUploader"] section {{ background: #fff; border: 2px dashed {BLUE};
  border-radius: 14px; padding: 1.1rem; }}
[data-testid="stFileUploader"] section:hover {{ background: #EEF5FF; border-color: {ORANGE}; }}

/* nút */
.stButton > button {{ border-radius: 10px; font-weight: 600; border: 2px solid {NAVY}; color: {NAVY};
  background: #fff; transition: all .15s; }}
.stButton > button:hover {{ background: {NAVY}; color: #fff; transform: translateY(-1px); }}
.stButton > button[kind="primary"] {{ background: {ORANGE}; border-color: {ORANGE}; color: #fff;
  box-shadow: 0 3px 10px rgba(232,89,12,.35); }}
.stButton > button[kind="primary"]:hover {{ background: #C94A06; border-color: #C94A06; }}
[data-testid="stDownloadButton"] button {{ background: {GREEN}; border: 2px solid {GREEN}; color: #fff;
  border-radius: 10px; font-weight: 700; box-shadow: 0 3px 10px rgba(18,128,92,.3); }}
[data-testid="stDownloadButton"] button:hover {{ background: #0D6548; border-color: #0D6548; color: #fff; }}

/* hộp thông báo */
[data-testid="stAlertContainer"] {{ border-radius: 12px; border-left: 6px solid {BLUE}; background: #DCEBFF; color: {NAVY}; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{ border-left-color: {GREEN}; background: #D3F2E3; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{ border-left-color: #E0A100; background: #FFF1C9; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{ border-left-color: #C92A2A; background: #FFE0E0; }}

/* khối mở rộng và bảng */
[data-testid="stExpander"] {{ background: #fff; border: 1px solid #C5D5EC; border-radius: 12px; }}
[data-testid="stExpander"] summary {{ font-weight: 600; color: {NAVY}; }}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border: 1px solid #C5D5EC; border-radius: 10px; }}
[data-testid="stImage"] img {{ border: 1px solid #B7C8E2; border-radius: 6px; box-shadow: 0 2px 6px rgba(11,37,69,.12); }}
[data-testid="stProgress"] > div > div > div {{ background-color: {ORANGE}; }}
hr {{ border-color: #C5D5EC; }}
/* ===== lưới tách trang mô phỏng ===== */
[data-testid="stHorizontalBlock"]:has(.splitrow) {{ gap: 0 !important; align-items: stretch !important; margin-bottom: 1.2rem; }}
[data-testid="stColumn"]:has(.sp) {{ padding: .6rem .5rem .3rem; }}
[data-testid="stColumn"]:has(.sp-g0) {{ background: #D6E6FF; }}
[data-testid="stColumn"]:has(.sp-g1) {{ background: #D5F2E2; }}
[data-testid="stColumn"]:has(.sp-g2) {{ background: #FFE9C2; }}
[data-testid="stColumn"]:has(.sp-g3) {{ background: #EBDDFA; }}
[data-testid="stColumn"]:has(.sp-g4) {{ background: #FFD9D9; }}
[data-testid="stColumn"]:has(.sp-g5) {{ background: #CFF1F7; }}
[data-testid="stColumn"]:has(.sp-g6) {{ background: #FAD7E8; }}
[data-testid="stColumn"]:has(.sp-g7) {{ background: #E6F3C8; }}
[data-testid="stElementContainer"]:has(.sp, .sep, .splitrow) {{ display: none; }}
[data-testid="stColumn"]:has(.sep) {{ display: flex; align-items: center; justify-content: center;
  background-repeat: no-repeat; background-position: center; padding: 0 !important; }}
[data-testid="stColumn"]:has(.sep) > div {{ width: auto !important; justify-content: center; align-items: center; }}
[data-testid="stColumn"]:has(.sep-on) {{ background-image: linear-gradient(to right, {NAVY}, {NAVY});
  background-size: 4px 100%; background-color: transparent !important; }}
[data-testid="stColumn"]:has(.sep-off) {{ background-image: repeating-linear-gradient(to bottom, #6F8FC4 0 7px, transparent 7px 14px);
  background-size: 2px 100%; }}
[data-testid="stColumn"]:has(.sep) button {{ width: 34px; height: 34px; min-height: 34px; padding: 0; border-radius: 50%;
  font-size: 1rem; line-height: 1; }}
[data-testid="stColumn"]:has(.sep-off) button {{ background: #fff; border: 2px solid #6F8FC4; color: #3C5A94; }}
[data-testid="stColumn"]:has(.sep-off) button:hover {{ background: {BLUE}; border-color: {BLUE}; color: #fff; }}
[data-testid="stColumn"]:has(.sep-on) button {{ background: {NAVY}; border: 2px solid {NAVY}; color: #fff;
  box-shadow: 0 0 0 4px rgba(11,37,69,.18); }}
[data-testid="stColumn"]:has(.sep-on) button:hover {{ background: {ORANGE}; border-color: {ORANGE}; }}
.simhead {{ border-left: 8px solid {BLUE}; background: #fff; padding: .25rem .7rem; margin: .5rem 0 .3rem; border-radius: 0 8px 8px 0; }}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def banner() -> None:
    st.markdown(
        """<div class="hero"><h1>📄 Công cụ PDF</h1>
        <p>Tách trang, chuyển đổi PDF ⇄ Word / Excel, OCR tiếng Việt – có xem trước trước khi tải</p>
        <span class="chip">✂ Tách trang trực quan</span><span class="chip">📊 PDF → Excel</span>
        <span class="chip">📝 PDF → Word</span><span class="chip">🖨 Word / Excel → PDF</span>
        <span class="chip">🔍 OCR vie + eng</span></div>""",
        unsafe_allow_html=True)
