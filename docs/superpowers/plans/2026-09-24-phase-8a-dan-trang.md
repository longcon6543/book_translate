# Phase 8A — Dàn trang theo thứ tự Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `--mode reflow` dàn chữ Việt theo thứ tự đoạn, neo độ cao gốc, không bao giờ để hai khối đè nhau.

**Architecture:** Phần tính vị trí là hàm thuần trong `render/dan_trang.py` (không PyMuPDF). `render/pdf_reflow.py` đo chiều cao từng khối bằng `insert_htmlbox`, gọi `xep_doc`, rồi vẽ; trang không vừa ở hệ số 0,75 thì rơi về bộ dựng theo vị trí cũ, đổi tên thành `trang_theo_vi_tri`. `overlay` không đổi.

**Tech Stack:** Python 3.12, PyMuPDF 1.28, pytest.

**Spec:** [docs/superpowers/specs/2026-09-24-dan-trang-theo-thu-tu-design.md](../specs/2026-09-24-dan-trang-theo-thu-tu-design.md)

## Global Constraints

- Chạy test: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q` — hiện 329 passed.
- Vân tay `tests/golden/` không được đổi (overlay giữ nguyên từng byte).
- Luật tầng: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py` phải rỗng.
- Không test nào gọi mạng. Không đổi DB, không init lại project nào.
- Lề `LE = 22.0` pt bốn phía; bậc co `THANG_S = (1.00, 0.95, 0.90, 0.85, 0.80, 0.75)`; khoảng cách khối `0,4 · than · s`; giãn dòng `1,2`.
- Chuẩn hoá `\xa0` → `" "` trước khi so chữ đọc ngược từ trang (`insert_htmlbox` dùng dấu cách không ngắt).
- `new_page()` làm vô hiệu Page cũ của cùng tài liệu — đo trên tài liệu nháp RIÊNG.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Không tái hiện nội dung sách trong log/ledger: chỉ in số đếm và vị trí.

## Review Focus

1. **Khối OCR hẹp bất thường** (harmonics: 519 khối rộng < 25% khung, 236 khối < 10%): giữ nguyên bề rộng vài pt làm chữ Việt thành cột một chữ cao hơn trang, kéo CẢ TRANG rơi về dự phòng. Người đọc mong trang đó vẫn được dàn. → Task 1 thêm bề rộng tối thiểu 25% khung cho khối hẹp, giữ tâm gốc (tinh chỉnh D4, ghi vào spec).
2. **Khối có `y0` âm hoặc nằm dưới đáy khung** (53 khối y âm ở harmonics): neo phải kẹp vào đỉnh khung, và khối neo dưới đáy phải chuyển sang dồn khít chứ không mất. → test ở Task 1 và Task 3.
3. **Trang chỉ có khối chưa dịch**: phải hiện chữ Anh, không ghi vào `ghi_nhan`, `co_trung_vi` không bị kéo. → Task 3.
4. **Khung OCR chồng nhau nặng** (nguyên nhân gốc của lỗi): ba khối có bbox gần trùng nhau vẫn phải ra ba dải chữ tách rời, đúng thứ tự. → Task 3.
5. **dry-run và cờ overflow**: dry-run không được ghi cờ; khối tràn trên trang dự phòng vẫn phải ghi cờ `overflow` để `status` đếm được. → test hiện có `test_reflow_dry_run_khong_ghi_co_vao_db` phải xanh nguyên ở Task 3.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `render/dan_trang.py` (mới) | Hằng số D2–D5 và ba hàm thuần: cỡ khối, khung ngang, xếp dọc |
| `render/pdf_reflow.py` | `trang_theo_vi_tri` (bộ dựng cũ + D7), `trang_reflow` mới (đo + vẽ), `co_than`, `write` |
| `render/pdf_trang.py` | Thêm `kind` vào dict khối |
| `cli.py` | In số trang dự phòng |
| `tests/test_dan_trang.py` (mới) | Test thuần |
| `tests/test_pdf_reflow.py` | Test cũ chuyển sang `trang_theo_vi_tri`; test mới cho `trang_reflow` |
| `tests/test_export_pdf.py` | Test mức lệnh cho trang dự phòng |

---

### Task 1: Module thuần `render/dan_trang.py`

**Files:**
- Create: `render/dan_trang.py`
- Create: `tests/test_dan_trang.py`
- Modify: `docs/superpowers/specs/2026-09-24-dan-trang-theo-thu-tu-design.md` (D4 thêm bề rộng tối thiểu)

**Interfaces:**
- Consumes: không có.
- Produces:
  - `LE: float = 22.0`, `THANG_S: tuple`, `TI_LE_KHOANG = 0.4`, `TI_LE_KHOI_RONG = 0.6`, `TI_LE_KHOI_HEP_MIN = 0.25`, `GIAN_DONG = 1.2`
  - `co_khoi(kind: str, size: float, than: float) -> float`
  - `khung_ngang(x0: float, x1: float, trai: float, phai: float) -> tuple[float, float]`
  - `xep_doc(neo: list[float], cao: list[float], tren: float, duoi: float, khoang: float) -> list[float] | None`

- [ ] **Step 1: Viết test thất bại**

`tests/test_dan_trang.py`:

```python
"""Phần tính vị trí của reflow: hàm thuần, không PyMuPDF, không gọi mạng."""
import pytest

from render import dan_trang as dt


# ---- co_khoi (D3)

def test_than_bai_dung_mot_co_chung():
    assert dt.co_khoi("text", 7.3, 9.1) == 9.1
    assert dt.co_khoi("text", 14.0, 9.1) == 9.1


def test_tieu_de_kep_giua_than_va_gap_doi():
    assert dt.co_khoi("heading", 14.0, 9.1) == 14.0
    assert dt.co_khoi("heading", 6.0, 9.1) == 9.1
    assert dt.co_khoi("heading", 120.0, 9.1) == pytest.approx(18.2)


@pytest.mark.parametrize("kind", ["caption", "table", "formula"])
def test_loai_khac_kep_tu_0_8_than_toi_than(kind):
    assert dt.co_khoi(kind, 8.0, 10.0) == 8.0
    assert dt.co_khoi(kind, 3.1, 10.0) == pytest.approx(8.0), "dòng OCR cỡ vài pt (7b)"
    assert dt.co_khoi(kind, 12.0, 10.0) == 10.0


# ---- khung_ngang (D4)

def test_khoi_rong_keo_ra_du_khung():
    # khung chữ 22..328 rộng 306; khối rộng 200 >= 60%
    assert dt.khung_ngang(40, 240, 22, 328) == (22, 328)


def test_khoi_hep_giu_nguyen_be_rong_va_vi_tri():
    # rộng 100: dưới 60% nhưng trên 25% -> giữ nguyên
    assert dt.khung_ngang(125, 225, 22, 328) == (125, 225)


def test_khoi_hep_bi_day_vao_trong_khung():
    a, b = dt.khung_ngang(300, 400, 22, 328)
    assert (a, b) == (228, 328)


def test_khoi_qua_hep_duoc_noi_toi_thieu_quanh_tam_goc():
    """Review Focus 1: 236 khối harmonics rộng < 10% khung. Giữ vài pt là
    ép chữ Việt thành cột một chữ, cao hơn trang, kéo cả trang về dự phòng."""
    a, b = dt.khung_ngang(170, 180, 22, 328)
    toi_thieu = dt.TI_LE_KHOI_HEP_MIN * 306
    assert b - a == pytest.approx(toi_thieu)
    assert (a + b) / 2 == pytest.approx(175)


def test_khoi_qua_hep_o_mep_van_nam_trong_khung():
    a, b = dt.khung_ngang(320, 330, 22, 328)
    assert b == pytest.approx(328) and a >= 22


def test_khoi_be_rong_am_hoac_bang_khong_van_ra_khung_hop_le():
    a, b = dt.khung_ngang(200, 200, 22, 328)
    assert b - a == pytest.approx(dt.TI_LE_KHOI_HEP_MIN * 306)


# ---- xep_doc (D1 + D5 bước 1-2)

def test_con_cho_thi_nam_dung_do_cao_neo():
    assert dt.xep_doc([50, 200], [30, 30], 22, 525, 4) == [50, 200]


def test_khoi_truoc_dai_ra_day_khoi_sau_xuong():
    y = dt.xep_doc([50, 100], [80, 30], 22, 525, 4)
    assert y == [50, 134]


def test_khong_cap_nao_chong_nhau():
    neo, cao = [50, 60, 70, 80], [40, 40, 40, 40]
    y = dt.xep_doc(neo, cao, 22, 525, 4)
    for i in range(len(y) - 1):
        assert y[i] + cao[i] + 4 <= y[i + 1] + 1e-9


def test_thu_tu_dinh_tang_dan_dung_thu_tu_vao():
    y = dt.xep_doc([300, 50, 200], [20, 20, 20], 22, 525, 4)
    assert y == sorted(y)
    assert y[0] == 300, "neo khối đầu, khối sau không được chen lên trên"


def test_neo_am_kep_vao_dinh_khung():
    """Review Focus 2: 53 khối harmonics có y0 âm."""
    assert dt.xep_doc([-3, 100], [20, 20], 22, 525, 4) == [22, 100]


def test_neo_tran_day_thi_don_khit_tu_dinh():
    # neo khối 2 ở 480, cao 60 -> đáy 540 > 525; dồn khít: 22, 22+100+4
    y = dt.xep_doc([200, 480], [100, 60], 22, 525, 4)
    assert y == [22, 126]


def test_neo_duoi_day_khung_van_duoc_don_khit():
    """Review Focus 2: khối neo dưới đáy khung không được mất."""
    y = dt.xep_doc([50, 600], [20, 20], 22, 525, 4)
    assert y == [22, 46]


def test_don_khit_van_tran_thi_tra_none():
    assert dt.xep_doc([50, 60], [300, 300], 22, 525, 4) is None


def test_khong_co_khoi_nao():
    assert dt.xep_doc([], [], 22, 525, 4) == []
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_dan_trang.py -q`
Expected: FAIL/ERROR — `ImportError: cannot import name 'dan_trang' from 'render'`.

- [ ] **Step 3: Viết code**

`render/dan_trang.py`:

```python
"""Phần tính vị trí của chế độ reflow: dàn khối theo thứ tự, neo độ cao gốc.

Hàm thuần, không đụng PyMuPDF: nhận số, trả số. Phần đo chiều cao chữ và vẽ
nằm ở pdf_reflow. Tách ra vì đây là toàn bộ phần logic khó, và test bằng số
thì nhanh và chính xác hơn đọc ngược chữ trên trang.

Spec: docs/superpowers/specs/2026-09-24-dan-trang-theo-thu-tu-design.md
"""

# D2: lề bốn phía. Người dùng cho nới lề; cột chữ gốc harmonics rộng ~277pt,
# khung chữ với lề này rộng 306pt. Đo thử: lề 18 và 36 đều cho trung vị 100%.
LE = 22.0
# D5: hệ số co chung cho cả trang, thử lần lượt, vừa là dừng. Dưới 0,75 chữ
# khó đọc — trang đó rơi về bố cục theo vị trí.
THANG_S = (1.00, 0.95, 0.90, 0.85, 0.80, 0.75)
# Khoảng cách giữa hai khối, tính theo cỡ thân bài.
TI_LE_KHOANG = 0.4
# D4: khối rộng từ ngần này bề rộng khung trở lên thì kéo ra đủ khung.
TI_LE_KHOI_RONG = 0.6
# D4: khối hẹp không được hẹp hơn ngần này bề rộng khung. Đo thật: 236 khối
# harmonics rộng dưới 10% khung — giữ nguyên thì chữ Việt thành cột một chữ.
TI_LE_KHOI_HEP_MIN = 0.25
# Giãn dòng đã dùng khi đo thử (spec mục 2).
GIAN_DONG = 1.2


def co_khoi(kind: str, size: float, than: float) -> float:
    """D3: cỡ chữ theo loại khối. `than` là cỡ thân bài của cả cuốn."""
    if kind == "text":
        return than
    if kind == "heading":
        return min(max(size, than), 2 * than)
    return min(max(size, 0.8 * than), than)


def khung_ngang(x0: float, x1: float, trai: float, phai: float) -> tuple:
    """D4: khoảng ngang của khối trong khung chữ [trai, phai]."""
    rong_khung = phai - trai
    rong = x1 - x0
    if rong >= TI_LE_KHOI_RONG * rong_khung:
        return trai, phai
    toi_thieu = TI_LE_KHOI_HEP_MIN * rong_khung
    if rong < toi_thieu:
        tam = (x0 + x1) / 2
        x0, rong = tam - toi_thieu / 2, toi_thieu
    a = min(max(x0, trai), phai - rong)
    return a, a + rong


def xep_doc(neo: list, cao: list, tren: float, duoi: float,
            khoang: float) -> "list | None":
    """D1 + D5 bước 1-2: độ cao đỉnh của từng khối, hoặc None nếu không vừa.

    Bước 1 neo: mỗi khối ở max(neo, đáy khối trước + khoảng). Con trỏ chỉ đi
    xuống nên hai khối không bao giờ chồng nhau. Bước 2 dồn khít từ đỉnh
    khung khi bước 1 vượt đáy.
    """
    if not cao:
        return []
    for dung_neo in (True, False):
        y, con_tro = [], tren
        for n, h in zip(neo, cao):
            dinh = max(n, con_tro) if dung_neo else con_tro
            y.append(dinh)
            con_tro = dinh + h + khoang
        if y[-1] + cao[-1] <= duoi + 1e-6:
            return y
    return None
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_dan_trang.py -q`
Expected: tất cả PASS (21 test, tính cả 3 tham số của test parametrize).

- [ ] **Step 5: Ghi tinh chỉnh D4 vào spec**

Trong spec, thay đoạn D4:

```
**D4 — Căn ngang.** Khối có bề rộng gốc ≥ 60% bề rộng khung chữ thì kéo ra đủ
bề rộng khung. Khối hẹp hơn giữ bề rộng và vị trí ngang gốc, kẹp vào khung —
tiêu đề căn giữa vẫn ở giữa.
```

bằng:

```
**D4 — Căn ngang.** Khối có bề rộng gốc ≥ 60% bề rộng khung chữ thì kéo ra đủ
bề rộng khung. Khối hẹp hơn giữ bề rộng và vị trí ngang gốc, kẹp vào khung —
tiêu đề căn giữa vẫn ở giữa. Khối hẹp dưới 25% bề rộng khung được nới ra
đúng 25%, giữ tâm ngang gốc: đo thật 519 khối harmonics rộng dưới 25% và 236
khối dưới 10% — giữ nguyên vài pt là ép chữ Việt thành cột một chữ, cao hơn
trang, kéo cả trang về dự phòng.
```

và trong khối kiến trúc mục 5 thêm dòng `    TI_LE_KHOI_HEP_MIN = 0.25` ngay dưới `    TI_LE_KHOI_RONG = 0.6`.

- [ ] **Step 6: Kiểm luật tầng, chạy cả bộ, commit**

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py`
Expected: không in gì.

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `350 passed` (329 + 21).

```bash
git add render/dan_trang.py tests/test_dan_trang.py docs/superpowers/specs/2026-09-24-dan-trang-theo-thu-tu-design.md
git commit -m "feat: dan_trang — tính vị trí dàn trang theo thứ tự, hàm thuần

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Đổi tên bộ dựng cũ thành `trang_theo_vi_tri`, thêm D7

**Files:**
- Modify: `render/pdf_reflow.py` (hàm `trang_reflow` → `trang_theo_vi_tri`; `write` gọi tên mới)
- Modify: `tests/test_pdf_reflow.py` (mọi lời gọi cũ sang tên mới; thêm 1 test D7)

**Interfaces:**
- Consumes: không có.
- Produces: `pdf_reflow.trang_theo_vi_tri(src_doc, page_no: int, khoi: list, kho=None, ghi_nhan=None) -> pymupdf.Document` — hành vi như `trang_reflow` cũ, trừ: khối chưa dịch (`html` rỗng) KHÔNG được ghi vào `ghi_nhan`.

- [ ] **Step 1: Chuyển test cũ sang tên mới, viết test D7**

Run: `sed -i '' 's/pdf_reflow\.trang_reflow(/pdf_reflow.trang_theo_vi_tri(/g' tests/test_pdf_reflow.py`

Sửa docstring đầu file `tests/test_pdf_reflow.py` thành:

```python
"""Chế độ reflow. Không gọi mạng.

trang_theo_vi_tri: bộ dựng theo vị trí (R1 cũ) — nay là dự phòng cho trang
không dàn được. trang_reflow: dàn theo thứ tự, neo vị trí gốc (spec 8A).
"""
```

Thêm vào cuối file:

```python
def test_vi_tri_khoi_chua_dich_khong_vao_ghi_nhan():
    """D7 (lỗi nhỏ 6a): khối chưa dịch tràn thì vẫn hiện chữ Anh, nhưng không
    được tính vào thống kê và không bị gắn cờ overflow — đo thật ~154 cờ giả
    trên harmonics nếu xuất khi chưa dịch."""
    ghi = []
    anh = "Untranslated English far too long for this tiny box. " * 30
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(10, 10, 110, 24, "", src=anh)], ghi_nhan=ghi)
    assert "Untranslated English" in chu(d[0])
    assert ghi == []
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_reflow.py -q`
Expected: FAIL — `AttributeError: module 'render.pdf_reflow' has no attribute 'trang_theo_vi_tri'` ở mọi test đã đổi tên.

- [ ] **Step 3: Đổi tên và thêm D7**

Trong `render/pdf_reflow.py`:

1. Đổi `def trang_reflow(` thành `def trang_theo_vi_tri(`, và docstring dòng đầu thành:

```python
    """Tài liệu một trang trắng đúng khổ trang gốc, chữ đặt đúng khung gốc.

    Bộ dựng của Phase 6 (R1). Từ Phase 8A chỉ còn là dự phòng: trang_reflow
    gọi nó cho trang không dàn được ở hệ số co 0,75.
```

(giữ nguyên phần còn lại của docstring.)

2. Thay khối cuối vòng lặp:

```python
        if ghi_nhan is not None:
            ghi_nhan.append((k.get("id"), ti_le, bi_tran))
```

bằng:

```python
        # D7: khối chưa dịch hiện chữ Anh nhưng không vào thống kê — tràn của
        # nó là tràn của chữ Anh, gắn cờ overflow cho nó là cờ giả.
        if ghi_nhan is not None and ban_dich:
            ghi_nhan.append((k.get("id"), ti_le, bi_tran))
```

3. Trong `write`, đổi `trang_reflow` thành `trang_theo_vi_tri` (tạm thời; Task 3 thay bằng bộ dàn mới).

4. Sửa docstring module dòng đầu thành `"""Chế độ reflow: dựng trang trắng mang chữ Việt, không chép gì từ trang gốc.` (giữ các dòng sau).

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_reflow.py tests/test_export_pdf.py -q`
Expected: tất cả PASS.

- [ ] **Step 5: Chạy cả bộ, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `351 passed`.

```bash
git add render/pdf_reflow.py tests/test_pdf_reflow.py
git commit -m "refactor: bộ dựng theo vị trí đổi tên trang_theo_vi_tri, khối chưa dịch không vào thống kê

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Bộ dàn mới `trang_reflow`, nối vào `write` và `export`

**Files:**
- Modify: `render/pdf_reflow.py` (thêm `trang_reflow`, `_thu_bac`, `co_than`; viết lại `write`)
- Modify: `render/pdf_trang.py` (SELECT thêm `kind`, dict khối thêm khoá `kind`)
- Modify: `cli.py` (`cmd_export` in số trang dự phòng)
- Test: `tests/test_pdf_reflow.py`, `tests/test_export_pdf.py`

**Interfaces:**
- Consumes: `dan_trang.LE`, `THANG_S`, `TI_LE_KHOANG`, `GIAN_DONG`, `co_khoi`, `khung_ngang`, `xep_doc` (Task 1); `pdf_reflow.trang_theo_vi_tri` (Task 2); `pdf_font.dung_css(size, line_height)`, `pdf_font.dung_archive`, `pdf_font.chon_bo_font`.
- Produces:
  - `pdf_reflow.trang_reflow(src_doc, page_no, khoi, kho=None, ghi_nhan=None, *, than: float, du_phong: list | None = None) -> pymupdf.Document`. `ghi_nhan` nhận `(id, s, False)` cho mỗi khối đã dịch trên trang dàn — `s` là hệ số co chung của trang.
  - `pdf_reflow.co_than(con) -> float`
  - `pdf_reflow.write(...)` trả `tk` có thêm khoá `"trang_du_phong": int`.
  - Dict khối của `pdf_trang.write` có thêm khoá `"kind": str`.

- [ ] **Step 1: Viết test thất bại cho bộ dàn**

Thêm vào `tests/test_pdf_reflow.py` (dùng lại `trang_scan`, `chu`, `KHO`; thêm tham số `kind` cho helper `khoi`):

Sửa helper `khoi` thành:

```python
def khoi(x0, y0, x1, y1, html, src="Original English text", id_=1, size=10.0,
         kind="text"):
    return {"id": id_, "bbox": pymupdf.Rect(x0, y0, x1, y1),
            "html": html, "src": src, "size": size, "kind": kind}
```

Thêm:

```python
# ------------------------------------------------ trang_reflow (spec 8A)

THAN = 10.0


def dan(khoi_list, ghi=None, du_phong=None):
    return pdf_reflow.trang_reflow(trang_scan(), 0, khoi_list, ghi_nhan=ghi,
                                   than=THAN, du_phong=du_phong)


def dinh_chu(page, tu):
    """Độ cao đỉnh của lần xuất hiện đầu tiên của một từ đánh dấu."""
    thay = page.search_for(tu)
    assert thay, f"không thấy '{tu}' trên trang"
    return min(r.y0 for r in thay)


def day_chu(page, tu):
    return max(r.y1 for r in page.search_for(tu))


def test_dan_khong_mang_anh_va_dung_kho():
    """R2 + khổ trang."""
    d = dan([khoi(40, 60, 300, 100, "Chữ Việt")])
    assert d[0].get_images(full=True) == []
    assert (d[0].rect.width, d[0].rect.height) == KHO


def test_dan_trang_khong_co_khoi_ra_trang_trang():
    """R5 / D8."""
    d = dan([])
    assert chu(d[0]).strip() == ""
    assert d[0].get_images(full=True) == []


def test_dan_con_cho_thi_neo_dung_do_cao_goc():
    """D1: còn chỗ thì khối nằm ở độ cao gốc."""
    d = dan([khoi(40, 300, 300, 330, "Neoday ở đây")])
    assert abs(dinh_chu(d[0], "Neoday") - 300) < 6


def test_dan_khung_chong_nhau_ra_ba_dai_tach_roi_dung_thu_tu():
    """Review Focus 4 — nguyên nhân gốc của lỗi đè chữ: khung OCR chồng nhau."""
    dai = " thêm chữ cho dài ra" * 12
    d = dan([khoi(30, 100, 310, 140, "Aaaxx" + dai, id_=1),
             khoi(30, 105, 310, 145, "Bbbxx" + dai, id_=2),
             khoi(30, 110, 310, 150, "Cccxx" + dai, id_=3)])
    p = d[0]
    assert day_chu(p, "Aaaxx") <= dinh_chu(p, "Bbbxx")
    assert dinh_chu(p, "Aaaxx") < dinh_chu(p, "Bbbxx") < dinh_chu(p, "Cccxx")


def test_dan_khong_hai_khoi_nao_chong_nhau():
    """Spec mục 7: 0 cặp chồng. Đo trên khung chữ thực vẽ của từng khối."""
    ds = [khoi(30, 60 + 5 * i, 310, 90 + 5 * i, f"Moc{i}x " + "chữ Việt " * 25,
               id_=i) for i in range(5)]
    d = dan(ds)
    p = d[0]
    for i in range(4):
        # từ cuối của khối i nằm trên từ đầu của khối i+1
        assert dinh_chu(p, f"Moc{i}x") < dinh_chu(p, f"Moc{i + 1}x")
    tu = p.get_text("words")
    theo_khoi = {}
    for w in tu:
        theo_khoi.setdefault(w[5], []).append(w)   # block_no của PyMuPDF
    hop = [(min(w[1] for w in ws), max(w[3] for w in ws))
           for ws in theo_khoi.values()]
    hop.sort()
    for (a0, a1), (b0, b1) in zip(hop, hop[1:]):
        assert a1 <= b0 + 0.5, f"hai khối chồng: {a0:.1f}-{a1:.1f} và {b0:.1f}-{b1:.1f}"


def test_dan_neo_am_van_hien_chu():
    """Review Focus 2 ở mức trang."""
    d = dan([khoi(30, -3.0, 300, 40, "Tiêu đề chạy đầu trang")])
    assert "Tiêu đề" in chu(d[0])


def test_dan_trang_nhieu_chu_co_chung_mot_he_so():
    """D5: mọi khối cùng một s < 1, không rơi về dự phòng."""
    ghi, dp = [], []
    doan = "Đây là một câu tiếng Việt khá dài để lấp đầy trang dịch. " * 17
    d = dan([khoi(30, 40 + 150 * i, 310, 180 + 150 * i, doan, id_=i)
             for i in range(3)], ghi=ghi, du_phong=dp)
    assert dp == [], "trang này phải vừa ở một bậc co, không cần dự phòng"
    he_so = {round(t, 3) for _, t, _ in ghi}
    assert len(he_so) == 1, f"các khối co khác nhau: {he_so}"
    assert he_so.pop() < 1.0, "độ dài chữ chưa đủ để phải co — chỉnh độ dài"
    assert all(not tran for _, _, tran in ghi)


def test_dan_khong_vua_o_0_75_thi_du_phong():
    """D6: rơi về trang_theo_vi_tri, được đếm, và khối tràn vẫn báo tràn."""
    ghi, dp = [], []
    d = dan([khoi(30, 60, 310, 100, "Chữ Việt rất dài. " * 1500, id_=7)],
            ghi=ghi, du_phong=dp)
    assert dp == [0]
    assert ghi and ghi[0][0] == 7 and ghi[0][2] is True
    assert d[0].get_images(full=True) == []


def test_dan_khoi_chua_dich_hien_chu_anh_khong_vao_ghi_nhan():
    """D7 / Review Focus 3."""
    ghi = []
    d = dan([khoi(40, 60, 300, 100, "", src="Untranslated paragraph here")],
            ghi=ghi)
    assert "Untranslated paragraph" in chu(d[0])
    assert ghi == []


def test_dan_khoi_hep_giu_tam_ngang():
    """D4: tiêu đề hẹp căn giữa vẫn ở giữa."""
    d = dan([khoi(137, 60, 197, 80, "Chương", kind="heading", size=14.0)])
    thay = d[0].search_for("Chương")
    tam = (thay[0].x0 + thay[0].x1) / 2
    assert abs(tam - 167) < 40
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_reflow.py -q -k dan_`
Expected: FAIL — `AttributeError: module 'render.pdf_reflow' has no attribute 'trang_reflow'`.

- [ ] **Step 3: Viết bộ dàn**

Trong `render/pdf_reflow.py`, thêm import:

```python
import functools
import statistics

from render import dan_trang
```

Thêm sau `trang_theo_vi_tri`:

```python
def _thu_bac(muc, khung, than, s, kho):
    """Một bậc của thang D5: đo chiều cao từng khối ở hệ số s rồi xếp dọc.

    Trả về list (rect, css) theo thứ tự `muc`, hoặc None khi không vừa. Đo
    trên tài liệu nháp riêng: vẽ lên trang thật rồi mới biết không vừa là để
    lại chữ thừa.
    """
    nhap = pymupdf.open()
    trang_nhap = nhap.new_page(width=khung.x1 + dan_trang.LE,
                               height=khung.y1 + dan_trang.LE)
    ngang, cao, css_ds = [], [], []
    try:
        for k, html, _ in muc:
            co = dan_trang.co_khoi(k.get("kind", "text"), k["size"], than) * s
            css = pdf_font.dung_css(co, dan_trang.GIAN_DONG)
            x0, x1 = dan_trang.khung_ngang(k["bbox"].x0, k["bbox"].x1,
                                           khung.x0, khung.x1)
            do = pymupdf.Rect(x0, khung.y0, x1, khung.y1)
            thua, _ = trang_nhap.insert_htmlbox(do, html, css=css,
                                                archive=kho, scale_low=1)
            if thua < 0:
                return None                 # một khối đã cao hơn cả khung
            ngang.append((x0, x1))
            cao.append(do.height - thua)
            css_ds.append(css)
    finally:
        nhap.close()

    khoang = dan_trang.TI_LE_KHOANG * than * s
    y = dan_trang.xep_doc([k["bbox"].y0 for k, _, _ in muc], cao,
                          khung.y0, khung.y1, khoang)
    if y is None:
        return None
    # Khung vẽ cao hơn chữ đúng một khoảng: insert_htmlbox cần chút dư để
    # không làm tròn thành "không vừa", và khối sau bắt đầu ở đúng chỗ đó
    # nên vẫn không chồng.
    return [(pymupdf.Rect(x0, yi, x1, yi + h + khoang), css)
            for (x0, x1), yi, h, css in zip(ngang, y, cao, css_ds)]


def trang_reflow(src_doc, page_no: int, khoi: list, kho=None,
                 ghi_nhan=None, *, than: float,
                 du_phong=None) -> "pymupdf.Document":
    """Tài liệu một trang trắng: khối dàn theo thứ tự, neo độ cao gốc (8A).

    Cùng giao kèo với pdf_overlay.trang_dich cộng hai tham số từ khoá:
    `than` là cỡ thân bài cả cuốn, `du_phong` nhận page_no của trang phải
    rơi về trang_theo_vi_tri (D6). `khoi` là list dict
    {id, bbox, html, src, size, kind}.
    """
    if kho is None:
        kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    goc = src_doc[page_no].rect
    le = dan_trang.LE
    khung = pymupdf.Rect(le, le, goc.width - le, goc.height - le)

    muc = []
    for k in khoi:
        da_dich = bool(k["html"].strip())
        # D7: chưa dịch thì hiện chữ Anh — khoảng trắng im lặng tệ hơn.
        html = k["html"] if da_dich else k.get("src", "")
        if html.strip():
            muc.append((k, html, da_dich))

    d = pymupdf.open()
    page = d.new_page(width=goc.width, height=goc.height)
    if not muc:
        return d                                # D8 / R5

    for s in dan_trang.THANG_S:
        dat = _thu_bac(muc, khung, than, s, kho)
        if dat is not None:
            break
    else:
        d.close()
        if du_phong is not None:
            du_phong.append(page_no)
        return trang_theo_vi_tri(src_doc, page_no, khoi, kho, ghi_nhan)

    for (k, html, da_dich), (rect, css) in zip(muc, dat):
        page.insert_htmlbox(rect, html, css=css, archive=kho, scale_low=1)
        if ghi_nhan is not None and da_dich:
            ghi_nhan.append((k.get("id"), s, False))
    return d


def co_than(con) -> float:
    """D3: cỡ thân bài cả cuốn = trung vị layout.size của khối kind='text'."""
    co = []
    for (lay,) in con.execute("SELECT layout FROM blocks WHERE kind='text'"):
        size = json.loads(lay or "{}").get("size")
        if size:
            co.append(float(size))
    return statistics.median(co) if co else 10.0
```

Thêm `import json` vào nhóm import chuẩn đầu file.

Viết lại `write`:

```python
def write(project, con, out_path, *, pages=None,
          dry_run=False, probe=False) -> dict:
    """Xuất PDF khổ đôi chế độ reflow. tk có thêm 'trang_du_phong'."""
    du_phong = []
    dung = functools.partial(trang_reflow, than=co_than(con),
                             du_phong=du_phong)
    tk = pdf_trang.write(project, con, out_path, dung, pages=pages,
                         dry_run=dry_run, probe=probe)
    tk["trang_du_phong"] = len(du_phong)
    return tk
```

Trong `render/pdf_trang.py` hàm `write`, sửa câu SELECT thành:

```python
    cot = ("SELECT id, page_no, pos, bbox, layout, kind, "
           "       COALESCE(dst_html, '') dst, src_html "
           "FROM blocks WHERE bbox IS NOT NULL")
```

và dict khối thêm khoá `kind`:

```python
        theo_trang.setdefault(r["page_no"], []).append(
            {"id": r["id"], "bbox": pymupdf.Rect(x0, y0, x1, y1),
             "html": noi_dung, "src": goc,
             "size": float(lay.get("size") or 10.0),
             "kind": r["kind"] or "text"})
```

- [ ] **Step 4: Chạy test bộ dàn, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_reflow.py -q`
Expected: tất cả PASS.

Nếu `test_dan_khong_hai_khoi_nao_chong_nhau` đỏ vì `get_text("words")` gộp hai khối vào một `block_no` hoặc tách một khối thành nhiều `block_no` (chứ không phải vì chữ thật sự chồng — xem bằng mắt qua ảnh `get_pixmap`): đổi phép đo sang so đỉnh/đáy của các từ đánh dấu `Moc{i}x` ở đầu mỗi khối và từ cuối mỗi khối, ghi `Ruling:`. Không đổi code để chiều phép đo.

Nếu `test_dan_trang_nhieu_chu_co_chung_mot_he_so` báo "độ dài chữ chưa đủ" hoặc `dp != []`: chỉnh hệ số `* 17` (lên nếu vừa ở s=1, xuống nếu rơi dự phòng) cho tới khi rơi vào một bậc giữa, và ghi `Ruling:` vào ledger kèm số đã chọn. Đó là chỉnh dữ liệu test, không phải chỉnh code.

- [ ] **Step 5: Viết test mức lệnh thất bại, sửa test dry-run cho luật mới**

Test hiện có `test_reflow_dry_run_khong_ghi_co_vao_db` (Review Focus 5) dựa trên
"khung tí hon thì tràn". Từ 8A khối hẹp được nới ra 25% khung và trang được
dàn lại, nên khung tí hon KHÔNG còn tràn — phần "phải có cờ" của test sẽ đỏ vì
lý do đúng. Tràn chỉ còn sinh ở trang dự phòng. Thay phần chuẩn bị của test
(giữ nguyên hai lần `render.write` và hai `assert` ở cuối):

```python
def test_reflow_dry_run_khong_ghi_co_vao_db(proj, tmp_path):
    """Review Focus 3 (Phase 6) / 5 (Phase 8A): chữ ở dry-run là chữ Anh độn,
    cờ sinh ra là giả. Từ 8A tràn chỉ sinh ở trang dự phòng, nên phép thử
    dùng một khối dài tới mức trang không dàn vừa ở 75% — cả ở dry-run (chữ
    Anh độn) lẫn khi xuất thật."""
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks WHERE page_no=0").fetchone()[0]
    dai = "noi dung rat dai " * 3000
    con.execute("UPDATE blocks SET src_html=?, dst_html=?, flag=NULL WHERE id=?",
                (dai, dai, bid))
    con.commit()
```

Chạy nó ngay: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_export_pdf.py -q -k dry_run` — Expected: PASS (Step 3 đã làm bộ dàn; test này ghim rằng dry-run vẫn không ghi cờ và xuất thật vẫn ghi cờ cho khối tràn trên trang dự phòng).

Thêm vào `tests/test_export_pdf.py`:

```python
def test_reflow_bao_so_trang_du_phong(proj, tmp_path):
    """D6: export phải nói có bao nhiêu trang rơi về bố cục theo vị trí."""
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=? WHERE page_no=2",
                ("Chữ Việt rất dài. " * 3000,))
    con.commit()
    tk = render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf",
                      mode="reflow")
    assert tk["trang_du_phong"] == 1


def test_reflow_trang_binh_thuong_khong_du_phong(proj, tmp_path):
    tk = render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf",
                      mode="reflow")
    assert tk["trang_du_phong"] == 0


def test_export_in_so_trang_du_phong(proj, tmp_path, capsys):
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=? WHERE page_no=2",
                ("Chữ Việt rất dài. " * 3000,))
    con.commit()
    cli.cmd_export(argparse.Namespace(
        project=str(proj), output=str(tmp_path / "ra.pdf"), bilingual=False,
        mode="reflow", pages=None, dry_run=False, probe=False))
    assert "1 trang dự phòng" in capsys.readouterr().out
```

Trước khi viết `test_export_in_so_trang_du_phong`, đọc các test hiện có trong `tests/test_export_pdf.py` gọi `cli.cmd_export` và dùng đúng bộ khoá `argparse.Namespace` như chúng; nếu khác bộ khoá ở trên thì theo file, ghi `Ruling:`.

- [ ] **Step 6: Chạy test, xác nhận chỉ test CLI thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_export_pdf.py -q`
Expected: `test_export_in_so_trang_du_phong` FAIL (chưa in); hai test kia PASS vì `write` đã làm ở Step 3.

- [ ] **Step 7: In số trang dự phòng**

Trong `cli.py` `cmd_export`, sau khối `print(f"  {tk['so_trang']} khổ, ...")` (vẫn trong `if tk:`):

```python
        if tk.get("trang_du_phong"):
            print(f"  {tk['trang_du_phong']} trang dự phòng: không dàn vừa ở "
                  f"cỡ chữ 75% nên giữ bố cục theo vị trí.")
```

- [ ] **Step 8: Chạy cả bộ, kiểm luật tầng, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: tất cả PASS (351 + 10 test dàn + 3 test lệnh = `364 passed`). Vân tay golden xanh.

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py`
Expected: không in gì.

```bash
git add render/pdf_reflow.py render/pdf_trang.py cli.py tests/test_pdf_reflow.py tests/test_export_pdf.py
git commit -m "feat: reflow dàn trang theo thứ tự đoạn, neo vị trí gốc, không đè chữ

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Nghiệm thu trên harmonics

**Files:**
- Create (scratchpad, KHÔNG commit): `<scratchpad>/nghiem_thu_8a.py`
- Không sửa code sản phẩm. Kết quả ghi vào ledger.

**Interfaces:**
- Consumes: `pdf_reflow.trang_reflow`, `pdf_reflow.co_than`, `pdf_reflow.write` (Task 3).
- Produces: số đo cho bảng spec mục 7; file `projects/harmonics/output.vi.pdf` mới; ảnh khổ 10, 13, 45, 60.

- [ ] **Step 1: Viết script đo**

`<scratchpad>/nghiem_thu_8a.py` — chạy từ gốc repo:

```python
"""Nghiệm thu 8A trên harmonics. Chỉ in số đếm, không in nội dung sách."""
import sqlite3, statistics, sys, time
sys.path.insert(0, ".")
import pymupdf
import pdf_font
from render import pdf_reflow, pdf_trang

con = sqlite3.connect("projects/harmonics/project.db")
con.row_factory = sqlite3.Row
src = pymupdf.open("projects/harmonics/source.pdf")
kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
than = pdf_reflow.co_than(con)

# Dựng lại danh sách khối đúng như pdf_trang.write làm.
import json
theo_trang = {}
for r in con.execute("SELECT id,page_no,pos,bbox,layout,kind,COALESCE(dst_html,'') dst,src_html "
                     "FROM blocks WHERE bbox IS NOT NULL ORDER BY page_no,pos"):
    x0, y0, x1, y1 = (float(v) for v in r["bbox"].split(","))
    theo_trang.setdefault(r["page_no"], []).append(
        {"id": r["id"], "bbox": pymupdf.Rect(x0, y0, x1, y1), "html": r["dst"],
         "src": r["src_html"] or "", "size": float(json.loads(r["layout"]).get("size") or 10),
         "kind": r["kind"] or "text"})

t0 = time.time()
du_phong, chong, sai_thu_tu, co_mat, he_so_trang, tran = [], 0, 0, 0, {}, 0
for pno in range(src.page_count):
    ds = theo_trang.get(pno, [])
    ghi = []
    d = pdf_reflow.trang_reflow(src, pno, ds, kho, ghi, than=than, du_phong=du_phong)
    if ghi:
        he_so_trang[pno] = min(t for _, t, _ in ghi)
    tran += sum(1 for _, _, b in ghi if b)
    if pno not in du_phong and ds:
        # khung thực vẽ: dải dọc của từng khối lấy từ block_no của get_text
        dai = {}
        for w in d[0].get_text("words"):
            a = dai.setdefault(w[5], [w[1], w[3]])
            a[0], a[1] = min(a[0], w[1]), max(a[1], w[3])
        v = sorted(dai.values())
        chong += sum(1 for p, q in zip(v, v[1:]) if p[1] > q[0] + 0.5)
        sai_thu_tu += 0 if len(dai) == len(v) else 1
    co_mat += len(ds)
    d.close()

tong = con.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
hs = list(he_so_trang.values())
print(f"than={than} | thời gian {time.time()-t0:.0f}s")
print(f"trang dự phòng: {len(du_phong)} -> {[p+1 for p in du_phong]}")
print(f"cặp dải chữ chồng trên trang dàn: {chong}")
print(f"khối có mặt: {co_mat}/{tong}")
print(f"khối tràn (chỉ được ở trang dự phòng): {tran}")
print(f"hệ số trung vị: {statistics.median(hs):.2f} | trang s<0.85: {sum(h < 0.85 for h in hs)}")
```

Ghi chú: thứ tự dọc đúng `pos` đã được `xep_doc` bảo đảm bằng cấu trúc (con trỏ chỉ đi xuống) và test `test_thu_tu_dinh_tang_dan_dung_thu_tu_vao`; ở mức trang, "0 cặp chồng" cộng với dải được sắp theo đỉnh là đủ.

- [ ] **Step 2: Chạy và so ngưỡng**

Run: `.venv/bin/python -W ignore::DeprecationWarning <scratchpad>/nghiem_thu_8a.py`
Expected (ngưỡng spec mục 7):
- `cặp dải chữ chồng trên trang dàn: 0`
- `khối có mặt: 3138/3138`
- `trang dự phòng: N` với N ≤ 10
- `khối tràn` > 0 chỉ khi N > 0 (khối tràn chỉ sinh ở trang dự phòng — bộ dàn luôn báo `False`)
- `hệ số trung vị: 1.00`, `trang s<0.85` ≤ 15

Nếu `cặp chồng > 0`: dùng superpowers:systematic-debugging — in page_no và hai dải chồng, không sửa ngưỡng. Nguyên nhân đáng ngờ đầu tiên: `get_text` gộp hai khối thành một `block_no`, hoặc một khối được `insert_htmlbox` chia thành nhiều block và dải của chúng xen nhau — khi đó đổi phép đo, ghi `Ruling:`, không đổi code.

Ghi vào ledger: một dòng `Task 4: nghiệm thu —` kèm đủ 6 số và thời gian chạy.

- [ ] **Step 3: Xuất lại cả cuốn và chụp khổ mẫu**

Run: `.venv/bin/python -W ignore::DeprecationWarning cli.py export projects/harmonics --mode reflow`
Expected: in `484 khổ, ... khối, cỡ chữ trung vị 100%, ... khối tràn khung.` và dòng trang dự phòng nếu N > 0. Số khối tràn phải thấp hơn 131 của bản cũ.

```bash
.venv/bin/python -W ignore::DeprecationWarning -c "
import pymupdf
d = pymupdf.open('projects/harmonics/output.vi.pdf')
for k in (10, 13, 45, 60):
    d[k-1].get_pixmap(dpi=70).save('<scratchpad>/8a_kho%d.png' % k)"
```

Xem bốn ảnh (Read), đối chiếu ảnh cũ `<scratchpad>/kho13.png`, `kho60.png`, `kho10.png`. Ghi nhận xét vào ledger: có đè chữ không, thứ tự đúng không.

- [ ] **Step 4: Chạy cả bộ lần cuối**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `364 passed`.

Task này không có commit code (không đổi file có trong git).
