# Phase 6 — Chế độ `reflow`: dựng lại trang sạch

**Spec mẹ:** [2026-09-21-pdf-song-ngu-design.md](2026-09-21-pdf-song-ngu-design.md) mục 10, Phase 6.
Mọi quyết định D1–D10 của spec mẹ còn hiệu lực trừ chỗ spec này nói khác.

## 1. Vấn đề

Chế độ `overlay` xoá chữ gốc rồi đặt chữ Việt vào đúng khung cũ. Nó dựa trên
một giả định: chữ gốc là **đối tượng văn bản** nên xoá được. Với sách scan,
giả định đó sai — chữ là **pixel trong ảnh**, và `apply_redactions` không đụng
tới pixel.

Đo thật trên `projects/harmonics` (bản scan 484 trang, đã OCR sẵn), xuất 2 khổ
bằng `overlay`:

| Khổ | Mực nửa gốc | Mực nửa dịch | Chênh |
|---|---|---|---|
| 1 | 24,61% | 35,00% | +42% |
| 2 | 12,10% | 19,64% | +62% |

Nửa dịch nhiều mực hơn vì mang **hai lớp chữ chồng nhau**: chữ Việt in đè lên
chữ Anh vẫn còn nguyên trong ảnh. Trang không đọc được.

Không vá được bằng cách tô nền: chữ và hình minh hoạ nằm chung một ảnh phủ kín
trang, tô đè lên chữ thì mất luôn hình.

## 2. Mục tiêu

Thêm chế độ `reflow`: dựng trang **trắng sạch** mang chữ Việt ở đúng vị trí
khối gốc, không sao chép gì từ ảnh nguồn.

Thành công khi: `export --mode reflow` trên `astrology.pdf` trang 149–170 ra
khổ đôi đọc được, không pixel ảnh nào của trang gốc lọt sang nửa dịch, và
nửa dịch không đậm hơn nửa dịch của `overlay` trên cùng khổ (cùng chữ Việt,
chỉ bớt ảnh). Trên harmonics thì nửa dịch phải nhạt hơn nửa gốc — nơi
`overlay` đo được +42% và +62%.

## 3. Phạm vi

**Trong phạm vi:** bộ render `reflow`, tách phần dùng chung khỏi `pdf_overlay`,
nối `--mode reflow` vào `render/__init__.py`.

**Ngoài phạm vi:** lọc rác OCR. Đo được 1.086/4.120 đoạn (26,4% số đoạn, 1,9%
ký tự) của harmonics là mảnh vụn OCR kiểu `rd os oe`, `| (`, `v1`. Chúng sẽ
hiện thành vệt chữ vô nghĩa trên trang reflow. **Đây là việc của Phase 7**;
Phase 6 chỉ làm đúng bộ render như spec mẹ viết. Hệ quả được chấp nhận có ý
thức: `reflow` một mình chưa làm harmonics sạch.

**Ngoài phạm vi:** OCR. Cuốn harmonics đã được OCR sẵn (482/484 trang có lớp
chữ, 853.354 ký tự) nên Phase 6 kiểm chứng được mà không cần Phase 7.

## 4. Quyết định

**R1 — Giữ đúng vị trí từng khối, không chảy chữ tự do.**
Mỗi đoạn dịch nằm đúng chỗ đoạn gốc từng nằm. Đối chiếu trái–phải theo vị trí
là công dụng chính của khổ đôi; chảy chữ tự do thì mất nó. Đổi lại, chữ Việt
dài hơn nên vẫn phải co — dùng nguyên thang co của Phase 4.

**R2 — Vùng hình để trống đúng kích thước, không cắt ảnh dán sang.**
Trang dịch sạch tuyệt đối, không bao giờ lẫn chữ Anh. Hình vẫn xem được ở nửa
trái của khổ đôi nên không mất thông tin. Cắt vùng ảnh dán sang sẽ kéo theo cả
chữ Anh mà OCR không bắt được.

*Chừa chỗ cho hình là miễn phí:* nền trắng là mặc định, chỗ nào không có khối
chữ thì tự nó đã trống đúng kích thước. Không phải dò vùng ảnh, không phải đo
kích thước, không có ngưỡng nào để chỉnh.

**R3 — Khung có toạ độ âm thì KẸP vào trong trang, không loại bỏ.**
Đo thật: 53/4.120 khối (1,3%) của harmonics có góc trên-trái nằm phía trên mép
trang; astrology có 0 khối. `_khung_dung` hiện loại thẳng chúng. Trong `overlay`
điều đó vô hại vì ảnh nền vẫn hiện chữ ở chỗ đó; trong `reflow` trên nền trắng
thì 53 khối **biến mất hẳn** — mất nội dung im lặng.

**R4 — Tràn ở mức co nhỏ nhất thì vẽ chữ Anh gốc vào khung đó.**
Spec mẹ mục 6 bậc 7 nói "hết cách thì GIỮ". `overlay` giữ bằng cách không xoá
chữ gốc; `reflow` không có sẵn chữ gốc trên trang nhưng `src_html` luôn có
trong DB nên vẽ lại được. Vẫn gắn cờ `overflow`.

**R5 — Trang không có khối nào thì ra trang trắng.**
Khác `overlay`, vốn trả về bản sao nguyên vẹn để trang chưa dịch vẫn hiện bản
gốc. Với `reflow` thì trang trắng mới nhất quán với R2, và nửa trái vẫn hiện
bản gốc.

**R6 — Phân cấp tiêu đề không cần code mới.**
Spec mẹ nói `reflow` phải "phân cấp tiêu đề và chú thích". `src_html` đã mang
sẵn `<b>`/`<i>` và `layout.size` đã mang cỡ chữ gốc; hai thứ đó cộng lại chính
là phân cấp. Không thêm luật theo `kind`.

## 5. Kiến trúc

Tách phần dùng chung thay vì để module mới phụ thuộc ngược vào module cũ.
Phần dùng chung chiếm 5/11 hàm của `pdf_overlay.py`, và `write` của hai chế độ
chỉ khác đúng bộ dựng trang.

```
render/pdf_trang.py
    # tách nguyên văn từ pdf_overlay, KHÔNG đổi hành vi:
    dat_chu, _khung_dung, ghep_kho_doi,
    _duong_nguon, _chen_trang_bao_cao, _don_cho_dai_ra,
    CO_SO_TRANG, TI_LE_DON
    write(project, con, out_path, dung_trang, *, pages, dry_run, probe)
    # hàm MỚI, chỉ reflow gọi:
    kep_khung(khung, trang) -> Rect

render/pdf_overlay.py   (còn lại)
    xoa_chu, trang_dich, write  -> gọi pdf_trang.write(dung_trang=trang_dich)

render/pdf_reflow.py    (mới)
    trang_reflow, write         -> gọi pdf_trang.write(dung_trang=trang_reflow)
```

`_khung_dung` **giữ nguyên hành vi loại bỏ** — `overlay` vẫn loại khối có khung
ngoài trang như trước, vì ở đó ảnh nền che chỗ mất nên loại là đúng. Chỉ
`trang_reflow` gọi `kep_khung` trước rồi mới qua `_khung_dung`. Bước tách module
do đó không đổi một hành vi nào; R3 là hành vi mới của riêng `reflow`.

`render/__init__.py`: nhánh `mode == "reflow"` thôi ném `UnsupportedTarget`,
chuyển sang gọi `pdf_reflow`. Nhánh EPUB và luật "mode không hợp lệ" giữ nguyên.

**Giao diện bộ dựng trang** — hai chế độ cùng ký:

```python
dung_trang(src_doc, page_no: int, khoi: list, kho=None,
           ghi_nhan=None) -> pymupdf.Document   # tài liệu MỘT trang
```

`khoi` là list dict `{id, bbox, html, size}`. `ghi_nhan`, nếu truyền, nhận
`(id, ti_le, bi_tran)` cho mỗi khối đã đặt. Người gọi đóng tài liệu.

**Thuật toán `trang_reflow`:**

1. Trang trắng đúng khổ `src_doc[page_no].rect`
2. Với từng khối theo `pos`: kẹp `bbox` vào trang (R3), bỏ khối có khung rỗng
3. `dat_chu` với thang co sẵn có
4. Khối tràn ở bậc cuối: `dat_chu` lại với `src_html` (R4), ghi cờ `overflow`
5. Không sao chép gì từ `src_doc` (R2)

Không có bước xoá chữ — nền trắng, không có gì để xoá.

## 6. Kiểm chứng

Theo đúng spec mẹ: chạy trên `astrology.pdf` trang 149–170. Đó là text-PDF đã
có bản dịch thật từ Phase 5, nên kiểm được bộ render mới mà **không tốn thêm
token nào** và không lẫn biến OCR. Bộ render và khâu OCR là hai nguồn lỗi khác
nhau; tách chúng ra là chủ ý của spec mẹ.

Chỉ số phải đạt:

| Chỉ số | Ngưỡng |
|---|---|
| Ảnh trên mỗi trang reflow | **0** — đo trên tài liệu một trang, không đo trên khổ ghép (XObject lồng nhau làm `get_images` đếm sai) |
| Mực nửa dịch reflow so với nửa dịch overlay, cùng khổ | **≤** (sai số 0,1 điểm %) trên cả 22 khổ |
| harmonics 60–61: mực nửa dịch so với nửa gốc | **thấp hơn** |

*Vì sao không so nửa dịch với nửa gốc trên astrology:* đo thật, ngay cả
`overlay` đúng (một lớp chữ) cũng có nửa dịch đậm hơn nửa gốc ở 22/22 khổ, tỉ
lệ 1,08–1,48 — chữ Việt có dấu nhiều mực hơn chữ Anh. Phép so đó chỉ phân biệt
được một lớp với hai lớp trên sách scan, nơi nền giấy và lớp chữ Anh trong ảnh
làm nửa gốc đậm.
| Khối đặt được | ≥ 108/109 — `overlay` đo được đúng 108/109 trên cùng khoảng |
| Cỡ chữ trung vị | ≥ 85% |

Sau đó chạy trên harmonics trang 60–61 để thấy khác biệt so với ảnh chồng chữ
đã đo ở mục 1.

## 7. Test

Phép tách `pdf_trang` là thuần tuý: **281 test đang xanh phải xanh nguyên**,
kể cả vân tay `tests/golden/`. Đó là lưới an toàn của bước tách.

Thêm `tests/test_pdf_reflow.py`:

- khung có `y` âm bị kẹp vào trang chứ không bị bỏ (R3)
- trang không có khối nào ra trang trắng, không phải bản sao (R5)
- khối tràn ở bậc cuối rơi về `src_html` và mang cờ `overflow` (R4)
- trang reflow không chứa ảnh nào của trang gốc (R2)
- khối nằm đúng vị trí `bbox` đã cho (R1)
- `--mode reflow` không còn ném `UnsupportedTarget`

Không test nào gọi mạng.

## 8. Rủi ro

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Tách module làm hỏng `overlay` | 281 test đỏ | Tách trước, không đổi hành vi, chạy test rồi mới thêm `reflow` |
| Kẹp khung làm chữ đè lên nhau | Khối cạnh nhau chồng mực | Chỉ kẹp, không dịch chuyển; khối âm chỉ 1,3% và lệch dưới 5pt |
| Chữ Việt dài hơn nên co nhiều | `--probe` báo cỡ trung vị thấp | Đã đo ở Phase 4: trung vị 100%, xấu nhất 74%; reflow dùng chung thang co |
| Rác OCR bôi bẩn trang harmonics | Vệt chữ vô nghĩa trên nền trắng | Chấp nhận có ý thức, để Phase 7 (mục 3) |
