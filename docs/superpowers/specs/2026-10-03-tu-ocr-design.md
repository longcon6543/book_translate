# Phase C — Tự OCR sách scan chưa có lớp chữ

**Spec mẹ:** [2026-09-21-pdf-song-ngu-design.md](2026-09-21-pdf-song-ngu-design.md).
**Liên quan:** [2026-09-24-doc-sach-scan-design.md](2026-09-24-doc-sach-scan-design.md)
(Phase 8B — luồng đọc trang scan mà Phase C dùng lại nguyên vẹn).

## 1. Vấn đề

Sách scan không có lớp chữ OCR thì `init` từ chối: *"…là sách scan chưa có
lớp chữ OCR, mà tool chưa tự chạy OCR."* Người dùng muốn đưa tool cho người
khác dùng, nên tool phải tự OCR được mà không bắt cài chương trình ngoài
(tesseract cần brew/apt/bộ cài riêng, `pip` không cài được).

## 2. Mục tiêu

`init` một PDF scan **không có lớp chữ nào** ra khối chữ dịch được, chất
lượng ngang lớp OCR có sẵn của sách thật — cài hoàn toàn bằng
`pip install -r requirements.txt`, chạy offline trên CPU.

## 3. Phạm vi

**Trong phạm vi:** bộ đọc OCR, nối vào `init` cho sách scan không có lớp chữ,
thông báo thiếu thư viện, `requirements.txt`.

**Ngoài phạm vi (người dùng chọn):**
- OCR lại sách đã có lớp chữ (sửa số trang OCR đọc sai kiểu "5a8").
- OCR từng trang lẻ thiếu chữ trong sách đã có lớp chữ (bìa harmonics).
- Lưu đệm kết quả OCR giữa các lần `init`.

**Bất biến:** sách có lớp chữ (harmonics) và text-PDF (astrology) cho kết quả
ingest giống hệt từng byte — chúng không bao giờ chạm tới OCR.

## 4. Đo trước khi thiết kế

RapidOCR 1.4.4 (`rapidocr-onnxruntime`, Apache-2.0; `onnxruntime` 1.30, MIT),
cài vào môi trường tạm: ~350MB kể cả OpenCV và numpy. Đo trên 10 trang
harmonics (thân bài, trang nghiêng, mục lục, chỉ mục, hình, bảng in máy tính),
so với lớp OCR có sẵn của sách — tỉ lệ từ của lớp gốc mà RapidOCR cũng đọc ra:

| | 150 dpi | 200 dpi |
|---|---|---|
| Khớp từ cả 10 trang | 85,9% | **95,9%** |
| Trang thân bài (13, 44, 45, 100, 200) | 81–93% | **98–100%** |
| Bảng in máy tính (63) | 65% | 86% |
| Thời gian | 2,6 s/trang | **3,0 s/trang** |

Lớp gốc cũng có lỗi, nên "khớp" là cận dưới của chất lượng thật.

Cỡ chữ: RapidOCR chỉ trả khung 4 góc và chữ của từng dòng. Trên 208 cặp dòng
khớp với lớp gốc: **cỡ chữ ≈ 0,80 × chiều cao khung** (p10 0,71, p90 0,93);
tâm dọc lệch trung vị 2pt.

## 5. Quyết định

**C1 — OCR khi cả cuốn không có lớp chữ.** `load` chạy luồng hiện có trước.
Chỉ khi luồng đó không ra đoạn nào **và** sách có trang scan
(`_la_trang_scan`) thì mới chạy lượt OCR trên các trang scan. Sách có lớp chữ
không bao giờ tới nhánh này — bất biến mục 3 giữ bằng cấu trúc, không bằng
ngưỡng. PDF không có lớp chữ lẫn trang scan (trang trắng) vẫn bị từ chối, với
thông báo mới không còn nói "chưa tự chạy OCR".

**C2 — Bộ đọc OCR `ingest/ocr.py`.**
- Chụp trang **200 dpi**, RGB, đưa vào RapidOCR.
- Mỗi kết quả `(4 góc, chữ, điểm)` thành một `pdf_layout.Line`: khung là
  min/max của 4 góc đổi về point (× 72/200); `text` là chữ đã `strip`;
  `html` là chữ đã escape; `size = 0,80 × chiều cao khung`.
- Bỏ dòng chữ rỗng; bỏ dòng có cạnh trên nghiêng ≥ 10° (cùng luật E1).
- Phần chuyển kết quả → `Line` là hàm thuần, tách khỏi phần gọi mô hình để
  test không cần mô hình.

**C3 — Dùng lại nguyên luồng trang scan của 8B.** Dòng OCR đi qua đúng các
bước trang scan đang có: dò vùng hình (E5/E6), dò cột, `tim_khe_hai_cot`,
ghép mảnh, `noi_so_trang`, gom đoạn theo vùng, `classify`, `mark_running`,
`link_continuations`. Thân xử lý một trang được tách thành một hàm dùng chung
cho cả hai lượt, để hai lượt không thể lệch nhau.

**C4 — Nạp mô hình lười, một lần.** `import rapidocr_onnxruntime` và dựng
`RapidOCR()` chỉ khi C1 quyết định OCR; dùng một engine cho cả cuốn. Thiếu thư
viện thì `UnsupportedSource` với thông báo: sách cần OCR, chạy
`pip install -r requirements.txt`.

**C5 — Tiến độ.** OCR ~3 s/trang (cuốn 480 trang ~25 phút): in
`OCR trang i/n` ra stderr mỗi 10 trang và ở trang cuối, để `init` không im
lặng hàng chục phút.

**C6 — `requirements.txt` thêm `rapidocr-onnxruntime>=1.4`** (người dùng
chọn có sẵn, không tuỳ chọn). EPUB và text-PDF không nạp nó (C4).

## 6. Kiến trúc

```
ingest/ocr.py                      (mới)
    DPI_OCR = 200
    TI_LE_CO_CHU = 0.80
    dong_tu_ket_qua(ket_qua, page_no, ti_le) -> list[Line]   # thuần
    tao_engine() -> engine          # import lười; thiếu thư viện -> UnsupportedSource
    doc_trang_ocr(page, page_no, engine) -> list[Line]

ingest/pdf_text.py
    _xu_ly_trang_scan(...)          # thân trang scan hiện có, tách ra dùng chung
    load(): lượt 1 như cũ; không ra đoạn + có trang scan -> lượt 2 OCR
requirements.txt: + rapidocr-onnxruntime>=1.4
```

`ingest/ocr.py` được phép import pymupdf (tầng ingest). Luật tầng cũ giữ
nguyên cho các module thuần.

## 7. Test

Không test nào gọi mạng. Test hiện có xanh; vân tay golden giữ nguyên.

- `dong_tu_ket_qua`: khung đổi đúng tỉ lệ; cỡ = 0,80 × cao; chữ rỗng bị bỏ;
  dòng nghiêng 15° bị bỏ, 5° được giữ; chữ có `<`/`&` được escape trong html.
- `load` với engine giả (monkeypatch `ocr.tao_engine`):
  - PDF toàn ảnh, không lớp chữ → ra khối từ chữ engine giả trả về;
  - sách có lớp chữ → engine **không bao giờ** được dựng;
  - trang hình không ảnh hưởng: vùng hình vẫn được dò trên trang OCR.
- PDF trang trắng (không ảnh, không chữ) vẫn bị từ chối, thông báo mới.
- Thiếu thư viện (monkeypatch import lỗi) → thông báo có `pip install -r requirements.txt`.
- Một test chạy RapidOCR thật trên trang dựng sẵn (chữ in to, rõ), đọc ra
  ≥ 90% số từ; `pytest.importorskip` khi máy chưa cài.

## 8. Nghiệm thu

1. Dựng `harmonics-anh-1-40.pdf`: trang 1–40 của harmonics, mỗi trang chỉ còn
   ảnh scan gốc (không lớp chữ). `init` vào thư mục tạm.
2. So với `projects/harmonics-8b` cùng trang:

| Chỉ số | Ngưỡng |
|---|---|
| Khớp từ (từ của 8B mà bản OCR cũng có), trang thân bài 13, 20, 25, 35 | **≥ 95%** |
| Tổng ký tự nguồn trang 1–40 | lệch **≤ ±10%** |
| Trang có vùng hình | cùng tập trang ± 2 |
| Thời gian OCR | **≤ 4 s/trang** |

3. `init` lại harmonics (bản có lớp chữ) và astrology vào thư mục tạm: khối và
   `vung_hinh` **giống hệt** project hiện có.

## 9. Rủi ro

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Cài nặng (~350MB) | người khác cài lâu | Chấp nhận — người dùng chọn có sẵn; ghi rõ trong README khi đóng gói |
| OCR chậm trên máy yếu | > 4 s/trang | In tiến độ (C5); lưu đệm OCR để dành cho sau |
| Không có đậm/nghiêng | tiêu đề không đậm | `classify` vẫn nhận tiêu đề theo cỡ chữ; chấp nhận |
| Mô hình tải thêm lúc chạy lần đầu | init cần mạng | Đã kiểm: wheel RapidOCR 1.4.4 mang sẵn 3 mô hình (det, rec, cls — 15MB); chạy offline |
