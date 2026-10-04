# Phase 7 — Gom dòng đúng cho sách scan đã OCR

**Spec mẹ:** [2026-09-21-pdf-song-ngu-design.md](2026-09-21-pdf-song-ngu-design.md) mục 10, Phase 7.
**Spec liền trước:** [2026-09-23-reflow-design.md](2026-09-23-reflow-design.md) mục 3 đã đẩy việc làm sạch OCR sang đây.

## 1. Vấn đề

Trên `projects/harmonics` (sách scan 484 trang, lớp chữ OCR có sẵn), reflow in
chồng dòng lên nhau ở 275/480 trang. Đo lại cho thấy đó không phải lỗi của reflow
và phần lớn không phải chữ lặp:

| Loại cặp khối có khung chồng nhau | Số cặp |
|---|---|
| Chữ khối nhỏ lặp nguyên trong khối lớn | 106 |
| Khối nhỏ ≤ 15 ký tự (mảnh vụn) | 1.267 |
| Hai đoạn chữ thật khác nhau | 1.021 |

Trong số cặp chữ khác nhau có đủ dữ liệu dòng, **947/974 (97%) chỉ chồng ở
khung, còn các dòng chữ thật không đè lên nhau**. OCR đặt từng dòng đúng chỗ;
lỗi nằm ở khâu gom dòng thành đoạn.

**Cơ chế.** OCR cắt một hàng chữ thành hai mảnh. `group_paragraphs` coi mảnh đuôi
là dòng thụt đầu đoạn vì nó nằm xa về bên phải
([pdf_layout.py:269](../../../pdf_layout.py)):

```python
thut_vao = sau.bbox[0] - truoc.bbox[0] > NGUONG_THUT_DAU_DONG
```

Mảnh đuôi thành dòng mở đầu của đoạn **sau**; khung đoạn sau trùm lên hàng cuối
của đoạn trước. Toạ độ thật, trang 402: dòng cuối đoạn A ở `(46,233)-(308,242)`,
dòng đầu đoạn B ở `(315,233)-(324,242)` — cùng một hàng.

**Hậu quả nặng hơn chuyện in đè: chữ bị chia sai giữa các đoạn.** Đoạn trước mất
vài chữ cuối, đoạn sau mở đầu bằng chữ lạc. Model dịch một câu cụt và một đoạn
mở đầu vô nghĩa. Đo trên harmonics: 1.292/3.640 cặp khối liền nhau (35%, trên
240 trang) có dòng đầu khối sau nằm cùng hàng với dòng cuối khối trước; 280 chỗ
trong đó cắt ngang câu chắc chắn (khối trước không có dấu kết câu, khối sau mở
bằng chữ thường).

## 2. Mục tiêu

Ghép các mảnh cùng hàng thành một dòng **trước khi** gom đoạn, chỉ trên trang
sách scan. Thành công khi chữ không còn bị chia sai giữa các đoạn, không mất ký
tự nào, và text-PDF không đổi một khối nào.

## 3. Phạm vi

**Trong phạm vi:** hàm ghép mảnh cùng hàng; dò trang scan theo từng trang; nối
vào `ingest/pdf_text.py`; `init` lại harmonics.

**Ngoài phạm vi — lọc rác OCR.** Đo bằng từ điển tiếng Anh
(`/usr/share/dict/words`, 235 nghìn từ): astrology, một text-PDF không có rác OCR
nào, vẫn có 737 khối (7,1%) dưới 40% từ thật và 86 khối chỉ toàn ký hiệu — tên
riêng, thuật ngữ Phạn và Latin, ký hiệu chiêm tinh. Luật lọc theo nội dung sẽ
xoá chữ thật. Rác chỉ chiếm 1,9% ký tự của harmonics. Người dùng quyết để nguyên.

**Ngoài phạm vi — chạy OCR thật.** Phase 7 gốc gồm cả OCR cho sách scan chưa có
lớp chữ. Chưa có cuốn nào như vậy để đo, nên để tới khi có.

## 4. Quyết định

**G1 — Sửa ở khâu gom dòng lúc `init`, không phải ở khâu xuất.**
Cắt khung lúc xuất chỉ che chuyện in đè; chữ vẫn nằm sai đoạn và vẫn được dịch
sai. Chỉ sửa lúc gom dòng mới đưa chữ về đúng đoạn trước khi nó tới model.

**G2 — Chỉ chạy trên trang scan, dò theo từng trang.**
Trang scan là trang có một ảnh phủ ≥ 90% diện tích trang và có lớp chữ. Đo thật:
harmonics 482/484 trang, astrology 0/925.

Không áp chung cho mọi sách vì astrology cũng có chỗ cùng hàng — 989 chỗ, khe
trung vị khoảng 3× cỡ chữ, tập trung ở trang bảng và mục lục tra cứu (ví dụ trang
708, 182, 908 có 88–127 khối và hàng chục vị trí `x`). Đó là ô bảng và cột mục lục
**đúng bố cục**. Áp cùng luật với ngưỡng 1,5× hay 2× sẽ ghép nhầm 116 hay 277
chỗ của astrology.

**G3 — Hai dòng liền nhau được ghép khi thoả cả bốn điều kiện:**

1. cùng trang, cùng cột (`col` do `detect_columns` gán);
2. cùng hàng: phần chồng theo chiều dọc > 60% chiều cao của dòng có chiều cao
   nhỏ hơn;
3. dòng sau nằm bên phải: `x0` dòng sau ≥ `x1` dòng trước − 2pt;
4. khe ngang `x0` dòng sau − `x1` dòng trước ≤ **2,0 × cỡ chữ dòng trước**.

*Vì sao 2,0×.* Đo trên harmonics (khe chia cho cỡ chữ):

| Ngưỡng | Chỗ cùng hàng được ghép | Chỗ cắt câu chắc chắn được ghép |
|---|---|---|
| ≤ 1,0× | 616/1.292 (48%) | 171/280 |
| ≤ 1,5× | 831/1.292 (64%) | 215/280 |
| **≤ 2,0×** | **1.037/1.292 (80%)** | **227/280** |
| ≤ 3,0× | 1.121/1.292 (87%) | 245/280 |

Sau 2,0× đường cong thưa dần và lẫn ô bảng, chú thích nằm cạnh nhau. Trên trang
scan, ghép nhầm chỉ dán hai ô bảng thành một dòng — dịch vẫn đúng. Bỏ sót thì
làm hỏng hai đoạn văn. Nên nghiêng về phía ghép nhưng dừng ở chỗ dữ liệu thưa.

**G4 — Dòng ghép:** khung là hợp hai khung; `text` và `html` nối bằng một dấu
cách; `size` lấy của mảnh có nhiều ký tự hơn (cỡ chữ trội, như `merge_spans`);
`col` và `page_no` giữ nguyên. Một hàng cắt thành 3 mảnh trở lên thì ghép dồn
từ trái sang phải.

**G5 — Hàm ghép là hàm thuần trong `pdf_layout.py`.**
Không import PyMuPDF — luật tầng của dự án. Việc dò trang scan cần đọc ảnh nên
nằm ở `ingest/pdf_text.py`.

## 5. Kiến trúc

```
pdf_layout.py
    NGUONG_KHE_CUNG_HANG = 2.0
    ghep_manh_cung_hang(lines, khe_toi_da=NGUONG_KHE_CUNG_HANG) -> list[Line]

ingest/pdf_text.py
    _la_trang_scan(page) -> bool     # ảnh phủ >= 90% diện tích trang
    load(): với mỗi trang
        lines = _doc_trang(...)
        detect_columns(lines, ...)
        if _la_trang_scan(page): lines = ghep_manh_cung_hang(lines)   # MỚI
        group_paragraphs(lines)
```

Ghép sau `detect_columns` để điều kiện "cùng cột" có nghĩa. `group_paragraphs`
tự sắp lại thứ tự đọc nên không cần giữ thứ tự đầu ra của hàm ghép.

Không thay đổi schema DB, không thay đổi `translate`, `export`, `reflow`.

## 6. Kiểm chứng — không tốn token

So hai lần `init` **mới**, không so với DB hiện có: DB hiện có có thể do phiên
bản code cũ hơn dựng ra, và khi đó chênh lệch không nói gì về phase này.

- Trước khi sửa code (commit `f60b862`): `init` harmonics vào
  `projects/harmonics-g7-truoc`, astrology vào `projects/astrology-g7-truoc`
  (nguồn: `projects/<tên>/source.pdf`).
- Sau khi sửa: `init` cùng hai nguồn vào `projects/harmonics-g7-sau` và
  `projects/astrology-g7-sau`.

| Chỉ số | Trước | Ngưỡng |
|---|---|---|
| harmonics: chỗ cắt câu chắc chắn | đo ở `-truoc` (DB cũ: 280) | ≤ 53 (phần nằm ngoài ngưỡng 2,0×) |
| harmonics: cặp khối chữ khác nhau có khung chồng | đo ở `-truoc` (DB cũ: 974) | giảm ít nhất một nửa |
| harmonics: tổng ký tự, bỏ khoảng trắng | — | **bằng nhau** |
| astrology: danh sách `(page_no, pos, bbox, src_html)`, `-truoc` so với `-sau` | — | **giống hệt** |

Cộng thêm ảnh nửa dịch reflow `--dry-run` trang 60–61 của bản mới.

Khi đạt, `init --force` lại `projects/harmonics`. Việc này xoá bản dịch trang
60–61 đã có ($0,01) — người dùng đã chấp nhận.

## 7. Test

Không test nào gọi mạng. Thêm:

- `ghep_manh_cung_hang`: hai mảnh cùng hàng khe nhỏ được ghép; khe > 2× không
  ghép; khác cột không ghép; khác hàng không ghép; ba mảnh ghép dồn; không mất ký
  tự; cỡ chữ lấy của mảnh dài hơn.
- Mức ingest: một PDF có ảnh phủ kín trang và một hàng chữ bị cắt đôi → ra đúng
  một đoạn, không phải hai.
- Mức ingest: cùng bố cục đó nhưng **không có ảnh phủ** → giữ nguyên hành vi cũ
  (hai khối). Đây là lưới an toàn cho text-PDF.

308 test hiện có phải xanh nguyên, kể cả vân tay `tests/golden/`.

## 8. Rủi ro

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Ghép nhầm hai ô bảng cạnh nhau trên trang scan | Dòng bảng thành một chuỗi | Chấp nhận: dịch vẫn đúng, khung vẫn đúng vị trí |
| Cỡ chữ OCR bị thổi lên làm ngưỡng lỏng ra | Ghép cả những mảnh cách xa | Ngưỡng tính theo dòng trước; đo lại ở mục 6 |
| Sách scan có ảnh chỉ phủ một phần trang | Trang không được nhận là scan | Chấp nhận: đi đường cũ, không tệ hơn hiện nay |
| Rác OCR vẫn hiện trên nửa dịch | Vệt chữ vô nghĩa quanh biểu đồ | Chấp nhận có ý thức (mục 3) |
