# Phase 8A — Dàn trang dịch theo thứ tự đoạn, neo vị trí gốc

**Spec mẹ:** [2026-09-21-pdf-song-ngu-design.md](2026-09-21-pdf-song-ngu-design.md).
**Thay thế một phần:** [2026-09-23-reflow-design.md](2026-09-23-reflow-design.md) —
quyết định **R1 (giữ đúng vị trí từng khối) bị bãi bỏ** cho chế độ `reflow`.
R2, R3, R4, R5, R6 còn hiệu lực trong phạm vi nói ở mục 5.

Phase 8 gồm hai phần, làm theo thứ tự người dùng đã chọn:
**8A** (spec này) — bộ dàn trang; **8B** (spec sau) — sửa khâu đọc sách scan:
dòng nghiêng dưới 10°, mục lục, dò vùng hình và bảng số liệu thành khối "hình".

## 1. Vấn đề

Người dùng xem bản xuất `reflow` cả cuốn harmonics (484 khổ) và báo: **đè chữ
xảy ra rất thường xuyên**.

Nguyên nhân: `reflow` đặt mỗi đoạn dịch vào đúng khung của đoạn gốc. Khung gốc
của sách scan đến từ OCR và chồng lên nhau — đo ở Phase 7 còn 732 cặp khung
chồng. Chữ Việt đặt vào hai khung chồng nhau thì đè lên nhau; không có cách
nào vá được trong khuôn khổ "giữ đúng khung".

## 2. Mục tiêu

Trang dịch **không bao giờ có hai khối đè nhau**, các đoạn xuất hiện **đúng
thứ tự** bản gốc, và vẫn **gióng hàng** với trang gốc ở nửa trái khi còn chỗ.

Đo thử trên bản dịch harmonics hiện có (dàn hết chữ Việt của trang theo thứ
tự, thân bài 9,1pt, giãn dòng 1,2): lề 36pt thì 466/480 trang vừa không cần
co, trung vị 100%, 9 trang cần co dưới 75%; lề 18pt thì 4 trang dưới 75%.
Các trang tệ nhất (63, 460, 410) là trang hình và bảng in máy tính mà OCR
đọc thành hàng trăm mảnh vụn — việc của 8B.

## 3. Phạm vi

**Trong phạm vi:** bộ dựng trang mới cho `--mode reflow`; tính cỡ thân bài
cả cuốn; đếm trang dự phòng; khối chưa dịch không tính vào thống kê tràn
(lỗi nhỏ 6a).

**Ngoài phạm vi (8B):** vẽ ô "ảnh" cho vùng hình và bảng số liệu; bỏ rác OCR
trong hình; đọc dòng nghiêng; mục lục. Trước khi có 8B, vùng hình trên trang
dịch là khoảng trắng — tự có nhờ neo vị trí gốc — và rác OCR trong hình vẫn
còn.

**Không đổi:** `overlay` (text-PDF) và vân tay `tests/golden/`. Không đổi DB,
không cần init lại, không tốn token.

## 4. Quyết định

**D1 — Dàn theo thứ tự `pos`, neo độ cao gốc.** Mỗi khối đặt ở
`y = max(y0 gốc, đáy mọi khối trước nó CÓ CHỒNG THEO CHIỀU NGANG + khoảng cách)`.
Còn chỗ thì khối nằm đúng độ cao gốc; khối trước dài ra thì đẩy khối sau
xuống. Hai khối chồng ngang không bao giờ chồng dọc, nên không bao giờ đè.
Khối ở cột khác (không chồng ngang) không đẩy nhau.

*Bổ sung khi nghiệm thu (Task 4):* bản đầu đẩy mỗi khối xuống dưới khối liền
trước bất kể cột. Chỉ mục 2 cột ở cuối harmonics (trang 470-480) — nơi dò cột
không bắt được, cả trang ghi `col 0` — bị xếp cột phải xuống dưới cột trái và
rơi dự phòng: 13 trang, vượt ngưỡng 10. Với trang một cột, luật mới cho kết
quả y hệt luật cũ.

**D2 — Khung chữ là trang trừ lề 22pt bốn phía.** Người dùng cho phép nới lề.
Cột chữ gốc của harmonics rộng khoảng 277pt (x0 trung vị 29, x1 trung vị 306
trên trang rộng 350); khung mới rộng 306pt. 22pt nằm giữa hai mức đã đo
(18pt và 36pt) và vẫn chừa lề in.

**D3 — Cỡ chữ theo loại khối, tính từ cỡ thân bài cả cuốn.**
`than` = trung vị `layout.size` của các khối `kind='text'` cả cuốn
(harmonics: 9,1pt).

| kind | cỡ |
|---|---|
| `text` | `than` |
| `heading` | `layout.size` kẹp vào `[than, 2·than]` |
| còn lại (`caption`, `table`, `formula`) | `layout.size` kẹp vào `[0,8·than, than]` |

Cỡ OCR nhiễu từng dòng; ép thân bài một cỡ làm trang đều. Kẹp dưới 0,8·than
cũng chặn luôn các dòng cỡ vài pt do OCR (lỗi nhỏ 7b trên trang dịch).

**D4 — Căn ngang.** Khối có bề rộng gốc ≥ 60% bề rộng khung chữ thì kéo ra đủ
bề rộng khung. Khối hẹp hơn giữ bề rộng và vị trí ngang gốc, kẹp vào khung —
tiêu đề căn giữa vẫn ở giữa. Khối hẹp dưới 25% bề rộng khung được nới ra
đúng 25%, giữ tâm ngang gốc: đo thật 519 khối harmonics rộng dưới 25% và 236
khối dưới 10% — giữ nguyên vài pt là ép chữ Việt thành cột một chữ, cao hơn
trang, kéo cả trang về dự phòng.

**D5 — Thang dàn một trang, vừa là dừng.** Hệ số co `s` áp **chung** cho mọi
khối trên trang, đi qua các bậc `1,00 · 0,95 · 0,90 · 0,85 · 0,80 · 0,75`.
Ở mỗi bậc:
1. **Neo** (D1). Khối cuối không vượt đáy khung → xong.
2. **Đẩy ngược từ đáy**: đi từ khối cuối lên, mỗi khối chỉ nâng vừa đủ để
   nó và các khối sau nó (chồng ngang) còn vừa khung; khối không cần nâng giữ
   nguyên neo. Không khối nào lên quá đỉnh khung → xong.

   *Sửa sau review toàn nhánh:* bản đầu ở bước này dồn khít CẢ trang từ đỉnh.
   Đo trên harmonics: 27/468 trang bị dồn chỉ vì một dòng chân trang hay chú
   thích neo dưới lề (y0 ≈ 538–543, đáy khung 524,8) — khối dời tới 300pt,
   mất gióng hàng dù còn thừa chỗ. Đẩy ngược hỏng đúng khi có một chuỗi khối
   chồng ngang dài hơn khung, cũng là lúc dồn khít hỏng, nên số trang rơi
   xuống bậc co sau không đổi.
3. Sang bậc kế.

Khoảng cách giữa hai khối: `0,4 · than · s`. Giãn dòng 1,2 (mức đã đo).

**D6 — Trang dự phòng.** Không vừa cả ở `s = 0,75` thì dựng trang bằng bộ
dựng theo vị trí hiện nay (đổi tên thành `trang_theo_vi_tri`, hành vi giữ
nguyên, gồm cả R3 và R4, trừ đúng một điểm: D7 áp cho nó luôn). Trang đó được đếm vào `trang_du_phong` và in ra ở
`export`. Chữ dưới 75% khó đọc; bố cục theo vị trí ở đó là thứ ít tệ nhất,
và các trang này chủ yếu là trang hình mà 8B sẽ thay bằng ô "ảnh".

**D7 — Khối chưa dịch.** Hiện chữ Anh gốc như trước (R4 vẫn đúng: khoảng
trống im lặng tệ hơn chữ Anh). Chúng được dàn như khối thường nhưng **không
ghi vào `ghi_nhan`**, nên không làm phồng thống kê tràn và không bị gắn cờ
`overflow` (6a).

**D8 — Trang không có khối nào** ra trang trắng đúng khổ (R5 giữ nguyên).
Không chép gì từ ảnh gốc (R2 giữ nguyên).

## 5. Kiến trúc

```
render/dan_trang.py          (mới, THUẦN — không import pymupdf)
    LE = 22.0
    THANG_S = (1.00, 0.95, 0.90, 0.85, 0.80, 0.75)
    TI_LE_KHOANG = 0.4
    TI_LE_KHOI_RONG = 0.6
    TI_LE_KHOI_HEP_MIN = 0.25
    co_khoi(kind, size, than) -> float                     # D3
    khung_ngang(x0, x1, trai, phai) -> (float, float)      # D4
    xep_doc(neo: list[float], cao: list[float],
            tren, duoi, khoang,
            ngang: list[(x0, x1)] | None = None) -> list[float] | None   # D1 + D5 bước 1-2

render/pdf_reflow.py
    trang_theo_vi_tri(...)      # = trang_reflow hiện nay, đổi tên; chỉ thêm D7
    trang_reflow(src_doc, page_no, khoi, kho=None, ghi_nhan=None,
                 *, than, du_phong=None) -> pymupdf.Document
    co_than(con) -> float       # trung vị layout.size của kind='text'
    write(...)                  # tính than, truyền qua functools.partial,
                                # thêm tk["trang_du_phong"]
```

`xep_doc` trả về độ cao đỉnh của từng khối, hoặc `None` khi cả neo lẫn dồn
khít đều vượt đáy. Đó là toàn bộ phần logic khó; tách thuần để test bằng số.

`trang_reflow` là phần đo và vẽ: với mỗi bậc `s`, đo chiều cao cần của từng
khối bằng `insert_htmlbox` trên trang nháp (khung cao bằng khung chữ, không
tự co; chỗ thừa âm = không vừa ở bậc này), gọi `xep_doc`, vừa thì vẽ lên
trang thật đúng các vị trí đó.

`pdf_trang.write` truyền thêm `kind` vào dict khối — `overlay` bỏ qua khóa
này nên không đổi hành vi. `trang_du_phong` là list do `pdf_reflow.write`
truyền vào; `cli export` in `N trang dự phòng` khi N > 0.

## 6. Test

Không test nào gọi mạng. 329 test hiện có phải xanh, vân tay golden giữ
nguyên. Các test Phase 6 về "khối nằm đúng khung" chuyển sang kiểm
`trang_theo_vi_tri`, vì đó là nơi R1 còn sống.

`tests/test_dan_trang.py` (thuần):
- còn chỗ thì khối nằm đúng độ cao neo
- khối trước cao hơn gốc thì đẩy khối sau xuống, không cặp nào chồng
- neo tràn đáy thì đẩy ngược từ đáy, khối không cần nâng giữ nguyên neo
- đẩy ngược vẫn lên quá đỉnh thì trả `None`
- thứ tự đỉnh tăng dần đúng thứ tự vào
- `co_khoi` đúng bảng D3; `khung_ngang` đúng D4 cho khối rộng và khối hẹp

`tests/test_pdf_reflow.py` (thêm):
- trang nhiều chữ vừa ở một `s < 1`, mọi khối cùng một `s`
- trang không vừa ở 0,75 thì dùng `trang_theo_vi_tri` và được đếm dự phòng
- không có hai khối chữ nào trên trang dàn chồng nhau
- khối chưa dịch hiện chữ Anh và không có mặt trong `ghi_nhan`
- trang không có khối nào ra trang trắng, không có ảnh (R2, R5)

## 7. Nghiệm thu trên harmonics

Dùng bản dịch hiện có, không tốn token. Đo trên khung thực vẽ, ghi lại khi
dựng trang.

| Chỉ số | Ngưỡng |
|---|---|
| Cặp khối chồng nhau trên các trang dàn | **0** |
| Thứ tự dọc đúng thứ tự `pos` trên các trang dàn | **100%** |
| Khối có mặt trên trang (kể cả chưa dịch) | **3.138/3.138** |
| Khối tràn | chỉ nằm trên trang dự phòng |
| Trang dự phòng | **≤ 10** |
| Cỡ chữ trung vị | **100%** |
| Trang có `s < 0,85` | **≤ 15** |

Sau đó xuất lại cả cuốn và gửi người dùng ảnh khổ 10, 13, 45, 60 để so với
bản cũ. Khổ 10 (mục lục) và 45 (mất chữ do dòng nghiêng) chỉ sửa hẳn ở 8B.

## 8. Rủi ro

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Đo chiều cao bằng `insert_htmlbox` chậm (mỗi khối × mỗi bậc) | xuất cả cuốn lâu hơn nhiều lần bản cũ | Phần lớn trang vừa ở bậc đầu; đo thời gian khi nghiệm thu, ghi vào ledger |
| Neo làm khối bị đẩy xuống xa vị trí gốc | trang dịch lệch hàng so với trang gốc | Chấp nhận: người dùng chọn "không đè" hơn "đúng chỗ" |
| Khung OCR hẹp bất thường làm khối "hẹp" thành cột chữ rất dài | trang có khối cao, dồn khít tràn | D4 kéo khối ≥ 60% ra đủ khung; khối hẹp còn lại chủ yếu là tiêu đề và mảnh vụn — 8B dọn |
| Rác OCR trong hình vẫn hiện trên trang dịch | chữ vô nghĩa to | Chấp nhận có ý thức, để 8B |
