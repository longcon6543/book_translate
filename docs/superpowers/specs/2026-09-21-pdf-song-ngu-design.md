# Dịch sách PDF Anh–Việt, xuất bản song song theo trang

Ngày: 2026-09-21
Trạng thái: thiết kế đã chốt, chờ lập kế hoạch thực thi
Tiếp nối: booktrans Phase 1 (EPUB), commit `b2ff79e`

## 1. Mục tiêu

Dịch sách từ tiếng Anh sang tiếng Việt, đầu vào là PDF — cả loại có sẵn lớp
chữ lẫn loại quét từ sách giấy. Đầu ra là **một file PDF khổ ngang**, mỗi khổ
chứa trang gốc bên trái và bản dịch của đúng trang đó bên phải. Người đọc lướt
tới trang nào thì có ngay bản dịch tương ứng kế bên.

Mức giữ bố cục khác nhau theo loại sách. **PDF có sẵn lớp chữ**: trang dịch là
bản sao trang gốc đã thay chữ, nên ảnh và vị trí từng khối giữ nguyên. **Sách
scan**: chữ trong đó là ảnh nên không thay được — trang dịch là một trang sạch
dựng lại, giữ đúng thứ tự nội dung và ranh giới trang, chừa chỗ trống cho ảnh,
nhưng không giữ vị trí từng dòng. Bản gốc luôn nằm bên trái để đối chiếu.

Dùng cá nhân, chạy bằng dòng lệnh. Không xây giao diện, không xây dịch vụ.

### Thế nào là thành công

Đo trên 20 trang mẫu của `astrology.pdf` (899 trang có chữ, 2,49 triệu ký tự):

1. Ở chế độ `--dry-run`, trang phải trùng khớp trang trái về vị trí từng khối.
2. Ảnh, bảng, đường kẻ, nền trên trang dịch còn nguyên vẹn — không bị khoét,
   không bị phủ trắng.
3. Từ 95% số đoạn trở lên giữ được cỡ chữ ít nhất 85% so với bản gốc.
4. Không có ký tự tiếng Việt nào hiện thành ô vuông vì font thiếu glyph.
5. Dừng giữa chừng bằng Ctrl+C rồi chạy lại: không mất tiến độ, không dịch lại
   chunk đã xong, không gọi API thừa.
6. `status` báo được số tiền thực đã tiêu và ước tính phần còn lại.

Tiêu chí 1 và 2 áp dụng cho chế độ `overlay`. Với `reflow`, hai tiêu chí tương
ứng là: nội dung trang dịch đúng thứ tự và đúng ranh giới trang so với bản gốc,
và chỗ trống chừa cho ảnh đúng kích thước với vùng ảnh trên trang gốc.

### Không thuộc phạm vi

Giao diện đọc, đồng bộ cuộn, sửa bản dịch trực tiếp trên trang. Dịch ngược
Việt–Anh. Ngôn ngữ thứ ba. Xuất DOCX. Sách có DRM. Dịch chữ nằm bên trong ảnh
minh hoạ. Chèn ảnh thật vào trang dịch ở chế độ `reflow` (D10). Giữ vị trí
từng dòng cho sách scan (D9).

## 2. Những quyết định đã chốt

| # | Quyết định | Lý do |
|---|---|---|
| D1 | Đầu ra là PDF khổ ngang, gốc trái / dịch phải | Mở bằng trình đọc sẵn có, không phải xây app |
| D2 | Text-PDF: đè chữ lên bản sao trang gốc (`overlay`) | Giữ ảnh và bố cục nguyên vẹn |
| D3 | Gọi API trực tiếp, không dùng sub-agent | Sub-agent tốn hơn 8 triệu token phụ trội cho 900 trang, và không cho phép kiểm soát xác định |
| D4 | Tầng provider thay được | Người dùng muốn đổi sang nhà cung cấp khác khi cần |
| D5 | OCR là một lượt riêng, chạy một lần, tự dò khi cần | Đắt nhất pipeline; không được lặp lại khi dịch lại |
| D6 | Mọi lệnh nhận khoảng trang | Đọc tới đâu dịch tới đấy; vòng phản hồi ngắn; không cam kết tiền cho cả cuốn |
| D7 | Tràn khung thì thu nhỏ chữ, không nhờ mô hình viết gọn lại | Ưu tiên trung thành với bản gốc. Cờ `--compress` mặc định tắt |
| D8 | Tái sử dụng `translator.py` và `db.py` của Phase 1 | Phần đắt giá nhất đã đúng và đã chạy được |
| D9 | Sách scan: OCR lấy chữ rồi dựng trang sạch (`reflow`), không tô nền đè lên trang quét | Chữ trong scan *là* ảnh; đè lên là che mất bản gốc. Dựng lại cho chữ sắc nét và không phụ thuộc độ chính xác toạ độ của OCR |
| D10 | Ảnh trong sách scan: chừa chỗ trống đúng kích thước, không chèn ảnh thật | Nhịp trang khớp bản gốc khi đặt cạnh nhau; ảnh đã có nguyên vẹn ở trang trái |

Chế độ `reflow` bắt buộc phải có vì sách scan cần nó (D9). Một khi đã có, nó
dùng được luôn cho text-PDF: nếu `--probe` cho thấy quá nhiều trang phải thu
chữ dưới 75% thì chuyển những trang đó sang `reflow`, ghép lai theo từng trang.
Khả năng này có sẵn, không phải làm thêm.

## 3. Kiến trúc

Phase 1 dính chặt vào EPUB: block định vị bằng `doc_href` + `pos`, và xuất bản
dịch bằng cách ghi đè lại chính file nguồn. PDF không có cấu trúc đó. Nhưng
`translator.py` thì không quan tâm nguồn là gì — nó nhận `(id, tag, src_html)`
và trả về bản dịch. Đó là đường cắt.

```
                 ├─ ingest/epub.py       (đã có, gói lại)
input ───────────┼─ ingest/pdf_text.py   (mới)
                 └─ ingest/pdf_scan.py   (mới: OCR rồi đi tiếp như pdf_text)
                            │
                            ▼
                    blocks trong SQLite
                    chunking + translator.py      ← lõi, không đổi hành vi
                    providers/{anthropic,openai_compat}.py
                            │
                            ▼
                 ├─ render/epub.py        (đã có)
output ──────────┴─ render/pdf_overlay.py (mới)
```

Giao kèo giữa các tầng:

- **ingest**: nhận đường dẫn file, trả về danh sách block.
- **render**: nhận danh sách block đã dịch, dựng file đầu ra.
- **provider**: `make_client(cfg)` và `call(client, model, system, user)` trả về
  `(text, usage, stop_reason)`, cộng một bảng phân loại lỗi thành *dừng hẳn* hay
  *thử lại*, cộng cờ báo có hỗ trợ prompt caching hay không.

Thêm định dạng mới hoặc nhà cung cấp mới về sau là thêm một file, không đụng
phần còn lại.

### Tầng provider

Chỗ dính vào Anthropic hiện gói gọn trong `make_client()` và `call_api()` của
`translator.py`. Ba thứ phải chuẩn hoá vì mỗi bên một kiểu: tên trường usage
(để tính tiền), phân loại lỗi (hiện `FATAL_ERRORS` bắt đúng lớp exception của
Anthropic), và khả năng cache.

Hai module phủ gần hết: Anthropic (đã có) và giao thức OpenAI — mở ra DeepSeek,
Qwen, OpenRouter, và model chạy tại máy qua Ollama hoặc LM Studio. Gemini thêm
sau nếu cần.

Mỗi chunk ghi lại provider và model đã dịch nó. Nhờ vậy có thể dịch cùng một
khoảng trang bằng nhiều nhà cung cấp rồi đặt cạnh nhau mà chọn.

## 4. Mô hình dữ liệu

Bảng `blocks` khái quát hoá từ `(doc_index, doc_href, pos)` thành:

| cột | ý nghĩa |
|---|---|
| `page_no` | số trang PDF, thay vai trò `doc_index` |
| `bbox` | `x0,y0,x1,y1` — khung chữ trên trang, đơn vị point |
| `line_bboxes` | JSON: khung từng dòng, cần cho bước đè chữ |
| `layout` | JSON tự do: font, cỡ, đậm/nghiêng, giãn dòng, căn lề, chỉ số cột |
| `kind` | `text` / `heading` / `caption` / `table` / `formula` / `skip` |
| `cont_group` | id nhóm nếu đoạn bị cắt ngang sang trang sau |

`src_html`, `dst_html`, `chunk_id`, `flag` giữ nguyên, nên `translator.py` chạy
y như cũ. `layout` là JSON tự do để mỗi nguồn nhét thứ nó cần — EPUB nhét
`{href, pos}`, PDF nhét toạ độ và font — tránh phải sinh bảng riêng cho từng
định dạng rồi nhân đôi mọi truy vấn thống kê.

`kind` quyết định cái gì **không** được dịch: công thức, bảng số liệu, khối
code, header/footer. Đánh dấu `skip` thì để nguyên tiếng Anh trên trang dịch và
báo trong `status`.

Bảng `chunks` thêm `provider` và `model`.

Bảng `meta` thêm `source_format`, `source_path`, `source_sha256`, `schema_version`.

### File nguồn

`init` nhận diện bằng magic bytes (`%PDF`, `PK`), **không tin phần mở rộng** —
đúng cái bẫy đã làm hỏng `projects/astrology.pdf` lần trước, khi một file PDF
bị copy thành `source.epub`.

File gốc không bao giờ bị sửa. Render mở nó chỉ để đọc. Checksum để phát hiện
file nguồn bị thay giữa chừng, thay vì âm thầm xuất ra một file lệch trang.

Cờ `--link` cho phép chỉ lưu đường dẫn thay vì copy: sách scan thường 300MB
đến 1GB, copy vào project là phí đĩa vô nghĩa.

### Nâng cấp schema

`db.py` thêm `SCHEMA_VERSION` và đường nâng cấp. Project EPUB tạo bằng Phase 1
phải mở được và giữ nguyên tiến độ dịch.

## 5. Bóc chữ ra khỏi trang

PDF không lưu đoạn văn, nó lưu những mảnh chữ rời có toạ độ — một dòng căn đều
hai bên có khi là hai chục mảnh. Dựng lại đoạn văn từ đống mảnh đó là bước mà
nếu sai thì mọi thứ sau đều hỏng.

Dùng PyMuPDF lấy từng mảnh kèm khung, font, cỡ, đậm/nghiêng. Ghép ba tầng:

- **Mảnh → dòng**: gộp các mảnh cùng độ cao. Mảnh in nghiêng hoặc in đậm bọc
  thành `<i>` / `<b>`. Đầu ra do đó có dạng HTML giống EPUB, và `translator.py`
  dùng lại nguyên si, kể cả cơ chế đếm thẻ để bắt lỗi.
- **Dòng → đoạn**: dựa vào khoảng cách dọc so với giãn dòng thường, thụt đầu
  dòng, và nối chữ bị gạch nối cuối dòng lại thành một từ.
- **Đoạn → thứ tự đọc**: gom theo cột. Có khoảng trắng dọc chạy suốt trang thì
  là sách hai cột; đọc hết cột trái rồi sang phải.

### Header, footer và số trang

Tên chương chạy đầu trang và số trang chân trang lặp gần như y hệt, cùng một độ
cao, suốt hàng trăm trang. So chéo vài chục trang là lộ ra. Đánh dấu `skip`:
khỏi dịch, khỏi tốn tiền, khỏi nguy cơ dịch "Chapter 7" thành một câu lạc lõng.

### Đoạn bị cắt ngang trang

PDF thường cắt một đoạn giữa chừng: nửa trên cuối trang 12, nửa dưới đầu trang
13. Dịch riêng hai nửa thì câu gãy và sai ngữ pháp.

Phát hiện bằng dấu hiệu: trang trước không kết bằng dấu kết câu, trang sau bắt
đầu bằng chữ thường. Gán chung `cont_group`, dịch như một đoạn liền, rồi cắt
bản dịch trả lại hai khung theo tỉ lệ độ dài của hai nửa bản gốc, ưu tiên cắt
tại ranh giới câu gần nhất.

### Phân loại khối

`heading` — font lớn hơn trung vị của trang và nội dung ngắn.
`caption` — font nhỏ, nằm sát một ảnh.
`table` — nhiều mảnh căn thẳng cột.
`formula` — nhiều ký tự toán hoặc font toán.
`skip` — header, footer, số trang.

## 6. Dựng trang dịch

Hai chế độ render, chọn theo loại sách. Cả hai dùng chung phần đặt chữ, phần
font và phần ghép khổ đôi ở cuối mục này.

| | `overlay` | `reflow` |
|---|---|---|
| Dùng cho | PDF có sẵn lớp chữ | Sách scan; và làm dự phòng cho text-PDF |
| Trang dịch là | bản sao trang gốc, thay chữ | trang sạch dựng lại từ nội dung |
| Vị trí từng dòng | giữ như gốc | không giữ |
| Ranh giới trang | giữ | giữ |
| Ảnh | nguyên vẹn, không đụng tới | chừa chỗ trống đúng kích thước |

### Chế độ `overlay` — xoá chữ Anh rồi đặt chữ Việt vào đúng khung

Chỉ dùng cho PDF có sẵn lớp chữ, vì chỉ ở đó chữ mới xoá được.

Xoá đúng glyph bằng redaction, nhưng **phải tắt chế độ xoá ảnh**. Mặc định
redaction quét sạch cả phần ảnh nằm trong khung — chú thích đè lên hình sẽ kéo
theo một mảng hình bị khoét trắng.

Không áp dụng cho sách scan. Ở sách scan chữ *là* ảnh nên không xoá được, và
cách duy nhất để đặt chữ Việt lên đó là tô đè che mất chữ Anh bên dưới. Quyết
định D9 loại bỏ hướng này: sách scan đi chế độ `reflow`.

### Chế độ `reflow` — dựng lại trang sạch

Trang trắng cùng khổ với trang gốc, cùng lề. Đổ các block đã dịch của đúng
trang đó vào theo thứ tự đọc, giữ phân cấp: `heading` cỡ lớn hơn, `caption` cỡ
nhỏ hơn, đoạn thường theo cỡ chữ thân sách.

Vùng ảnh trên trang gốc được **chừa chỗ trống đúng kích thước**, không chèn ảnh
thật vào (D10). Nhịp trang vì thế khớp với bản gốc khi đặt cạnh nhau, và ảnh
thì đã có sẵn nguyên vẹn ở trang bên trái để xem. Chú thích ảnh vẫn được dịch
và đặt ngay dưới khoảng trống đó.

Vẫn giữ **một trang gốc ứng một trang dịch**. Nếu chữ Việt không vừa thì thu cỡ
chữ theo đúng thang bên dưới, không đẩy tràn sang trang sau — vì tràn một trang
là lệch toàn bộ phần còn lại của sách.

### Đặt chữ Việt

Đưa HTML đã dịch vào khung hợp của cả đoạn (`bbox` ở chế độ `overlay`, khung đã
tính lại ở chế độ `reflow`), để thư viện tự xuống dòng và giữ đậm/nghiêng.
Không đặt theo từng dòng gốc, vì tiếng Việt ngắt dòng ở chỗ khác hẳn tiếng Anh.
`line_bboxes` dùng cho hai việc khác: xác định vùng cần xoá chữ cho khít ở chế
độ `overlay`, và đo giãn dòng gốc để bước 2 của thang biết đang bóp từ mức nào.

Tiếng Việt dài hơn tiếng Anh khoảng 20–30%, nên tràn khung là chuyện chắc chắn
xảy ra. Thang xử lý, chạy từ trên xuống, vừa là dừng:

1. cỡ chữ gốc
2. bóp giãn dòng còn 95%
3. thu cỡ chữ dần xuống 85%
4. nếu ngay dưới khung là lề trắng thì cho tràn xuống
5. thu tiếp xuống 75%
6. thu tiếp xuống 70%
7. hết cách: giữ 70%, gắn cờ `overflow`, báo trong `status`

Bước "nhờ mô hình viết gọn lại khoảng 15% mà giữ nguyên ý" có trong code nhưng
**mặc định tắt**, chỉ bật bằng `--compress`. Quyết định D7: trung thành với bản
gốc được ưu tiên hơn cỡ chữ.

### Font

Nhúng một font có đủ dấu tiếng Việt. Ánh xạ có chân sang có chân, không chân
sang không chân, giữ đậm và nghiêng.

**Không dùng lại font của sách gốc.** Font nhúng trong sách tiếng Anh gần như
luôn thiếu glyph tiếng Việt, và kết quả là những chữ như "ặ", "ữ", "ổ" biến
thành ô vuông rỗng, rải khắp 900 trang.

### Ghép khổ đôi

Tạo trang ngang rộng gấp đôi. Dán nguyên trang gốc vào nửa trái — text-PDF thì
dán dạng vector nên chữ vẫn bôi đen và tìm kiếm được; sách scan thì dán nguyên
ảnh quét ở độ phân giải gốc. Dán trang dịch vào nửa phải. Số trang gốc in nhỏ ở
giữa.

File ra không phình gấp đôi: hai trang dùng chung bộ ảnh và font nhúng, phần
tăng thêm chủ yếu là chữ tiếng Việt.

## 7. Chất lượng bản dịch

### Tách lỗi layout khỏi lỗi dịch

Khi một trang ra xấu, có hai nguyên nhân khác hẳn nhau: bóc chữ sai, hoặc dịch
sai. Trộn chung thì mất cả buổi để đoán.

`--dry-run` đè **chính chữ tiếng Anh gốc** trở lại khung, kèm chữ độn cho dài
ra đúng tỉ lệ tiếng Việt thường dài hơn. Trang phải phải trông gần y hệt trang
trái. Chỗ nào lệch là lỗi layout, chắc chắn không phải lỗi dịch — và phát hiện
được mà không tốn đồng API nào.

`inspect` in thứ tự đoạn đọc được kèm phân loại, để soi xem tool có hiểu đúng
cuốn sách không, trước khi cho nó dịch.

### Glossary trích tự động

Một lượt quét rẻ toàn sách, gom tên riêng và thuật ngữ lặp nhiều, xếp theo tần
suất, ghi ra `glossary.candidates.txt` để duyệt bằng mắt.

Với sách 900 trang đây là thứ quyết định tính nhất quán: hàng trăm thuật ngữ
phải được dịch giống nhau từ trang 1 tới trang 899.

### Kiểm tra máy móc

`check_translation` hiện bắt thẻ HTML lệch, bản dịch rỗng, và bản dịch ngắn bất
thường. Thêm: mọi chữ số và mọi tên viết hoa trong bản gốc phải xuất hiện đủ
trong bản dịch. Bỏ sót một câu chứa ngày tháng hay tên người là lỗi im lặng
nguy hiểm nhất, và bắt nó chỉ tốn vài dòng regex, không tốn token.

### Sửa tay

Bản dịch nằm trong SQLite, không nằm trong file PDF. Sửa một đoạn rồi `export`
lại là xong, không phải dịch lại. Lệnh `edit` sửa nhanh theo id đoạn.

## 8. Giao diện dòng lệnh

```bash
python cli.py init ebook/astrology.pdf.pdf          # nhận diện, dò OCR, tách đoạn, chia chunk
python cli.py glossary projects/astrology --top 200 # gom thuật ngữ để duyệt
python cli.py inspect  projects/astrology --pages 1-20
python cli.py export   projects/astrology --pages 1-20 --dry-run --probe
python cli.py translate projects/astrology --pages 1-20
python cli.py export    projects/astrology --pages 1-20
python cli.py export    projects/astrology --pages 1-20 --mode reflow
python cli.py status    projects/astrology
python cli.py edit      projects/astrology --block 1423
python cli.py ocr       projects/astrology --pages 1-50    # chỉ sách scan
```

Mọi lệnh chạy trên dữ liệu đều nhận `--pages`. `--provider` và `--model` chọn
nhà cung cấp. `--probe` thêm một trang báo cáo ở đầu file xuất: trang nào phải
thu chữ và thu bao nhiêu, đoạn nào tràn, đoạn nào bị bỏ qua.

`--mode` nhận `overlay` hoặc `reflow`. Mặc định suy ra từ `source_format`:
text-PDF dùng `overlay`, sách scan dùng `reflow`. Chỉ định tay để ép khác đi —
chạy `reflow` trên một text-PDF là cách kiểm bộ render dựng lại mà không cần
sách scan.

## 9. Quy mô và chi phí

Đo thực trên `astrology.pdf`:

| | |
|---|---|
| Trang có chữ | 899 |
| Ký tự nguồn | 2.487.832 |
| Trung bình mỗi trang | 2.767 ký tự |
| Số chunk (6.000 ký tự) | khoảng 415 |
| Token vào, nội dung | khoảng 620.000 |
| Token vào, ngữ cảnh 3 đoạn trước | khoảng 165.000 |
| Token ra, tiếng Việt | khoảng 1.070.000 |

Với mức giá 3 và 15 đô một triệu token thì rơi vào khoảng 18–20 đô cho cả cuốn.
`status` tính số thật khi đặt `PRICE_IN` và `PRICE_OUT`.

Prompt caching đã bật sẵn trong `translator.py`, nên style guide và glossary tuy
gửi kèm mọi chunk nhưng chỉ tính tiền đầy đủ ở lần đầu.

Để so sánh: phương án sub-agent tốn thêm khoảng 8 triệu token phụ trội cho 415
lượt spawn — riêng phần thừa đã đắt hơn toàn bộ việc dịch. Đó là căn cứ của D3.

## 10. Lộ trình

**Phase 2 — Nền.** Tầng provider; khái quát hoá `blocks`; tách `ingest/` và
`render/`.
*Kiểm chứng: chạy lại một project EPUB, kết quả giống hệt trước khi sửa.*

**Phase 3 — Bóc chữ khỏi PDF text.** Mảnh → dòng → đoạn, cột, header/footer,
nối đoạn cắt ngang trang, phân loại khối. Lệnh `inspect`.
*Kiểm chứng: soi mắt trên 20 trang thật. Không tốn token.*

**Phase 4 — Chế độ `overlay` và ghép khổ đôi.** Xoá chữ, đặt chữ, thang thu
nhỏ, font tiếng Việt, ghép trang. Lệnh `export --dry-run --probe`.
*Kiểm chứng: `--dry-run` trên 20 trang. Không tốn token.*

**Phase 5 — Nối vào mạch dịch.** `--pages` cho mọi lệnh, `glossary`, kiểm tra
số và tên riêng, `edit`, `status` mở rộng.
*Kiểm chứng: dịch thật 20 trang, đọc, tính tiền thật cho cả cuốn.*

**Phase 6 — Chế độ `reflow`.** Dựng trang sạch từ block đã dịch: phân cấp tiêu
đề và chú thích, chừa chỗ trống cho vùng ảnh, ép một trang gốc ứng một trang
dịch.
*Kiểm chứng: chạy `export --mode reflow` trên chính `astrology.pdf` — một
text-PDF đã có sẵn bản dịch từ Phase 5. Kiểm được bộ render mới mà chưa cần
OCR, và chưa tốn thêm token nào.*

**Phase 7 — Sách scan.** Dò tự động xem có cần OCR, OCR một lượt ra
`source.ocr.pdf`, dò vùng ảnh để chừa chỗ, nối vào `reflow`, resume theo khoảng
trang.
*Kiểm chứng: một cuốn scan thật.*

Ba phase đầu không tiêu đồng API nào. Tới cuối Phase 4 đã nhìn thấy trang song
song thật và biết chế độ `overlay` có hợp cuốn sách này không, trước khi cam
kết tiền cho việc dịch. Nếu nó vỡ thì đảo thứ tự: làm Phase 6 trước, dùng
`reflow` cho cả text-PDF.

Thứ tự Phase 6 trước Phase 7 là có chủ ý. Bộ render `reflow` và khâu OCR là hai
nguồn lỗi hoàn toàn khác nhau; làm `reflow` trước trên một cuốn text-PDF đã
biết rõ nghĩa là khi đụng vào sách scan thì chỉ còn đúng một biến mới.

Phase 8 để ngỏ: so sánh nhiều provider trên cùng một khoảng trang, và ghép lai
`overlay`/`reflow` theo từng trang cho những trang chữ quá dày.

## 11. Rủi ro

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Bố cục phức tạp làm bóc chữ sai | `inspect` và `--dry-run` cho trang lệch | Phát hiện ở Phase 3–4, trước khi tiêu tiền; chuyển trang đó sang `reflow` nếu diện rộng |
| Quá nhiều trang phải thu chữ dưới 75% | Báo cáo `--probe` | Bật `--compress`, hoặc chuyển những trang đó sang `reflow` |
| PDF có sẵn lớp OCR nhưng sai bét | `init` đo tỉ lệ ký tự rác | Cảnh báo và đề nghị OCR đè lại — trường hợp này làm hỏng nhiều tool dịch sách nhất vì lớp text *có* tồn tại nên tool tin luôn |
| Font thiếu glyph tiếng Việt | Ô vuông rỗng trên trang dịch | Luôn nhúng font riêng, không dùng font của sách gốc |
| Redaction khoét mất ảnh | Mảng trắng trên trang dịch | Tắt chế độ xoá ảnh khi redaction |
| Đổi provider giữa chừng làm lệch giọng văn | Đọc thấy văn phong đổi | `chunks` ghi provider và model; dịch lại khoảng trang đó bằng provider cũ |
| OCR đọc sai chữ, bản dịch thành vô nghĩa | Đọc 20 trang đầu của sách scan | Bản gốc nằm ngay bên trái để đối chiếu; `inspect` cho xem chữ OCR ra trước khi dịch |
| Dò nhầm vùng ảnh trong sách scan | Trang dịch chừa chỗ trống sai kích thước hoặc sai chỗ | Kiểm ở `inspect`, trước khi dịch; sai sót chỉ ảnh hưởng chỗ trống, không mất chữ |

## 12. Cách viết code

Những phần khó nhất lại là hàm thuần, không cần PDF thật và không cần gọi API:
ghép mảnh thành đoạn, dò header/footer, tính bậc thang thu nhỏ, cắt đoạn dịch
trả về hai khung. Viết test trước cho đúng mấy hàm này — chạy trong mili giây,
và chúng chính là chỗ bug sẽ nằm. Phần đụng PyMuPDF và đụng mạng thì mỏng, bọc
quanh cái lõi đã được kiểm chứng.

Giữ nguyên nguyên tắc của Phase 1: hàm thuần tách khỏi hàm đụng thư viện ngoài,
như `extract_from_html` và `apply_to_html` hiện đang tách khỏi phần ebooklib.

## 13. Phụ thuộc mới

- **PyMuPDF** — bóc chữ, redaction, đặt chữ, ghép trang. Giấy phép AGPL; dùng
  cá nhân không phát hành thì không vướng.
- **OCRmyPDF** cộng **Tesseract** — chỉ cần cho sách scan, ở Phase 6.
- Một font có đủ dấu tiếng Việt, nhúng kèm repo hoặc tải khi cài.
