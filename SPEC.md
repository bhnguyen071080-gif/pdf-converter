# SPEC – Ứng dụng chuyển đổi file (Streamlit)

Nguồn chuẩn duy nhất. Trạng thái: Đạt / Chưa làm / Hỏng (cập nhật sau mỗi lần kiểm tra).

## Ràng buộc
| Mã | Yêu cầu | Trạng thái |
|---|---|---|
| R1 | Chỉ dùng công cụ miễn phí/mã nguồn mở | Đạt |
| R2 | Tiếng Việt Unicode đúng dấu ở mọi chiều chuyển đổi | Đạt (đã kiểm: trích lớp chữ, xuất xlsx); OCR còn lỗi dấu lẻ → sửa tay ở bước xem trước |
| R3 | PDF tạo ra nhúng font TTF tiếng Việt (DejaVu Sans/Noto Sans/Be Vietnam Pro) | Đạt cho Word/Excel → PDF (LibreOffice nhúng Liberation/DejaVu, app báo font đã nhúng chưa); PDF tách trang là bản sao, giữ nguyên font gốc |
| R4 | Phát hiện font cũ VnTime/VNI/TCVN3 và đổi sang Unicode | Chưa làm |
| R5 | OCR Tesseract `vie+eng`; tiền xử lý: xoay thẳng, khử nghiêng, đen trắng, 300 DPI | Đạt một phần (khử nghiêng nhỏ ±5°; chưa tự xoay trang ngược 90°/180°) |
| R6 | Luôn có bước "Xem trước kết quả" trước khi tải | Đạt (cho PDF→Excel) |
| R7 | Tự nhận biết PDF có lớp chữ hay PDF scan, và báo cho người dùng | Đạt |
| R8 | Nhật ký thao tác (tên file, thời gian, loại, kết quả) vào bảng Supabase `pdf_tool_log` | Đạt khi đã khai báo SUPABASE_URL và SUPABASE_KEY (khóa publishable); đã thử ghi bằng quyền ẩn danh |
| R9 | Chạy được trên Windows và triển khai Streamlit Community Cloud + GitHub | Online: Đạt (16/11, kho GitHub công khai `bhnguyen071080-gif/pdf-converter`, app Streamlit Cloud, khóa Supabase đặt trong Secrets). Windows: có hướng dẫn README, chưa thử trên máy thật |

## Chức năng
| Mã | Yêu cầu | Trạng thái |
|---|---|---|
| R10 | PDF → Excel: nhận diện bảng; chọn mỗi bảng/trang một sheet hoặc gộp | Đạt (mỗi trang một sheet hoặc gộp; chưa có "mỗi bảng một sheet") |
| R11 | PDF → Word (.docx): giữ bảng, ô gộp, canh lề, font Times New Roman | Đạt (thử nghiệm 4 trang mẫu: 4 trang Word) |
| R12 | Word → PDF (LibreOffice headless) | Đạt (.docx/.doc/.odt/.rtf; có xem trước; kiểm đủ dấu Việt) |
| R13 | Excel → PDF (LibreOffice headless) | Đạt (.xlsx/.xls/.ods/.csv; cột hẹp có thể hiện ### như Excel; chưa có tùy chọn vừa khổ giấy) |
| R14 | Giữ bố cục bảng, canh lề; số liệu là số; ngày dd/mm/yyyy | Đạt |
| R15 | Tách trang: ảnh thu nhỏ theo hàng, "đường ngắt" bật/tắt giữa hai trang, tô màu nhóm | Đạt (ảnh thu nhỏ theo hàng; dải nền màu từng file; đường cắt nét liền/nét đứt + nút tròn ✂; mô phỏng kết quả sau khi cắt) |
| R16 | Nút nhanh: tách từng trang / theo nhóm N trang / nhập dải trang (1-3, 4, 5-8) | Đạt (3 nút nhanh + gộp 1 file) |
| R17 | Xem trước danh sách file sẽ tạo (tên, số trang); nhiều file nén .zip; tên sửa được | Đạt (xem trước danh sách, sửa tên, tự thêm .pdf/chống trùng, nhiều file nén .zip) |
| R18 | Xoay trang, xóa trang, sắp xếp lại thứ tự trang | Đạt (xoay, xóa, khôi phục, dời trang; dời bằng nút, chưa kéo-thả) |
| R19 | Chuyển một phần: chọn trang/vùng sang Word hoặc Excel | Chọn trang sang Excel: Đạt; chọn trang sang Word: Đạt; chọn vùng: Chưa làm |

## Quy trình
Giai đoạn: 1 tách trang → 2 PDF→xlsx → 3 PDF→docx → 4 chiều ngược lại → 5 OCR và font.
Thứ tự thực tế: 2 (PDF scan → xlsx) → 1 (tách trang) → 3 (PDF → docx) → 4 (Word/Excel → PDF), xong 16/11; còn giai đoạn 5 (font cũ VnTime/VNI/TCVN3, tự xoay trang) và triển khai.

## Bổ sung từ ảnh người dùng gửi 16/11/2026 (giao diện tách trang – R15 đến R18, R20)
Giao diện mẫu: ảnh thu nhỏ các trang xếp theo hàng; giữa hai trang là biểu tượng kéo; đường liền xanh = có ngắt, đường nét đứt = không ngắt; mỗi nhóm giữa hai đường ngắt tô nền riêng; nút "Tách (5 PDF)" ghi số file sẽ tạo; có ô "Tách sau mỗi N trang"; có chế độ Trích trang; xoay, xóa trang; sắp xếp.
Cách làm trong Streamlit (miễn phí, không cần thành phần trả phí): cột ảnh thu nhỏ + nút bật/tắt ngắt giữa các cột; tô nền theo nhóm.
Nhu cầu thực tế từ ảnh: một file scan 16 trang gồm nhiều biên bản liền nhau, cần tách thành từng biên bản (ví dụ 5 file).
| Mã | Yêu cầu bổ sung | Trạng thái |
|---|---|---|
| R20 | Gợi ý điểm ngắt tự động: OCR phần đầu mỗi trang, nơi có tiêu đề "BIÊN BẢN…" hoặc mã mẫu "BM:…" thì đề xuất ngắt trước trang đó; người dùng bấm sửa lại | Đạt (thử nghiệm): 2 chế độ gợi ý – A mỗi biên bản một file, B theo bộ hồ sơ lặp lại |
| R21 | (chưa được đồng ý) Tên file khi tách gợi ý theo tiêu đề biên bản + ngày đọc được; người dùng sửa được | Đề xuất |
| R22 | Con dấu, chữ ký giữ nguyên dạng ảnh (không OCR) trong Word và Excel; xem trước, bỏ chọn được | Đạt thử nghiệm. Hạn chế: chữ ký dính sát chữ in (vd. "KTVTAT") có thể không tách được |
