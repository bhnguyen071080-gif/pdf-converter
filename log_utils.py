"""Nhật ký thao tác (R8): ghi vào bảng Supabase `pdf_tool_log`; lỗi mạng không làm hỏng ứng dụng.

Cấu hình trong .streamlit/secrets.toml (hoặc mục Secrets trên Streamlit Cloud):
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_KEY = "khóa anon/publishable"
"""
from __future__ import annotations

import json
import urllib.request

TABLE = "pdf_tool_log"


def write_log(url: str | None, key: str | None, file_name: str, kind: str, result: str,
              detail: dict | None = None, token: str | None = None) -> tuple[bool, str]:
    """Trả (đã ghi?, thông báo). Không ném lỗi ra ngoài."""
    if not url or not key:
        return False, "Chưa cấu hình Supabase (SUPABASE_URL / SUPABASE_KEY)"
    # Cột thật của bảng: action, file_name, page_count, status (user_id/created_at tự điền)
    row = {"action": kind, "file_name": file_name, "page_count": (detail or {}).get("pages"),
           "status": result}
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/{TABLE}", data=json.dumps(row).encode("utf-8"), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {token or key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 201, 204), f"HTTP {r.status}"
    except Exception as e:  # noqa: BLE001 - nhật ký không được làm hỏng thao tác chính
        return False, f"Không ghi được nhật ký: {e}"
