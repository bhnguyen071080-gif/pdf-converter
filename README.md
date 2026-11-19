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

## D. Dịch tài liệu (tab "🌐 Dịch tài liệu")
1. Chọn file PDF ở tab "📄 PDF → Word / Excel, tách trang", rồi bấm thẻ **🌐 Dịch tài liệu**.
2. Chọn "Ngôn ngữ của tài liệu (gốc)" và "Dịch sang". Muốn dịch một vài trang thì gõ vào ô "Trang cần dịch" (vd. 1-3, 5).
3. (Tùy chọn) Nhập email của bạn để MyMemory nâng hạn mức từ 5.000 lên 50.000 ký tự/ngày.
4. (Tùy chọn) Mở "Từ điển thuật ngữ" để thêm thuật ngữ riêng, mỗi dòng `gốc = dịch`.
5. Mở "Dịch thử một đoạn" và bấm **Dịch thử** để chắc dịch vụ đang chạy.
6. Tích ô **"Tôi đồng ý gửi nội dung văn bản…"** (bắt buộc) rồi bấm **Dịch tài liệu**.
7. Xem bảng Gốc / Bản dịch: sửa trực tiếp. Muốn dịch lại dòng nào thì sửa ô "Gốc", tích "Dịch lại", bấm nút "Dịch lại … dòng".
8. Bấm **Tạo file Word** hoặc **Tạo file PDF và xem trước**, rồi bấm nút tải.
Lưu ý: văn bản được gửi ra dịch vụ miễn phí trên Internet nên không dùng cho tài liệu mật. Chữ nằm trong hình vẽ không được dịch (giữ nguyên hình).
