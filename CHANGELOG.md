# CHANGELOG

## 2026-11-18 – Tăng tốc PDF → Excel/Word (không đổi kết quả)
**Sửa:** `pdf_to_excel.py`: `convert_pdf` xử lý nhiều trang song song (tối đa 4 trang cùng lúc, theo số nhân CPU), dựng ảnh trang ở luồng chính vì PyMuPDF không an toàn đa luồng; thanh tiến trình ghi "Xong trang n – x/y". `process_scan_page` nhận thêm ảnh dựng sẵn.
**Đo thử:** file mẫu 8 trang scan, máy 2 nhân: 146 giây → 108 giây (-26%); nội dung 8/8 trang giống hệt bản trước. Máy nhiều nhân hơn sẽ nhanh hơn nữa.
**Đã thử và KHÔNG áp dụng:** thay khử nhiễu fastNlMeans bằng medianBlur (-3 giây/trang) và dò độ nghiêng trên ảnh thu nhỏ (-4 giây/trang): nhanh hơn nhưng làm đổi nội dung đọc được ở 6–7/8 trang, chưa có căn cứ là tốt hơn hay kém hơn.
**Ảnh hưởng:** chỉ tốc độ; hồi quy đạt toàn bộ.

## 2026-11-18 – Chọn file cần tải, chuyển Word/Excel theo nhóm (R23, R24)
**Thêm:** `ui_split.py`: cột tích "Tải" trong bảng "Danh sách file sẽ tạo" (bỏ tích thì file không được tạo và không có trong .zip; nút ghi "Tách (x/y PDF đã tích)"); mục "Chuyển các file đã tích sang Word / Excel" điền sẵn ô "Trang cần chuyển". `pdf_splitter.py`: `selected_pages`, `pages_to_range_text`. `app.py`: ô "Trang cần chuyển" có khóa riêng theo tên file để được điền sẵn. `tests`: thêm `test_select_groups_and_range_text`.
**Ảnh hưởng:** logic tách và các chức năng cũ không đổi; hồi quy đạt toàn bộ bài hiện có (bài dùng file mẫu thiếu thì bỏ qua như trước).

## 2026-11-16 (đêm) – Lưới tách trang mô phỏng như công cụ mẫu (R15)
**Thêm/sửa:** `ui_split.py` + `style.py`: mỗi file là một dải nền màu liền nhau (cùng màu với thanh "File n"); giữa hai trang là đường dọc – nét liền đậm kèm nút tròn ✂ đặc = đang cắt, nét đứt nhạt kèm nút tròn rỗng = chưa cắt; dòng tóm tắt "N trang → M file · K điểm cắt"; khối "Mô phỏng kết quả sau khi cắt" liệt kê từng file với ảnh thu nhỏ các trang; nút cuối ghi "Tách (M PDF) → tạo file để tải".
**Ảnh hưởng:** logic tách không đổi; chỉ đổi cách hiển thị.

## 2026-11-16 (đêm) – Giao diện nổi bật hơn
**Thêm:** `style.py` (biểu ngữ xanh đậm có đường cam, thẻ tab lớn đổi màu khi chọn, khung tải file nét đứt xanh, nút chính màu cam, nút tải màu xanh lá, hộp thông báo có màu theo loại); `.streamlit/config.toml` đặt bảng màu (chữ xanh đen, nền xanh nhạt, nút cam).
**Ảnh hưởng:** chỉ đổi giao diện, không đổi chức năng.

## 2026-11-16 (đêm) – Giai đoạn 4: Word/Excel → PDF (R12, R13, R3)
**Thêm:** `office_to_pdf.py` (LibreOffice headless, hồ sơ riêng mỗi lần chạy nên nhiều người dùng cùng lúc không tranh khóa; kiểm tra font nhúng và đối chiếu chữ có dấu với file gốc), `ui_office.py` (xem trước ảnh trang, báo font, tải PDF); `app.py` chia hai tab lớn: "PDF → Word / Excel, tách trang" và "Word / Excel → PDF"; `packages.txt` thêm fonts-liberation, fonts-dejavu, fonts-crosextra-carlito/caladea; README thêm bước cài LibreOffice.
**Sửa:** PDF tạo từ Word có font thiếu dấu Việt (Cambria) làm pdfplumber đọc ra `(cid:N)` → đọc lại vùng đó bằng PyMuPDF.
**Hạn chế:** font gốc thiếu glyph tiếng Việt (Cambria) bị thay bằng DejaVu, app cảnh báo; chữ thay thế làm lớp chữ bị tách rời khi đọc lại.
**Ảnh hưởng:** hồi quy 12/12 đạt (thêm 2 bài); các chức năng cũ không đổi.
**Sửa khi đưa lên Streamlit Cloud:** `requirements.txt` thiếu `python-docx` và `pillow` → thêm (lỗi ModuleNotFoundError khi chạy online).

## 2026-11-16 (tối) – Giai đoạn 3: PDF → Word + R22 (dấu, chữ ký là ảnh)
**Thêm:** `pdf_to_word.py` (đoạn, tab nhiều cột, căn giữa, bảng có ô gộp và độ rộng cột, ảnh dấu/chữ ký nổi đúng vị trí); `mark_utils.py` (tách dấu đỏ, chữ ký xanh/đen thành PNG nền trong suốt); `app.py`: tab "PDF → Excel / Word", xem trước ảnh dấu/chữ ký có ô "Giữ", nút "Tạo file Word".
**Sửa:** xóa mực màu mạnh hơn trước OCR; lọc từ rác do nét ký bị đọc nhầm; Excel cũng chèn ảnh dấu/chữ ký; 3 bài kiểm tra mới (Word, Excel có ảnh, tách dấu).
**Cơ sở dữ liệu:** migration `pdf_tool_log_cho_phep_ghi_an_danh` (cho phép ghi nhật ký không cần đăng nhập; bảng chỉ cho người đăng nhập đọc).
**Ảnh hưởng:** hồi quy 10/10 đạt; PDF → Excel chỉ thêm ảnh, số liệu không đổi.

## 2026-11-16 (chiều) – Giai đoạn 1: tách / sắp xếp trang trực quan
**Thêm:** `pdf_splitter.py` (nhóm trang, tách, xoay, xóa, dời, zip, tên file an toàn), `ui_split.py`, `preview_utils.py`; `app.py` thành hai tab (Tách/sắp xếp trang; PDF → Excel). R20: gợi ý điểm ngắt theo tiêu đề đầu trang (A: mỗi biên bản một file; B: theo bộ hồ sơ lặp lại).
**Sửa trong lúc làm:** dòng chữ thường "Nhân viên Ban KTVTAT" bị nhận nhầm là tiêu đề "BIÊN BẢN" → chỉ xét từ viết hoa. Đổi `use_container_width` sang `width="stretch"`; yêu cầu `streamlit>=1.52`.
**Phát hiện:** file 16 trang mẫu gồm 4 bộ hồ sơ × 4 loại biên bản (1-4, 5-8, 9-12, 13-16); chế độ B tách đúng như vậy.
**Ảnh hưởng:** PDF → Excel không đổi, hồi quy 7/7 đạt.

## 2026-11-16 – Giai đoạn 2 (PDF → Excel) + lõi OCR của giai đoạn 5
**Thêm**
- `ocr_utils.py`: nhận biết PDF có lớp chữ / scan / hỗn hợp; dựng ảnh 300 DPI; khử nghiêng; loại dấu mộc màu; OCR Tesseract `vie+eng` (2 biến thể ảnh, chọn theo độ tin cậy).
- `pdf_to_excel.py`: dò bảng bằng đường kẻ, nhận ô gộp, OCR từng ô, cột số đọc bằng chế độ chỉ-chữ-số; PDF có lớp chữ dùng pdfplumber; xuất xlsx (số là số, ngày dd/mm/yyyy, giữ số 0 đầu, mỗi trang một sheet hoặc gộp, khổ in A4 vừa ngang).
- `app.py`: tải PDF, báo cách xử lý, chọn trang, xem trước và sửa tay trước khi tải.
- `validators.py`, `log_utils.py`, `tests/test_regression.py`, `SPEC.md`.
- `tessdata/` (model Tesseract "best" vie + eng, tải từ kho chính thức tesseract-ocr/tessdata_best), `fonts/` (DejaVu Sans).
**Sửa trong lúc làm:** ô bắt đầu bằng "=" bị Excel hiểu là công thức; cột STT không thành số khi có 1 ô OCR sai; khổ in tràn trang.
**Chưa hoạt động:** nhật ký Supabase – bảng `pdf_tool_log` hiện chỉ cho người đã đăng nhập ghi (RLS), chờ quyết định.
**Ảnh hưởng:** chưa có phần cũ nào bị ảnh hưởng (đây là phiên bản đầu).
