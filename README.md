# booktrans

Dịch sách tiếng Anh sang tiếng Việt bằng mô hình AI (DeepSeek, Claude, hay bất
kỳ dịch vụ nào nói giao thức OpenAI). Chạy bằng dòng lệnh, dịch theo từng
khoảng trang, dừng giữa chừng rồi chạy lại vẫn tiếp tục được.

| Sách nguồn | Bản xuất |
|---|---|
| EPUB | EPUB tiếng Việt (thêm `--bilingual` để có bản song ngữ) |
| PDF có chữ | PDF khổ đôi: trang gốc bên trái, trang dịch bên phải, giữ ảnh và bố cục |
| PDF sách scan có sẵn lớp chữ OCR | PDF khổ đôi, trang dịch dựng lại sạch, hình thành ô "ảnh" |
| PDF sách scan **chưa** có lớp chữ | tool tự OCR khi `init` (RapidOCR, chạy offline) rồi xử lý như trên |

## Yêu cầu

- **Python 3.12.** Thư viện OCR (`rapidocr-onnxruntime`) chưa chạy trên Python
  3.13 trở lên. Trên Python mới hơn tool vẫn cài được và dịch EPUB/PDF có chữ,
  chỉ không tự OCR được sách scan chưa có lớp chữ.
- Khoảng **450MB** dung lượng cho thư viện (phần lớn là OCR: onnxruntime,
  OpenCV, numpy, mô hình nhận dạng).
- Khoá API của một nhà cung cấp mô hình (xem mục Cấu hình).
- Font đủ dấu tiếng Việt để xuất PDF: tool tự tìm Times New Roman / Georgia
  (macOS), Times New Roman / Arial (Windows), DejaVu / Liberation (Linux).
  Máy không có các font này thì đặt `BOOKTRANS_FONT` (xem `.env.example`).

## Cài đặt

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip ...
.venv/bin/pip install -r requirements-dev.txt      # chỉ cần nếu chạy test
```

Các lệnh bên dưới viết `python` cho gọn — hãy dùng `.venv/bin/python`
(Windows: `.venv\Scripts\python`), hoặc kích hoạt venv trước.

## Cấu hình

Chép file mẫu rồi điền khoá vào khối nhà cung cấp bạn dùng:

```bash
cp .env.example .env
```

`.env` đã nằm trong `.gitignore`; đừng commit khoá thật. Tool **không tự đọc**
`.env` — nạp nó vào shell trước khi chạy `translate`:

```bash
set -a && . ./.env && set +a
```

Ba cách cấu hình phổ biến (đã có sẵn trong `.env.example`):

| Nhà cung cấp | Biến cần đặt | Tên model ví dụ |
|---|---|---|
| DeepSeek (API gốc) | `BOOKTRANS_PROVIDER=openai`, `OPENAI_API_KEY`, `BOOKTRANS_BASE_URL=https://api.deepseek.com` | `deepseek-flash` |
| OpenRouter | `BOOKTRANS_PROVIDER=openai`, `OPENAI_API_KEY`, `BOOKTRANS_BASE_URL=https://openrouter.ai/api/v1` | `deepseek/deepseek-v4-flash` |
| Anthropic Claude (mặc định) | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |

Mỗi nhà cung cấp đặt tên model khác nhau: tên model luôn truyền bằng
`--model` trên dòng lệnh `translate`. `status` ghi lại chunk nào dịch bằng
model nào.

## Quy trình

```bash
# 1. Tạo project (sách scan chưa có chữ: tự OCR, ~3 giây/trang, có in tiến độ)
python cli.py init sach.pdf                       # -> projects/sach/

# 2. Gom thuật ngữ hay gặp, duyệt rồi dán sang glossary.txt
python cli.py glossary projects/sach --top 200

# 3. Sửa style.md (giọng văn, xưng hô) và glossary.txt trong thư mục project

# 4. Soi xem tool hiểu sách thế nào — chưa tốn token
python cli.py inspect projects/sach --pages 1-20
python cli.py export  projects/sach --pages 1-20 --dry-run

# 5. Dịch thử một khúc rồi đọc
set -a && . ./.env && set +a
python cli.py translate projects/sach --pages 1-30 --model deepseek-flash
python cli.py export    projects/sach --pages 1-30
python cli.py status    projects/sach        # tiền đã tiêu + ước tính cả cuốn

# 6. Ưng thì dịch hết (dừng giữa chừng, chạy lại sẽ dịch tiếp phần còn lại)
python cli.py translate projects/sach --model deepseek-flash

# 7. Sửa tay đoạn chưa ưng rồi xuất cả cuốn
python cli.py edit   projects/sach --block 1423
python cli.py edit   projects/sach --block 1423 --set "bản dịch mới"
python cli.py export projects/sach
```

**Sách scan** (kể cả sách tool tự OCR) thì xuất bằng `--mode reflow`:

```bash
python cli.py export projects/sach --mode reflow
```

`overlay` (mặc định cho PDF) thay chữ ngay trên bản sao trang gốc — hợp với
PDF có chữ. Trên sách scan chữ gốc là ảnh nên không xoá được; `reflow` dựng
trang dịch mới: các đoạn xếp đúng thứ tự từ trên xuống, neo theo vị trí gốc,
không bao giờ đè nhau; hình thành ô "ảnh" (nửa trái khổ đôi vẫn hiện hình gốc).

`translate --pages` chọn mọi chunk *chạm* vào khoảng trang, nên vùng thực dịch
có thể rộng hơn vài trang — lệnh báo con số đó trước khi chạy.
`reset --pages 150-169 --yes` xoá bản dịch một khoảng trang để dịch lại.

## Xử lý sự cố

| Thông báo | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Error code: 402 … Insufficient Balance` | Tài khoản API hết tiền | Nạp tiền hoặc đổi khoá trong `.env`, chạy lại đúng lệnh `translate` — chunk đã dịch được giữ, tool dịch tiếp phần còn lại |
| `Error code: 404 … model does not exist` | Tên model không có ở nhà cung cấp đang cấu hình | Kiểm `BOOKTRANS_BASE_URL` và `--model` khớp nhau (bảng ở mục Cấu hình) |
| `chunk N lỗi … bị cắt do hết token` | Model trả thiếu đoạn 3 lần liền | Chạy lại đúng lệnh `translate` — chunk lỗi chưa xong nên được thử lại; thường lần sau là được |
| `cần OCR, nhưng máy chưa cài thư viện OCR` | Thiếu `rapidocr-onnxruntime` hoặc Python ≥ 3.13 | `pip install -r requirements.txt` trên Python 3.12 |
| `font … thiếu ký tự tiếng Việt` / `không thấy file font` | Máy không có font đủ dấu | Đặt `BOOKTRANS_FONT` (một file, hoặc ba file thường/đậm/nghiêng ngăn bằng `:` — Windows dùng `;`) |
| `N đoạn bị gắn cờ` trong `status` | Bản dịch thiếu số hay thiếu thuật ngữ trong glossary | Xem bằng lệnh `edit` mà `status` in sẵn, sửa tay nếu cần |

## Chi phí

Đặt `PRICE_IN` và `PRICE_OUT` (USD trên 1 triệu token, lấy từ trang giá của
nhà cung cấp) để `status` tính tiền:

```bash
export PRICE_IN=0.28 PRICE_OUT=0.42      # ví dụ — thay bằng giá thật của model
```

Token cache tính riêng, mặc định 0,1x giá vào khi đọc và 1,25x khi ghi; đổi
bằng `PRICE_CACHE_READ` và `PRICE_CACHE_WRITE`. Style và glossary đi kèm mọi
chunk dưới dạng cache đọc. Sau khi dịch thử một khúc, `status` ngoại suy chi
phí cả cuốn từ số ký tự đã dịch thật. Ví dụ thật: một cuốn sách scan 484 trang
(~840.000 ký tự) bằng `deepseek-flash` tốn khoảng $0,7.

## Cách hoạt động

- **Đọc sách** (`init`): EPUB lấy từng khối HTML lá. PDF có chữ dựng lại đoạn
  văn từ các dòng (cột, tiêu đề, chú thích, header/footer lặp bị bỏ). Sách
  scan còn được: nhận dòng OCR hơi nghiêng (< 10°), ghép mảnh OCR bị cắt trên
  cùng một hàng, nhận chỉ mục hai cột, nối số trang mục lục vào đúng mục, dò
  vùng hình từ ảnh scan và bỏ chữ rác OCR trong hình.
- **Dịch** (`translate`): gửi từng chunk dạng `<seg id="..">`, nhận lại đúng
  id nên ghép chính xác từng đoạn và giữ in nghiêng, liên kết. Mỗi chunk kèm
  3 đoạn liền trước để giữ mạch và xưng hô. Đoạn thiếu, lệch thẻ, ngắn bất
  thường thì dịch lại tối đa 3 lần; hết lượt vẫn lỗi thì gắn cờ.
- **Trạng thái** nằm trong `projects/<sách>/project.db` (SQLite).
  `init --force` tạo lại project và **xoá mọi bản dịch đã trả tiền** của nó —
  muốn thử cách đọc sách khác thì `init` vào thư mục mới bằng `--dir`.

## Giới hạn đã biết

- Sách scan: hình chỉ gồm ký hiệu (không có nét vẽ) không được nhận thành ô
  "ảnh", chữ rác OCR ở đó còn lại; số trang bị OCR đọc sai thì tool không sửa.
- Sách scan có sẵn chút lớp chữ (ví dụ dấu website in trên mọi trang) thì không
  được tự OCR — tool coi là sách đã có lớp chữ.
- OCR chỉ đọc chữ, không biết in đậm / in nghiêng.
- EPUB: thẻ khối vừa có chữ trực tiếp vừa chứa khối con thì phần chữ trực tiếp
  không được dịch. EPUB có DRM không đọc được.
- Glossary đi vào prompt ở mọi chunk; glossary hàng trăm mục sẽ tốn token.

## Chạy test

```bash
.venv/bin/python -m pytest tests/ -q
```

Không test nào gọi mạng. `tests/golden/` giữ vân tay của đầu ra EPUB — nếu nó
đổi mà bạn không cố ý đổi, nghĩa là vừa có gì đó hỏng.
