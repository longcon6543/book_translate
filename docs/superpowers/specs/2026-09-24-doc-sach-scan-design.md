# Phase 8B — Đọc sách scan đúng: dòng nghiêng, cột, mục lục, vùng hình

**Spec mẹ:** [2026-09-21-pdf-song-ngu-design.md](2026-09-21-pdf-song-ngu-design.md).
**Liên quan:** [2026-09-23-gom-dong-sach-scan-design.md](2026-09-23-gom-dong-sach-scan-design.md)
(Phase 7, ghép mảnh OCR), [2026-09-24-dan-trang-theo-thu-tu-design.md](2026-09-24-dan-trang-theo-thu-tu-design.md)
(Phase 8A, bộ dàn trang — 8B thêm ô "ảnh" vào đó).

## 1. Vấn đề

Người dùng xem bản xuất harmonics và báo: trang 14, 45 và nhiều trang khác
không có bản dịch; mục lục nhảy chữ; ký hiệu chiêm tinh trong hình hiện thành
chữ rác. Nghiệm thu 8A thêm: 9 trang chỉ mục rơi về bố cục dự phòng.

Nguyên nhân, đo trên `projects/harmonics/source.pdf` (484 trang scan có lớp OCR):

| Lỗi | Nguyên nhân | Số đo |
|---|---|---|
| Mất chữ | `_doc_trang` bỏ mọi dòng có `dir` khác đúng `(1, 0)`. Trang scan hơi nghiêng nên OCR ghi dòng lệch dưới 1° | Dòng lệch < 10°: 462 dòng, **16.969 ký tự**; ≥ 10°: 276 dòng, 1.164 ký tự (nhãn xoay trong hình). 59 trang mất ≥ 100 ký tự; trang 14 mất trắng, 45 mất gần nửa |
| Chỉ mục 1 cột | `detect_columns` đòi khe dọc KHÔNG dòng hẹp nào bắc qua; OCR để 1–2 mảnh lấn khe | 14/14 trang chỉ mục (469–482) có đúng 1–2 dòng bắc qua khe |
| Chỉ mục thành khối rộng cả trang | Hệ quả: cả trang ghi `col 0`, `ghep_manh_cung_hang` (Phase 7) nối mục cột trái với mục cột phải cùng hàng | 9 trang rơi dự phòng ở 8A |
| Mục lục nhảy chữ | Số trang tách thành cột riêng; dòng mục gom thành một đoạn | Trang 9–10: 21 mảnh số cùng hàng với chữ |
| Chữ rác trong hình | OCR đọc nét vẽ và ký hiệu thành chữ | Khối kiểu "K Ores", "Bis eas" cỡ tiêu đề |

**Astrology** (text-PDF 925 trang): 0 dòng lệch, 0 trang scan.

## 2. Mục tiêu

Khâu đọc sách scan không mất chữ thật, nhận đúng cột chỉ mục, giữ mỗi mục
lục một khối, và biến vùng hình vẽ thành ô "ảnh" không dịch — mà **kết quả
ingest của text-PDF không đổi một byte**.

## 3. Phạm vi

**Trong phạm vi:** `ingest/pdf_text.py`, `pdf_layout.py`, module dò hình mới,
bộ dựng trang `reflow` vẽ ô "ảnh".

**Ngoài phạm vi:**
- Bảng số liệu in máy tính (trang 63, 410, 460): **giữ nhận diện dạng bảng
  như trước** — người dùng chọn.
- Hình chỉ gồm ký hiệu, không có nét vẽ (trang 60, 104) và hình nét quá mảnh
  (hai hình bên của trang 22): không nhận được; rác OCR ở đó còn như hiện nay.
- Tự OCR (RapidOCR): việc C sau này.
- Chế độ `overlay`: không vẽ ô "ảnh" (ảnh gốc vẫn còn trên trang).

## 4. Quyết định

Mọi quyết định dưới đây **chỉ áp cho trang scan** (`_la_trang_scan`: một ảnh
phủ ≥ 90% trang), trừ E1 vốn không đổi được gì trên text-PDF.

**E1 — Nhận dòng lệch dưới 10°.** `_doc_trang` nhận dòng có góc
`|atan2(dy, dx)| < 10°` và `dx > 0` (người dùng chọn 10°). Dòng ≥ 10° vẫn bỏ
có kiểm soát. Text-PDF không có dòng lệch nào (đo astrology: 0), nên luật này
không đổi được kết quả của nó; test golden canh điều đó.

**E2 — Dò hai cột bằng bằng chứng từng hàng.** Trên trang scan mà
`detect_columns` (không đổi) không tìm ra cột, chạy thêm hàm mới
`tim_khe_hai_cot`: xét các dòng thân bài (cần ≥ 12 dòng), gom hàng theo `y0`
lệch ≤ 3pt; với mỗi vị trí khe `x` trong 30–70% bề rộng trang (thử tại mép
phải mỗi dòng + 0,5pt), đếm số hàng **có chữ ở cả hai bên khe mà không dòng
nào của hàng bắc qua**; khe hợp lệ khi số dòng bắc qua ≤ `max(2, ⌈5% số
dòng⌉)`. Nhận khe có nhiều hàng tách nhất nếu số đó ≥ **60%** số hàng; mọi
dòng có `x0 ≥ x` vào cột 1.

*Vì sao không nới `detect_columns`:* đo thật, cho phép 2 dòng bắc qua trong
`detect_columns` chỉ bắt 10/14 trang chỉ mục và chia sai 10 trang khác —
trang hình (mảnh rác quanh hình giả làm cột) và trang Ghi chú 374 (một cột;
chia sai là đảo thứ tự đọc). Bằng chứng từng hàng: 14/14 trang chỉ mục, và
ngoài chỉ mục chỉ 55 (vốn đã 2 cột), 63, 410, 460 (bảng in máy tính nhiều
cột — đúng là nhiều cột). Kết quả không đổi khi ngưỡng đi từ 40% tới 60%.

**E3 — Nối số trang vào hàng.** Sau `ghep_manh_cung_hang`, trên trang scan:
mảnh mà toàn bộ chữ là một số ả-rập 1–3 chữ số hoặc số La Mã (`i v x l c`, ≤ 6
ký tự), nằm cùng hàng (chồng dọc > 60% chiều cao nhỏ hơn) với một dòng ở bên
trái nó, được nối vào cuối dòng đó (cách một dấu cách); dòng ghép mang khung
hợp. Chọn dòng bên trái gần nhất **cùng cột** — trừ khi **quá nửa** cột của
mảnh số là mảnh số (cột số trang của mục lục), khi đó được nối sang cột trái.
*Sửa khi nghiệm thu:* bản đầu đòi cột "toàn số" và nối 0 mảnh trên mục lục
thật — OCR đọc sai vài số trang ("5a8"). Đo thật: cột số mục lục 75–88% là số,
cột phải chỉ mục 0–13%. Không
có luật cùng cột thì dòng chỉ có số ở đầu cột phải chỉ mục bị nối vào mục cột
trái. Mảnh số ở vùng lề (số trang chạy) không xét.

**E4 — Mục lục: mỗi hàng có số trang là cuối một đoạn.** Nếu trên một trang
E3 nối **≥ 3** hàng thì trang đó là mục lục hoặc chỉ mục: mỗi dòng đã được nối
số được đánh dấu `ket_doan`, và `group_paragraphs` tách đoạn ngay sau nó. Mục
dài hai dòng (số ở dòng thứ hai) vẫn là một khối. Dưới 3 hàng (thân bài có số
lẻ loi) thì chỉ nối, không tách đoạn — tách ở đó là cắt câu.

**E5 — Dò vùng hình từ ảnh scan.** Module thuần mới nhận ảnh xám của trang
(bytes, rộng, cao) và các dòng OCR, trả về list khung vùng hình. Tham số đã đo:

| Bước | Luật |
|---|---|
| Ảnh | chụp 72 dpi, thang xám; ngưỡng mực = trung vị độ xám − 50 |
| Hạt nhân | thành phần liên thông (4 hướng) cao ≥ 25pt, không nằm trong dải mép 4% ngang / 3% dọc (bóng gáy sách) |
| Gộp | hạt nhân cách nhau ≤ 20pt gộp thành một vùng |
| Nở | vùng nuốt thành phần mực bất kỳ trong phạm vi 12pt, lặp tới khi hết, TRỪ thành phần có tâm nằm trong dòng được bảo vệ hoặc chạm dải mép 2% ngang |
| Dòng được bảo vệ | (a) chú thích: chữ bắt đầu bằng `Figure N` / `Fig. N`, cùng các dòng tiếp theo nằm ngay dưới nó (khoảng cách ≤ 0,8 chiều cao dòng, chồng ngang); (b) văn xuôi: ≥ 80% là chữ cái hoặc dấu cách, và dài ≥ 25 ký tự hoặc có ≥ 3 từ (từ = ≥ 2 chữ cái) |
| Cắt mép | dòng được bảo vệ chạm vùng: tâm nằm nửa dưới vùng thì kéo đáy vùng lên trên dòng, nửa trên thì kéo đỉnh xuống dưới dòng; vùng còn cao < 25pt thì bỏ |

Đo trên harmonics: 153 trang có vùng hình; 0 chú thích và 0 dòng văn xuôi
nằm trong vùng. So với danh sách trang có chú thích "Figure N.N": bắt được
147/171, 8 trang dò ra mà không có chú thích đều là hình thật (chú thích xoay
dọc, bìa); các trang "sót" gồm trang thân bài có câu bắt đầu bằng "Figure
2.5 shows…", hình chỉ gồm ký hiệu, và vòng tròn nét mảnh. Thời gian ~0,2 s/trang.

**E6 — Bỏ rác OCR trong vùng hình.** Dòng OCR có ≥ 50% diện tích nằm trong
một vùng hình thì bỏ **trước** khi ghép mảnh và gom đoạn — trừ chú thích và
dòng văn xuôi dài ≥ 40 ký tự (luôn giữ). Đo: bỏ 303 dòng, 1.093 ký tự (trung
bình 4 ký tự/dòng — đúng kiểu mảnh vụn).

**E7 — Vùng hình lưu trong `meta`, không trong `blocks`.** Khoá
`vung_hinh`, giá trị JSON `{"<page_no>": [[x0, y0, x1, y1], ...]}`, chỉ ghi khi
có ít nhất một vùng. Không thêm khối nào: chia chunk, dịch, `status`, `reset`,
chi phí và EPUB không đổi; hình không tốn token.

**E8 — Ô "ảnh" khi xuất `reflow`.** `pdf_reflow.write` đọc `vung_hinh` và
chèn mỗi vùng vào danh sách khối của trang dưới dạng
`{"kind": "hinh", "bbox": ..., "id": None}`, đặt trước khối đầu tiên có
`bbox.y0` lớn hơn `y0` của vùng (giữ thứ tự đọc theo độ cao).

- **Bộ dàn (8A):** ô giữ bề rộng gốc kẹp vào khung chữ (không nới/kéo như D4);
  cao `max(30, 0,5 · cao gốc) · s`; neo ở `y0` gốc và dàn cùng các khối chữ
  theo `xep_doc` — không đè chữ.
- **Bộ theo vị trí (dự phòng):** ô nằm đúng khung gốc đã kẹp vào trang.
- **Hình vẽ:** viền xám nhạt 0,5pt, chữ "ảnh" giữa ô, cỡ `than`.
- Ô không vào `ghi_nhan` (không có trong thống kê, không gắn cờ).

## 5. Kiến trúc

```
vung_hinh.py                  (mới, THUẦN — không import pymupdf)
    NGUONG_MUC = 50; CAO_HAT = 25.0; GOP_HAT = 20.0; SAT = 12.0
    MEP_NGANG = 0.04; MEP_DOC = 0.03; MEP_NUOT = 0.02
    thanh_phan(xam: bytes, rong: int, cao: int, ti_le: float) -> list[khung]
    la_chu_thich(text) -> bool; la_van_xuoi(text) -> bool
    dong_bao_ve(dong: list[(khung, text)]) -> list[khung]
    tim_vung(thanh_phan, dong, rong_trang, cao_trang) -> list[khung]
    loc_dong_trong_hinh(dong, vung) -> list[bool]   # True = giữ

pdf_layout.py
    tim_khe_hai_cot(lines, page_width, page_height) -> float | None  # E2
    noi_so_trang(lines, page_height) -> int     # E3 + đánh dấu E4, trả số hàng đã nối
    Line.ket_doan: bool = False                  # E4
    group_paragraphs: tách đoạn sau dòng ket_doan

ingest/pdf_text.py
    _doc_trang: E1
    load(): trang scan -> chụp xám 72 dpi -> vung_hinh.tim_vung -> E6 lọc dòng
            -> detect_columns -> (không ra cột) tim_khe_hai_cot -> ghep
            -> noi_so_trang -> gom đoạn
    Ingested thêm `meta: dict` -> init ghi `vung_hinh`

render/pdf_reflow.py
    write: chèn ô hình (E8); trang_reflow và trang_theo_vi_tri vẽ ô
```

Luật tầng: `vung_hinh.py` và `pdf_layout.py` không import pymupdf; chỉ
`ingest/pdf_text.py` chụp ảnh và đưa bytes vào.

## 6. Test

Không test nào gọi mạng. 370 test hiện có xanh, vân tay golden giữ nguyên.
Helper mới `trang_scan_gia(path, hinh, dong_ocr)`: vẽ hình (đường, vòng tròn)
và chữ lên trang nháp, chụp thành ảnh phủ kín trang mới, đặt lớp chữ OCR vô
hình (`render_mode=3`) đè lên.

- E1: dòng lệch 5° được nhận, 15° bị bỏ
- E2: trang 2 cột có 1 dòng bắc qua khe được nhận; trang một cột có dòng
  ngắn (kiểu Ghi chú) không bị chia; text-PDF không chạy luật này
- E3: mảnh số cùng hàng được nối; mảnh số ở lề không bị nối; số La Mã được nối
- E4: trang 3 hàng có số thành 3 khối (kể cả mục 2 dòng); trang 1 hàng có số
  không tách đoạn
- E5: vòng tròn → 1 vùng; trang chỉ có chữ → 0 vùng; bóng gáy ở mép → 0 vùng;
  chú thích ngay dưới hình nằm ngoài vùng
- E6: rác trong vùng bị bỏ; chú thích và văn xuôi dài được giữ
- E7: `init` ghi `vung_hinh` vào meta; text-PDF không có khoá này
- E8: xuất reflow có chữ "ảnh", ô cao 50% gốc (tối thiểu 30pt), không đè chữ;
  trang dự phòng cũng vẽ ô

## 7. Nghiệm thu

Không tốn token. `init` harmonics vào project **mới** `projects/harmonics-8b`;
`projects/harmonics` và bản dịch của nó không bị đụng tới.

| Chỉ số (so với `projects/harmonics` hiện tại) | Ngưỡng |
|---|---|
| Ký tự nguồn cả cuốn | tăng **≥ 15.000** |
| Trang 14 | có khối chữ |
| Trang 45 | **≥ 2.300** ký tự nguồn |
| Trang 469–482 dò ra 2 cột | **14/14** |
| Trang 9–10: dòng đã nối số trang | **≥ 21** |
| Trang scan dò ra ≥ 2 cột ngoài 469–482 | ghi số vào ledger, soát bằng mắt ≥ 5 trang — không trang thân bài một cột nào bị chia cột |
| Trang có vùng hình | **≥ 150** |
| Khối chú thích bắt đầu bằng "Figure N" | **không ít hơn** hiện tại |
| Astrology init lại vào thư mục tạm: `(page_no, pos, tag, kind, src_html, bbox, line_bboxes, layout)` mọi khối | **giống hệt** DB hiện có |
| `export --mode reflow --dry-run` harmonics-8b: trang dự phòng | **≤ 5** |
| Thời gian `init` harmonics | ghi vào ledger |

Sau đó gửi người dùng ảnh khổ mục lục (10), trang 14, 45, một trang chỉ mục và
vài trang hình của bản xuất thử.

**Dịch thử** (tốn token — chỉ chạy khi người dùng cho phép): chép
`glossary.txt` từ harmonics, dịch `harmonics-8b` trang 1–30 bằng
`deepseek-flash`, xuất `reflow` trang 1–30. Người dùng xem rồi mới quyết dịch
cả cuốn (~$0,7).

## 8. Rủi ro

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Vùng hình nuốt chữ thật | chú thích/văn xuôi nằm trong vùng | Dòng bảo vệ + cắt mép; nghiệm thu đếm chú thích; E6 luôn giữ văn xuôi ≥ 40 ký tự |
| Dòng lệch lớn làm khung dòng cao, xáo thứ tự hàng | dòng nghiêng 5–10° gom sai | Đo: dòng 3–10° chỉ có 7 dòng, 15 ký tự — gần như mọi dòng nhận thêm lệch < 1° |
| Luật hai cột chia sai trang một cột | trang một cột ra 2 cột | Chỉ trên trang scan khi `detect_columns` không ra cột; đòi ≥ 60% hàng tách; nghiệm thu đếm số trang 2 cột ngoài chỉ mục (đo trước: 55, 63, 410, 460) và soát bằng mắt |
| E3 nối số của bảng số liệu vào hàng | bảng 460 thay đổi | Chấp nhận: bảng vẫn là chữ, cùng hàng nối lại là đúng hàng |
| Chụp ảnh làm `init` chậm | ~0,2 s/trang trang scan | Chấp nhận; text-PDF không chụp |
