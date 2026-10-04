# Phase 6 — Chế độ `reflow` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm `export --mode reflow`: dựng trang trắng sạch mang chữ Việt đúng vị trí khối gốc, để sách scan không còn hai lớp chữ chồng nhau.

**Architecture:** Tách phần dùng chung của `render/pdf_overlay.py` sang `render/pdf_trang.py` (thuần tuý, không đổi hành vi); `pdf_trang.write` nhận bộ dựng trang làm tham số. `render/pdf_reflow.py` mới chỉ chứa bộ dựng trang `trang_reflow`. `render/__init__.py` chọn bộ dựng theo `mode`.

**Tech Stack:** Python 3.12, PyMuPDF 1.28.2, pytest, SQLite.

**Spec:** `docs/superpowers/specs/2026-09-23-reflow-design.md` (R1–R6). Spec mẹ: `docs/superpowers/specs/2026-09-21-pdf-song-ngu-design.md`.

## Global Constraints

- Chạy test bằng `.venv/bin/python -m pytest tests/ -q`. Không test nào gọi mạng.
- Nền: 281 test xanh ở commit `4b6a158`. Bước tách (Task 1) không được làm đỏ test nào.
- `tests/test_export_pdf.py::test_mode_reflow_bi_tu_choi_ro_rang` là test DUY NHẤT được phép thay, và chỉ ở Task 4 — nó ghim đúng hành vi "reflow chưa làm" mà phase này xoá bỏ.
- Vân tay `tests/golden/` không được đổi: `git diff --stat 4b6a158 -- tests/golden/` phải rỗng.
- Luật tầng: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py` phải rỗng.
- `pdf_trang.write` giữ `ra.save(..., garbage=4, deflate=True)` — garbage=3 làm 20 trang ra 75MB.
- dry-run KHÔNG ghi gì vào DB. Chỉ đụng vào cờ `flag='overflow'`, không đè cờ chất lượng của translator.
- Mọi chỗ đọc ngược chữ đã đặt bằng `insert_htmlbox` phải `.replace("\xa0", " ")` trước khi so — nó đặt dấu cách không ngắt.
- Không lọc rác OCR trong phase này (spec mục 3, để Phase 7).
- Commit kết thúc bằng: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Khối chưa dịch trên trang reflow** (trang dịch dở) — người dùng mong thấy chữ Anh ở đó như overlay vẫn làm, không phải khoảng trắng im lặng. Spec không nói; suy từ R4 "hết cách thì GIỮ". → Task 3 (bộ dựng) và Task 4 (mức lệnh).
2. **`--mode reflow` trên project EPUB** — phải báo lỗi rõ có chữ "EPUB", không traceback, không rơi vào bộ render PDF. → Task 4.
3. **`--mode reflow --dry-run`** — không được ghi cờ nào vào DB; chữ ở dry-run là chữ Anh độn, cờ sinh ra là giả. → Task 4.
4. **Khung nằm hẳn ngoài trang ngay cả sau khi kẹp** (ví dụ `x0` vượt bề ngang trang) — bỏ qua, không đặt chữ vào một khung rỗng rồi báo thành công. → Task 2 và Task 3.
5. **Khung lớn hơn cả trang** — kẹp về đúng khổ trang, không thành khung suy biến. → Task 2.

---

## Pre-flight: giao diện giữa các task

| Task | Tạo ra | Task dùng |
|---|---|---|
| 1 | `pdf_trang.write(project, con, out_path, dung_trang, *, pages=None, dry_run=False, probe=False) -> dict`; `pdf_trang.dat_chu(page, khung, html, size, kho) -> (ti_le, bi_tran)`; `pdf_trang._khung_dung(khung, trang) -> bool` | 3, 4 |
| 2 | `pdf_trang.kep_khung(khung, trang) -> pymupdf.Rect` (khung rỗng `Rect()` nếu không giao) | 3 |
| 3 | `pdf_reflow.trang_reflow(src_doc, page_no, khoi, kho=None, ghi_nhan=None) -> pymupdf.Document`; `khoi` là list dict `{id, bbox, html, src, size}`; đọc `src` bằng `k.get("src", "")` nên chạy được cả trước khi Task 4 thêm khoá đó | 4 |
| 4 | `pdf_reflow.write(...)`; `pdf_trang.write` thêm khoá `src` và giữ khối chưa dịch | 5 |

---

### Task 1: Tách `render/pdf_trang.py` — không đổi hành vi

**Files:**
- Create: `render/pdf_trang.py`
- Modify: `render/pdf_overlay.py` (viết lại toàn bộ từ chính nó)
- Test: `tests/test_pdf_trang.py`

**Interfaces:**
- Consumes: không.
- Produces: `pdf_trang.write(project, con, out_path, dung_trang, *, pages=None, dry_run=False, probe=False) -> dict`, cùng `dat_chu`, `_khung_dung`, `ghep_kho_doi`, `_duong_nguon`, `_chen_trang_bao_cao`, `_don_cho_dai_ra`, `CO_SO_TRANG`, `TI_LE_DON`. `pdf_overlay` vẫn có thuộc tính `dat_chu`, `ghep_kho_doi`, `_khung_dung`, `xoa_chu`, `trang_dich`, `write` — test hiện có truy cập qua `pdf_overlay.<tên>`.

- [ ] **Step 1: Viết test**

Tạo `tests/test_pdf_trang.py`:

```python
"""Phần dùng chung của hai chế độ xuất PDF khổ đôi. Không gọi mạng."""
from render import pdf_overlay, pdf_trang


def test_phan_dung_chung_nam_o_pdf_trang():
    for ten in ("dat_chu", "_khung_dung", "ghep_kho_doi", "_duong_nguon",
                "_chen_trang_bao_cao", "_don_cho_dai_ra", "write",
                "CO_SO_TRANG", "TI_LE_DON"):
        assert hasattr(pdf_trang, ten), ten


def test_overlay_dung_lai_chu_khong_chep_mot_ban_rieng():
    """Hai bản sao của dat_chu là hai chỗ phải sửa cùng lúc — rồi sẽ lệch nhau."""
    assert pdf_overlay.dat_chu is pdf_trang.dat_chu
    assert pdf_overlay.ghep_kho_doi is pdf_trang.ghep_kho_doi
    assert pdf_overlay._khung_dung is pdf_trang._khung_dung


def test_overlay_chi_con_viec_rieng_cua_no():
    assert hasattr(pdf_overlay, "xoa_chu")
    assert hasattr(pdf_overlay, "trang_dich")
    assert not hasattr(pdf_trang, "xoa_chu"), "reflow không có gì để xoá"
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_trang.py -q`
Expected: FAIL — `ImportError: cannot import name 'pdf_trang' from 'render'`.

- [ ] **Step 3: Tách bằng script, không gõ lại tay**

Gõ lại 250 dòng bằng tay là chỗ sinh ra khác biệt tinh vi. Script dưới đây cắt theo khoảng dòng của `render/pdf_overlay.py` ở commit `4b6a158` và KIỂM dòng đầu mỗi khoảng trước khi cắt; lệch một dòng là nó dừng.

```bash
.venv/bin/python - <<'PY'
import pathlib

p = pathlib.Path("render/pdf_overlay.py")
dong = p.read_text(encoding="utf-8").splitlines(keepends=True)


def khoang(dau, cuoi, mo_dau):
    """Dòng dau..cuoi, đánh số từ 1, gồm cả hai đầu."""
    assert dong[dau - 1].startswith(mo_dau), (dau, dong[dau - 1])
    return "".join(dong[dau - 1:cuoi])


dat_chu = khoang(34, 56, "def dat_chu")
co_so_trang = khoang(58, 71, "# Cỡ chữ của số trang")
ghep = khoang(118, 140, "def ghep_kho_doi")
ti_le_don = khoang(142, 159, "# Chữ độn cho --dry-run")
duong_bao_cao = khoang(161, 198, "def _duong_nguon")
write = khoang(200, 284, "def write")
xoa_chu = khoang(19, 32, "def xoa_chu")
trang_dich = khoang(73, 116, "def trang_dich")


def doi(van, cu, moi):
    assert van.count(cu) == 1, cu
    return van.replace(cu, moi)


write = doi(write,
    'def write(project, con, out_path, *, pages=None,\n'
    '          dry_run=False, probe=False) -> dict:\n'
    '    """Xuất PDF khổ đôi. Trả về thống kê để `export` in ra và `--probe` dùng."""\n',
    'def write(project, con, out_path, dung_trang, *, pages=None,\n'
    '          dry_run=False, probe=False) -> dict:\n'
    '    """Xuất PDF khổ đôi. Trả về thống kê để `export` in ra và `--probe` dùng.\n'
    '\n'
    '    `dung_trang` là bộ dựng trang dịch của chế độ đang dùng — chỗ DUY NHẤT\n'
    '    hai chế độ khác nhau. Ký: (src_doc, page_no, khoi, kho, ghi_nhan) ->\n'
    '    tài liệu một trang.\n'
    '    """\n')
write = doi(write, "d = trang_dich(nguon, pno,", "d = dung_trang(nguon, pno,")

dau_trang = '''"""Phần dùng chung của hai chế độ xuất PDF khổ đôi: overlay và reflow.

Hai chế độ chỉ khác nhau đúng ở bộ dựng trang dịch — cách biến một trang gốc
thành một trang tiếng Việt. Mọi thứ còn lại (đặt chữ theo thang tự co, ghép
khổ đôi, trang báo cáo, ghi cờ overflow) nằm ở đây để hai chế độ không nói
hai kiểu.
"""
import html as _html
import json
import statistics
from pathlib import Path

import pymupdf

import db
import pdf_font
import pdf_layout
from render import UnsupportedTarget


'''
pathlib.Path("render/pdf_trang.py").write_text(
    dau_trang + "\n".join([dat_chu, co_so_trang, ghep, ti_le_don,
                           duong_bao_cao, write]),
    encoding="utf-8")

dau_overlay = '''"""Chế độ overlay: đè chữ Việt lên bản sao trang gốc, rồi ghép khổ đôi.

Chỉ đúng cho text-PDF, nơi chữ gốc là đối tượng văn bản nên xoá được. Sách
scan có chữ là pixel trong ảnh — xoá không được, đè lên là ra hai lớp chữ;
dùng pdf_reflow. Phần dùng chung của hai chế độ nằm ở pdf_trang.py.
"""
import pymupdf

import pdf_font
from render import pdf_trang
# Dùng lại từ pdf_trang, không chép: trang_dich gọi chúng, và test hiện có
# truy cập qua pdf_overlay.<tên>.
from render.pdf_trang import _khung_dung, dat_chu, ghep_kho_doi  # noqa: F401


'''
cuoi_overlay = '''def write(project, con, out_path, *, pages=None,
          dry_run=False, probe=False) -> dict:
    """Xuất PDF khổ đôi chế độ overlay."""
    return pdf_trang.write(project, con, out_path, trang_dich, pages=pages,
                           dry_run=dry_run, probe=probe)
'''
p.write_text(dau_overlay + "\n".join([xoa_chu, trang_dich, cuoi_overlay]),
             encoding="utf-8")
print("đã tách")
PY
```

Expected: in ra `đã tách`. Nếu một `assert` nổ thì file đã khác commit `4b6a158` — đọc lại file, sửa khoảng dòng trong script, KHÔNG gõ lại tay.

- [ ] **Step 4: Chứng minh thân hàm giống hệt bản cũ**

```bash
.venv/bin/python - <<'PY'
import ast, subprocess

cu = subprocess.run(["git", "show", "HEAD:render/pdf_overlay.py"],
                    capture_output=True, text=True, check=True).stdout


def cay(nguon):
    goc = ast.parse(nguon).body
    ham = {n.name: ast.dump(n) for n in goc if isinstance(n, ast.FunctionDef)}
    hang = {n.targets[0].id: ast.dump(n.value) for n in goc
            if isinstance(n, ast.Assign)}
    return ham, hang


a, a_hang = cay(cu)
b, b_hang = cay(open("render/pdf_trang.py", encoding="utf-8").read())
c, _ = cay(open("render/pdf_overlay.py", encoding="utf-8").read())
for t in ("dat_chu", "_khung_dung", "ghep_kho_doi", "_don_cho_dai_ra",
          "_duong_nguon", "_chen_trang_bao_cao"):
    assert a[t] == b[t], f"{t} đã bị đổi khi tách"
for t in ("xoa_chu", "trang_dich"):
    assert a[t] == c[t], f"{t} đã bị đổi khi tách"
for t in ("CO_SO_TRANG", "TI_LE_DON"):
    assert a_hang[t] == b_hang[t], t
print("8 hàm và 2 hằng giống hệt bản cũ")
PY
```

Expected: `8 hàm và 2 hằng giống hệt bản cũ`. `write` cố ý khác (thêm `dung_trang`) nên không nằm trong phép so này; Step 5 là thứ kiểm nó.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: `284 passed` (281 cũ + 3 mới). Nếu một test cũ đỏ vì nó `monkeypatch` một tên đã dời sang `pdf_trang` qua đường `pdf_overlay.<tên>`, thì test đó đang vá sai chỗ: sửa nó vá `pdf_trang.<tên>` và ghi Ruling — không đổi code.

- [ ] **Step 6: Commit**

```bash
git add render/pdf_trang.py render/pdf_overlay.py tests/test_pdf_trang.py
git commit -m "refactor: tách phần dùng chung của xuất PDF sang pdf_trang

Hai chế độ overlay và reflow chỉ khác nhau đúng ở bộ dựng trang dịch;
write của chúng giống hệt ngoài chỗ đó. Tách bằng script cắt theo khoảng
dòng, rồi chứng minh bằng so cây AST rằng 8 hàm và 2 hằng giống hệt bản
cũ. write nhận bộ dựng trang làm tham số.

Không đổi hành vi: 281 test cũ xanh nguyên.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `kep_khung` — kẹp khung vào trang thay vì loại

**Files:**
- Modify: `render/pdf_trang.py` (thêm hàm ngay sau `_khung_dung`)
- Test: `tests/test_pdf_trang.py`

**Interfaces:**
- Consumes: `pdf_trang._khung_dung` từ Task 1.
- Produces: `pdf_trang.kep_khung(khung, trang) -> pymupdf.Rect`. Không sửa khung đầu vào. Không giao thì trả `pymupdf.Rect()` (0,0,0,0), để `_khung_dung` loại.

- [ ] **Step 1: Viết test**

Nối vào cuối `tests/test_pdf_trang.py`:

```python
import pymupdf
import pytest

TRANG = pymupdf.Rect(0, 0, 334, 547)   # khổ trang harmonics, đo thật


def toa_do(k):
    return pytest.approx((k.x0, k.y0, k.x1, k.y1))


def test_khung_y_am_duoc_kep_vao_trang():
    """Đo thật: 53/4.120 khối của harmonics có góc trên-trái trên mép trang,
    ví dụ trang 2: 228.2,-3.0,347.5,51.5. _khung_dung loại thẳng chúng."""
    goc = pymupdf.Rect(228.2, -3.0, 347.5, 51.5)
    assert not pdf_trang._khung_dung(goc, TRANG), "tiền đề: khung này đang bị loại"
    k = pdf_trang.kep_khung(goc, TRANG)
    assert (k.x0, k.y0, k.x1, k.y1) == toa_do(pymupdf.Rect(228.2, 0, 334, 51.5))
    assert pdf_trang._khung_dung(k, TRANG), "kẹp xong phải qua được cửa kiểm"


def test_khung_da_nam_trong_trang_thi_giu_nguyen():
    goc = pymupdf.Rect(34.2, 47.8, 311.5, 93.5)
    k = pdf_trang.kep_khung(goc, TRANG)
    assert (k.x0, k.y0, k.x1, k.y1) == toa_do(goc)


def test_khung_lon_hon_ca_trang_thi_ve_dung_bang_trang():
    """Review Focus 5."""
    k = pdf_trang.kep_khung(pymupdf.Rect(-10, -10, 400, 600), TRANG)
    assert (k.x0, k.y0, k.x1, k.y1) == toa_do(TRANG)


def test_khung_nam_han_ngoai_trang_thi_khong_dung_duoc():
    """Review Focus 4: kẹp không được biến khung ngoài trang thành khung hợp lệ."""
    k = pdf_trang.kep_khung(pymupdf.Rect(400, 100, 500, 200), TRANG)
    assert not pdf_trang._khung_dung(k, TRANG)


def test_kep_khong_sua_khung_dau_vao():
    goc = pymupdf.Rect(228.2, -3.0, 347.5, 51.5)
    pdf_trang.kep_khung(goc, TRANG)
    assert goc.y0 == pytest.approx(-3.0)
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_trang.py -q`
Expected: FAIL 5 test — `AttributeError: module 'render.pdf_trang' has no attribute 'kep_khung'`. `test_khung_y_am_duoc_kep_vao_trang` phải qua được dòng "tiền đề" rồi mới hỏng ở `kep_khung`; nếu nó hỏng ở dòng tiền đề thì `_khung_dung` đã bị đổi ở Task 1.

- [ ] **Step 3: Viết `kep_khung`**

Trong `render/pdf_trang.py`, chèn ngay sau hàm `_khung_dung`:

```python
def kep_khung(khung, trang):
    """Phần giao của khung với trang. Không giao thì trả khung rỗng.

    Chỉ reflow gọi. Overlay LOẠI khối có khung ra ngoài trang và như thế là
    đúng, vì ảnh nền vẫn hiện chữ gốc ở chỗ đó. Reflow dựng trên nền trắng
    nên loại là mất nội dung im lặng — đo thật: 53/4.120 khối của một cuốn
    scan có góc trên-trái nằm trên mép trang, lệch chưa tới 5pt.

    Tự tính thay vì dùng Rect.intersect: với hai khung rời nhau thì
    intersect trả về một khung "không hợp lệ" mà tài liệu không nói rõ hình
    dạng. Khung rỗng Rect() thì _khung_dung chắc chắn loại.
    """
    x0, y0 = max(khung.x0, trang.x0), max(khung.y0, trang.y0)
    x1, y1 = min(khung.x1, trang.x1), min(khung.y1, trang.y1)
    if x1 <= x0 or y1 <= y0:
        return pymupdf.Rect()
    return pymupdf.Rect(x0, y0, x1, y1)
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_trang.py -q`
Expected: `8 passed`.

- [ ] **Step 5: Chạy cả bộ và commit**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: `289 passed`.

```bash
git add render/pdf_trang.py tests/test_pdf_trang.py
git commit -m "feat: kep_khung — kẹp khung vào trang thay vì loại

Chỉ reflow dùng. Overlay loại khối có khung ngoài trang là đúng vì ảnh
nền vẫn hiện chữ gốc ở đó; trên nền trắng thì loại là mất nội dung im
lặng. Đo thật: 53/4.120 khối của harmonics có y âm.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `trang_reflow` — bộ dựng trang trắng

**Files:**
- Create: `render/pdf_reflow.py`
- Test: `tests/test_pdf_reflow.py`

**Interfaces:**
- Consumes: `pdf_trang.dat_chu`, `pdf_trang._khung_dung`, `pdf_trang.kep_khung`.
- Produces: `pdf_reflow.trang_reflow(src_doc, page_no: int, khoi: list, kho=None, ghi_nhan=None) -> pymupdf.Document`. Cùng giao kèo với `pdf_overlay.trang_dich`. `khoi` là list dict `{id, bbox: pymupdf.Rect, html: str, src: str, size: float}`; `src` đọc bằng `k.get("src", "")`. `ghi_nhan` nhận `(id, ti_le, bi_tran)` cho mỗi khối đã đặt.

- [ ] **Step 1: Viết test**

Tạo `tests/test_pdf_reflow.py`:

```python
"""Chế độ reflow: trang trắng mang chữ Việt đúng vị trí khối gốc. Không gọi mạng."""
import pymupdf

from render import pdf_reflow

KHO = (334, 547)   # khổ trang harmonics, đo thật


def chu(page):
    """insert_htmlbox đặt dấu cách không ngắt; chuẩn hoá trước khi so."""
    return page.get_text().replace("\xa0", " ")


def trang_scan(chu_anh="English words baked into the scan"):
    """Giống một trang sách scan: ảnh phủ kín trang, chữ OCR nằm đè lên ảnh."""
    d = pymupdf.open()
    p = d.new_page(width=KHO[0], height=KHO[1])
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 100), 0)
    pix.clear_with(180)
    p.insert_image(p.rect, pixmap=pix)
    p.insert_text((40, 80), chu_anh, fontsize=10)
    return d


def khoi(x0, y0, x1, y1, html, src="Original English text", id_=1, size=10.0):
    return {"id": id_, "bbox": pymupdf.Rect(x0, y0, x1, y1),
            "html": html, "src": src, "size": size}


def test_tien_de_trang_scan_co_anh():
    """Nếu trang mẫu không có ảnh thì test R2 bên dưới xanh vô nghĩa."""
    assert trang_scan()[0].get_images(full=True)


def test_khong_mang_anh_nao_cua_trang_goc():
    """R2: chữ Anh của sách scan nằm TRONG ảnh. Chép ảnh sang là chép chữ Anh."""
    d = pdf_reflow.trang_reflow(trang_scan(), 0, [khoi(40, 60, 300, 100, "Chữ Việt")])
    assert d[0].get_images(full=True) == []


def test_dung_kho_trang_goc():
    d = pdf_reflow.trang_reflow(trang_scan(), 0, [khoi(40, 60, 300, 100, "Chữ Việt")])
    assert (d[0].rect.width, d[0].rect.height) == KHO


def test_chu_viet_nam_dung_khung_da_cho():
    """R1: đối chiếu trái-phải theo vị trí là công dụng chính của khổ đôi."""
    khung = pymupdf.Rect(40, 200, 300, 240)
    d = pdf_reflow.trang_reflow(
        trang_scan(), 0, [khoi(*khung, "Xin chào bạn đọc")])
    thay = d[0].search_for("Xin")
    assert thay, "không thấy chữ Việt trên trang"
    tam = pymupdf.Point((thay[0].x0 + thay[0].x1) / 2, (thay[0].y0 + thay[0].y1) / 2)
    assert (khung + (-2, -2, 2, 2)).contains(tam), f"{thay[0]} lệch khỏi {khung}"


def test_trang_khong_co_khoi_nao_ra_trang_trang():
    """R5: overlay trả bản sao trang gốc; reflow ra trang trắng."""
    d = pdf_reflow.trang_reflow(trang_scan(), 0, [])
    assert chu(d[0]).strip() == ""
    assert d[0].get_images(full=True) == []


def test_khung_y_am_duoc_kep_chu_khong_bi_mat():
    """R3: đo thật, 53/4.120 khối của harmonics có y âm."""
    d = pdf_reflow.trang_reflow(
        trang_scan(), 0, [khoi(30, -3.0, 300, 40, "Tiêu đề chạy đầu trang")])
    assert "Tiêu đề" in chu(d[0])


def test_tran_o_bac_cuoi_thi_ve_chu_anh_goc_va_bao_tran():
    """R4: hết cách thì GIỮ — vẽ lại chữ Anh gốc vào đúng khung đó."""
    ghi = []
    dai = "Chữ Việt rất dài không thể nào vừa khung nhỏ này được. " * 30
    d = pdf_reflow.trang_reflow(
        trang_scan(), 0, [khoi(10, 10, 110, 24, dai, src="Short")], ghi_nhan=ghi)
    assert "Short" in chu(d[0])
    assert "Chữ Việt rất dài" not in chu(d[0]), "bản tràn không được vẽ dở dang"
    assert ghi and ghi[0][2] is True, "khối tràn phải được báo để ghi cờ overflow"


def test_khoi_chua_dich_thi_hien_chu_anh():
    """Review Focus 1: trang dịch dở không có khoảng trắng im lặng."""
    d = pdf_reflow.trang_reflow(
        trang_scan(), 0,
        [khoi(40, 60, 300, 100, "", src="Untranslated paragraph here")])
    assert "Untranslated paragraph" in chu(d[0])


def test_khung_han_ngoai_trang_bi_bo_qua():
    """Review Focus 4."""
    ghi = []
    d = pdf_reflow.trang_reflow(
        trang_scan(), 0, [khoi(400, 100, 500, 200, "Ngoài trang")], ghi_nhan=ghi)
    assert chu(d[0]).strip() == ""
    assert ghi == []
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_reflow.py -q`
Expected: `ImportError: cannot import name 'pdf_reflow' from 'render'` khi thu thập test.

- [ ] **Step 3: Viết `render/pdf_reflow.py`**

```python
"""Chế độ reflow: dựng trang trắng mang chữ Việt ở đúng vị trí khối gốc.

Dành cho sách scan, nơi chữ gốc là pixel trong ảnh nên overlay không xoá
được: đè chữ Việt lên là ra hai lớp chữ chồng nhau (đo thật: nửa dịch đậm
hơn nửa gốc 42% và 62%). Reflow không chép gì từ trang gốc — nửa trái của
khổ đôi đã mang nguyên bản gốc, kể cả hình, nên vùng hình ở nửa phải để
trống là đủ (spec R2). Nền trắng tự nó đã trống đúng kích thước.
"""
import pymupdf

import pdf_font
from render.pdf_trang import _khung_dung, dat_chu, kep_khung


def trang_reflow(src_doc, page_no: int, khoi: list, kho=None,
                 ghi_nhan=None) -> "pymupdf.Document":
    """Tài liệu một trang trắng đúng khổ trang gốc, chữ đặt đúng khung.

    Cùng giao kèo với pdf_overlay.trang_dich để pdf_trang.write gọi được cả
    hai. `khoi` là list dict {id, bbox, html, src, size}.

    Trả về tài liệu mới; người gọi có trách nhiệm đóng.
    """
    if kho is None:
        kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    goc = src_doc[page_no].rect
    d = pymupdf.open()
    page = d.new_page(width=goc.width, height=goc.height)

    for k in khoi:
        src = k.get("src", "")
        ban_dich = k["html"].strip()
        # Khối chưa dịch thì hiện chữ Anh, như overlay vẫn làm: trên nền trắng
        # mà bỏ qua là để lại khoảng trống im lặng ở chỗ chưa dịch.
        html = k["html"] if ban_dich else src
        if not html.strip():
            continue
        # R3: kẹp chứ không loại. Overlay loại được vì ảnh nền còn hiện chữ ở
        # chỗ đó; ở đây loại là mất nội dung.
        khung = kep_khung(k["bbox"], page.rect)
        if not _khung_dung(khung, page.rect):
            continue
        ti_le, bi_tran = dat_chu(page, khung, html, k["size"], kho)
        if bi_tran and ban_dich and src.strip():
            # R4: hết cách thì GIỮ. insert_htmlbox không vẽ gì khi không vừa,
            # nên khung đó đang trống — vẽ lại chữ Anh gốc vào.
            dat_chu(page, khung, src, k["size"], kho)
        if ghi_nhan is not None:
            ghi_nhan.append((k.get("id"), ti_le, bi_tran))
    return d
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_reflow.py -q`
Expected: `9 passed`. Nếu `test_tran_o_bac_cuoi...` hỏng ở dòng `"Chữ Việt rất dài" not in` thì `insert_htmlbox` ĐÃ vẽ dở dang khi báo không vừa — giả định ở comment R4 sai: dừng, đo lại, ghi Ruling; đừng nới test.

- [ ] **Step 5: Chạy cả bộ và commit**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: `298 passed`.

```bash
git add render/pdf_reflow.py tests/test_pdf_reflow.py
git commit -m "feat: trang_reflow — dựng trang trắng mang chữ Việt đúng khung

Không chép gì từ trang gốc (R2): chữ Anh của sách scan nằm trong ảnh.
Kẹp khung âm thay vì loại (R3), tràn ở bậc cuối thì vẽ lại chữ Anh gốc
(R4), khối chưa dịch hiện chữ Anh thay vì khoảng trắng im lặng.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Nối `--mode reflow` từ lệnh tới file

**Files:**
- Modify: `render/pdf_reflow.py` (thêm `write`)
- Modify: `render/pdf_trang.py` (vòng dựng `theo_trang` trong `write`)
- Modify: `render/__init__.py` (hàm `write`)
- Modify: `tests/test_export_pdf.py` (thay `test_mode_reflow_bi_tu_choi_ro_rang`, thêm test)
- Modify: `README.md:77-78`

**Interfaces:**
- Consumes: `pdf_reflow.trang_reflow` (Task 3), `pdf_trang.write` (Task 1).
- Produces: `pdf_reflow.write(project, con, out_path, *, pages=None, dry_run=False, probe=False) -> dict`; `render.write(..., mode="reflow")` chạy được với project PDF và báo lỗi có chữ "EPUB" với project EPUB.

- [ ] **Step 1: Viết test**

Trong `tests/test_export_pdf.py`, THAY nguyên hàm `test_mode_reflow_bi_tu_choi_ro_rang` bằng:

```python
def test_mode_reflow_xuat_duoc_kho_doi(proj, tmp_path):
    """Trước Phase 6 test này ghim 'reflow chưa làm'. Giờ nó đã làm."""
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    d = pymupdf.open(out)
    assert d.page_count == 3
    assert d[0].rect.width == 522 * 2 and d[0].rect.height == 666
    d.close()
```

Rồi nối vào cuối file:

```python
def _nua_phai(out, trang):
    d = pymupdf.open(out)
    chu = d[trang].get_text(clip=pymupdf.Rect(522, 0, 1044, 666)).replace("\xa0", " ")
    d.close()
    return chu


def test_reflow_nua_phai_chi_co_chu_viet(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    phai = _nua_phai(out, 0)
    assert "Bản dịch" in phai
    assert "noi dung day du" not in phai, "chữ Anh gốc lọt sang nửa dịch"


def test_reflow_chua_dich_thi_hien_chu_anh(proj, tmp_path):
    """Review Focus 1 ở mức lệnh: write phải đưa khối chưa dịch tới bộ dựng."""
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=NULL WHERE page_no=1")
    con.commit()
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    assert "hai 0 noi dung" in _nua_phai(out, 1)


def test_reflow_dry_run_khong_ghi_co_vao_db(proj, tmp_path):
    """Review Focus 3: chữ ở dry-run là chữ Anh độn, cờ sinh ra là giả."""
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks WHERE page_no=0").fetchone()[0]
    # Khung tí hon: chữ nào cũng tràn, kể cả chữ Anh — để phép thử có nghĩa.
    con.execute("UPDATE blocks SET bbox='67,70,80,74', flag=NULL WHERE id=?", (bid,))
    con.commit()

    def dem():
        return db.connect(proj).execute(
            "SELECT COUNT(*) FROM blocks WHERE flag='overflow'").fetchone()[0]

    render.write("pdf", proj, db.connect(proj), tmp_path / "a.pdf",
                 mode="reflow", dry_run=True)
    assert dem() == 0, "dry-run đã ghi cờ vào DB"
    render.write("pdf", proj, db.connect(proj), tmp_path / "b.pdf", mode="reflow")
    assert dem() >= 1, "khung tí hon phải gây tràn — không thì phép thử trên vô nghĩa"


def test_reflow_probe_them_trang_bao_cao(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow", probe=True)
    d = pymupdf.open(out)
    assert d.page_count == 4
    d.close()


def test_epub_khong_dung_duoc_mode_reflow(source_epub, tmp_path):
    """Review Focus 2: reflow cũng cần toạ độ trang mà EPUB không có."""
    p = run_init(source_epub, tmp_path / "proj")
    with pytest.raises(render.UnsupportedTarget, match="EPUB"):
        render.write("epub", p, db.connect(p), tmp_path / "ra.epub", mode="reflow")


def test_cli_export_mode_reflow_chay_duoc(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    cli.cmd_export(argparse.Namespace(
        project=str(proj), output=str(out), bilingual=False, mode="reflow",
        pages=None, dry_run=False, probe=False))
    assert out.exists()
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `.venv/bin/python -m pytest tests/test_export_pdf.py -q`
Expected: 7 test hỏng — năm test gọi `render.write(..., mode="reflow")` với project PDF ném `UnsupportedTarget: ... Phase 6, chưa làm`, test EPUB hỏng vì thông điệp không có chữ "EPUB", test CLI hỏng bằng `SystemExit`. Mọi test overlay cũ trong file vẫn xanh.

- [ ] **Step 3: `pdf_trang.write` đưa khối chưa dịch và chữ gốc tới bộ dựng**

Trong `render/pdf_trang.py`, hàm `write`, thay:

```python
    for r in con.execute(cot, tham):
        noi_dung = _don_cho_dai_ra(r["src_html"]) if dry_run else r["dst"]
        if not noi_dung.strip():
            continue
        x0, y0, x1, y1 = (float(v) for v in r["bbox"].split(","))
        lay = json.loads(r["layout"] or "{}")
        theo_trang.setdefault(r["page_no"], []).append(
            {"id": r["id"], "bbox": pymupdf.Rect(x0, y0, x1, y1),
             "html": noi_dung, "size": float(lay.get("size") or 10.0)})
```

bằng:

```python
    for r in con.execute(cot, tham):
        noi_dung = _don_cho_dai_ra(r["src_html"]) if dry_run else r["dst"]
        goc = r["src_html"] or ""
        # Khối chưa dịch vẫn phải tới bộ dựng trang: overlay tự bỏ qua nó
        # (chữ gốc còn nguyên trên bản sao trang), reflow thì vẽ chữ Anh vào
        # — trên nền trắng mà bỏ qua là để lại khoảng trống im lặng.
        if not noi_dung.strip() and not goc.strip():
            continue
        x0, y0, x1, y1 = (float(v) for v in r["bbox"].split(","))
        lay = json.loads(r["layout"] or "{}")
        theo_trang.setdefault(r["page_no"], []).append(
            {"id": r["id"], "bbox": pymupdf.Rect(x0, y0, x1, y1),
             "html": noi_dung, "src": goc,
             "size": float(lay.get("size") or 10.0)})
```

Overlay không đổi hành vi: `trang_dich` tự lọc `k["html"].strip()`, nên khối chưa dịch không tới được `ghi_nhan` và không vào thống kê.

- [ ] **Step 4: `pdf_reflow.write`**

Nối vào cuối `render/pdf_reflow.py`:

```python
def write(project, con, out_path, *, pages=None,
          dry_run=False, probe=False) -> dict:
    """Xuất PDF khổ đôi chế độ reflow."""
    return pdf_trang.write(project, con, out_path, trang_reflow, pages=pages,
                           dry_run=dry_run, probe=probe)
```

và sửa dòng import ở đầu file thành:

```python
from render import pdf_trang
from render.pdf_trang import _khung_dung, dat_chu, kep_khung
```

- [ ] **Step 5: Dispatcher**

Trong `render/__init__.py`, thay toàn bộ hàm `write` bằng:

```python
def write(fmt: str, project, con, out_path, *, bilingual: bool = False,
          mode=None, pages=None, dry_run: bool = False, probe: bool = False):
    """`mode=None` nghĩa là tự suy ra theo định dạng.

    Phải phân biệt được với việc người dùng NÊU RÕ một chế độ PDF cho project
    EPUB — đó mới là chỗ cần từ chối, vì cả overlay lẫn reflow đều đặt chữ
    theo toạ độ trang.
    """
    if mode is not None and mode not in ("overlay", "reflow"):
        raise UnsupportedTarget(f"chế độ '{mode}' không có. Chọn overlay hoặc reflow.")

    if fmt == "epub":
        if mode is not None:
            raise UnsupportedTarget(
                f"EPUB không có toạ độ trang nên không dùng được chế độ {mode}."
            )
        if pages or dry_run or probe:
            raise UnsupportedTarget(
                "EPUB không có toạ độ trang nên không dùng được --pages, "
                "--dry-run hay --probe."
            )
        from render import epub as adapter
        adapter.write(project, con, out_path, bilingual=bilingual)
        return None

    if fmt == "pdf":
        if mode == "reflow":
            from render import pdf_reflow as adapter
        else:
            from render import pdf_overlay as adapter
        return adapter.write(project, con, out_path, pages=pages,
                             dry_run=dry_run, probe=probe)

    raise UnsupportedTarget(f"chưa ghi ra được định dạng '{fmt}'.")
```

- [ ] **Step 6: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_export_pdf.py -q`
Expected: toàn bộ xanh.

- [ ] **Step 7: README**

Trong `README.md`, thay hai dòng 77–78:

```
`--mode reflow` dựng lại trang sạch thay vì đè lên bản gốc — dành cho sách
scan, khi Phase 7 có OCR.
```

bằng:

```
`--mode reflow` dựng trang trắng mang chữ Việt đúng vị trí khối gốc, không
chép gì từ trang gốc. Dùng cho sách scan: ở đó chữ gốc là pixel trong ảnh nên
overlay không xoá được, đè lên là ra hai lớp chữ chồng nhau. Vùng hình để
trống; nửa trái khổ đôi vẫn hiện nguyên bản gốc. Sách scan đã có lớp chữ OCR
thì dùng được ngay; mảnh vụn OCR chưa được lọc (Phase 7).
```

- [ ] **Step 8: Chạy cả bộ, kiểm luật tầng, commit**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: `304 passed` (298 + 6 test mới; test bị thay không đổi tổng).

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py; git diff --stat 4b6a158 -- tests/golden/`
Expected: không in gì.

```bash
git add render/pdf_reflow.py render/pdf_trang.py render/__init__.py tests/test_export_pdf.py README.md
git commit -m "feat: export --mode reflow chạy được từ lệnh tới file

Dispatcher chọn bộ dựng trang theo mode; EPUB từ chối cả hai chế độ PDF
vì cả hai cần toạ độ trang. pdf_trang.write đưa khối chưa dịch và chữ
gốc tới bộ dựng — overlay tự bỏ qua chúng như trước, reflow vẽ chữ Anh.

Thay test_mode_reflow_bi_tu_choi_ro_rang: nó ghim đúng hành vi 'chưa
làm' mà phase này xoá bỏ.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Nghiệm thu trên sách thật — không tốn token

**Files:** không sửa code. Các file xuất nằm trong `projects/` (đã gitignore).

**Interfaces:**
- Consumes: `export --mode overlay|reflow` (Task 4), `pdf_reflow.trang_reflow` (Task 3).
- Produces: số đo đối chiếu với ngưỡng spec mục 6.

- [ ] **Step 1: Xuất astrology 149–170 bằng cả hai chế độ**

```bash
.venv/bin/python cli.py export projects/astrology --pages 149-170 --mode overlay -o projects/astrology/nt-overlay.pdf
.venv/bin/python cli.py export projects/astrology --pages 149-170 --mode reflow -o projects/astrology/nt-reflow.pdf
```

Expected: dòng tổng kết của lệnh reflow in `22 khổ, 109 khối`, số khối tràn ≤ 1, cỡ chữ trung vị ≥ 85%. Overlay đo được đúng 22 khổ, 109 khối, 1 khối tràn, trung vị 100%.

- [ ] **Step 2: Đo theo ngưỡng spec**

```bash
.venv/bin/python - <<'PY'
import json, sqlite3, sys
import pymupdf
sys.path.insert(0, ".")
import pdf_font
from render.pdf_reflow import trang_reflow


def muc(pg, clip):
    pix = pg.get_pixmap(dpi=60, clip=clip, colorspace=pymupdf.csGRAY)
    return sum(1 for v in pix.samples if v < 200) / len(pix.samples) * 100


def phai(p):
    return pymupdf.Rect(p.rect.width / 2, 0, p.rect.width, p.rect.height)


ov = pymupdf.open("projects/astrology/nt-overlay.pdf")
rf = pymupdf.open("projects/astrology/nt-reflow.pdf")
vuot = [(i, muc(rf[i], phai(rf[i])), muc(ov[i], phai(ov[i])))
        for i in range(rf.page_count)]
vuot = [(i, a, b) for i, a, b in vuot if a > b + 0.1]
print(f"khổ có nửa dịch reflow đậm hơn overlay: {len(vuot)}/{rf.page_count}")
for i, a, b in vuot:
    print(f"   khổ {i}: reflow {a:.2f}% > overlay {b:.2f}%")

# Đếm ảnh trên TÀI LIỆU MỘT TRANG, không trên khổ ghép: show_pdf_page lồng
# XObject nên get_images trên khổ ghép đếm sai.
con = sqlite3.connect("projects/astrology/project.db"); con.row_factory = sqlite3.Row
src = pymupdf.open("projects/astrology/source.pdf")
kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
anh = 0
for pno in range(148, 170):
    khoi = []
    for r in con.execute("SELECT id, bbox, layout, COALESCE(dst_html,'') dst, "
                         "src_html FROM blocks WHERE page_no=? AND bbox IS NOT NULL "
                         "ORDER BY pos", (pno,)):
        x0, y0, x1, y1 = (float(v) for v in r["bbox"].split(","))
        khoi.append({"id": r["id"], "bbox": pymupdf.Rect(x0, y0, x1, y1),
                     "html": r["dst"], "src": r["src_html"] or "",
                     "size": float(json.loads(r["layout"] or "{}").get("size") or 10.0)})
    d = trang_reflow(src, pno, khoi, kho)
    anh += len(d[0].get_images(full=True))
    d.close()
print(f"ảnh trên 22 trang reflow: {anh}")
PY
```

Expected: `khổ có nửa dịch reflow đậm hơn overlay: 0/22` và `ảnh trên 22 trang reflow: 0`. Khổ nào vượt thì đó là phát hiện: render nửa phải khổ đó ra ảnh, nhìn, rồi báo — không nới ngưỡng.

- [ ] **Step 3: harmonics 60–61 — sách scan thật**

```bash
.venv/bin/python cli.py export projects/harmonics --pages 60-61 --mode overlay -o projects/harmonics/nt-overlay.pdf
.venv/bin/python cli.py export projects/harmonics --pages 60-61 --mode reflow -o projects/harmonics/nt-reflow.pdf
.venv/bin/python - <<'PY'
import pymupdf


def muc(pg, clip):
    pix = pg.get_pixmap(dpi=60, clip=clip, colorspace=pymupdf.csGRAY)
    return sum(1 for v in pix.samples if v < 200) / len(pix.samples) * 100


for ten in ("overlay", "reflow"):
    d = pymupdf.open(f"projects/harmonics/nt-{ten}.pdf")
    for i, p in enumerate(d):
        w, h = p.rect.width, p.rect.height
        a = muc(p, pymupdf.Rect(0, 0, w / 2, h))
        b = muc(p, pymupdf.Rect(w / 2, 0, w, h))
        print(f"{ten:8s} khổ {i}: gốc {a:5.2f}%  dịch {b:5.2f}%  ({(b - a) / a * 100:+.0f}%)")
d = pymupdf.open("projects/harmonics/nt-reflow.pdf")
p = d[0]
p.get_pixmap(dpi=130, clip=pymupdf.Rect(p.rect.width / 2, 0, p.rect.width,
                                        p.rect.height)).save(
    "projects/harmonics/nt-reflow-phai.png")
print("đã xuất nửa phải khổ 0 ra projects/harmonics/nt-reflow-phai.png")
PY
```

Expected: overlay giữ đúng số đã đo (+42%, +62%); reflow có nửa dịch **nhạt hơn** nửa gốc ở cả 2 khổ. Mở ảnh PNG để nhìn: chữ Việt một lớp trên nền trắng. Mảnh vụn OCR vẫn hiện thành chữ vô nghĩa — đúng như spec mục 3 đã chấp nhận, không phải lỗi của phase này.

- [ ] **Step 4: Kiểm tổng**

Run: `.venv/bin/python -m pytest tests/ -q; grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py; git diff --stat 4b6a158 -- tests/golden/`
Expected: `304 passed`, hai lệnh sau không in gì.

Không commit ở task này — không có file nào trong repo thay đổi. Ghi số đo vào ledger.
