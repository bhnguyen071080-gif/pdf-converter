"""Dịch văn bản bằng dịch vụ MIỄN PHÍ (không cần khóa/ tài khoản trả phí).

- MyMemory (api.mymemory.translated.net): giới hạn ~5.000 ký tự/ngày/IP; nhập email để lên ~50.000.
- Google (điểm cuối web translate.googleapis.com, không chính thức): dùng dự phòng khi MyMemory hết hạn mức.
Văn bản được cắt theo câu (<= 400 byte/đoạn cho MyMemory), có bộ nhớ đệm (cùng câu không gửi lại),
thay thuật ngữ chuyên ngành (glossary) trước khi gửi khi dịch sang tiếng Việt.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import glossary as gl

# mã -> (tên hiển thị, mã Tesseract OCR, font Đông Á cho Word)
LANGS = {
    "vi": ("Tiếng Việt", "vie+eng", "Times New Roman"),
    "en": ("Tiếng Anh", "eng", "Times New Roman"),
    "de": ("Tiếng Đức", "deu+eng", "Times New Roman"),
    "ja": ("Tiếng Nhật", "jpn", "MS Mincho"),
    "zh-CN": ("Tiếng Trung giản thể", "chi_sim", "SimSun"),
    "zh-TW": ("Tiếng Trung phồn thể", "chi_tra", "PMingLiU"),
}
CJK_LANGS = {"ja", "zh-CN", "zh-TW"}


class QuotaExceeded(Exception):
    """Hết hạn mức dịch miễn phí trong ngày."""


class EngineError(Exception):
    pass


@dataclass
class Stats:
    chars_sent: int = 0
    cached: int = 0
    engines: set = field(default_factory=set)
    fallback: bool = False
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------- HTTP (thay được khi kiểm thử)
def _http_get(url: str, params: dict):
    import requests
    r = requests.get(url, params=params, timeout=25, headers={"User-Agent": "Mozilla/5.0 pdf-converter"})
    if r.status_code in (429, 403):
        raise QuotaExceeded(f"HTTP {r.status_code}")
    r.raise_for_status()
    return r.json()


HTTP = _http_get  # kiểm thử gán hàm giả vào đây


def _mymemory(text: str, sl: str, tl: str, email: str) -> str:
    p = {"q": text, "langpair": f"{sl}|{tl}"}
    if email:
        p["de"] = email
    j = HTTP("https://api.mymemory.translated.net/get", p)
    out = (j.get("responseData") or {}).get("translatedText") or ""
    status = str(j.get("responseStatus", "200"))
    if j.get("quotaFinished") or "MYMEMORY WARNING" in out.upper() or status == "429":
        raise QuotaExceeded("MyMemory hết hạn mức")
    if status != "200" or not out:
        raise EngineError(f"MyMemory trả lỗi {status}: {out[:80]}")
    return out


def _google(text: str, sl: str, tl: str, email: str = "") -> str:
    j = HTTP("https://translate.googleapis.com/translate_a/single",
             {"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": text})
    try:
        return "".join(seg[0] for seg in j[0] if seg and seg[0])
    except Exception as e:  # cấu trúc trả về lạ
        raise EngineError(f"Google trả dữ liệu lạ: {e}")


# ---------------------------------------------------------------- tách đoạn
_SENT = re.compile(r"(?<=[.!?;:。！？；])\s+|(?<=[。！？；])")


def split_chunks(text: str, max_bytes: int = 400) -> list[str]:
    """Cắt văn bản thành các đoạn <= max_bytes (UTF-8), ưu tiên ngắt theo câu."""
    text = text.strip()
    if not text:
        return []
    out, cur = [], ""

    def push(s):
        nonlocal cur
        if cur and len((cur + " " + s).encode()) > max_bytes:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip() if cur else s

    for sent in [s for s in _SENT.split(text) if s and s.strip()]:
        if len(sent.encode()) <= max_bytes:
            push(sent)
            continue
        # câu quá dài: cắt theo từ, không có khoảng trắng (CJK) thì cắt theo ký tự
        words = sent.split(" ") if " " in sent else list(sent)
        sep = " " if " " in sent else ""
        piece = ""
        for w in words:
            if piece and len((piece + sep + w).encode()) > max_bytes:
                push(piece)
                piece = w
            else:
                piece = piece + sep + w if piece else w
        if piece:
            push(piece)
    if cur:
        out.append(cur)
    return out


def needs_translation(s: str) -> bool:
    """Chuỗi chỉ gồm số/ký hiệu thì giữ nguyên."""
    return any(c.isalpha() for c in s)


# ---------------------------------------------------------------- thuật ngữ
def parse_glossary(text: str) -> dict[str, str]:
    """Mỗi dòng: 'gốc = dịch'."""
    d = {}
    for line in (text or "").splitlines():
        if "=" in line:
            a, b = line.split("=", 1)
            if a.strip() and b.strip():
                d[a.strip()] = b.strip()
    return d


def apply_glossary(text: str, sl: str, tl: str, extra: dict[str, str] | None = None) -> str:
    terms = dict(extra or {})
    if tl == "vi":
        for k, v in gl.DEFAULT.get(sl, {}).items():
            terms.setdefault(k, v)
    if not terms:
        return text
    low = {k.lower(): v for k, v in terms.items()}
    alt = "|".join(re.escape(k) for k in sorted(terms, key=len, reverse=True))
    # một lượt duy nhất: phần đã thay không bị quét lại (tránh thay lồng nhau)
    return re.sub(rf"(?<![\w-])(?:{alt})(?![\w-])", lambda m: low[m.group(0).lower()], text, flags=re.I)


# ---------------------------------------------------------------- dịch
def _call(engine: str, text: str, sl: str, tl: str, email: str, st: Stats) -> str:
    order = {"mymemory": ["mymemory"], "google": ["google"], "auto": ["mymemory", "google"]}[engine]
    last = None
    for i, name in enumerate(order):
        fn = _mymemory if name == "mymemory" else _google
        for attempt in range(2):
            try:
                out = fn(text, sl, tl, email)
                st.engines.add(name)
                if i > 0:
                    st.fallback = True
                st.chars_sent += len(text)
                return out
            except QuotaExceeded as e:
                last = e
                break  # sang engine kế tiếp
            except Exception as e:
                last = e
                time.sleep(0.6 * (attempt + 1))
    if isinstance(last, QuotaExceeded):
        raise QuotaExceeded("Đã hết hạn mức dịch miễn phí hôm nay. Nhập email (tăng hạn mức) hoặc thử lại ngày mai.")
    raise EngineError(f"Không gọi được dịch vụ dịch: {last}")


def translate_strings(strings: list[str], sl: str, tl: str, engine: str = "auto", email: str = "",
                      extra_glossary: dict[str, str] | None = None, cache: dict | None = None,
                      progress=None, workers: int = 3) -> tuple[list[str], Stats]:
    """Dịch danh sách chuỗi, giữ thứ tự. Chuỗi không có chữ (số, ký hiệu) giữ nguyên."""
    cache = {} if cache is None else cache
    st = Stats()
    join = "" if tl in CJK_LANGS else " "
    jobs: dict[tuple, None] = {}
    plan = []  # mỗi chuỗi -> danh sách khóa chunk
    for s in strings:
        if not needs_translation(s) or sl == tl:
            plan.append(None)
            continue
        pre = apply_glossary(s, sl, tl, extra_glossary)
        keys = []
        for c in split_chunks(pre, 400 if engine != "google" else 1200):
            k = (sl, tl, c)
            keys.append(k)
            if k in cache:
                st.cached += 1
            else:
                jobs[k] = None
        plan.append(keys)
    todo = list(jobs)
    done = 0

    def work(k):
        out = _call(engine, k[2], sl, tl, email, st)
        cache[k] = out.strip()  # lưu ngay: nếu giữa chừng hết hạn mức thì lần sau không dịch lại phần đã xong
        return k, out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for k, out in pool.map(work, todo):
            cache[k] = out.strip()
            done += 1
            if progress:
                progress(done / max(1, len(todo)), f"Đã dịch {done}/{len(todo)} đoạn")
    res = [s if keys is None else join.join(cache[k] for k in keys) for s, keys in zip(strings, plan)]
    return res, st
