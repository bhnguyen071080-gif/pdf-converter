# Ứng dụng chuyển đổi PDF (Streamlit)

## A. Chạy thử trên máy Windows
1. Cài Python 3.12 từ https://www.python.org/downloads/ . Ở màn hình đầu tiên **tích ô "Add python.exe to PATH"** rồi bấm **Install Now**.
2. Cài Tesseract (miễn phí): vào https://github.com/UB-Mannheim/tesseract/wiki , tải bản cài Windows 64-bit mới nhất, chạy, để nguyên đường dẫn mặc định `C:\Program Files\Tesseract-OCR`.
3. Cài LibreOffice (miễn phí, cần cho Word/Excel → PDF): vào https://www.libreoffice.org/download/download-libreoffice/ , tải bản Windows, chạy, để nguyên đường dẫn mặc định `C:\Program Files\LibreOffice`. Font Times New Roman/Arial có sẵn trên Windows nên PDF ra đúng font.
4. Giải nén thư mục dự án (ví dụ `D:\pdf_converter`). Trong File Explorer, bấm vào thanh địa chỉ, gõ `cmd`, nhấn Enter.
5. Trong cửa sổ đen gõ lần lượt:
   - `python -m venv .venv` rồi Enter
   - `.venv\Scripts\activate` rồi Enter
   - `pip install -r requirements.txt` rồi Enter (chờ vài phút)
   - `streamlit run app.py` rồi Enter. Trình duyệt tự mở trang ứng dụng.
5. Lần sau chỉ cần làm bước 3 rồi gõ `.venv\Scripts\activate` và `streamlit run app.py`.

Model tiếng Việt chất lượng cao nằm sẵn trong thư mục `tessdata/`, ứng dụng tự dùng, không cần cài thêm ngôn ngữ.

## B. Đưa lên mạng miễn phí (Streamlit Community Cloud)
1. Vào https://github.com , bấm **New** (tạo repository mới), đặt tên `pdf-converter`, chọn **Public**, bấm **Create repository**.
2. Bấm **uploading an existing file**, kéo toàn bộ nội dung thư mục dự án vào (kể cả `tessdata`, `fonts`, `packages.txt`), bấm **Commit changes**.
3. Vào https://share.streamlit.io , đăng nhập bằng GitHub, bấm **Create app** → chọn repository `pdf-converter`, nhánh `main`, tệp chính `app.py` → **Deploy**.
4. Lưu ý: app công khai thì ai có đường dẫn đều dùng được; không đưa tài liệu nhạy cảm lên app công khai.

## C. Chạy kiểm tra
`python tests/test_regression.py`
